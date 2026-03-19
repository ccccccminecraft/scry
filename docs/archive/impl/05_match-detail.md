# 詳細設計: 対戦詳細画面 (S04)

## 対象ファイル

| ファイル | 種別 | 内容 |
|----------|------|------|
| `frontend/src/api/matches.ts` | 編集 | 対戦詳細・アクションログ・PATCH 関数を追加 |
| `frontend/src/views/MatchDetailView.vue` | 新規 | S04 対戦詳細画面 |
| `frontend/src/components/GameAccordion.vue` | 新規 | ゲームごとのアコーディオン |
| `frontend/src/components/ActionLog.vue` | 新規 | アクションログ表示 |

---

## `api/matches.ts` への型追加

```typescript
interface PlayerInfo {
  player_name: string
  deck_name: string | null
  game_plan: string | null
}

interface GameSummary {
  game_id: number           // DB の games.id（アクションログ取得に使用）
  game_number: number
  winner: string
  turns: number
  first_player: string
  mulligans: Record<string, number>  // { PlayerA: 0, PlayerB: 1 }（0回も含む）
}

interface MatchDetail {
  match_id: string
  date: string
  players: PlayerInfo[]
  match_winner: string
  format: string | null
  games: GameSummary[]
}

interface ActionEntry {
  turn: number
  player: string
  action_type: string
  card_name: string | null
  sequence: number
}

interface ActionLogResponse {
  game_id: number
  actions: ActionEntry[]
}
```

**追加 API 関数**

| 関数 | エンドポイント | 説明 |
|------|--------------|------|
| `fetchMatchDetail(matchId)` | `GET /api/matches/{match_id}` | 対戦詳細取得 |
| `fetchActionLog(matchId, gameId)` | `GET /api/matches/{match_id}/games/{game_id}/actions` | アクションログ取得 |
| `patchPlayer(matchId, playerName, body)` | `PATCH /api/matches/{match_id}/players/{player_name}` | デッキ名・ゲームプラン更新 |

---

## コンポーネント構成

```
MatchDetailView.vue
├── GameAccordion.vue  × games.length
│     └── ActionLog.vue  （展開時のみマウント）
└── （デッキ名・ゲームプラン編集はインライン）
```

---

## MatchDetailView.vue

### 状態

| 変数 | 型 | 説明 |
|------|----|------|
| `detail` | `MatchDetail \| null` | 取得したマッチ詳細 |
| `loading` | `boolean` | ローディング中フラグ |
| `deckEditing` | `Record<string, boolean>` | プレイヤーごとのデッキ名入力モード |
| `deckDraft` | `Record<string, string>` | デッキ名編集中の一時値 |
| `gamePlanSaving` | `Record<string, boolean>` | ゲームプラン PATCH リクエスト中フラグ |

### 処理フロー

**初期化**
- `onMounted` で `fetchMatchDetail(matchId)` を呼ぶ
- 取得後、各プレイヤーの `deckEditing`・`deckDraft` を初期化する

**デッキ名インライン編集**
- ✎ クリックで `deckEditing[player]` を `true` にして入力欄を表示する
- Enter または blur で確定。変更がなければ PATCH を呼ばない
- Escape でキャンセルし `deckDraft` を元の値に戻す
- PATCH 成功後、`player.deck_name` をローカルに更新する
- PATCH 失敗時はトーストを表示して入力欄の値を元に戻す

**ゲームプランドロップダウン**
- 選択肢: 未設定 / aggro / midrange / control / combo
- `change` イベントで即時 PATCH を呼ぶ。空文字は `null` に変換して送信する
- PATCH 中は `gamePlanSaving[player]` を `true` にして `disabled` 表示にする

### 表示仕様

- ヘッダー: 日時・フォーマットバッジ・プレイヤー vs 表示・勝者
- プレイヤー行: プレイヤー名 / デッキ名（インライン編集）/ ゲームプラン（ドロップダウン）
- ゲーム一覧: GameAccordion を game_number 順に表示する
- 戻るボタンで `router.back()` を呼ぶ

---

## GameAccordion.vue

### Props

| Prop | 型 | 説明 |
|------|----|------|
| `game` | `GameSummary` | ゲーム情報 |
| `matchId` | `string` | アクションログ取得に使用 |

### 状態

| 変数 | 型 | 説明 |
|------|----|------|
| `open` | `boolean` | 展開状態 |
| `actions` | `ActionEntry[] \| null` | null = 未取得、取得後はキャッシュ |
| `loading` | `boolean` | ローディング中フラグ |

### 処理フロー

- ヘッダークリックで `open` を toggle する
- `open === true && actions === null` のときのみ `fetchActionLog` を呼ぶ（2回目以降は再取得しない）
- 取得失敗時はトーストを表示して `open` を `false` に戻す

### 表示仕様

- ヘッダー: ゲーム番号・先手プレイヤー・ターン数・展開アイコン（▼/▲）
- サブヘッダー: 各プレイヤーのマリガン回数（常時表示）
- 展開時: ActionLog コンポーネントを表示する

---

## ActionLog.vue

### Props

| Prop | 型 | 説明 |
|------|----|------|
| `actions` | `ActionEntry[]` | アクション一覧 |

### 表示仕様

- ターン番号でグルーピングし、ターンヘッダー + アクション行の形で表示する
- アクション行: プレイヤー名 / アクション種別（日本語ラベル）/ カード名
- `action_type` → 日本語ラベルのマッピングテーブルを定数で定義する

**アクション種別ラベル**

| action_type | 日本語 |
|-------------|--------|
| `play` | 土地プレイ |
| `cast` | 唱える |
| `activate` | 能力起動 |
| `trigger` | 誘発 |
| `attack` | 攻撃 |
| `draw` | ドロー |
| `discard` | 捨てる |
| `reveal` | 公開 |
| `add_counter` | カウンター追加 |
| `remove_counter` | カウンター除去 |
| `mulligan` | マリガン |

---

## 設計上の補足事項

### `game_id` について

`GameAccordion` がアクションログを取得するには `games[].game_id`（DB の `games.id`）が必要。
`GET /api/matches/{match_id}` のレスポンス `games[]` に `game_id` フィールドを追加する（`03_api-design.md` の `GameSummary` を更新済み）。

### `mulligans` の返却形式

バックエンドは `match_players` から2名のプレイヤー名を取得し、`mulligans` テーブルにレコードがないプレイヤーは `0` として補完した `Record<string, number>` を返す。
フロントは補完済みの値をそのまま表示すればよい。

---

## 動作確認手順

1. 対戦履歴画面（S03）から行をクリックして S04 に遷移することを確認する
2. マッチ情報（日時・プレイヤー・フォーマット）が正しく表示されることを確認する
3. デッキ名の ✎ クリックで入力欄が表示され、Enter で確定・Escape でキャンセルされることを確認する
4. ゲームプランをドロップダウンで変更し、再読み込み後も保持されていることを確認する
5. ゲームのアコーディオンを展開してアクションログが表示されることを確認する
6. 同じアコーディオンを2回展開しても API が1回しか呼ばれないことを確認する（キャッシュ動作）
7. 戻るボタンで S03 に戻ることを確認する
