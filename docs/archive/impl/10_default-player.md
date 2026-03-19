# 詳細設計: デフォルトプレイヤー設定

## 概要

設定画面でデフォルトプレイヤーを保存し、各画面（統計・AI分析・エクスポート）の初期表示時にそのプレイヤーを自動選択する。

---

## 対象ファイル

| ファイル | 種別 | 内容 |
|----------|------|------|
| `backend/app/routers/settings.py` | 編集 | `default_player` の取得・保存を追加 |
| `frontend/src/api/settings.ts` | 編集 | 型定義・関数に `default_player` を追加 |
| `frontend/src/views/SettingsView.vue` | 編集 | デフォルトプレイヤー選択UIセクションを追加 |
| `frontend/src/views/StatsView.vue` | 編集 | `initLists()` の自動選択ロジックを変更 |
| `frontend/src/views/AnalysisView.vue` | 編集 | `initData()` の自動選択ロジックを変更 |
| `frontend/src/views/AIExportView.vue` | 編集 | `onMounted` の自動選択ロジックを変更 |

---

## DBスキーマ変更なし

`settings` テーブルはキーバリュー形式（`key` / `value`）のため、`key = "default_player"` の行を追加するだけで対応できる。マイグレーション不要。

---

## バックエンド変更

### `GET /api/settings` レスポンスに追加

```json
{
  "llm_provider": "claude",
  "api_key_configured": true,
  "quick_import_folder": "/path/to/logs",
  "default_player": "PlayerA"
}
```

- 未設定の場合は `null` を返す

### `PUT /api/settings` リクエストに追加

```json
{
  "default_player": "PlayerA"
}
```

- `null` または空文字で設定を削除する

### `SettingsInput` モデル変更

```python
class SettingsInput(BaseModel):
    llm_provider: str | None = None
    api_key: str | None = None
    quick_import_folder: str | None = None
    default_player: str | None = None  # 追加
```

---

## フロントエンド変更

### `api/settings.ts`

```typescript
export interface SettingsResponse {
  llm_provider: string
  api_key_configured: boolean
  quick_import_folder: string | null
  default_player: string | null  // 追加
}

export async function updateSettings(body: {
  llm_provider?: string
  api_key?: string
  quick_import_folder?: string | null
  default_player?: string | null  // 追加
}): Promise<void>
```

---

### `SettingsView.vue` UIセクション追加

APIキーセクションの下に「デフォルトプレイヤー」セクションを追加する。

```
[デフォルトプレイヤー]
[select: プレイヤー一覧 + "未設定"] [保存]
※ 各画面（統計・AI分析・エクスポート）の初期表示で自動選択されます
```

**状態変数**

| 変数 | 型 | 説明 |
|------|----|------|
| `defaultPlayer` | `string` | 現在保存済みのデフォルトプレイヤー（空文字 = 未設定） |
| `defaultPlayerInput` | `string` | セレクトの選択値 |
| `playerList` | `string[]` | プレイヤー一覧（`fetchPlayers()` で取得） |

**処理フロー**

1. `onMounted` で `fetchSettings()` と `fetchPlayers()` を並列取得
2. `defaultPlayer` に取得値をセットし、セレクトの初期値とする
3. 「保存」ボタン押下で `updateSettings({ default_player: defaultPlayerInput || null })` を送信
4. 成功後トーストで「保存しました」を表示

---

### 各画面の自動選択ロジック変更

共通の方針：`fetchSettings()` と `fetchPlayers()` を並列取得し、デフォルトプレイヤーがプレイヤー一覧に存在すればそちらを優先選択する。

#### `StatsView.vue` — `initLists()`

```typescript
const [players, formats, settings] = await Promise.all([
  fetchPlayers(), fetchFormats(), fetchSettings(),
])
playerList.value = players
formatList.value = formats
const preferred = settings.default_player
if (!selectedPlayer.value && players.length > 0) {
  selectedPlayer.value =
    (preferred && players.includes(preferred)) ? preferred : players[0]
}
```

#### `AnalysisView.vue` — `initData()`

```typescript
const [playerList, templates, qSets, settings] = await Promise.all([
  fetchPlayers(), fetchPromptTemplates(), fetchQuestionSets(), fetchSettings(),
])
// ...
const preferred = settings.default_player
if (!_initialized.value && playerList.length > 0) {
  selectedPlayer.value =
    (preferred && playerList.includes(preferred)) ? preferred : playerList[0]
}
```

#### `AIExportView.vue` — `onMounted`

```typescript
const [players, formats, settings] = await Promise.all([
  fetchPlayers(), fetchFormats(), fetchSettings(),
])
playerList.value = players
formatList.value = formats
const preferred = settings.default_player
if (players.length > 0) {
  expPlayer.value =
    (preferred && players.includes(preferred)) ? preferred : players[0]
}
```

---

## エラーハンドリング

| ケース | 対応 |
|--------|------|
| `fetchSettings()` 失敗 | 既存のエラーハンドリングに含める。デフォルトプレイヤーは `null` 扱いで先頭を選択 |
| 保存済みプレイヤーがリストに存在しない（ログ削除等） | リストの先頭を選択（フォールバック） |
| プレイヤー一覧が空 | 現状通り何も選択しない |

---

## 動作確認手順

1. 設定画面でデフォルトプレイヤーを選択・保存できることを確認する
2. 統計画面を開き、保存したプレイヤーが初期選択されることを確認する
3. AI分析画面・エクスポート画面でも同様に確認する
4. デフォルトプレイヤーを「未設定」に戻して保存後、各画面が先頭プレイヤーを選択することを確認する
5. 保存済みプレイヤーがリストに存在しない場合、先頭プレイヤーが選択されることを確認する
