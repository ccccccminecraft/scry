# 詳細設計: プリセット管理画面 (S08)

## 対象ファイル

| ファイル | 種別 | 内容 |
|----------|------|------|
| `frontend/src/api/presets.ts` | 新規 | プロンプトテンプレート・質問セット CRUD API 関数 |
| `frontend/src/views/PresetsView.vue` | 新規 | S08 プリセット管理一覧 |
| `frontend/src/views/PromptTemplateEditView.vue` | 新規 | テンプレート作成・編集 |
| `frontend/src/views/QuestionSetEditView.vue` | 新規 | 質問セット作成・編集 |
| `frontend/src/router/index.ts` | 編集 | `/presets` 関連ルートを追加 |
| `backend/app/routers/presets.py` | 新規 | テンプレート・質問セット CRUD エンドポイント |
| `backend/app/main.py` | 編集 | presets router を登録 |

---

## `api/presets.ts` の型定義

`PromptTemplate`・`QuestionSet`・`QuestionItem` は `analysis.ts` から再エクスポートして使用する。

```typescript
interface PromptTemplateInput {
  name: string
  content: string
  is_default: boolean
}

interface QuestionItemInput {
  text: string
  display_order: number
}

interface QuestionSetInput {
  name: string
  is_default: boolean
  items: QuestionItemInput[]
}
```

**API 関数**

| 関数 | エンドポイント | 説明 |
|------|--------------|------|
| `createPromptTemplate(body)` | `POST /api/prompt-templates` | テンプレート作成 |
| `updatePromptTemplate(id, body)` | `PUT /api/prompt-templates/{id}` | テンプレート更新 |
| `deletePromptTemplate(id)` | `DELETE /api/prompt-templates/{id}` | テンプレート削除 |
| `createQuestionSet(body)` | `POST /api/question-sets` | 質問セット作成 |
| `updateQuestionSet(id, body)` | `PUT /api/question-sets/{id}` | 質問セット更新 |
| `deleteQuestionSet(id)` | `DELETE /api/question-sets/{id}` | 質問セット削除 |

---

## ルーター設定

| パス | コンポーネント | 説明 |
|------|--------------|------|
| `/presets` | PresetsView | 一覧画面 |
| `/presets/templates/new` | PromptTemplateEditView | テンプレート新規作成 |
| `/presets/templates/:id/edit` | PromptTemplateEditView | テンプレート編集 |
| `/presets/question-sets/new` | QuestionSetEditView | 質問セット新規作成 |
| `/presets/question-sets/:id/edit` | QuestionSetEditView | 質問セット編集 |

`?setDefault=true` クエリパラメータで「デフォルトに設定」ボタンからの遷移を表現する。

---

## PresetsView.vue

### 状態

| 変数 | 型 | 説明 |
|------|----|------|
| `templates` | `PromptTemplate[]` | テンプレート一覧 |
| `questionSets` | `QuestionSet[]` | 質問セット一覧 |
| `loading` | `boolean` | ローディング中フラグ |

### 処理フロー

- `onMounted` で `fetchPromptTemplates()` と `fetchQuestionSets()` を並列取得する
- 削除: 対応する delete 関数を呼び、成功後にリストからローカル削除する
- 編集・デフォルト設定: 対応する edit ルートに遷移する

### 表示仕様

**テンプレート一覧**

- デフォルトは `●`、非デフォルトは `○` で表示する
- 非デフォルトには「デフォルトに設定」ボタンを表示する
- 削除ボタンはデフォルトには `--`（非活性）、非デフォルトには「削除」で表示する

**質問セット一覧**

- テンプレート一覧と同じ表示ルール

---

## PromptTemplateEditView.vue

### ルートパラメータ判定

- `:id` がない → 新規作成モード
- `:id` がある → 編集モード（`fetchPromptTemplates()` で既存データを取得してフォームに投入）
- `?setDefault=true` → 保存時に `is_default: true` で送信する

### 状態

| 変数 | 型 | 説明 |
|------|----|------|
| `name` | `string` | テンプレート名 |
| `content` | `string` | プロンプト本文 |
| `isDefault` | `boolean` | デフォルト設定フラグ |
| `saving` | `boolean` | 保存リクエスト中フラグ |

### バリデーション

- 名前・プロンプト本文が空の場合は保存前にトーストでエラーを表示してリクエストを送らない

### 保存フロー

1. バリデーション
2. 新規: `createPromptTemplate(body)` / 編集: `updatePromptTemplate(id, body)` を呼ぶ
3. 成功後 `/presets` にリダイレクトする

### 表示仕様

- 名前入力欄（1行テキスト）
- プロンプト本文入力欄（複数行テキストエリア）
- ヒント: `{player_name}` `{stats_text}` が使えることを明示する
- 保存ボタン（リクエスト中は「保存中...」と表示して `disabled`）

---

## QuestionSetEditView.vue

### ルートパラメータ判定

`PromptTemplateEditView` と同じ方針。

### 状態

| 変数 | 型 | 説明 |
|------|----|------|
| `name` | `string` | セット名 |
| `isDefault` | `boolean` | デフォルト設定フラグ |
| `items` | `DraftItem[]` | 質問一覧（編集用） |
| `saving` | `boolean` | 保存リクエスト中フラグ |

```typescript
interface DraftItem {
  draftKey: number   // 一時的なリスト key（負数 = 新規、正数 = 既存の id）
  text: string
}
```

### 質問の操作

- **追加**: 空の `DraftItem` をリスト末尾に追加する
- **削除**: インデックスを指定して `items` から除去する
- **並び替え**: `vue-draggable-next` のドラッグ＆ドロップで `items` の順序を変更する（`package.json` への追加が必要）

### バリデーション

- セット名が空の場合はエラー
- 空の質問文がある場合はエラー

### 保存フロー

1. バリデーション
2. `items` の配列インデックスから `display_order`（1始まり）を計算する
3. 新規: `createQuestionSet(body)` / 編集: `updateQuestionSet(id, body)` を呼ぶ（items は全件洗い替え）
4. 成功後 `/presets` にリダイレクトする

---

## バックエンド `presets.py` の設計

### プロンプトテンプレート

- `PUT /api/prompt-templates/{id}` で `is_default: true` を受け取った場合、既存の全テンプレートの `is_default` を 0 にリセットしてから対象を 1 に更新する（排他制御）
- `DELETE /api/prompt-templates/{id}` はデフォルトテンプレートの場合 HTTP 400 を返す

### 質問セット

- `PUT /api/question-sets/{id}` の items 更新は全件 DELETE → INSERT の洗い替えで行う
- `DELETE /api/question-sets/{id}` はデフォルトセットの場合 HTTP 400 を返す

---

## エラーハンドリング

| ケース | 対応 | HTTP Status |
|--------|------|-------------|
| デフォルトテンプレートを削除 | HTTP 400 | 400 |
| デフォルト質問セットを削除 | HTTP 400 | 400 |
| 存在しない ID を編集 | HTTP 404 | 404 |
| 名前・内容が空で保存 | フロント側バリデーションでガード | — |
| 空の質問で保存 | フロント側バリデーションでガード | — |

---

## 依存パッケージ追加

```
vue-draggable-next: ^2.x  （質問セットの並び替え用）
```

---

## 動作確認手順

1. `/presets` にアクセスしてテンプレート・質問セットの一覧が表示されることを確認する
2. 「+ 新規作成」でテンプレート編集画面に遷移し、保存後に一覧に追加されることを確認する
3. 「編集」ボタンで既存データが読み込まれた編集画面に遷移することを確認する
4. 「デフォルトに設定」後、以前のデフォルトが `○` に変わることを確認する
5. デフォルトテンプレートの削除ボタンが `--` で非活性になっていることを確認する
6. 質問セット編集画面で追加・削除・ドラッグ並び替えが動作することを確認する
7. 保存後、S06 AI分析画面の質問ボタンに内容が反映されることを確認する
