# 設計書: 使用デッキ・相手デッキ 複数選択（OR）

## 実装ステータス

**実装済み（2026-03-25）**
- 全変更ファイル一覧の内容を設計通りに実装済み
- axios の `paramsSerializer: { indexes: null }` 設定により配列パラメータを `key=v1&key=v2` 形式で送信
- FastAPI 側は `list[int] = Query(default=[])` / `list[str] = Query(default=[])` で受信

## 1. 概要

FilterBar の「使用デッキ」「相手デッキ」フィルターを複数選択に対応させ、選択した項目を OR 条件で絞り込む。

---

## 2. デッキリストとアーキタイプの混在について

デッキリスト選択は DeckVersion テーブルへの JOIN を経由して絞り込む経路、アーキタイプ選択は MatchPlayer.deck_name を直接参照する経路であり、フィルタリングの参照先が根本的に異なる。

この 2 経路を OR で束ねることは技術的には成立するが、どの試合が対象になるかがユーザーに見えにくくなる。また将来どちらかの仕組みを変更した際に挙動が変わりやすいという保守上のリスクもある。

**結論: デッキリストとアーキタイプは排他的とする。**

セクションをまたいだ選択は行わず、デッキリストを選択したらアーキタイプ側のチェックはクリア（逆も同様）。各セクション内での複数選択はOK。

---

## 3. 状態設計（useFilterState.ts）

### 型変更

| 現在 | 変更後 |
|---|---|
| `deckId`（単一のデッキID） | `deckIds`（デッキIDの配列） |
| `deck`（単一のアーキタイプ名） | `decks`（アーキタイプ名の配列） |
| `opponentDeck`（単一の相手デッキ名） | `opponentDecks`（相手デッキ名の配列） |
| `versionId` | 変更なし |

`deckIds` と `decks` は排他的に管理し、一方が非空であれば他方は必ず空とする。

### バージョンフィルターの変更

複数デッキ選択時はバージョン指定を「バージョン=すべて」扱いとし、クエリに渡さない（UI の有効・無効は変更しない）。

| 状態 | versionId の扱い |
|---|---|
| `deckIds` が 1 件のみ | クエリに適用する |
| `deckIds` が 2 件以上 | クエリに渡さない（バージョン=すべて扱い） |
| `decks` が 1 件以上 | クエリに渡さない（同上） |
| 何も選択なし | クエリに渡さない（変化なし） |

### localStorage 形式

保存するキーを `deckIds`（配列）・`decks`（配列）・`opponentDecks`（配列）に変更する。旧形式のキー（`deckId`・`deck`・`opponentDeck`）は読み込み時に無視し、デッキ系フィルターはリセット状態として扱う。

---

## 4. UI 設計

### 4-1. DeckSelectModal.vue

**排他制御ルール:**
- デッキリストの項目をチェックした場合、アーキタイプ側の選択を全クリアする
- アーキタイプの項目をチェックした場合、デッキリスト側の選択を全クリアする

**操作フロー:**
- 項目をクリックするとチェックが切り替わる（モーダルは閉じない）
- 「すべて」をクリックすると全チェックを解除してモーダルを閉じる
- 「クリア」ボタンは全チェックを解除するがモーダルは閉じない
- 「確定」ボタンでモーダルを閉じる

**props/emits 変更:**
- props: `deckId`・`deck`（単数）→ `deckIds`・`decks`（配列）
- emits: `selectDeckId`・`selectDeck`（単数選択）→ `update:deckIds`・`update:decks`（配列更新）

### 4-2. FilterSelectModal.vue（相手デッキ用）

`multiple` プロパティを追加してシングル・マルチのモードを切り替える。

マルチモード時はチェックボックス形式で複数選択でき、DeckSelectModal と同様にクリア・確定ボタンを表示する。選択値は配列として扱い、`update:multipleValues` イベントで通知する。

### 4-3. FilterBar ボタンラベル

**使用デッキボタン:**

| 状態 | 表示 |
|---|---|
| 何も選択なし | `すべて` |
| deckIds または decks が 1 件 | そのデッキ名 / アーキタイプ名 |
| deckIds または decks が 2 件以上 | `N件選択` |

**バージョンボタン:**
- `deckIds` が 1 件のみのときは選択中の versionId をラベルに反映する
- `deckIds` が 2 件以上または `decks` が 1 件以上のときはラベルを `すべて` で固定表示する（versionId が設定されていてもラベルには反映しない）

**相手デッキボタン:**

| 状態 | 表示 |
|---|---|
| 0 件 | `すべて` |
| 1 件 | そのデッキ名 |
| 2 件以上 | `N件選択` |

---

## 5. API 設計

### バックエンド変更

以下の 4 エンドポイントのクエリパラメータを変更する。

- `GET /api/stats`
- `GET /api/matches`
- `GET /api/matches/export/count`
- `GET /api/matches/export/markdown`

**変更内容:**
- `deck_id`（単一整数）→ `deck_ids`（整数のリスト、デフォルト空リスト）
- `deck`（単一文字列）→ `decks`（文字列のリスト、デフォルト空リスト）
- `opponent_deck`（単一文字列）→ `opponent_decks`（文字列のリスト、デフォルト空リスト）

**`_build_match_id_list` のフィルタリングロジック（stats.py）:**

使用デッキの絞り込みは以下の優先順で適用する。

1. `version_id` が指定されており、かつ `deck_ids` が 1 件の場合: バージョンで絞り込む
2. `deck_ids` が 1 件以上の場合: 指定されたデッキ ID のいずれかに合致する試合を抽出する（IN 句）
3. `decks` が 1 件以上の場合: 指定されたアーキタイプ名のいずれかに合致する試合を抽出する（IN 句）
4. いずれも空の場合: 使用デッキによる絞り込みを行わない

相手デッキの絞り込みは、`opponent_decks` が 1 件以上の場合に相手プレイヤーの `deck_name` が指定リストのいずれかに合致する試合を抽出する（IN 句）。

排他制御はフロントエンド側で担保するため、バックエンドは `deck_ids` と `decks` が同時に送られることを想定しない（送られた場合も `elif` による優先順で自然に処理される）。

### フロントエンド API 呼び出し

配列パラメータは URLSearchParams で同じキーを複数回 append する形式で送信する（例: `deck_ids=1&deck_ids=2`）。

`version_id` は `deckIds` が 1 件のときのみ送信し、複数選択時や `decks` 選択時は送信しない（バージョン=すべて扱い）。

---

## 6. 変更ファイル一覧

| ファイル | 変更内容 |
|---|---|
| `useFilterState.ts` | 状態型変更・排他制御・localStorage 形式変更 |
| `DeckSelectModal.vue` | マルチ選択・排他制御・確定ボタン追加 |
| `FilterSelectModal.vue` | `multiple` モード追加 |
| `FilterBar.vue` | ラベル表示更新・バージョンラベル条件更新 |
| `api/stats.ts` | クエリパラメータ型変更 |
| `api/matches.ts` | クエリパラメータ型変更 |
| `StatsView.vue` | `currentFilters()` 更新 |
| `MatchListView.vue` | `currentFilters()` 更新 |
| `AIExportView.vue` | `currentFilters()` 更新 |
| `AnalysisView.vue` | `currentFilters()` 更新 |
| `backend/app/routers/stats.py` | `_build_match_id_list`・`get_stats` パラメータ変更 |
| `backend/app/routers/matches.py` | `list_matches`・export 系パラメータ変更 |
