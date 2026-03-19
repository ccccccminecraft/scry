# 18: デッキ管理カードビュー

## 概要

デッキ管理画面の右ペイン（カードリスト）に、現行のリスト表示に加えて MTGO の CardView に倣ったグリッド表示モードを追加する。カード画像を並べて表示し、左下に枚数をオーバーレイする。

---

## 対象ファイル

### 新規作成

なし

### 編集

| ファイル | 変更内容 |
|----------|---------|
| `frontend/src/views/DeckBuilderView.vue` | 表示切替ボタン追加、カードビュー用テンプレート・スタイル追加 |

---

## UI 仕様

### 表示切替ボタン

右ペインのヘッダー右端に「リスト / カード」のトグルボタンを追加する。

```
[ v2 MH3後調整 ]  [一括適用] [削除]  [リスト] [カード]
```

- デフォルトはリスト表示
- 切替状態はコンポーネント内の `ref` で管理（永続化なし）

### カードビューレイアウト

```
メインデッキ (60)
┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐
│    │ │    │ │    │ │    │ │    │
│    │ │    │ │    │ │    │ │    │
│[4] │ │[4] │ │[3] │ │[2] │ │[1] │
└────┘ └────┘ └────┘ └────┘ └────┘

サイドボード (15)
┌────┐ ┌────┐ ...
│    │ │    │
│[3] │ │[2] │
└────┘ └────┘
```

- CSS Grid で `repeat(auto-fill, minmax(80px, 1fr))` によるレスポンシブ列数
- カードのアスペクト比は MTG カード標準（63:88 ≒ 5:7）
- 枚数バッジ: `position: absolute; bottom: 4px; left: 4px`、半透明黒背景・白テキスト・太字
- `scryfall_id` なしのカードはグレーのプレースホルダー＋カード名テキスト表示

---

## インターフェース定義

### 追加する state

```ts
const viewMode = ref<'list' | 'card'>('list')
```

### テンプレート構造（カードビュー部分）

```html
<div class="card-grid">
  <!-- メインデッキ -->
  <div class="card-section__title">メインデッキ (N)</div>
  <div class="card-grid__section">
    <div v-for="entry in selectedVersion.main" class="card-thumb">
      <img v-if="entry.scryfall_id" :src="cardImageUrl(entry.scryfall_id)" />
      <div v-else class="card-thumb__placeholder">
        <span class="card-thumb__name">{{ entry.card_name }}</span>
      </div>
      <span class="card-thumb__qty">{{ entry.quantity }}</span>
    </div>
  </div>

  <!-- サイドボード -->
  <div class="card-section__title card-section__title--sb">サイドボード (N)</div>
  <div class="card-grid__section">
    ...
  </div>
</div>
```

---

## スタイル定義

```css
.card-grid {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}

.card-grid__section {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
  gap: 6px;
  padding: 6px 0 12px;
}

.card-thumb {
  position: relative;
  aspect-ratio: 5 / 7;
  border-radius: 4px;
  overflow: hidden;
  background: #e0d8c8;
}

.card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.card-thumb__placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
}

.card-thumb__name {
  font-size: 9px;
  color: #7a6a55;
  text-align: center;
  word-break: break-word;
  line-height: 1.3;
}

.card-thumb__qty {
  position: absolute;
  bottom: 4px;
  left: 4px;
  background: rgba(0, 0, 0, 0.65);
  color: #fff;
  font-size: 12px;
  font-weight: bold;
  padding: 1px 5px;
  border-radius: 3px;
  line-height: 1.4;
}
```

---

## エラーハンドリング

| 状況 | 対応 |
|------|------|
| `scryfall_id` が未解決 | プレースホルダー（グレー背景）＋カード名テキストを表示 |
| 画像読み込み失敗 | `@error` でプレースホルダーにフォールバック（任意） |

---

## 動作確認手順

1. デッキ管理画面でバージョンを選択し、右ペインにカードリストが表示されることを確認する
2. ヘッダーの「カード」ボタンを押してカードビューに切り替わることを確認する
3. カード画像がグリッド状に並び、左下に枚数バッジが表示されることを確認する
4. `scryfall_id` が未解決のカードがプレースホルダーで表示されることを確認する
5. 「リスト」ボタンで元のリスト表示に戻ることを確認する
6. サイドボードが別セクションとして正しく表示されることを確認する
