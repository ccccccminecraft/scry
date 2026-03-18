# API 設計

## 基本仕様

- ベース URL: `http://localhost:18432`
- フォーマット: JSON
- 文字コード: UTF-8

---

## エンドポイント一覧

| メソッド | パス | 概要 |
|----------|------|------|
| GET | `/api/health` | ヘルスチェック |
| POST | `/api/import` | .dat ファイルのインポート（単体） |
| POST | `/api/import/batch` | .dat ファイルの一括インポート（フォルダスキャン用） |
| GET | `/api/matches` | 対戦履歴一覧取得 |
| GET | `/api/matches/{match_id}` | 対戦詳細取得 |
| GET | `/api/matches/{match_id}/games/{game_id}/actions` | ゲームのアクションログ取得 |
| GET | `/api/stats` | 集計統計取得 |
| GET | `/api/stats/cards` | カード別統計取得 |
| GET | `/api/stats/opponents` | 対戦相手一覧取得 |
| GET | `/api/stats/players` | プレイヤー一覧取得（統計画面ドロップダウン用） |
| PATCH | `/api/matches/{match_id}/players/{player_name}` | デッキ名・ゲームプラン更新 |
| PUT | `/api/matches/{match_id}/players/{player_name}/deck-version` | 使用デッキバージョン設定 |
| DELETE | `/api/matches/{match_id}/players/{player_name}/deck-version` | 使用デッキバージョン解除 |
| POST | `/api/analysis/chat` | AI チャット（SSE ストリーミング）・セッション自動保存 |
| GET | `/api/analysis/sessions` | チャットセッション一覧取得 |
| GET | `/api/analysis/sessions/{id}` | チャットセッション詳細取得（メッセージ含む） |
| DELETE | `/api/analysis/sessions/{id}` | チャットセッション削除 |
| GET | `/api/settings` | 設定取得（API キー設定済み確認） |
| PUT | `/api/settings` | 設定保存（API キー登録） |
| DELETE | `/api/settings/api-key` | API キー削除 |
| GET | `/api/prompt-templates` | プロンプトテンプレート一覧取得 |
| POST | `/api/prompt-templates` | プロンプトテンプレート作成 |
| PUT | `/api/prompt-templates/{id}` | プロンプトテンプレート更新 |
| DELETE | `/api/prompt-templates/{id}` | プロンプトテンプレート削除 |
| GET | `/api/question-sets` | 質問セット一覧取得（質問一覧含む） |
| POST | `/api/question-sets` | 質問セット作成 |
| PUT | `/api/question-sets/{id}` | 質問セット更新（名前・質問一覧） |
| DELETE | `/api/question-sets/{id}` | 質問セット削除 |

---

## エンドポイント詳細

### GET /api/health

ヘルスチェック。

**レスポンス**

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

### POST /api/import

.dat ファイルを1件パースして DB に保存する（ルート A / B 用）。

**リクエスト**

```
Content-Type: multipart/form-data
file: <.dat ファイル>
```

**レスポンス（成功）**

```json
{
  "match_id": "abc123",
  "status": "imported",
  "format": "modern"
}
```

**レスポンス（重複）**

```json
{
  "match_id": "abc123",
  "status": "skipped",
  "reason": "already imported"
}
```

**レスポンス（失敗）**

```json
{
  "detail": "Invalid .dat file format"
}
```

---

### POST /api/import/batch

複数の .dat ファイルを一括でパース・保存する（フォルダスキャン用）。
各ファイルは順次処理され、重複はスキップ、エラーは件数に加算されて処理を継続する。

**リクエスト**

```
Content-Type: multipart/form-data
files: <.dat ファイル>[]   ← 複数ファイル
```

**レスポンス**

```json
{
  "total": 20,
  "imported": 15,
  "skipped": 4,
  "errors": 1,
  "results": [
    { "name": "Match_GameLog_xxxx.dat", "status": "imported", "match_id": "abc123" },
    { "name": "Match_GameLog_yyyy.dat", "status": "skipped",  "reason": "already imported" },
    { "name": "Match_GameLog_zzzz.dat", "status": "error",    "reason": "Invalid format" }
  ]
}
```

---

### GET /api/matches

対戦履歴一覧を返す。

**クエリパラメータ**

| パラメータ | 型 | デフォルト | 上限 | 説明 |
|------------|----|------------|------|------|
| `limit` | int | 50 | 100 | 取得件数 |
| `offset` | int | 0 | - | 取得開始位置 |

**レスポンス**

```json
{
  "total": 120,
  "limit": 50,
  "offset": 0,
  "matches": [
    {
      "match_id": "abc123",
      "date": "2024-01-15T10:30:00",
      "players": ["PlayerA", "PlayerB"],
      "match_winner": "PlayerA",
      "game_count": 3,
      "format": "modern"
    }
  ]
}
```

**フロント側のページ計算**

```
総ページ数 = ceil(total / limit)
現在ページ = floor(offset / limit) + 1
次ページ   = offset + limit  （total を超えない場合のみ表示）
前ページ   = offset - limit  （0 を下回らない場合のみ表示）
```

---

### GET /api/matches/{match_id}

対戦詳細（ゲームごとの情報）を返す。

**レスポンス**

```json
{
  "match_id": "abc123",
  "date": "2024-01-15T10:30:00",
  "players": [
    { "player_name": "PlayerA", "deck_name": "Modern Burn", "game_plan": "aggro" },
    { "player_name": "PlayerB", "deck_name": null, "game_plan": null }
  ],
  "match_winner": "PlayerA",
  "format": "modern",
  "games": [
    {
      "game_number": 1,
      "winner": "PlayerA",
      "turns": 8,
      "first_player": "PlayerA",
      "mulligans": {
        "PlayerA": 0,
        "PlayerB": 1
      }
    }
  ]
}
```

---

### GET /api/matches/{match_id}/games/{game_id}/actions

ゲームのアクションログ一覧を返す。S04 対戦詳細のアコーディオン展開時に呼び出す。

**レスポンス**

```json
{
  "game_id": 12,
  "actions": [
    { "turn": 1, "player": "PlayerA", "action_type": "play",  "card_name": "Mountain",       "sequence": 1 },
    { "turn": 1, "player": "PlayerA", "action_type": "cast",  "card_name": "Lightning Bolt", "sequence": 2 },
    { "turn": 2, "player": "PlayerB", "action_type": "draw",  "card_name": null,             "sequence": 1 }
  ]
}
```

---

### GET /api/stats

集計統計を返す。

**クエリパラメータ**

| パラメータ | 型 | デフォルト | 説明 |
|------------|----|------------|------|
| `player` | string | 必須 | 対象プレイヤー名 |
| `opponent` | string | - | 対戦相手名でフィルタ |
| `deck` | string | - | 自分のデッキ名でフィルタ |
| `opponent_deck` | string | - | 相手のデッキ名でフィルタ |
| `format` | string | - | フォーマットでフィルタ |
| `date_from` | string | - | 対戦日時の開始日（YYYY-MM-DD） |
| `date_to` | string | - | 対戦日時の終了日（YYYY-MM-DD、当日を含む） |
| `history_size` | int | 20 | 勝率推移グラフの対象マッチ数（直近 N マッチ） |

**フィールド定義**

| フィールド | 説明 |
|------------|------|
| `mulligan_rate` | マリガンを1回以上行ったゲーム数 / 総ゲーム数 |
| `first_play_win_rate` | `games.first_player` = 対象プレイヤーのゲームの勝率 |
| `second_play_win_rate` | `games.first_player` ≠ 対象プレイヤーのゲームの勝率 |
| `win_rate_history` | 直近 `history_size` マッチを時系列に並べた勝敗（グラフ用） |

**レスポンス**

```json
{
  "total_matches": 120,
  "win_rate": 0.583,
  "avg_turns": 9.2,
  "mulligan_rate": 0.31,
  "first_play_win_rate": 0.62,
  "second_play_win_rate": 0.54,
  "win_rate_history": [
    { "date": "2024-01-01", "match_index": 1, "won": true  },
    { "date": "2024-01-02", "match_index": 2, "won": false }
  ],
  "deck_stats": [
    { "deck_name": "Modern Burn", "matches": 60, "win_rate": 0.617 },
    { "deck_name": "Amulet Titan", "matches": 60, "win_rate": 0.550 }
  ]
}
```

- `deck_stats` は `deck_name` が NULL のマッチを除外して集計する

---

### POST /api/analysis/chat

AI とのチャットメッセージを送信し、SSE（Server-Sent Events）でストリーミング返却する。
API キーが未設定の場合は 400 を返す。

**リクエスト**

```json
{
  "player": "PlayerA",
  "prompt_template_id": 1,
  "session_id": 3,
  "message": "マリガンについて詳しく教えて",
  "history": [
    { "role": "user",      "content": "私のプレイの傾向を教えて" },
    { "role": "assistant", "content": "先手時の勝率が後手より 8% 高く..." }
  ]
}
```

| フィールド | 型 | 必須 | 説明 |
|------------|----|------|------|
| `player` | string | ✓ | 対象プレイヤー名 |
| `prompt_template_id` | int | - | 使用するプロンプトテンプレート ID（省略時はデフォルト） |
| `session_id` | int | - | 保存先セッション ID。省略時は新規セッションを自動作成 |
| `message` | string | ✓ | ユーザーのメッセージ |
| `history` | array | - | 過去の会話履歴（省略時は新規会話） |

**レスポンス（SSE ストリーミング）**

```
Content-Type: text/event-stream

data: {"delta": "マリガン後の勝率は"}
data: {"delta": " 38% と平均を大きく"}
data: {"delta": "下回っています。"}
data: {"done": true, "session_id": 3}
```

**SSE イベント種別**

| イベント | 説明 |
|---------|------|
| `{"delta": "..."}` | テキストの断片。順次フロントに追記する |
| `{"done": true, "session_id": N}` | ストリーミング完了。`session_id` はセッション保存先 |
| `{"error": "..."}` | エラー発生。LLM API タイムアウト / 接続エラー等。フロントはエラートーストを表示する |

フロントはストリーミング中に `error` イベントを受信した場合、それまでに受信済みのテキストをそのまま表示し、末尾にエラーメッセージを付記する。

**レスポンス（API キー未設定）**

```json
{
  "detail": "API key is not configured"
}
```

> 会話履歴はフロント側（Vue）で保持・管理する。バックエンドはステートレス。

---

### GET /api/settings

現在の設定を返す。API キーは OS キーストアに登録済みか否かのみ返す（値は返さない）。

**レスポンス**

```json
{
  "llm_provider": "claude",
  "api_key_configured": true
}
```

> API キーの値・マスク文字列はレスポンスに含めない。
> `llm_provider` は SQLite の `settings` テーブルから取得。
> `api_key_configured` は `keyring.get_password("scry", "llm_api_key") is not None` で判定。

---

### PUT /api/settings

LLM プロバイダー設定と API キーを保存する。
API キーは OS キーストア（keyring）に保存し、SQLite には書き込まない。
保存後に LLM API への疎通確認を行う。

**リクエスト**

```json
{
  "llm_provider": "claude",
  "api_key": "sk-ant-xxxxxxxxxxxx"
}
```

**保存先**

| 項目 | 保存先 |
|------|--------|
| `llm_provider` | SQLite `settings` テーブル |
| `api_key` | OS キーストア（keyring） |

**レスポンス（成功）**

```json
{
  "status": "saved"
}
```

**レスポンス（API キー不正）**

```json
{
  "detail": "Invalid API key"
}
```

---

### DELETE /api/settings/api-key

OS キーストアから API キーを削除する。

**レスポンス**

```json
{
  "status": "deleted"
}
```

---

### GET /api/stats/cards

カード別統計を返す。`actions` テーブルの `play` / `cast` アクションを集計する。`perspective` パラメータで自分・相手どちらのカードを集計するか切り替えられる。

**クエリパラメータ**

| パラメータ | 型 | デフォルト | 説明 |
|------------|----|------------|------|
| `player` | string | 必須 | 対象プレイヤー名 |
| `opponent` | string | - | 対戦相手名でフィルタ |
| `deck` | string | - | 自分のデッキ名でフィルタ |
| `opponent_deck` | string | - | 相手のデッキ名でフィルタ |
| `format` | string | - | フォーマットでフィルタ |
| `date_from` | string | - | 対戦日時の開始日（YYYY-MM-DD） |
| `date_to` | string | - | 対戦日時の終了日（YYYY-MM-DD、当日を含む） |
| `limit` | int | 20 | 返却件数上限（プレイ頻度順） |
| `perspective` | string | `self` | `self`：自分が使ったカード / `opponent`：相手が使ったカード |

**レスポンス**

```json
{
  "cards": [
    {
      "card_name": "Lightning Bolt",
      "play_count": 143,
      "game_count": 87,
      "win_rate": 0.644
    }
  ]
}
```

| フィールド | 説明 |
|------------|------|
| `play_count` | そのカードを cast / play した総アクション数 |
| `game_count` | そのカードが登場したゲーム数 |
| `win_rate` | そのカードが登場したゲームにおける **選択プレイヤー（`player`）の勝率**（`perspective` に関わらず常に同じ視点） |

---

### GET /api/stats/opponents

対戦したことのある相手の一覧を返す（フィルタ用ドロップダウン向け）。

**クエリパラメータ**

| パラメータ | 型 | 説明 |
|------------|----|------|
| `player` | string | 対象プレイヤー名（必須） |

**レスポンス**

```json
["OpponentA", "OpponentB", "OpponentC"]
```

---

### GET /api/stats/players

`match_players` テーブルに登録されているプレイヤー名の一覧を返す。
統計画面（S05）のプレイヤー選択ドロップダウンの選択肢生成に使用する。

**クエリパラメータ**

なし

**レスポンス**

```json
["PlayerA", "PlayerB", "PlayerC"]
```

- `match_players.player_name` の DISTINCT 一覧をアルファベット順で返す
- 1件もない場合は空配列を返す

---

### PUT /api/matches/{match_id}/players/{player_name}/deck-version

対戦プレイヤーに使用デッキバージョンを紐づける。すでに設定済みの場合は上書きする。

**リクエスト**

```json
{ "deck_version_id": 3 }
```

**レスポンス**

```json
{ "status": "updated" }
```

**エラー**

| 状況 | コード | 説明 |
|------|--------|------|
| match_id または player_name が存在しない | 404 | - |
| deck_version_id が存在しない | 404 | - |

---

### DELETE /api/matches/{match_id}/players/{player_name}/deck-version

対戦プレイヤーのデッキバージョン紐づけを解除する（`deck_version_id` を NULL に設定）。

**レスポンス**

```json
{ "status": "updated" }
```

---

### PATCH /api/matches/{match_id}/players/{player_name}

対戦詳細画面からデッキ名・ゲームプランを更新する。

**リクエスト**

```json
{ "deck_name": "Modern Burn", "game_plan": "aggro" }
```

**レスポンス**

```json
{ "status": "updated" }
```

---

### GET /api/analysis/sessions

チャットセッション一覧を返す。

**クエリパラメータ**

| パラメータ | 型 | 説明 |
|------------|----|------|
| `player` | string | プレイヤー名でフィルタ（省略時は全件） |

**レスポンス**

```json
[
  {
    "id": 3,
    "player_name": "PlayerA",
    "prompt_template_id": 1,
    "title": "マリガンについて詳しく教えて",
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:45:00"
  }
]
```

---

### GET /api/analysis/sessions/{id}

セッション詳細をメッセージ一覧込みで返す。

**レスポンス**

```json
{
  "id": 3,
  "player_name": "PlayerA",
  "prompt_template_id": 1,
  "title": "マリガンについて詳しく教えて",
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:45:00",
  "messages": [
    { "id": 1, "role": "assistant", "content": "PlayerA さんの統計データを読み込みました。", "display_order": 1 },
    { "id": 2, "role": "user",      "content": "マリガンについて詳しく教えて", "display_order": 2 },
    { "id": 3, "role": "assistant", "content": "マリガン後の勝率は 38% と...", "display_order": 3 }
  ]
}
```

---

### DELETE /api/analysis/sessions/{id}

セッションをメッセージごと削除する。

**レスポンス**

```json
{ "status": "deleted" }
```

---

### GET /api/prompt-templates

プロンプトテンプレート一覧を返す。

**レスポンス**

```json
[
  { "id": 1, "name": "デフォルト", "content": "あなたはMagic...", "is_default": true },
  { "id": 2, "name": "マリガン重点", "content": "...", "is_default": false }
]
```

---

### POST /api/prompt-templates

プロンプトテンプレートを作成する。

**リクエスト**

```json
{ "name": "マリガン重点", "content": "...", "is_default": false }
```

**レスポンス**

```json
{ "id": 2, "name": "マリガン重点", "content": "...", "is_default": false }
```

---

### PUT /api/prompt-templates/{id}

プロンプトテンプレートを更新する。`is_default: true` を設定すると他のテンプレートの `is_default` は自動的に `false` になる。

**リクエスト**

```json
{ "name": "マリガン重点", "content": "...", "is_default": true }
```

**レスポンス**

```json
{ "id": 2, "name": "マリガン重点", "content": "...", "is_default": true }
```

---

### DELETE /api/prompt-templates/{id}

プロンプトテンプレートを削除する。デフォルトテンプレートは削除不可（400 を返す）。

**レスポンス**

```json
{ "status": "deleted" }
```

---

### GET /api/question-sets

質問セット一覧を質問一覧込みで返す。

**レスポンス**

```json
[
  {
    "id": 1,
    "name": "基本分析",
    "is_default": true,
    "items": [
      { "id": 1, "text": "私のプレイの傾向を教えてください", "display_order": 1 },
      { "id": 2, "text": "先手・後手の勝率の差について分析してください", "display_order": 2 }
    ]
  }
]
```

---

### POST /api/question-sets

質問セットを作成する。質問一覧を同時に登録する。

**リクエスト**

```json
{
  "name": "詳細分析",
  "is_default": false,
  "items": [
    { "text": "ゲーム序盤の傾向を教えてください", "display_order": 1 },
    { "text": "最もよく使うカードを教えてください", "display_order": 2 }
  ]
}
```

**レスポンス**: 作成されたセット（`GET /api/question-sets` と同形式）

---

### PUT /api/question-sets/{id}

質問セットの名前・質問一覧を更新する。`items` は全件洗い替えで更新する。

**リクエスト**: `POST /api/question-sets` と同形式

**レスポンス**: 更新後のセット

---

### DELETE /api/question-sets/{id}

質問セットを削除する。デフォルトセットは削除不可（400 を返す）。

**レスポンス**

```json
{ "status": "deleted" }
```

---

## エラーレスポンス共通仕様

```json
{
  "detail": "エラーメッセージ"
}
```

| ステータスコード | 説明 |
|------------------|------|
| 400 | リクエスト不正 |
| 404 | リソースが存在しない |
| 422 | バリデーションエラー |
| 500 | サーバー内部エラー |
