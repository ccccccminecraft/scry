# 詳細設計: Surveil JSON インポート（MTGA 対応）

## 対象ファイル

| ファイル | 種別 | 内容 |
|----------|------|------|
| `backend/parser/surveil_parser.py` | 新規 | Surveil JSON → 内部データ構造への変換 |
| `backend/app/routers/surveil_import.py` | 新規 | `/api/import/surveil/*` エンドポイント群 |
| `backend/models/core.py` | 編集 | `source`, `phase`, `deck_json` カラム追加 |
| `backend/database.py` | 編集 | 新カラムの ALTER TABLE マイグレーション追加 |
| `backend/services/import_service.py` | 編集 | `SurveilImportService` クラスを追加 |
| `backend/app/main.py` | 編集 | `surveil_import` router を登録 |
| `frontend/src/api/import.ts` | 編集 | Surveil API 関数追加 |
| `frontend/src/views/ImportView.vue` | 編集 | "MTGA (Surveil)" タブ追加 |
| `frontend/src/components/ActionLog.vue` | 編集 | `phase` 表示・新 action_type 対応 |

---

## Surveil JSON フォーマット（入力）

Surveil（MTGA ログパーサー）が出力する JSON ファイルの仕様。
詳細は `/home/cccccc/claude/surveil/docs/03_event_model.md` を参照。

```json
{
  "schema_version": 2,
  "match_id": "UUID文字列",
  "source": "mtga",
  "players": ["Player1", "Player2"],
  "self_seat_id": 1,
  "match_winner": "Player1",
  "played_at": "2026-03-19T12:00:00+00:00",
  "deck": {
    "main": {"Lightning Bolt": 4, "Ragavan, Nimble Pilferer": 4, ...},
    "sideboard": {"Flusterstorm": 2, ...}
  },
  "games": [
    {
      "game_number": 1,
      "winner": "Player1",
      "turns": 6,
      "first_player": "Player1",
      "mulligans": [{"player_name": "Player1", "count": 1}],
      "events": [
        {"seq": 1, "turn": 0, "phase": "beginning", "event_type": "turn_start", "active_player": "Player1"},
        {"seq": 3, "turn": 1, "phase": "main1", "event_type": "play_land", "player": "Player1", "card_name": "Fetchland"},
        {"seq": 7, "turn": 1, "phase": "main1", "event_type": "cast", "player": "Player1", "card_name": "Lightning Bolt", "targets": [{"player": "Player2"}]},
        ...
      ]
    }
  ]
}
```

### event_type 一覧

| event_type | 説明 |
|---|---|
| `turn_start` | ターン開始（active_player フィールドあり） |
| `phase_change` | フェイズ変化 |
| `cast` | 呪文を唱える |
| `play_land` | 土地をプレイ |
| `draw` | カードをドロー |
| `discard` | カードを捨てる |
| `resolve` | 呪文・能力の解決 |
| `mill` | ライブラリからの落下 |
| `attack` | 攻撃宣言 |
| `block` | ブロック宣言 |
| `damage` | ダメージ |
| `life_change` | ライフ変化 |
| `ability_activated` | 起動型能力 |
| `ability_mana` | マナ能力（起動型のうちマナ生産系） |
| `ability_triggered` | 誘発型能力 |
| `ability_resolved` | 能力の解決 |
| `mulligan` | マリガン |

---

## DB スキーマ変更

### 追加カラム

| テーブル | カラム名 | 型 | デフォルト | 用途 |
|---|---|---|---|---|
| `matches` | `source` | TEXT NOT NULL | `'mtgo'` | データ出所（`"mtgo"` / `"mtga"`） |
| `actions` | `phase` | TEXT | NULL | フェイズ名（`"main1"`, `"declare_attackers"` 等） |
| `match_players` | `deck_json` | TEXT | NULL | Surveil の deck.main / deck.sideboard を JSON 文字列で保存 |

### `init_db()` への追加（`database.py`）

```python
# matches: source 列の追加
if "matches" in inspector.get_table_names():
    cols = {c["name"] for c in inspector.get_columns("matches")}
    if "source" not in cols:
        conn.execute(text("ALTER TABLE matches ADD COLUMN source TEXT NOT NULL DEFAULT 'mtgo'"))
        conn.commit()

# actions: phase 列の追加
if "actions" in inspector.get_table_names():
    cols = {c["name"] for c in inspector.get_columns("actions")}
    if "phase" not in cols:
        conn.execute(text("ALTER TABLE actions ADD COLUMN phase TEXT"))
        conn.commit()

# match_players: deck_json 列の追加
if "match_players" in inspector.get_table_names():
    cols = {c["name"] for c in inspector.get_columns("match_players")}
    if "deck_json" not in cols:
        conn.execute(text("ALTER TABLE match_players ADD COLUMN deck_json TEXT"))
        conn.commit()
```

---

## Surveil イベント → Action マッピング

全イベントのうち、ActionLog 表示・統計に有用なもののみ Action レコードとして保存する。

| event_type | action_type | card_name | target_name | player_name | 備考 |
|---|---|---|---|---|---|
| `cast` | `cast` | `card_name` | `targets[0]` の card_name または player | `player` | |
| `play_land` | `play` | `card_name` | — | `player` | |
| `draw` | `draw` | `card_name` | — | `player` | `card_name` なし（相手の非公開）はスキップ |
| `discard` | `discard` | `card_name` | — | `player` | |
| `mulligan` | `mulligan` | — | — | `player` | |
| `attack` | `attack` | `card_name` | `target_player` | `player` | |
| `block` | `block` | `card_name` | `blocking[0]` | `player` | **新 action_type** |
| `ability_activated` | `activate` | `source_card` | — | `player` | |
| `ability_triggered` | `trigger` | `source_card` | — | — | player 情報なし |
| `mill` | `mill` | `card_name` | — | `player` | **新 action_type** |
| `damage` | `damage` | `source_card` | `target_player` または `target_card` | — | **新 action_type**、省略も可 |
| `turn_start` | スキップ | | | | turn フィールドで管理 |
| `phase_change` | スキップ | | | | phase フィールドで管理 |
| `ability_mana` | スキップ | | | | ノイズが多いため除外 |
| `ability_resolved` | スキップ | | | | |
| `resolve` | スキップ | | | | cast で記録済み |
| `life_change` | スキップ | | | | damage から派生 |

### `active_player` の付与方法

`turn_start` イベントの `active_player` フィールドを追跡し、以降の全イベントに付与する。

### `sequence` の設定

Surveil の `seq`（ゲーム内通し番号）をそのまま使用する。

### `phase` の設定

イベントの `phase` フィールドをそのまま `actions.phase` に保存する。

---

## `surveil_parser.py` の設計

### 型定義

```python
class SurveilParseResult(TypedDict):
    match_id: str
    source: Literal["mtga"]
    players: list[str]         # index 0 = seat 1, index 1 = seat 2
    self_seat_id: int
    match_winner: str
    played_at: datetime
    deck_main: dict[str, int]       # card_name → count（self のみ）
    deck_sideboard: dict[str, int]  # card_name → count（self のみ）
    self_player: str                # deck を持つプレイヤー名
    games: list[SurveilGameResult]

class SurveilGameResult(TypedDict):
    game_number: int
    winner: str
    turns: int
    first_player: str
    mulligans: list[dict]   # [{"player_name": str, "count": int}]
    actions: list[dict]     # Action テーブルに保存するイベントのみ
```

### `parse_surveil_json(data: dict) -> SurveilParseResult`

1. `schema_version` を確認（2 以外は `ParseError` を送出）
2. トップレベルフィールドを展開
3. `self_seat_id` から `self_player` を確定
4. `games` を反復し、イベントを Action マッピングテーブルに従って変換
   - `turn_start` イベントから `active_player` を追跡
   - マッピング対象外のイベントはスキップ
5. `SurveilParseResult` を返す

---

## `SurveilImportService` の設計（`import_service.py` に追加）

### クラス定義

```python
class SurveilImportService:
    def __init__(self, db: Session) -> None: ...
    def import_one(self, data: dict, filename: str) -> ImportResult: ...
    def _save(self, parsed: SurveilParseResult) -> None: ...
    def _infer_format_from_deck(self, deck_main: dict[str, int]) -> str: ...
```

### `import_one(data, filename)` の処理フロー

```
1. parse_surveil_json(data) でパース（ParseError → status="error"）
2. db.get(Match, match_id) で重複チェック（存在 → status="skipped"）
3. _save(parsed) で DB に flush
4. _infer_format_from_deck(parsed["deck_main"]) でフォーマット推定
5. match.format を更新して commit
6. status="imported" を返す（3〜5 で例外 → rollback → status="error"）
```

### `_save(parsed)` の保存内容

```
Match（source="mtga"）
  ↓
MatchPlayer × 2
  - self_player には deck_json を JSON シリアライズして保存
  - 対戦相手の deck_json は NULL
  ↓
Game × n（game_number, winner, turns, first_player）
  ↓
Mulligan × n（player_name, count）
Action × n（turn, phase, active_player, player_name, action_type, card_name, target_name, sequence）
```

### `_infer_format_from_deck(deck_main)` のロジック

MTGO インポートの `_infer_format` と同じ Scryfall ルックアップを使うが、入力をデッキリストから取得することで精度を向上させる。

```
1. deck_main のキー（カード名）から基本土地を除外
   除外対象: {"Plains", "Island", "Swamp", "Mountain", "Forest",
              "Snow-Covered Plains", ..., "Wastes"}
2. ScryfallClient.fetch_legalities(card_names) でレガリティを取得
3. FORMAT_PRIORITY 順に全カードが legal/banned なフォーマットを返す
4. 該当なし → "unknown"
```

### デッキ自動検出

MTGO インポートと同じ `_detect_deck()` を使用するが、`used_cards` を play/cast の動的収集ではなく `deck_main` の全カード名から構築するため、精度が大幅に向上する。

---

## API エンドポイント設計（`surveil_import.py`）

### `POST /api/import/surveil`

JSON ファイルを multipart/form-data でアップロードしてインポートする。

**リクエスト**: `UploadFile`（JSON ファイル）
**レスポンス**: `ImportResult`（既存と同形式）
**エラー**: `status="error"` → HTTP 400

### `GET /api/import/surveil/folder`

監視フォルダの設定値を返す。Setting テーブルの `surveil_folder` キーを使用する。

**レスポンス**:
```json
{"folder": "C:\\Users\\...\\Surveil\\matches"}
// 未設定時
{"folder": null}
```

### `PUT /api/import/surveil/folder`

監視フォルダを設定する。

**リクエスト**: `{"folder": "絶対パス文字列"}`
**バリデーション**: パスが存在するディレクトリであることを確認（存在しない場合 HTTP 400）

### `GET /api/import/surveil/pending`

監視フォルダをスキャンして未インポートのファイル一覧を返す。

```
1. surveil_folder 設定を取得（未設定 → HTTP 400）
2. フォルダ内の *.json をスキャン
3. ファイル名（拡張子除く）= match_id として matches テーブルと照合
4. 未インポートのものを返す
```

**レスポンス**:
```json
{
  "folder": "C:\\Users\\...\\matches",
  "pending": [
    {"filename": "9ce5e7b1-....json", "match_id": "9ce5e7b1-...", "mtime": "2026-03-19T14:23:00Z"},
    ...
  ],
  "total": 3
}
```

### `POST /api/import/surveil/scan`

pending を全件インポートする。既存の batch インポートと同様に1件ずつ独立トランザクションで処理する。

**レスポンス**:
```json
{
  "total": 3,
  "imported": 2,
  "skipped": 0,
  "errors": 1,
  "results": [{"match_id": "...", "status": "imported", "format": "modern"}, ...]
}
```

---

## フロントエンド設計

### ImportView.vue の変更

MTGO タブと並んで「MTGA (Surveil)」タブを追加する。

```
[ MTGO ]  [ MTGA (Surveil) ]

── MTGA タブ ──────────────────────────────────────────────────────
監視フォルダ: [C:\Users\...\Surveil\matches　　　　　　　] [変更]

  未取り込み: 3 ファイル
  ・9ce5e7b1-...json  (2026-03-19 14:23)
  ・d4be713b-...json  (2026-03-18 09:45)
  ・02470289-...json  (2026-03-17 11:10)

  [全て取り込む]

─── または ────────────────────────────────────────────────────────
  JSON ファイルをここにドロップ
```

**フォルダ未設定時**:
```
監視フォルダが設定されていません。
Surveil の出力フォルダ（matches/）を登録してください。
[フォルダを登録する]
```

### API 関数追加（`frontend/src/api/import.ts`）

```typescript
// 監視フォルダの取得・設定
export const getSurveilFolder = (): Promise<{ folder: string | null }>
export const setSurveilFolder = (folder: string): Promise<void>

// pending 一覧
export const getSurveilPending = (): Promise<SurveilPendingResult>

// 一括インポート
export const scanSurveil = (): Promise<BatchImportResult>

// 単体ファイルアップロード
export const importSurveilFile = (name: string, data: ArrayBuffer): Promise<ImportResult>
```

### ActionLog.vue の変更

**`phase` フィールドの表示**:
`phase` が設定されているイベントはフェイズ名をラベルとして表示する（例: `[main1] Lightning Bolt を唱えた`）。

**新 action_type の対応**:

| action_type | 表示文言例 |
|---|---|
| `block` | `{card_name} で {target_name} をブロックした` |
| `mill` | `{card_name} がライブラリから墓地に落ちた` |
| `damage` | `{card_name} が {target} に {amount} ダメージを与えた` |

---

## 全体フロー

```
Surveil（Windows）
  → Player.log を監視
  → 試合完結後に {match_id}.json を matches/ フォルダに書き出し

Scry（フロントエンド）
  → ImportView の「MTGA」タブを開く
  → GET /api/import/surveil/pending で未インポートファイル一覧を取得
  → 「全て取り込む」を押す
  → POST /api/import/surveil/scan
       ↓
  SurveilImportService（バックエンド）
    1. JSON を読み込み parse_surveil_json() でパース
    2. 重複チェック（match_id）
    3. DB 保存（Match source="mtga", MatchPlayer with deck_json, Game, Action with phase）
    4. _infer_format_from_deck() でフォーマット推定
    5. _detect_deck() でデッキ名判定
    6. commit
  ↓
  ImportResult を集計してレスポンス
```

---

## トランザクション方針

既存インポートと同じ方針を踏襲する。

| 操作 | commit/rollback |
|---|---|
| `_save()` | flush のみ（commit しない） |
| `import_one()` の正常終了 | format 更新後に1回 commit |
| `import_one()` のエラー | rollback してそのファイル分を取り消す |
| `scan`（一括） | 1ファイルごとに独立。1件のエラーが他に波及しない |

---

## エラーハンドリング

| ケース | 対応 | HTTP Status |
|---|---|---|
| schema_version が 2 以外 | `status="error"`, reason を返す | 400 |
| 重複（match_id 既存） | `status="skipped"` を返す | 200 |
| DB 保存エラー | rollback → `status="error"` | 400 |
| 監視フォルダ未設定で pending/scan を呼んだ | エラーメッセージを返す | 400 |
| 監視フォルダが存在しない | エラーメッセージを返す | 400 |
| Scryfall 取得失敗 | そのカードをスキップ（format="unknown" になり得る） | — |
| scan 中の1件エラー | errors カウント増加、処理継続 | 200 |

---

## 動作確認手順

1. Docker で backend を起動し、`GET /api/health` が返ることを確認する
2. Surveil の `tests/output/` にある JSON ファイルを1件アップロードし、`status: "imported"`, `format: "..."` が返ることを確認する
3. 同じファイルを再アップロードして `status: "skipped"` が返ることを確認する
4. SQLite で `matches.source = "mtga"`, `match_players.deck_json IS NOT NULL`, `actions.phase IS NOT NULL` のレコードが存在することを確認する
5. `PUT /api/import/surveil/folder` で Surveil の出力フォルダを設定する
6. `GET /api/import/surveil/pending` で未インポートファイル一覧が返ることを確認する
7. `POST /api/import/surveil/scan` で一括インポートが実行され、結果が返ることを確認する
8. フロントエンドの「MTGA」タブでフォルダ設定・取り込みが動作することを確認する
9. 取り込んだ試合が対戦履歴に表示され、ActionLog にフェイズ名・新イベント種別が表示されることを確認する
