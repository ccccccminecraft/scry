# 詳細設計: AIエクスポート画面

## 対象ファイル

| ファイル | 種別 | 内容 |
|----------|------|------|
| `frontend/src/views/AIExportView.vue` | 新規 | AIエクスポート専用画面 |
| `frontend/src/components/GlobalNav.vue` | 編集 | ナビメニューに「AIエクスポート」追加 |
| `frontend/src/router/index.ts` | 編集 | `/ai-export` ルートを追加 |
| `frontend/src/views/MatchListView.vue` | 編集 | 「AI用エクスポート」ボタン・モーダルを削除 |
| `backend/app/routers/matches.py` | 編集 | `_build_export_markdown()` にカード統計セクションを追加 |

---

## 画面設計 (AIExportView.vue)

### レイアウト

現在の対戦履歴画面のモーダルUIをそのまま専用画面に移植する。

```
[ページタイトル] AI エクスポート

[フィルターセクション]
  プレイヤー    [select]
  対戦相手      [select]
  使用デッキ    [select]
  相手デッキ    [select]
  フォーマット  [select]
  対戦日時（開始）[date]
  対戦日時（終了）[date]

[出力設定セクション]
  詳細レベル    ○ サマリーのみ  ○ マッチ一覧  ○ アクション詳細
  件数上限      [number input] 件（直近）

[ダウンロードボタン]
  [確認メッセージ（件数が多い場合）]
  [ダウンロード] ボタン
```

### 状態変数

| 変数 | 型 | 説明 |
|------|----|------|
| `playerList` | `string[]` | プレイヤー一覧 |
| `opponentList` | `string[]` | 対戦相手一覧 |
| `deckList` | `string[]` | 自分デッキ一覧 |
| `opponentDeckList` | `string[]` | 相手デッキ一覧 |
| `formatList` | `string[]` | フォーマット一覧 |
| `selectedPlayer` | `string` | 選択プレイヤー |
| `selectedOpponent` | `string` | 選択対戦相手 |
| `selectedDeck` | `string` | 選択デッキ |
| `selectedOpponentDeck` | `string` | 選択相手デッキ |
| `selectedFormat` | `string` | 選択フォーマット |
| `dateFrom` | `string` | 開始日 |
| `dateTo` | `string` | 終了日 |
| `detailLevel` | `'summary' \| 'matches' \| 'actions'` | 出力詳細レベル（初期値: `'matches'`） |
| `limit` | `number` | 件数上限（初期値: `200`） |
| `confirmMsg` | `string` | 件数警告メッセージ |
| `confirmed` | `boolean` | 警告確認済みフラグ |
| `downloading` | `boolean` | ダウンロード中フラグ |

### 処理フロー

1. `onMounted` でプレイヤー一覧・フォーマット一覧を取得し、プレイヤーを自動選択する
2. プレイヤー選択時に対戦相手・デッキ・相手デッキ一覧を取得する（現行モーダルと同じ）
3. ダウンロードボタン押下時:
   - `GET /api/matches/export/count` で件数を取得する
   - 50件以上かつ `actions` レベル、または 200件以上の場合は `confirmMsg` を表示して `confirmed = false` にする
   - `confirmed = false` の状態でボタンを再押下すると `confirmed = true` にしてダウンロード実行
   - `confirmed = true` の状態、または件数が少ない場合は即時ダウンロード実行
4. `GET /api/matches/export` でMarkdownを取得しブラウザからファイルダウンロードさせる

### ナビゲーション配置

`GlobalNav.vue` の AI分析（`/analysis`）の直後に追加する。

```
AI 分析
AIエクスポート   ← ここに追加
インポート
```

---

## バックエンド変更: カード統計セクションの追加

### 追加位置

`_build_export_markdown()` 内、サマリー集計（デッキ別勝率）の直後・`if detail_level == "summary": return` の前にカード統計セクションを挿入する。

すべての詳細レベル（`summary` / `matches` / `actions`）でカード統計を含める。

### 追加するMarkdownセクション

```markdown
### カード統計（選択プレイヤー Top 20）

| カード名 | 使用回数 | 登場ゲーム | 勝率 |
|---------|---------|-----------|------|
| Lightning Bolt | 143 | 87 | 64.4% |
...

### カード統計（対戦相手 Top 20）

| カード名 | 使用回数 | 登場ゲーム | 選択プレイヤー勝率 |
|---------|---------|-----------|-----------------|
| Ragavan, Nimble Pilferer | 98 | 72 | 38.9% |
...
```

### データ取得方法

`_build_export_markdown()` 内で直接クエリを実行する。`stats.py` の `get_card_stats` エンドポイントのクエリロジックを関数 `_calc_card_stats(db, player, game_ids, perspective, limit=20)` として `stats.py` に切り出し、`matches.py` からインポートして呼び出す。

```python
# stats.py に追加
def _calc_card_stats(
    db: Session,
    player: str,
    game_ids: list[int],
    perspective: str,  # "self" or "opponent"
    limit: int = 20,
) -> list[dict]:
    """game_ids を対象にカード別統計を集計する。"""
    ...（get_card_stats の内部ロジックを移植）
```

```python
# matches.py の _build_export_markdown() 内
from app.routers.stats import _calc_card_stats

game_ids = [g.id for g in games_all]
self_card_stats = _calc_card_stats(db, player, game_ids, "self")
opp_card_stats  = _calc_card_stats(db, player, game_ids, "opponent")
```

---

## MatchListView からの削除対象

以下を削除する（専用画面に移行するため）:

- 「AI用エクスポート」ボタン（ヘッダー部分）
- エクスポートモーダル全体（`v-if="showExportModal"` のブロック）
- 関連する状態変数: `showExportModal`, `expPlayer`, `expOpponent`, `expDeck`, `expOpponentDeck`, `expFormat`, `expDateFrom`, `expDateTo`, `expDetailLevel`, `expLimit`, `expDownloading`, `expConfirmMsg`, `expConfirmed`
- 関連する関数: `openExportModal()`, `runExport()`, `confirmExport()`, `doDownload()`
- `fetchExportCount`, `fetchExportMarkdown` のインポート（他で使用していない場合）

---

## API変更なし

既存の以下エンドポイントをそのまま使用する。変更不要。

- `GET /api/matches/export/count`
- `GET /api/matches/export`

---

## エラーハンドリング

| ケース | 対応 |
|--------|------|
| 件数0件でダウンロード | ボタンを `disabled` にするか、実行後トーストで「対象データなし」を表示 |
| API取得失敗（件数確認・エクスポート） | トーストでエラーメッセージを表示 |
| プレイヤー未選択 | ダウンロードボタンを `disabled` にする |

---

## 動作確認手順

1. ナビメニューに「AIエクスポート」が AI分析の直後に表示されることを確認する
2. `/ai-export` にアクセスし、プレイヤー・フィルターが正しく機能することを確認する
3. 各詳細レベル（サマリー / マッチ一覧 / アクション詳細）でダウンロードし、Markdownの構成を確認する
4. すべての詳細レベルでカード統計（選択プレイヤー・対戦相手）セクションが含まれることを確認する
5. 件数が多い場合（50件以上のアクション詳細 or 200件以上）に警告メッセージが表示されることを確認する
6. 対戦履歴画面に「AI用エクスポート」ボタンとモーダルが表示されないことを確認する
