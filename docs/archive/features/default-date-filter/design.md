# デフォルト期間フィルター 設計ドキュメント

## 実装ステータス

**実装済み（2026-03-25）**
- バックエンド・フロントエンドともに設計通りに実装済み
- `SettingsView.vue` に「デフォルト期間」セクション追加済み
- `useFilterState.ts` の `init()` で設定値を読み込み `dateFrom` に反映

## 概要

統計・対戦履歴画面を開いたとき、毎回手動で日付を入力しなくても済むよう、
デフォルトの絞り込み期間を設定に登録できる機能を追加する。

---

## 背景・動機

現状、統計・対戦履歴は全期間のデータが表示される。
ユーザーが実際に見たいのは「今シーズン」「今月」など直近の期間であることが多く、
毎回起動のたびに日付を手動入力する手間が生じている。

---

## 設定値

### 新規設定キー

| キー | 型 | デフォルト | 説明 |
|------|----|-----------|------|
| `default_date_filter` | string | `"none"` | デフォルト期間フィルターの種別 |
| `default_date_filter_from` | string | `null` | カスタム開始日（`custom` 選択時のみ使用・YYYY-MM-DD形式） |

### 選択肢

| 値 | 表示名 | `date_from` の計算方法 |
|----|--------|----------------------|
| `none` | 全期間 | なし（絞り込みなし） |
| `this_month` | 今月 | 当月1日（毎回自動計算） |
| `last_30_days` | 直近30日 | 今日から30日前（毎回自動計算） |
| `custom` | カスタム開始日 | 設定に保存した固定日付 |

---

## 動作仕様

- 統計画面・対戦履歴画面の初期表示時に、設定値をもとに `date_from` を計算してフィルターに適用する
- `this_month` / `last_30_days` はアプリ起動のたびに動的に計算するため手動更新不要
- `custom` はセット発売日・シーズン開始日などを一度設定すれば以後自動適用される
- ユーザーが画面上でフィルターを変更した場合は、その変更が優先される（設定値は初期値として使用するのみ）

---

## 修正が必要なファイル

### バックエンド

#### `backend/app/routers/settings.py`
- `SettingsInput` に `default_date_filter: str | None` と `default_date_filter_from: str | None` を追加
- `GET /api/settings` レスポンスに両フィールドを追加（デフォルト: `"none"` / `null`）
- `PUT /api/settings` に両フィールドの保存処理を追加

### フロントエンド

#### `frontend/src/api/settings.ts`
- `SettingsResponse` に `default_date_filter: string` と `default_date_filter_from: string | null` を追加
- `updateSettings()` の引数型に両フィールドを追加

#### `frontend/src/composables/useFilterState.ts`
- 設定値をもとに `date_from` の初期値を計算するヘルパー関数 `calcDefaultDateFrom()` を追加

```ts
function calcDefaultDateFrom(filter: string, customFrom: string | null): string {
  const today = new Date()
  if (filter === 'this_month') {
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-01`
  }
  if (filter === 'last_30_days') {
    const d = new Date(today)
    d.setDate(d.getDate() - 30)
    return d.toISOString().slice(0, 10)
  }
  if (filter === 'custom' && customFrom) {
    return customFrom
  }
  return ''
}
```

- `init()` 関数で設定を取得し `dateFrom` の初期値に適用する

#### `frontend/src/views/SettingsView.vue`
- 「デフォルト期間」セクションを追加
- プルダウンで種別選択（全期間 / 今月 / 直近30日 / カスタム開始日）
- `custom` 選択時のみ日付入力欄を表示

---

## UI イメージ（SettingsView）

```
┌─────────────────────────────────────────────────────┐
│ デフォルト期間                                        │
│                                                      │
│  統計・対戦履歴の初期絞り込み期間:                    │
│  [全期間          ▼]                                 │
│                                                      │
│  ※「カスタム開始日」選択時:                           │
│  開始日: [2025-01-01      ]  [保存]                  │
│                                                      │
│  画面を開いたときに自動的にこの期間で絞り込みます。    │
└─────────────────────────────────────────────────────┘
```

---

## 適用対象画面

| 画面 | 適用するフィルター |
|------|-----------------|
| 統計画面（StatsView） | `dateFrom` |
| 対戦履歴画面（MatchListView） | `dateFrom` |

---

## 変更しない仕様

- ユーザーが画面上でフィルターを変更した場合は設定値を上書きしない
- `date_to`（終了日）はデフォルト設定の対象外とする
- 画面ごとにデフォルト値を変えることはしない（全画面共通の1設定）
