# 詳細設計: インポートAPI + ImportService

## 対象ファイル

| ファイル | 種別 | 内容 |
|----------|------|------|
| `backend/services/__init__.py` | 新規 | 空ファイル |
| `backend/services/import_service.py` | 新規 | ImportService クラス |
| `backend/services/scryfall_client.py` | 新規 | ScryfallClient クラス |
| `backend/app/routers/import_.py` | 新規 | POST /api/import・/api/import/batch |
| `backend/parser/log_parser.py` | 編集 | `parse_bytes()` メソッドを追加 |
| `backend/app/main.py` | 編集 | import router を登録 |

---

## 全体フロー

```
フロントエンド
  → ファイルを Electron の read-dat-file IPC で読み込み
  → multipart/form-data で POST /api/import に送信
        ↓
FastAPI Router（import_.py）
  → UploadFile からバイト列取得
  → ImportService.import_one(data, filename) を呼ぶ
        ↓
ImportService
  1. MTGOLogParser.parse_bytes(data) でパース
  2. matches テーブルに重複チェック（match_id）
  3. DB に保存（トランザクション）
  4. ScryfallClient でフォーマット推定
  5. matches.format を更新・commit
  6. ImportResult を返す
```

---

## `MTGOLogParser` への変更

`parse_file` を `parse_bytes(data: bytes)` に委譲する形にリファクタリングする。
`UploadFile` のバイト列を直接受け取れるようにするため。

- `parse_bytes(data: bytes) -> ParseResult` を公開メソッドとして追加
- `parse_file(filepath: str) -> ParseResult` はファイルを読み込んで `parse_bytes` に委譲する後方互換ラッパーとする
- `ParseResult` に `played_at: datetime` を追加する（先頭イベントのタイムスタンプ）

---

## 型定義

### `ImportResult`（Python TypedDict）

| フィールド | 型 | 説明 |
|------------|----|------|
| `match_id` | `str` | パースしたマッチID（エラー時は空文字） |
| `status` | `"imported" \| "skipped" \| "error"` | 処理結果 |
| `format` | `str \| None` | imported 時のみ設定 |
| `reason` | `str \| None` | skipped / error 時のみ設定 |

---

## ScryfallClient の設計

**責務**: `multiverse_id` のリストを受け取り、キャッシュ確認・未キャッシュ分の Scryfall API 取得・DB 保存を行い、`{multiverse_id: CardLegality}` の辞書を返す。

**主要メソッド**

| メソッド | 説明 |
|----------|------|
| `fetch_legalities(multiverse_ids) -> dict` | キャッシュ確認 → 未取得分を Scryfall に問い合わせて返す |
| `_fetch_one(multiverse_id) -> CardLegality \| None` | 1件取得。失敗時（404・タイムアウト等）は `None` を返す |
| `_rate_limit()` | 前回リクエストから 100ms 未満なら `time.sleep` で待機 |

**処理フロー**

1. `card_legality` テーブルから `multiverse_id IN (...)` でキャッシュ済み分を一括取得
2. 未キャッシュの ID を特定し、順次 `_fetch_one` を呼ぶ
3. 取得成功した分は `card_legality` に `flush` して結果辞書に追加
4. 失敗した ID は結果辞書に含めない（フォーマット判定からも除外される）

---

## ImportService の設計

**責務**: パース済みデータの DB 保存とフォーマット推定を行う。

**`import_one(data, filename) -> ImportResult` の処理フロー**

1. `parse_bytes(data)` を呼び、`ParseError` は `status="error"` で即返す
2. `db.get(Match, match_id)` で重複チェック。存在すれば `status="skipped"` で即返す
3. `_save(parsed)` で match / match_players / games / mulligans / actions を一括 flush
4. `_infer_format(parsed)` でフォーマット推定
5. `match.format` を更新して commit
6. `status="imported"` で返す。3〜5 のいずれかで例外が出たら rollback して `status="error"`

**`_save(parsed)` の保存対象と注意点**

- `Match.played_at` は `parsed["played_at"]`（先頭イベントのタイムスタンプ）を使用
- `actions` の `card_name` は空文字を `None` に変換して保存する
- `multiverse_id` は `actions` テーブルには保存しない（フォーマット推定のみに使用）
- flush 順序: Match → MatchPlayer → Game → Mulligan / Action（FK 制約のため）

**`_infer_format(parsed)` のロジック**

1. 全ゲームの `play` / `cast` アクションから `multiverse_id` を収集（重複除去・None 除外）
2. `ScryfallClient.fetch_legalities()` で適正情報を取得
3. `FORMAT_PRIORITY = ["standard", "pioneer", "modern", "pauper", "legacy", "vintage"]` の順に、全カードが `"legal"` なフォーマットを探して返す
4. 該当なし・カードなし・全取得失敗の場合は `"unknown"` を返す

---

## FastAPI Router の設計

### `POST /api/import`

- `UploadFile` からバイト列を読み取り `ImportService.import_one` に渡す
- `status="error"` → HTTP 400
- `status="skipped"` / `"imported"` → HTTP 200（レスポンス仕様は `03_api-design.md` 参照）

### `POST /api/import/batch`

- `list[UploadFile]` を順次処理する
- 1件のエラーは他のファイルに影響しない（独立トランザクション）
- 全件処理後に `total` / `imported` / `skipped` / `errors` / `results` をまとめて返す

---

## トランザクション方針

| 操作 | commit/rollback |
|------|----------------|
| `_save()` | flush のみ（commit しない） |
| `import_one()` の正常終了 | format 更新後に1回 commit |
| `import_one()` のエラー | rollback してそのファイル分を取り消す |
| batch | 1ファイルごとに独立。1件のエラーが他に波及しない |

---

## エラーハンドリングまとめ

| ケース | 対応 | HTTP Status |
|--------|------|-------------|
| ParseError（不正ファイル） | `status="error"`, detail を返す | 400 |
| 重複（match_id 既存） | `status="skipped"` を返す | 200 |
| DB 保存エラー | rollback → `status="error"` | 400 |
| Scryfall 取得失敗 | そのカードをスキップ（フォーマット判定から除外） | - |
| 全カードがスキップ | `format="unknown"` | - |
| batch: 1件エラー | errors カウント増加、処理継続 | 200 |

---

## 動作確認手順

1. Docker で backend を起動する
2. curl で単体インポートを実行し `{"status": "imported", "format": "..."}` が返ることを確認する
3. 同じファイルを再送信して `{"status": "skipped"}` が返ることを確認する
4. SQLite で matches / actions のレコードが保存されていることを確認する
5. 複数ファイルで batch エンドポイントをテストし `total` / `imported` / `skipped` が正しいことを確認する

---

## 追加機能: クイックインポート

### 概要

フォルダパスを保存しておき、1クリックで前回インポート以降の新規ファイルのみを自動インポートする。
ファイル内容を読まずにファイルシステムの更新日時 (mtime) で判定することで高速に動作する。

### 新規ファイルの判定ロジック

```
最新 played_at = SELECT MAX(played_at) FROM matches

対象ファイル = スキャン結果のうち mtime > 最新 played_at のもの
```

- `mtime`（ファイル更新日時）を使う理由: MTGO は試合終了時にファイルを書き出すため `mtime ≒ played_at` になる。ファイル内容を読まずに判定できるため高速。
- matches テーブルが空のときは全件を対象とする。
- 対象ファイルが 0 件のときは「新しいログはありません」とトーストで通知してインポートは行わない。

### 対象ファイル一覧

| ファイル | 種別 | 内容 |
|----------|------|------|
| `electron/main.ts` | 編集 | `scan-folder-quick` IPC ハンドラーを追加 |
| `electron/preload.ts` | 編集 | `scanFolderQuick` を expose |
| `frontend/src/electron.d.ts` | 編集 | `scanFolderQuick` の型定義を追加 |
| `backend/app/routers/matches.py` | 編集 | `GET /api/matches/latest-date` エンドポイントを追加 |
| `backend/app/routers/settings.py` | 編集 | `quick_import_folder` キーの読み書きに対応 |
| `frontend/src/api/settings.ts` | 編集 | `fetchQuickImportFolder` / `saveQuickImportFolder` を追加 |
| `frontend/src/api/matches.ts` | 編集 | `fetchLatestMatchDate` を追加 |
| `frontend/src/views/ImportView.vue` | 編集 | Idle 状態にクイックインポート UI を追加 |

### Electron IPC: `scan-folder-quick`

ダイアログを表示せずに指定フォルダをスキャンし、ファイルの mtime（Unix ミリ秒）を付けて返す。

```typescript
// preload 経由で公開するシグネチャ
scanFolderQuick(folderPath: string): Promise<Array<{ path: string; mtime: number }>>
```

main.ts 側の実装は既存の `scanForDatFiles` を流用し、各ファイルに `fs.statSync(path).mtimeMs` を付加する。

### バックエンド API

#### `GET /api/matches/latest-date`

```json
{ "latest_date": "2024-01-15T10:30:00+00:00" }
// matches が空のとき
{ "latest_date": null }
```

`SELECT MAX(played_at) FROM matches` の結果を ISO8601 文字列で返す。

#### `GET /api/settings` / `PUT /api/settings` の拡張

既存の `Setting` テーブル（key-value形式）に `quick_import_folder` キーを追加する。

| キー | 値 |
|------|----|
| `quick_import_folder` | 監視フォルダの絶対パス文字列（未設定時はレコードなし） |

`GET /api/settings` のレスポンスに `quick_import_folder: string \| null` を追加する。
`PUT /api/settings` のリクエストボディに `quick_import_folder?: string \| null` を追加する（`null` を送ると設定を削除する）。

### フロントエンド UI

Idle 状態の上部にクイックインポートセクションを追加する。

**フォルダ登録済みの場合**

```
┌──────────────────────────────────────────────┐
│  ── クイックインポート ───────────────────── │
│  📁 C:\Users\...\Apps\2.0                    │
│  最終インポート: 2024/01/15 10:30            │
│  [⚡ クイックインポート]  [フォルダを変更]   │
└──────────────────────────────────────────────┘
```

**フォルダ未登録の場合**

```
┌──────────────────────────────────────────────┐
│  ── クイックインポート ───────────────────── │
│  フォルダを登録するとワンクリックで           │
│  新規ログをインポートできます                 │
│  [フォルダを登録する]                        │
└──────────────────────────────────────────────┘
```

### クイックインポートのフロー

```
1. GET /api/settings で保存済みフォルダパスを取得
2. GET /api/matches/latest-date で最新 played_at を取得
3. scanFolderQuick(folderPath) で mtime 付きファイル一覧を取得
4. mtime > latest_date のファイルのみ抽出
5. 対象 0 件 → 「新しいログはありません」トースト表示して終了
6. 対象あり → 確認なしで即インポート開始 → [Importing] → [BatchResult] 状態へ
```

「フォルダを登録する」「フォルダを変更」ボタンは既存の `scanFolder`（ダイアログあり）を呼び、
選択されたフォルダパスを `PUT /api/settings` で保存する。

### エラーハンドリング

| ケース | 対応 |
|--------|------|
| 保存フォルダが存在しない | エラートーストを表示し、フォルダ未登録状態に戻す |
| スキャン失敗 | エラートーストを表示 |
| 新規ファイルなし | 「新しいログはありません」トーストを表示 |

### 動作確認手順（クイックインポート）

1. 「フォルダを登録する」でフォルダを選択し、パスが表示されることを確認する
2. 「クイックインポート」を実行し、新規ファイルのみインポートされることを確認する
3. 再度「クイックインポート」を実行し、「新しいログはありません」と表示されることを確認する
4. フォルダに新しい .dat ファイルを追加して「クイックインポート」を実行し、1件のみインポートされることを確認する
5. 「フォルダを変更」で別のフォルダに切り替えられることを確認する
6. matches テーブルが空の状態でクイックインポートを実行し、全件インポートされることを確認する
