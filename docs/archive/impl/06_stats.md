# 詳細設計: 統計画面 (S05)

## 対象ファイル

| ファイル | 種別 | 内容 |
|----------|------|------|
| `frontend/src/api/stats.ts` | 新規 | 統計 API 呼び出し関数・型定義 |
| `frontend/src/views/StatsView.vue` | 新規 | S05 統計ダッシュボード |
| `frontend/src/components/charts/WinRateHistoryChart.vue` | 新規 | 勝率推移折れ線グラフ |
| `frontend/src/components/charts/FirstSecondChart.vue` | 新規 | 先手/後手勝率棒グラフ |
| `frontend/src/components/charts/DeckStatsChart.vue` | 新規 | デッキ別勝率棒グラフ |
| `frontend/src/router/index.ts` | 編集 | `/stats` ルートを追加 |
| `backend/app/routers/stats.py` | 新規 | GET /api/stats・/stats/cards・/stats/opponents・/stats/players |
| `backend/app/main.py` | 編集 | stats router を登録 |

---

## `api/stats.ts` の型定義

```typescript
interface WinRatePoint {
  date: string
  match_index: number
  won: boolean
}

interface DeckStat {
  deck_name: string
  game_plan: string | null
  matches: number
  win_rate: number
}

interface StatsResponse {
  total_matches: number
  win_rate: number
  avg_turns: number
  mulligan_rate: number
  first_play_win_rate: number
  second_play_win_rate: number
  win_rate_history: WinRatePoint[]
  deck_stats: DeckStat[]
  opponent_stats: OpponentStat[]
}

interface CardStat {
  card_name: string
  play_count: number
  game_count: number
  win_rate: number
}
```

**API 関数**

| 関数 | エンドポイント | 説明 |
|------|--------------|------|
| `fetchStats(filters)` | `GET /api/stats` | フィルタ付き統計取得 |
| `fetchCardStats(player, limit?)` | `GET /api/stats/cards` | カード別統計取得（デフォルト limit=20） |
| `fetchOpponents(player)` | `GET /api/stats/opponents` | 対戦相手一覧取得 |
| `fetchPlayers()` | `GET /api/stats/players` | プレイヤー一覧取得 |

---

## StatsView.vue

### 状態

| 変数 | 型 | 説明 |
|------|----|------|
| `selectedPlayer` | `string` | 選択中プレイヤー |
| `selectedOpponent` | `string` | フィルター: 対戦相手 |
| `selectedDeck` | `string` | フィルター: デッキ名 |
| `playerList` | `string[]` | プレイヤードロップダウン選択肢 |
| `opponentList` | `string[]` | 対戦相手ドロップダウン選択肢 |
| `stats` | `StatsResponse \| null` | 統計データ |
| `cardStats` | `CardStat[]` | カード統計データ |
| `deckList` | computed | `stats.deck_stats` から生成 |

### 初期化フロー

1. `onMounted` で `fetchPlayers()` を呼ぶ
2. プレイヤーが1件以上あれば先頭を `selectedPlayer` に設定し `loadAll()` を呼ぶ
3. プレイヤーが0件なら「対戦ログがありません」を表示する

### フィルター連動

- `selectedPlayer` 変更 → 他フィルターをリセット → `loadAll()`（stats + cardStats 両方を再取得）・`fetchOpponents()` も再取得
- `selectedOpponent` / `selectedDeck` 変更 → `loadStats()` のみ再取得（cardStats は変更しない）

### データ取得

- `loadStats()`: フィルターを params に乗せて `fetchStats` を呼ぶ。`history_size: 20` 固定
- `loadCardStats()`: `fetchCardStats(selectedPlayer)` を呼ぶ
- どちらもエラー時は `showError` でトーストを表示する

---

## グラフコンポーネント

ECharts + vue-echarts を使用する。`package.json` への追加が必要：
- `"echarts": "^5.x"`
- `"vue-echarts": "^7.x"`

`main.ts` で `CanvasRenderer`・`LineChart`・`BarChart`・必要な Components をグローバル登録する。

**共通テーマカラー**

| 用途 | カラー |
|------|--------|
| 先手・棒グラフ標準 | `#4a6fa5` |
| 後手 | `#c8622a` |
| 勝利 | `#5a7a4a` |
| 敗北 | `#a03030` |
| 軸テキスト | `#7a6a55` |
| グリッド線 | `#e0d8c8` |

### WinRateHistoryChart.vue

- **データ**: `WinRatePoint[]`（`won` の真偽値列）
- **グラフ**: 折れ線グラフ。X 軸はマッチインデックス、Y 軸は 0〜1 の累積勝率
- **ラベル**: Y 軸を `%` 表示にフォーマットする
- **tooltip**: マッチ番号・日付・勝敗を表示する

> 累積勝率（直近 i 件での wins/total）で描画する。ローリング平均は将来の改善候補とする。

### FirstSecondChart.vue

- **データ**: `firstRate: number`・`secondRate: number`（0〜1）
- **グラフ**: 棒グラフ2本（先手・後手）。各バーの色を上記テーマカラーで区別する
- **ラベル**: バー上部に `%` 表示する

### DeckStatsChart.vue

- **データ**: `DeckStat[]`
- **グラフ**: 棒グラフ。X 軸がデッキ名、Y 軸が勝率
- **tooltip**: 試合数と勝率を表示する
- X 軸ラベルが長い場合は `rotate: 15` で傾けて表示する

---

## バックエンド `stats.py` の集計設計

各エンドポイントで以下の集計クエリを実装する。

### `GET /api/stats`

- **対象マッチ**: `match_players.player_name = :player` に合致するマッチに絞り込む
- **フィルター付与**: `opponent` / `deck` / `game_plan` パラメータがある場合、追加 JOIN / WHERE で動的に絞り込む
- **勝率**: `match_winner = :player` の件数 / 総マッチ数
- **先手/後手勝率**: `games.first_player = :player` か否かでゲームをグルーピングし、それぞれの `winner = :player` 率を計算する
- **マリガン率**: `mulligans.count > 0 AND mulligans.player_name = :player` となるゲーム数 / 総ゲーム数
- **デッキ別勝率**: `match_players.deck_name IS NOT NULL` のマッチを `deck_name` でグルーピングして集計する
- **勝率推移**: 直近 `history_size` 件のマッチを `played_at` 昇順で取得し、日付・勝敗フラグを返す

### `GET /api/stats/cards`

- `actions.action_type IN ('play', 'cast')` かつ `actions.player_name = :player` のアクションを `card_name` でグルーピングする
- `play_count`: アクション総数
- `game_count`: `DISTINCT game_id` の件数
- `win_rate`: そのカードが登場したゲームの `winner = :player` 率

### `GET /api/stats/players`

- `match_players.player_name` の DISTINCT 一覧をアルファベット順で返す

---

## 動作確認手順

1. `/stats` にアクセスしてプレイヤードロップダウンが表示されることを確認する
2. プレイヤー選択後にサマリー数値・グラフが表示されることを確認する
3. 対戦相手フィルターを変更したとき stats のみ再取得され、カード統計が変わらないことを確認する
4. デッキが設定されているデータがある場合、対応するグラフが表示されることを確認する
5. カード統計テーブルに play/cast アクションのカードが使用数順で表示されることを確認する
6. データが0件の場合、グラフが空のまま正常に表示されることを確認する（エラーにならないこと）
