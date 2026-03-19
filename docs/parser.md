# パーサー設計

## MTGO パーサー（`backend/parser/mtgo_parser.py`）

### .dat ファイル形式

- バイナリ形式（メッセージ本文は UTF-8）
- 1ファイル = 1マッチ（複数ゲームを含む）

**ヘッダー構造**

```
[01 00]                     # マジックバイト
[24]                        # マッチID長 (= 36)
[match_id: 36 bytes UTF-8]  # UUID 例: "01564d49-9b3b-4bd4-a879-09bc7a91e602"
[04 00][24]
[match_id: 36 bytes UTF-8]  # 同じIDが繰り返し
[2 bytes]                   # パディング
```

**イベントレコード（繰り返し）**

```
[8 bytes]  タイムスタンプ（Windows FILETIME、リトルエンディアン 64bit）
[1 byte]   0x00（固定）
[1 byte]   メッセージ長
[2 bytes]  0x40 0x50（= "@P" プレフィックス）
[N bytes]  メッセージ本文（UTF-8）
```

タイムスタンプ変換: `(value - 621_355_968_000_000_000) / 10_000_000` → Unix timestamp

---

### カード参照形式

```
@[CardName@:multiverseId,permanentId:@]

例: @[Slickshot Show-Off@:248406,428:@]
```

- `CardName` をカード名として使用
- `multiverseId` は MTGO 内部 ID（Scryfall multiverse ID とは異なる）
- フォーマット判定時は Scryfall `/cards/named?exact=<CardName>` でカード名引き
- `permanentId`（ゲーム内オブジェクトID）は使用しない

---

### メッセージパターン → action_type マッピング

| メッセージパターン | action_type |
|-------------------|-------------|
| `{player} plays @[{card}...]` | `play` |
| `{player} casts @[{card}...]` | `cast` |
| `{player} activates an ability of @[{card}...]` | `activate` |
| `{player} puts triggered ability from @[{card}...]` | `trigger` |
| `{player} is being attacked by @[{card}...]` | `attack`（注: group(1) が防御側、attacker = active_player） |
| `{player} draws a card` / `draws {n} cards` | `draw` |
| `{player} discards @[{card}...]` | `discard` |
| `{player} reveals @[{card}...]` | `reveal` |
| `{player} puts ... counter on` | `add_counter` |
| `{player} removes ... counter` | `remove_counter` |
| `{player} mulligans to {n} cards.` | `mulligan` |

**スキップ（アクションとして記録しない）**

`joined the game.` / `wins the game.` / `loses the game.` / `Turn N:` / `wins the match` / `leads the match` / 先手選択・ダイスロール等

---

### ゲーム境界検出

同一マッチ内のゲームは `joined the game.` を区切りとして分割。

```
[ゲームN 終了]
  {player} wins/loses the game.
  {player} leads the match {W}-{L}

[ゲームN+1 開始]
  {player} joined the game.  （2行）
  {player} chooses to play first.
```

マッチ終了: `wins the match {W}-{L}` / `Match Tied {N}-{N}`

---

### プレイヤー名処理

メッセージ先頭の `@P` プレフィックスを再帰的に除去する。

```python
while message.startswith('@P'):
    message = message[2:]
```

---

### フォーマット判定（ImportService）

```
1. 全ゲームの play / cast アクションからカード名を収集
2. card_legality テーブルで未キャッシュのカードを特定
3. 未キャッシュ分を Scryfall /cards/named?exact= で取得（100ms 間隔）
4. 全カードが legal なフォーマットのうち最も制限の厳しいものを採用
   優先順位: standard > pioneer > modern > pauper > legacy > vintage
5. 判定不能（カードなし / 全スキップ）→ "unknown"
```

`banned` カードは `legal` 扱い（プレイ時点では合法だった可能性）。

---

## Surveil パーサー（`backend/parser/surveil_parser.py`）

[surveil](../../surveil/) が出力する `schema_version: 2` の JSON を解析する。

### 入力 JSON 構造

```json
{
  "schema_version": 2,
  "self_player": "PlayerName",
  "opponent_player": "OpponentName",
  "deck": {
    "main": [{"name": "Lightning Bolt", "quantity": 4}, ...],
    "sideboard": [...]
  },
  "games": [
    {
      "game_number": 1,
      "winner": "PlayerName",
      "events": [...]
    }
  ]
}
```

### イベント → action_type マッピング

| Surveil イベント | action_type | 備考 |
|----------------|-------------|------|
| `cast` | `cast` | |
| `play_land` | `play` | |
| `draw` | `draw` | |
| `discard` | `discard` | |
| `mulligan` | `mulligan` | |
| `attack` | `attack` | |
| `block` | `block` | |
| `ability_activated` | `activate` | |
| `ability_triggered` | `trigger` | |
| `mill` | `mill` | |
| `damage` | `damage` | |
| `ability_mana` | スキップ | マナ能力（記録不要） |
| `ability_resolved` | スキップ | |
| `turn_start` | スキップ（active_player 更新のみ） | |
| `phase_change` | スキップ | |
| `resolve` | スキップ | |
| `life_change` | スキップ | |

`phase` フィールド: Surveil JSON のフェーズ情報を `actions.phase` に記録（MTGO は NULL）。

---

### フォーマット判定（SurveilImportService）

デッキのメインカードから基本土地を除いたカード名リストで Scryfall 検索。
MTGO パーサーと同じ判定ロジックを使用（`_detect_deck` 共通関数）。

---

### 出力データ構造（共通）

```python
# ImportService / SurveilImportService が DB に保存するデータ
Match(
    id=str,           # ログから抽出したマッチID
    source="mtgo",    # or "mtga"
    played_at=datetime,
    match_winner=str,
    game_count=int,
    format=str,       # standard / pioneer / modern / ... / unknown
)
MatchPlayer(deck_json=str|None)  # MTGA のみデッキ JSON を保存
Action(
    active_player=str,   # 手番プレイヤー
    player_name=str,     # アクション実行プレイヤー
    phase=str|None,      # MTGA のみ
    target_name=str|None,
)
```
