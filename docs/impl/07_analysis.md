# 詳細設計: AI分析画面 (S06)

## 対象ファイル

| ファイル | 種別 | 内容 |
|----------|------|------|
| `frontend/src/api/analysis.ts` | 新規 | 分析・セッション API 関数・型定義 |
| `frontend/src/api/settings.ts` | 新規 | 設定 API 関数・型定義 |
| `frontend/src/views/AnalysisView.vue` | 新規 | S06 AI分析画面 |
| `frontend/src/components/ChatMessage.vue` | 新規 | 1メッセージの表示コンポーネント |
| `frontend/src/components/SessionBar.vue` | 新規 | セッション履歴バー |
| `frontend/src/router/index.ts` | 編集 | `/analysis` ルートを追加 |
| `backend/app/routers/analysis.py` | 新規 | POST /api/analysis/chat・セッション CRUD |
| `backend/app/routers/settings.py` | 新規 | GET・PUT /api/settings・DELETE /api/settings/api-key |
| `backend/app/main.py` | 編集 | analysis・settings router を登録 |

---

## `api/settings.ts` の型定義

```typescript
interface SettingsResponse {
  llm_provider: string
  api_key_configured: boolean
}
```

**API 関数**

| 関数 | エンドポイント |
|------|--------------|
| `fetchSettings()` | `GET /api/settings` |

---

## `api/analysis.ts` の型定義

```typescript
interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface ChatRequest {
  player: string
  prompt_template_id?: number
  session_id?: number
  message: string
  history?: ChatMessage[]
}

interface SessionSummary {
  id: number
  player_name: string
  prompt_template_id: number | null
  title: string
  created_at: string
  updated_at: string
}

interface SessionDetail extends SessionSummary {
  messages: Array<{
    id: number
    role: 'user' | 'assistant'
    content: string
    display_order: number
  }>
}

interface PromptTemplate {
  id: number
  name: string
  content: string
  is_default: boolean
}

interface QuestionSet {
  id: number
  name: string
  is_default: boolean
  items: QuestionItem[]
}

interface QuestionItem {
  id: number
  text: string
  display_order: number
}
```

**API 関数**

| 関数 | エンドポイント | 説明 |
|------|--------------|------|
| `fetchSessions(player?)` | `GET /api/analysis/sessions` | セッション一覧 |
| `fetchSessionDetail(id)` | `GET /api/analysis/sessions/{id}` | セッション詳細 |
| `deleteSession(id)` | `DELETE /api/analysis/sessions/{id}` | セッション削除 |
| `fetchPromptTemplates()` | `GET /api/prompt-templates` | テンプレート一覧 |
| `fetchQuestionSets()` | `GET /api/question-sets` | 質問セット一覧 |
| `streamChat(req, callbacks, signal?)` | `POST /api/analysis/chat` | SSE ストリーミング（後述） |

---

## SSE ストリーミング処理

`POST /api/analysis/chat` は `text/event-stream` で返却される。
axios は SSE に非対応のため、**`fetch` + `ReadableStream`** で実装する。

**`streamChat` の設計**

- `fetch` で POST を送信し、`response.body` の `ReadableStream` を `getReader()` で読み取る
- 受信バイト列を `TextDecoder` でデコードし、`\n` で分割して `data: ` プレフィックスの行を処理する
- 末尾の不完全な行はバッファに保持して次のチャンクと結合する
- `AbortSignal` を受け取ることでキャンセルに対応する

**コールバック**

```typescript
interface StreamCallbacks {
  onDelta: (text: string) => void      // テキスト断片受信
  onDone: (sessionId: number) => void  // 完了（session_id を受け取る）
  onError: (message: string) => void   // エラー発生
}
```

---

## AnalysisView.vue

### 状態

| 変数 | 型 | 説明 |
|------|----|------|
| `apiKeyConfigured` | `boolean \| null` | null = 確認中 |
| `players` | `string[]` | プレイヤー選択肢 |
| `selectedPlayer` | `string` | 選択中プレイヤー |
| `promptTemplates` | `PromptTemplate[]` | テンプレート一覧 |
| `selectedTemplateId` | `number \| null` | 選択中テンプレート ID |
| `questionSets` | `QuestionSet[]` | 質問セット一覧 |
| `selectedSetId` | `number \| null` | 選択中質問セット ID |
| `sessions` | `SessionSummary[]` | セッション履歴一覧 |
| `currentSessionId` | `number \| null` | 現在のセッション ID |
| `isReadOnly` | `boolean` | 過去セッション閲覧中か |
| `messages` | `ChatMessage[]` | 表示中のメッセージ一覧 |
| `inputText` | `string` | 入力欄の文字列 |
| `streaming` | `boolean` | ストリーミング中フラグ |
| `streamingContent` | `string` | ストリーミング中の一時テキスト |
| `currentQuestionItems` | computed | 選択中セットの質問一覧 |

### 初期化フロー

1. `fetchSettings()` で API キー設定済みかを確認する
2. 未設定なら未設定メッセージを表示して終了する
3. 設定済みなら `fetchPlayers()`・`fetchPromptTemplates()`・`fetchQuestionSets()` を並列で取得する
4. 各デフォルト値を初期選択し、プレイヤーが1件以上あれば `loadSessions()` → `startNewSession()` を呼ぶ

### セッション管理フロー

**新規セッション開始（`startNewSession()`）**
1. 進行中のストリーミングを `AbortController.abort()` で中断する
2. `messages`・`streamingContent`・`currentSessionId` をリセットする
3. `isReadOnly` を `false` にする
4. 挨拶メッセージを `sendMessage` で自動送信する（ユーザーメッセージ行には表示しない）

**過去セッション閲覧（`selectSession(id)`）**
1. `fetchSessionDetail(id)` でメッセージ一覧を取得する
2. `messages` にセットして `isReadOnly = true` にする

**セッション削除（`deleteCurrentSession()`）**
1. `deleteSession(currentSessionId)` を呼ぶ
2. `sessions` から該当エントリを除去する
3. `startNewSession()` で新規セッションを開始する

### メッセージ送信フロー（`sendMessage(text, isGreeting?)`）

1. `streaming === true` またはテキストが空の場合は何もしない
2. `isGreeting` でない場合はユーザーメッセージを `messages` に追加し `inputText` をクリアする
3. `streaming = true`・新規 `AbortController` を作成する
4. `streamChat` を呼ぶ
   - `onDelta`: `streamingContent` にテキストを追記する
   - `onDone`: `messages` にアシスタントメッセージを追加、`currentSessionId` を更新、`loadSessions()` を呼ぶ
   - `onError`: ストリーミング途中のテキストがあれば末尾に `（エラーが発生しました）` を付記してメッセージに追加、`showError` でトーストを表示する

### watch による再取得

| 変更対象 | 実行する処理 |
|----------|------------|
| `selectedPlayer` | `loadSessions()` + `startNewSession()` |
| `selectedTemplateId` | `startNewSession()`（会話リセット） |
| `selectedSetId` | なし（質問ボタンの表示だけ切り替わる） |
| `messages` | 次 tick でチャット末尾に自動スクロール |

### キーボード操作

- Enter: 送信
- Shift+Enter: 改行

---

## コンポーネント設計

### `ChatMessage.vue`

| Prop | 型 | 説明 |
|------|----|------|
| `message` | `{role, content}` | 表示するメッセージ |
| `streaming?` | `boolean` | ストリーミング中フラグ（カーソル表示用） |

- ユーザーメッセージは右寄せ、アシスタントは左寄せで表示する
- `content` の改行を `<br>` に変換して表示する（HTML エスケープ必須）
- `streaming === true` のとき末尾に点滅カーソル `▌` を表示する

### `SessionBar.vue`

| Prop | 型 | 説明 |
|------|----|------|
| `sessions` | `SessionSummary[]` | セッション一覧 |
| `currentId` | `number \| null` | アクティブなセッション ID |

| Emit | 説明 |
|------|------|
| `select(id)` | セッションタブクリック |
| `new` | 「新しい会話 +」クリック |

- タイトルは12文字以内に切り詰めて `…` を付ける
- 日付は `MM/DD` 形式で表示する
- 現在のセッションはアクティブスタイルで表示する

---

## バックエンド `analysis.py` の設計

### `POST /api/analysis/chat` の処理フロー

1. `keyring.get_password("scry", "llm_api_key")` で API キーを取得。なければ HTTP 400
2. `build_stats_text(req.player, db)` で統計テキストを生成する
3. `db.get(PromptTemplate, req.prompt_template_id)` でテンプレートを取得し、`{player_name}` / `{stats_text}` を置換してシステムプロンプトを生成する（ID 省略時はデフォルトを使用）
4. `StreamingResponse` で SSE ジェネレーターを返す

**SSE ジェネレーターの処理**

- `settings.llm_provider` に応じて Claude または OpenAI のストリーミング API を呼ぶ
- 各 delta を `data: {"delta": "..."}` 形式で yield する
- ストリーミング完了後にセッション保存（`_save_messages`）を行い、`data: {"done": true, "session_id": N}` を yield する
- 例外発生時は `data: {"error": "..."}` を yield する

**LLM 呼び出し**

| プロバイダー | モデル | API |
|------------|--------|-----|
| Claude | `claude-opus-4-6` | `anthropic` SDK のストリーミング |
| OpenAI | `gpt-4o` | `openai` SDK のストリーミング |

**セッション保存（`_save_messages`）**

- `req.session_id` がある場合は既存セッションにメッセージを追記する
- ない場合は新規 `AnalysisSession` を作成する（`title` = `req.message[:50]`）
- ユーザーメッセージと アシスタントメッセージを `display_order` を連番で保存する
- `session.updated_at` を現在時刻で更新して commit する

### `build_stats_text(player, db)` の設計

`GET /api/stats` と同等の集計を行い、`07_analysis-design.md` のフォーマットに従ってテキスト化して返す。
`stats.py` の集計関数を内部で再利用する。

---

## エラーハンドリング

| ケース | 対応 |
|--------|------|
| API キー未設定 | HTTP 400 を返す（SSE 開始前） |
| LLM API タイムアウト / 接続エラー | `{"error": "..."}` SSE イベントを送信 |
| テンプレートが見つからない | デフォルトテンプレートにフォールバック |
| セッション保存失敗 | ログ記録のみ、SSE レスポンスには影響させない |

---

## 動作確認手順

1. API キー未設定の状態で `/analysis` にアクセスし、未設定メッセージと設定画面へのリンクが表示されることを確認する
2. API キー設定後、挨拶メッセージが自動表示されることを確認する
3. 質問ボタンをクリックしてメッセージが送信され、SSE でストリーミング表示されることを確認する
4. Enter 送信・Shift+Enter 改行が動作することを確認する
5. セッション履歴バーに会話が追加されることを確認する
6. 履歴タブクリックで過去の会話が読み取り専用で表示されることを確認する
7. 「この会話を削除」で履歴から除去され、新規セッションが開始されることを確認する
8. 「会話をリセット」で新規セッションが開始され、削除した会話は履歴に残ることを確認する
9. プレイヤー変更時に履歴・会話がリセットされることを確認する
10. backend を停止した状態でメッセージ送信し、エラートーストが表示されることを確認する
