# API

- ベース URL: `http://localhost:18432`
- フォーマット: JSON（エクスポートは text/plain）
- 文字コード: UTF-8

---

## エンドポイント一覧

### ヘルス

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/health` | ヘルスチェック → `{"status":"ok","version":"0.1.0"}` |

---

### インポート（MTGO）

| メソッド | パス | 説明 |
|----------|------|------|
| POST | `/api/import` | .dat ファイル単体インポート（multipart/form-data） |
| POST | `/api/import/batch` | .dat ファイル一括インポート（multipart/form-data、複数ファイル） |
| GET | `/api/import/mtgo/pending` | 未取り込みファイル一覧（`quick_import_folder` を直接スキャン） |
| POST | `/api/import/mtgo/scan` | `quick_import_folder` の pending ファイルを一括インポート |

**POST /api/import レスポンス**

```json
{
  "match_id": "abc123",
  "status": "imported",   // "imported" | "skipped" | "error"
  "format": "modern",
  "reason": null
}
```

---

### インポート（MTGA / Surveil）

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/import/surveil/folder` | 監視フォルダ設定取得 → `{"folder": str\|null}` |
| PUT | `/api/import/surveil/folder` | 監視フォルダ設定保存 `{"folder": str}` |
| GET | `/api/import/surveil/imported-ids` | 取り込み済み match_id 一覧（フロントエンド pending 判定用） |
| GET | `/api/import/surveil/pending` | 未取り込みファイル一覧（バックエンドがフォルダを直接スキャン） |
| POST | `/api/import/surveil/scan` | pending を一括インポート |
| POST | `/api/import/surveil` | Surveil JSON 単体インポート（multipart/form-data） |

> 開発環境（Docker）ではバックエンドがホストのフォルダにアクセスできないため、
> pending 一覧と一括スキャンは Electron 側（`scanSurveilFolder` IPC）で実施する。
> バックエンドの `/pending` と `/scan` は本番（ローカルバイナリ）向け。

---

### 対戦履歴

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/matches` | 試合一覧（フィルター・ページネーション対応） |
| GET | `/api/matches/latest-date` | 最新インポート日時取得 |
| GET | `/api/matches/export/count` | エクスポート対象件数取得 |
| GET | `/api/matches/export` | Markdown エクスポート（text/plain） |
| GET | `/api/matches/bulk-assign-deck-version/count` | 一括デッキ紐づけ対象件数 |
| POST | `/api/matches/bulk-assign-deck-version` | デッキバージョン一括紐づけ |
| GET | `/api/matches/{match_id}` | 試合詳細（プレイヤー・ゲーム一覧） |
| GET | `/api/matches/{match_id}/games/{game_id}/actions` | アクションログ取得 |
| PATCH | `/api/matches/{match_id}/players/{player_name}` | デッキ名・ゲームプラン更新 |
| PUT | `/api/matches/{match_id}/players/{player_name}/deck-version` | デッキバージョン紐づけ |
| DELETE | `/api/matches/{match_id}/players/{player_name}/deck-version` | デッキバージョン解除 |

**GET /api/matches クエリパラメータ**

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `limit` | int | 取得件数（default: 50） |
| `offset` | int | オフセット（default: 0） |
| `player` | str | プレイヤー名フィルター |
| `opponent` | str | 相手プレイヤー名フィルター |
| `deck_id` | int | デッキ ID フィルター |
| `deck` | str | デッキ名フィルター |
| `version_id` | int | デッキバージョン ID フィルター |
| `opponent_deck` | str | 相手デッキ名フィルター |
| `format` | str | フォーマットフィルター |
| `date_from` | str | 開始日（ISO 8601） |
| `date_to` | str | 終了日（ISO 8601） |

---

### データ削除

| メソッド | パス | 説明 |
|----------|------|------|
| DELETE | `/api/matches/all` | 全試合データ削除（matches / games / actions / mulligans） |
| DELETE | `/api/matches/range` | 期間指定削除（`date_from` / `date_to` クエリパラメータ） |
| DELETE | `/api/reset` | 完全リセット（全テーブルを DROP → 再作成） |

---

### 統計

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/stats/players` | プレイヤー一覧（ドロップダウン用） |
| GET | `/api/stats/opponents` | 対戦相手一覧 |
| GET | `/api/stats/opponent-decks` | 相手デッキ名一覧 |
| GET | `/api/stats/player-decks` | 自分のデッキ名一覧 |
| GET | `/api/stats/formats` | フォーマット一覧 |
| GET | `/api/stats` | 集計統計（勝率・マリガン・ターン数等） |
| GET | `/api/stats/cards` | カード別統計（相手カード出現頻度等） |

主なクエリパラメータ: `player`, `opponent`, `deck`, `opponent_deck`, `format`, `date_from`, `date_to`

---

### デッキ管理（デッキリスト）

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/decklist/decks` | デッキ一覧 |
| POST | `/api/decklist/decks` | デッキ新規作成 |
| PUT | `/api/decklist/decks/{deck_id}` | デッキ情報更新 |
| DELETE | `/api/decklist/decks/{deck_id}` | デッキ完全削除 |
| POST | `/api/decklist/decks/{deck_id}/archive` | デッキアーカイブ |
| POST | `/api/decklist/decks/{deck_id}/unarchive` | デッキアーカイブ解除 |
| GET | `/api/decklist/decks/{deck_id}/versions` | バージョン一覧 |
| GET | `/api/decklist/decks/{deck_id}/versions/{version_id}` | バージョン詳細（カードリスト含む） |
| POST | `/api/decklist/decks/{deck_id}/versions` | バージョン新規作成（テキスト入力） |
| POST | `/api/decklist/decks/{deck_id}/versions/import` | .dek ファイルからバージョン作成 |
| PUT | `/api/decklist/decks/{deck_id}/versions/{version_id}` | バージョン更新（カードリスト含む） |
| DELETE | `/api/decklist/decks/{deck_id}/versions/{version_id}` | バージョン削除 |
| POST | `/api/decklist/decks/{deck_id}/versions/{version_id}/archive` | バージョンアーカイブ |
| POST | `/api/decklist/decks/{deck_id}/versions/{version_id}/unarchive` | バージョンアーカイブ解除 |
| GET | `/api/cards/{scryfall_id}/image` | カード画像取得（ローカルキャッシュ or Scryfall） |

---

### デッキ定義（自動識別）

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/deck-definitions` | デッキ定義一覧 |
| POST | `/api/deck-definitions` | デッキ定義作成 |
| PUT | `/api/deck-definitions/{definition_id}` | デッキ定義更新 |
| DELETE | `/api/deck-definitions/{definition_id}` | デッキ定義削除 |
| POST | `/api/deck-definitions/generate` | AI によるデッキ定義自動生成 |
| POST | `/api/deck-definitions/import` | デッキ定義 JSON インポート |
| GET | `/api/deck-definitions/export` | デッキ定義 JSON エクスポート |
| PATCH | `/api/deck-bulk` | デッキ名一括更新 |
| POST | `/api/decks/apply-definitions` | デッキ定義をマッチに一括適用 |

---

### AI 分析

| メソッド | パス | 説明 |
|----------|------|------|
| POST | `/api/analysis/chat` | AI チャット（SSE ストリーミング） |
| GET | `/api/analysis/sessions` | セッション一覧 |
| GET | `/api/analysis/sessions/{id}` | セッション詳細（メッセージ含む） |
| DELETE | `/api/analysis/sessions/{id}` | セッション削除 |

---

### プリセット（プロンプトテンプレート・定型質問）

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/prompt-templates` | テンプレート一覧 |
| POST | `/api/prompt-templates` | テンプレート作成 |
| PUT | `/api/prompt-templates/{template_id}` | テンプレート更新 |
| DELETE | `/api/prompt-templates/{template_id}` | テンプレート削除 |
| GET | `/api/question-sets` | 質問セット一覧（質問一覧含む） |
| POST | `/api/question-sets` | 質問セット作成 |
| PUT | `/api/question-sets/{set_id}` | 質問セット更新 |
| DELETE | `/api/question-sets/{set_id}` | 質問セット削除 |

---

### 自動インポート

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/import/auto-import/status` | スケジューラーの状態取得（最終実行日時・結果・有効/無効） |

設定（有効/無効・間隔）は `/api/settings` の `auto_import_enabled` / `auto_import_interval_sec` で管理する。

**GET /api/import/auto-import/status レスポンス**

```json
{
  "enabled": true,
  "interval_sec": 30,
  "last_run_at": "2026-03-21T10:00:00Z",
  "last_result": {
    "mtgo": { "imported": 2, "skipped": 0, "errors": 0 },
    "mtga": { "imported": 1, "skipped": 3, "errors": 0 }
  }
}
```

---

### 設定

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/settings` | 設定取得（`default_player`, `llm_provider`, `quick_import_folder`, `auto_import_enabled`, `auto_import_interval_sec`, APIキー設定済みフラグ） |
| PUT | `/api/settings` | 設定更新 |
| DELETE | `/api/settings/api-key` | API キー削除 |

---

### バックアップ・リストア

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/backup` | DB ファイルをダウンロード（application/octet-stream） |
| POST | `/api/restore` | DB ファイルをアップロードしてリストア（multipart/form-data） |
