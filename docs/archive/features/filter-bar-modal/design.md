# フィルターバー モーダル選択 設計ドキュメント

## 実装ステータス

**実装済み（2026-03-25）**
- 全選択項目をボタン＋モーダルに変更済み
- `FilterSelectModal.vue`・`DeckSelectModal.vue`・`DateRangeModal.vue` 新規作成済み
- `FilterBar.vue` 全面改修済み

**設計からの変更点（filter-multiselect 機能追加に伴う変更）:**
- `DeckSelectModal.vue` の props/emits を単一値から配列に変更:
  - `deckId: number | null` → `deckIds: number[]`
  - `deck: string` → `decks: string[]`
  - emits: `selectDeckId`・`selectDeck` → `update:deckIds`・`update:decks`
- `FilterSelectModal.vue` に `multiple` props と複数選択モードを追加（相手デッキ用）
- 詳細は `docs/features/filter-multiselect/design.md` を参照

## 概要

フィルターバーの各選択項目をネイティブ `<select>` からボタン＋モーダルに置き換える。
候補が多くなっても検索ボックスで絞り込めるようにし、操作感を改善する。
対戦日もボタン化し、カスタムカレンダーによる範囲選択モーダルで設定する。

---

## 変更前 / 変更後

### 変更前
```
[select: プレイヤー▼] [select: フォーマット▼] [select: 対戦相手▼]
[select: 使用デッキ▼] [select: バージョン▼]  [select: 相手デッキ▼]
[date: 開始日] [date: 終了日]
```

### 変更後
```
プレイヤー        フォーマット    対戦相手
[necepanecepa ▼]  [modern ▼]     [すべて ▼]

使用デッキ         バージョン      相手デッキ
[Amulet Titan ▼]  [すべて ▼]     [Burn ▼]

対戦期間                          [リセット]
[2025-01-01 〜 未設定 ▼]
```

すべての項目がボタン化され、クリックでモーダルが開く。

---

## リスト選択モーダルの仕様

プレイヤー・フォーマット・対戦相手・使用デッキ・バージョン・相手デッキで使用。

### 外観
```
┌─────────────────────────────────────┐
│ 対戦相手を選択                    ✕ │
│ ┌─────────────────────────────────┐ │
│ │ 🔍 絞り込み...                  │ │
│ └─────────────────────────────────┘ │
│  ─────────────────────────────────  │
│  ✓ すべて                           │  ← 未選択時はここにチェック
│    necepanecepa                     │
│    PlayerB                          │
│    PlayerC                          │
│                                     │
└─────────────────────────────────────┘
```

### 動作
- 検索ボックスへの入力でリストをリアルタイム絞り込み（部分一致）
- 候補をクリックで即時選択・モーダルを閉じる
- 「すべて」を選択すると選択解除（空文字 / null）
- オーバーレイ背景クリックで閉じる（選択変更なし）
- ESC キーで閉じる（選択変更なし）
- 選択中の項目にチェックマーク表示

---

## 日付範囲モーダルの仕様

「対戦期間」ボタンをクリックすると開く。外部ライブラリは使用せず、カスタム実装。

### 外観
```
┌──────────────────────────────────────────────────┐
│ 対戦期間を設定                                 ✕ │
│                                                  │
│  ◀     2025年1月              2025年2月    ▶     │
│  月 火 水 木 金 土 日    月 火 水 木 金 土 日     │
│           1  2  3  4                    1        │
│   5  6  7  8  9 10 11    2  3  4  5  6  7  8     │
│  12 13 14 15 16 17 18    9 10 11 12 13 14 15     │
│  19 20 21 22 23 24 25   16 17 18 19 20 21 22     │
│  26 27 28 29 30 31      23 24 25 26 27 28        │
│                                                  │
│  開始: 2025-01-13      終了: 2025-02-05          │
│  [クリア]                              [確定]    │
└──────────────────────────────────────────────────┘
```

### 動作
- カレンダーを2ヶ月分横並びで表示
- ◀ / ▶ で表示月を前後に移動
- 1回目のクリックで開始日を設定、2回目のクリックで終了日を設定
  - 開始日より前の日付を2回目にクリックした場合は開始日として再設定
- 選択中の範囲をハイライト表示
- 「クリア」で開始日・終了日をどちらもリセット
- 「確定」または ✕ / オーバーレイクリック / ESC で閉じる
- 開始日のみ設定・終了日は未設定の状態も有効（上限なし）

### ボタンの表示ラベル
| 状態 | ラベル |
|------|--------|
| 両方未設定 | 「すべての期間 ▼」 |
| 開始日のみ | 「2025-01-13 〜 ▼」 |
| 両方設定 | 「2025-01-13 〜 2025-02-05 ▼」 |

---

## コンポーネント構成

### `FilterSelectModal.vue`（新規）

リスト選択用の汎用モーダル。

```ts
interface Item {
  value: string | number | null
  label: string
}

Props:
  title: string
  items: Item[]           // "すべて" は自動で先頭に追加
  modelValue: string | number | null

Emits:
  update:modelValue
  close
```

### `DeckSelectModal.vue`（新規）

デッキリスト＋アーキタイプ統合モーダル。

```
┌─────────────────────────────────────┐
│ デッキを選択                      ✕ │
│ ┌─────────────────────────────────┐ │
│ │ 🔍 絞り込み...                  │ │
│ └─────────────────────────────────┘ │
│  ✓ すべて                           │
│  ── デッキリスト ──────────────────  │
│    Amulet Titan                     │
│    Burn                             │
│  ── アーキタイプ ──────────────────  │
│    UW Control                       │
│    Jund                             │
└─────────────────────────────────────┘
```

```ts
Props:
  deckList: Deck[]         // デッキリスト（id + name）
  deckNameList: string[]   // アーキタイプ名リスト
  deckId: number | null    // 現在選択中のデッキID
  deck: string             // 現在選択中のアーキタイプ名

Emits:
  selectDeckId(id: number | null)
  selectDeck(name: string)
  close
```

- デッキリストから選択 → `deckId` セット、`deck` クリア
- アーキタイプから選択 → `deck` セット、`deckId` クリア
- 「すべて」を選択 → `deckId`・`deck` をどちらもクリア
- 検索は両セクションを横断して絞り込む

### `DateRangeModal.vue`（新規）

カスタムカレンダーによる日付範囲選択モーダル。外部ライブラリ不使用。

```ts
Props:
  dateFrom: string    // YYYY-MM-DD or ''
  dateTo: string      // YYYY-MM-DD or ''

Emits:
  update:dateFrom
  update:dateTo
  close
```

### `FilterBar.vue`（既存を全面改修）

各フィルター項目をボタンに変更。どの項目のモーダルを開いているかを `activeFilter` で管理。

```ts
type ActiveFilter =
  | 'player' | 'format' | 'opponent'
  | 'deck' | 'version' | 'opponentDeck'
  | 'date'
  | null

const activeFilter = ref<ActiveFilter>(null)
```

---

## 各フィルター項目の仕様

| 項目 | モーダル | タイトル | 候補リスト |
|------|---------|----------|------------|
| プレイヤー | `FilterSelectModal` | プレイヤーを選択 | `playerList` |
| フォーマット | `FilterSelectModal` | フォーマットを選択 | `formatList` |
| 対戦相手 | `FilterSelectModal` | 対戦相手を選択 | `opponentList` |
| 使用デッキ | `DeckSelectModal` | デッキを選択 | `deckList` + `deckNameList` |
| バージョン | `FilterSelectModal` | バージョンを選択 | `versionList`（デッキ未選択時は disabled） |
| 相手デッキ | `FilterSelectModal` | 相手デッキを選択 | `opponentDeckList` |
| 対戦期間 | `DateRangeModal` | 対戦期間を設定 | カスタムカレンダー |

---

## フィルターボタンの外観

```
┌──────────────────────┐
│ プレイヤー            │  ← ラベル（10px、薄い色）
│ necepanecepa      ▼  │  ← 選択中の値 or「すべて」
└──────────────────────┘
```

- 選択済み: ボーダーを青くハイライト
- 未選択（すべて）: 通常のボーダー
- disabled: 薄く表示（バージョン選択・デッキ未選択時）

---

## 修正・追加が必要なファイル

| ファイル | 変更内容 |
|---------|---------|
| `frontend/src/components/FilterSelectModal.vue` | 新規作成（汎用リスト選択モーダル） |
| `frontend/src/components/DeckSelectModal.vue` | 新規作成（デッキリスト＋アーキタイプ統合モーダル） |
| `frontend/src/components/DateRangeModal.vue` | 新規作成（カスタムカレンダー日付範囲モーダル） |
| `frontend/src/components/FilterBar.vue` | 全面改修（select → ボタン＋モーダル、date input → ボタン＋モーダル、チェックボックス廃止） |
| `frontend/src/composables/useFilterState.ts` | `useDeckManager` ref を内部化（外部公開を廃止） |

---

## 変更しない仕様

- `useFilterState.ts` のフィルター状態・API 呼び出しロジックは変更しない
- リセットボタンは現状通り（`resetFilters()`）
- FilterBar を使用している画面（StatsView / MatchListView）は変更不要
