# 初回セットアップウィザード 実装設計

## アーキテクチャ概要

```
App.vue (onMounted)
  └─ GET /api/settings → onboarding_completed を確認
       ├─ false → <OnboardingWizard> をオーバーレイ表示
       └─ true  → 通常表示
```

ウィザードは `App.vue` 上でオーバーレイとして表示する。
Router は変更せず、既存ページの上に重ねる形とする。

---

## バックエンド変更

### `backend/app/routers/settings.py`

#### SettingsResponse に追加
```python
onboarding_completed: bool
```

#### SettingsInput に追加
```python
onboarding_completed: bool | None = None
```

#### GET /api/settings ハンドラ
```python
onboarding_completed=_get_bool(db, "onboarding_completed", False),
```

#### PUT /api/settings ハンドラ
```python
if body.onboarding_completed is not None:
    _set(db, "onboarding_completed", "1" if body.onboarding_completed else "0")
```

---

## フロントエンド変更

### `frontend/src/api/settings.ts`

`SettingsResponse` に追加：
```typescript
onboarding_completed: boolean
```

`updateSettings` の body 型に追加：
```typescript
onboarding_completed?: boolean
```

---

### `frontend/src/App.vue`

`onMounted` を追加して起動時チェック：

```typescript
import { ref, onMounted } from 'vue'
import { fetchSettings } from './api/settings'
import OnboardingWizard from './components/OnboardingWizard.vue'

const showOnboarding = ref(false)

onMounted(async () => {
  try {
    const settings = await fetchSettings()
    if (!settings.onboarding_completed) {
      showOnboarding.value = true
    }
  } catch { /* ignore */ }
})
```

テンプレート：
```html
<OnboardingWizard
  v-if="showOnboarding"
  @complete="showOnboarding = false"
/>
```

---

### `frontend/src/components/OnboardingWizard.vue`（新規）

#### ステップ定義

```typescript
type Step = 'welcome' | 'games' | 'import' | 'ai' | 'done'
```

#### 内部状態

```typescript
const currentStep = ref<Step>('welcome')

// Step 1
const selectedGames = ref<Set<'mtgo' | 'mtga'>>(new Set())

// Step 2 - MTGO
const mtgoFolder = ref<string | null>(null)
const mtgoAutoImport = ref(false)

// Step 2 - MTGA
const surveilFolder = ref<string | null>(null)
const mtgaFolder = ref<string | null>(null)
const mtgaAutoImport = ref(false)

// Step 3
const apiKey = ref('')
```

#### ステップ遷移ロジック

```
welcome → games → import → ai → done
                       ↘ done（ゲーム選択なしでスキップ時）
```

- `next()`: currentStep を次へ進める
- `skip()`: welcome → done、その他 → next() と同じ
- `back()`: 前ステップへ戻る

#### 完了時の保存処理

```typescript
async function complete() {
  // 各設定を保存
  await updateSettings({
    quick_import_folder: mtgoFolder.value,
    auto_import_enabled: mtgoAutoImport.value || mtgaAutoImport.value,
    api_key: apiKey.value || undefined,
    onboarding_completed: true,
  })
  if (surveilFolder.value) {
    await setSurveilFolder(surveilFolder.value)
  }
  if (mtgaFolder.value) {
    await updateSettings({ /* mtga_folder は将来対応 */ })
  }
  emit('complete')
}
```

> **注意**: MTGO と MTGA で別々に `auto_import_enabled` を管理したい場合は将来の拡張とし、ウィザードでは「どちらかが有効なら自動インポートON」とする。

#### フォルダ選択

ウィザード内のフォルダ選択には `window.electronAPI.selectFolder()` を使用する（ファイルスキャンは不要なためこちらを優先）。

```typescript
async function selectMtgoFolder() {
  const path = await window.electronAPI.selectFolder()
  if (path) mtgoFolder.value = path
}
```

#### コンポーネント構成

```
OnboardingWizard.vue
  ├─ オーバーレイ背景（全画面固定）
  ├─ ウィザードカード
  │   ├─ ステップインジケーター
  │   ├─ ステップコンテンツ（v-if で切り替え）
  │   │   ├─ StepWelcome
  │   │   ├─ StepGames
  │   │   ├─ StepImport（selectedGames に応じてセクション表示）
  │   │   ├─ StepAi
  │   │   └─ StepDone
  │   └─ フッター（戻る / 次へ / スキップボタン）
  └─
```

単一ファイルで `v-if` による切り替えで実装する（サブコンポーネントへの分割は不要）。

---

### `frontend/src/views/SettingsView.vue`

アプリケーションセクションに「セットアップウィザードを再実行」ボタンを追加。

クリック時: `updateSettings({ onboarding_completed: false })` 後にページリロードまたは `showOnboarding` を直接操作する。
→ `App.vue` の `showOnboarding` を `provide/inject` で渡す方式とする。

---

## UI設計

### レイアウト

```
┌─────────────────────────────────────────────┐
│  (オーバーレイ: rgba(0,0,0,0.6) 全画面固定)       │
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │  ● ○ ○ ○  (ステップインジケーター)       │   │
│  │                                      │   │
│  │  [ステップタイトル]                    │   │
│  │                                      │   │
│  │  [コンテンツ]                         │   │
│  │                                      │   │
│  │  [スキップ]    [戻る]  [次へ / 完了]   │   │
│  └──────────────────────────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

### ウィザードカードサイズ

- 幅: `560px`
- 最大高さ: `80vh`（内容が多い場合はスクロール）
- `z-index: 1000`（GlobalNav より前面）

### ステップインジケーター

Welcome はインジケーター非表示。Step 1〜3 + 完了の4段階を `●○○○` 形式で表示。

### ボタン配置

| 位置 | ボタン | 表示条件 |
|------|--------|---------|
| 左 | スキップ（テキストリンク） | welcome 以外 |
| 右端 | 次へ / 完了 | 常に |
| 右端から2番目 | 戻る | welcome 以外 |

---

## 実装ステップ

### Step 1: バックエンド — `onboarding_completed` 追加
- `settings.py`: `SettingsResponse` / `SettingsInput` / GET / PUT に追加

### Step 2: フロントエンド API — `settings.ts` 更新
- `SettingsResponse` に `onboarding_completed: boolean` 追加
- `updateSettings` の body 型に追加

### Step 3: `App.vue` — 起動時チェック
- `onMounted` で `fetchSettings()` → `onboarding_completed` を確認
- `showOnboarding` ref を `provide` で公開（SettingsView から操作できるようにする）
- `<OnboardingWizard v-if="showOnboarding" @complete="..." />`

### Step 4: `OnboardingWizard.vue` 作成
- Welcome → Step 1（ゲーム選択）→ Step 2（インポート設定）→ Step 3（AIキー）→ 完了
- フォルダ選択・トグル・入力欄の実装
- `complete()` で各設定を保存

### Step 5: `SettingsView.vue` — 再実行ボタン追加
- アプリケーションセクションに「セットアップウィザードを再実行」ボタン
- クリックで `onboarding_completed = false` に更新 → `inject` した `showOnboarding` を true に

---

## 考慮事項

| 項目 | 対応方針 |
|------|---------|
| MTGAフォルダ保存先 | 現状 `settings` テーブルに `mtga_folder` キーは存在しないため、ウィザードでは選択のみ行い `updateSettings` 呼び出しは既存 API を使用。将来的に正式対応 |
| 自動インポート間隔 | ウィザードでは ON/OFF のみ表示し、間隔はデフォルト（30秒）のまま。詳細設定は設定画面へ誘導 |
| ESC / 背景クリック | ウィザードは閉じない（`@click.self` を使わない）|
| ネットワークエラー | 保存失敗時はエラートースト表示。ウィザード自体は閉じない |
| DB未起動時 | バックエンド未起動の場合 `fetchSettings` が失敗 → `showOnboarding` は false のまま（ウィザード非表示）|
