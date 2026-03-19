# 詳細設計: 対戦履歴画面 (S03) + 共通基盤

## 対象ファイル

| ファイル | 種別 | 内容 |
|----------|------|------|
| `frontend/src/api/client.ts` | 新規 | axios インスタンス・共通エラーハンドリング |
| `frontend/src/api/matches.ts` | 新規 | 対戦履歴 API 呼び出し関数・型定義 |
| `frontend/src/components/GlobalNav.vue` | 新規 | グローバルナビゲーション（左サイドバー） |
| `frontend/src/components/AppToast.vue` | 新規 | エラートースト（共通） |
| `frontend/src/composables/useToast.ts` | 新規 | トースト表示の Composable |
| `frontend/src/views/MatchListView.vue` | 編集 | S03 対戦履歴一覧（プレースホルダーを置換） |
| `frontend/src/App.vue` | 編集 | GlobalNav・AppToast を組み込む |
| `frontend/src/router/index.ts` | 編集 | S04 ルートを追加 |

---

## レイアウト構造

```
App.vue  （1200×800 固定）
├── GlobalNav.vue  （左サイドバー、幅 160px）
└── <router-view>  （残り 1040px）
      └── MatchListView.vue
```

`App.vue` は GlobalNav と router-view を横並びにする flex レイアウトとする。
GlobalNav 以外の共通要素（AppToast）は `position: fixed` で画面右下に配置する。

---

## API クライアント基盤

### `api/client.ts`

- `axios.create` で `baseURL: http://localhost:8000`・`timeout: 10000` を設定した共通インスタンスを作成する
- レスポンスインターセプターで `response.data.detail` を取り出して `Error` に変換する。全 API 関数はこの共通エラー形式を受け取る

### `api/matches.ts` の型定義

```typescript
interface MatchSummary {
  match_id: string
  date: string           // ISO8601
  players: string[]
  match_winner: string
  game_count: number
  format: string | null
}

interface MatchListResponse {
  total: number
  limit: number
  offset: number
  matches: MatchSummary[]
}
```

**API 関数**

| 関数 | エンドポイント | 説明 |
|------|--------------|------|
| `fetchMatches(limit, offset)` | `GET /api/matches` | 一覧取得。デフォルト limit=50, offset=0 |

---

## Composable: `useToast`

- モジュールレベルの `ref<Toast[]>` を保持し、全コンポーネントで状態を共有するシングルトン設計
- `showError(message, duration?)` / `showSuccess(message, duration?)` で追加、duration 経過後に自動削除

```typescript
interface Toast {
  id: number
  message: string
  type: 'error' | 'success'
}
```

---

## コンポーネント設計

### `GlobalNav.vue`

**レイアウト**

```
┌──────────────┐
│ Scry         │
│              │
│ 対戦履歴      │ ← /matches
│ 統計          │ ← /stats
│ AI 分析       │ ← /analysis
│ インポート    │ ← /import
│ ─────────    │
│ 設定          │ ← /settings
│ プリセット管理 │ ← /presets
└──────────────┘
```

- `router-link` の active クラスで現在画面のアイテムをハイライト表示する
- サイドバー背景色は `#2c2416`（濃い茶）、通常テキストは `#c8b89a`、アクティブは `#4a6fa5` 背景 + 白テキスト

### `AppToast.vue`

- `useToast` から `toasts` を取得して右下固定位置に縦並びで表示する
- クリックで即時削除する
- error: `#a03030` 背景、success: `#5a7a4a` 背景

### `MatchListView.vue`

**状態**

| 変数 | 型 | 説明 |
|------|----|------|
| `matches` | `MatchSummary[]` | 現在ページのデータ |
| `total` | `number` | 総件数 |
| `page` | `number` | 現在ページ（1始まり） |
| `loading` | `boolean` | ローディング中フラグ |
| `totalPages` | computed | `ceil(total / 50)` |

**処理フロー**

- `onMounted` と `page` の watch で `fetchMatches(50, (page-1)*50)` を呼ぶ
- エラー時は `showError` でトーストを表示する
- 行クリックで `router.push('/matches/:match_id')` に遷移する

**表示仕様**

- カラム: 日時 / 対戦（PlayerA vs PlayerB）/ 勝者 / ゲーム数 / フォーマット
- 日時は `ja-JP` ロケールで `YYYY/MM/DD HH:mm` 形式にフォーマットする
- データ 0 件時は「対戦ログがありません」を表示する
- `totalPages > 1` のときのみページネーション（前へ・N/M・次へ）を表示する

---

## ルーター設定

| パス | コンポーネント | 備考 |
|------|--------------|------|
| `/` | HomeView | 既存 |
| `/import` | ImportView | 既存 |
| `/matches` | MatchListView | 今回実装 |
| `/matches/:match_id` | MatchDetailView | プレースホルダーを作成、実装は05で行う |

---

## 動作確認手順

1. Docker と Electron を起動する
2. `/matches` にアクセスして対戦履歴テーブルが表示されることを確認する
3. データがない場合は「対戦ログがありません」が表示されることを確認する
4. 行クリックで `/matches/:match_id` に遷移することを確認する
5. 50件超のデータがある場合はページネーションが表示されることを確認する
6. グローバルナビの各リンクで画面遷移でき、アクティブ表示が切り替わることを確認する
7. backend を停止した状態で `/matches` を開き、エラートーストが表示されることを確認する

---

## 追加機能: AI 分析用データエクスポート

### 概要

対戦データを Markdown ファイル (.md) としてエクスポートする機能。
Claude.ai・ChatGPT・Gemini 等のブラウザ AI ツールへの貼り付け・ファイルアップロードを想定。

### UI

- `MatchListView` 右上に「AI用エクスポート」ボタンを追加
- クリックでエクスポートモーダルを開く
- モーダル内でフィルター条件・詳細レベルを設定してダウンロード実行

### エクスポートモーダル

```
┌──────────────────────────────────────────┐
│ AI 用データエクスポート                    │
│                                          │
│ ── フィルター ──────────────────────────  │
│ プレイヤー  [select]                      │
│ 対戦相手   [select]  使用デッキ [select]  │
│ 相手デッキ [select]  フォーマット[select] │
│ 対戦日（開始）[date] 〜（終了）[date]     │
│                                          │
│ ── 出力内容 ──────────────────────────── │
│ ○ サマリーのみ                            │
│   （統計サマリー + デッキ別勝率）          │
│ ○ マッチ一覧あり                          │
│   （↑ + 各マッチの基本情報 + ゲーム結果）  │
│ ○ アクション詳細あり                      │
│   （↑ + 各ゲームのターン別アクション）     │
│                                          │
│ ── 件数上限 ──────────────────────────── │
│ 直近 [  200  ] 件                        │
│                                          │
│  [キャンセル]  [ダウンロード]             │
└──────────────────────────────────────────┘
```

### 件数確認メッセージ

ダウンロード実行前にフィルター条件で対象マッチ数を取得し、以下のルールで確認を出す。

| 条件 | 動作 |
|------|------|
| 対象件数 ≤ 上限件数 | 確認なしでダウンロード |
| 対象件数 > 上限件数 | 「N 件中 上限M 件をエクスポートします（直近順）。続けますか？」を表示 |
| アクション詳細あり かつ 対象件数 > 50 | 上記に加え「アクション詳細を含むため、ファイルサイズが大きくなる可能性があります」を追記 |

### 出力ファイル形式

**ファイル名**: `scry_export_[プレイヤー名]_[YYYYMMDD].md`

**構造**:

```markdown
# 対戦データ — [プレイヤー名]

エクスポート日時: YYYY-MM-DD HH:mm
フィルター: [設定された条件を列挙、なければ「なし（全データ）」]

---

## サマリー

| 項目 | 値 |
|------|-----|
| 総マッチ数 | N |
| 勝利 / 敗北 | W / L |
| 勝率 | XX.X% |
| 先手勝率 | XX.X% |
| 後手勝率 | XX.X% |
| 平均ターン数 | X.X |
| マリガン率 | XX.X% |

### デッキ別勝率

| デッキ | マッチ数 | 勝率 |
|--------|---------|------|
| Deck A | N | XX.X% |

---

## 対戦一覧
※ 詳細レベル「マッチ一覧あり」以上の場合のみ出力

### [1] YYYY-MM-DD — [フォーマット]

- **対戦相手**: [名前]
- **使用デッキ**: [デッキ名]
- **相手デッキ**: [デッキ名]
- **結果**: 勝利 / 敗北 (W-L)

| ゲーム | 結果 | 先後 | ターン数 | マリガン |
|--------|------|------|---------|---------|
| Game 1 | 勝利 | 先手 | 8 | なし |
| Game 2 | 敗北 | 後手 | 12 | 1回 |

#### Game 1 アクション詳細
※ 詳細レベル「アクション詳細あり」の場合のみ出力

| ターン | プレイヤー | 種別 | カード | 対象 |
|--------|-----------|------|--------|------|
| 1 | PlayerA | play | Island | — |
| 2 | Opponent | cast | Lightning Bolt | PlayerA |
| 3 | PlayerA | cast | Counterspell | Lightning Bolt |
```

### バックエンド API

**エンドポイント**: `GET /api/matches/export`

| パラメーター | 型 | 説明 |
|-------------|-----|------|
| `player` | string (required) | プレイヤー名 |
| `opponent` | string? | 対戦相手フィルター |
| `deck` | string? | 使用デッキフィルター |
| `opponent_deck` | string? | 相手デッキフィルター |
| `format` | string? | フォーマットフィルター |
| `date_from` | string? | 開始日 (YYYY-MM-DD) |
| `date_to` | string? | 終了日 (YYYY-MM-DD) |
| `detail_level` | `summary` \| `matches` \| `actions` | 詳細レベル |
| `limit` | int (default: 200) | 最大件数 |

レスポンス: `text/plain; charset=utf-8` で Markdown 文字列を返す。
フロントエンドで `Blob` に変換してダウンロードさせる。

件数確認用に `GET /api/matches/export/count` も用意し、実際のダウンロード前に対象件数のみ返す。

| パラメーター | 型 | 説明 |
|-------------|-----|------|
| `player` | string (required) | 上記と同じフィルターパラメーター |
| … | … | （フィルター系は同一） |

レスポンス: `{ "count": N }`

### フロントエンド

| ファイル | 変更内容 |
|----------|---------|
| `frontend/src/views/MatchListView.vue` | エクスポートボタン・モーダル追加 |
| `frontend/src/api/matches.ts` | `fetchExportCount()` / `downloadExport()` 追加 |

### 動作確認手順（エクスポート機能）

1. 「AI用エクスポート」ボタンをクリックしてモーダルが開くことを確認する
2. フィルターを設定してダウンロードし、条件に合ったデータのみ出力されることを確認する
3. 詳細レベルを切り替えて出力内容が変わることを確認する
4. 対象件数 > 上限件数のとき確認メッセージが表示されることを確認する
5. アクション詳細あり かつ 対象件数 > 50 のとき追加警告が表示されることを確認する
6. ダウンロードしたファイルを AI ツールに貼り付けて正常に解釈されることを確認する
