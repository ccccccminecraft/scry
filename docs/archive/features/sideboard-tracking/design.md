# サイドボード差分トラッキング 設計ドキュメント

## 概要

MTGA の対戦ログからゲーム間のサイドボーディング内容を取得し、各ゲーム開始時のサイドイン・サイドアウト差分を DB に保存する。AI エクスポートに付加することで「ゲーム2・3でのサイドボーディングが適切だったか」「投入したカードが実際に機能したか」といった分析を可能にする。

---

## 実装ステータス

実装済み（Surveil 0.1.1 / Scry schema_version=4 対応）

---

## 背景・動機

旧実装ではゲーム2・3のサイドボードが正しく記録できていなかった。原因は `GREMessageType_SubmitDeckReq`（サーバー→クライアント）がサイドボード画面の**オープン時**に発火し、変更前のデッキを含むため。Surveil 0.1.1 で `ClientMessageType_SubmitDeckResp`（クライアント→サーバー）を捕捉するよう修正し、確定後のデッキを `submit_deck_resps` フィールドとして schema_version=4 JSON に出力するようになった。

---

## 対象ログの範囲

MTGA 専用機能。MTGO ログにはゲーム間のサイドボード情報が含まれないため対応しない。

MTGA の Player.log には2種類のデッキ関連イベントが含まれる。

- `GREMessageType_SubmitDeckReq`（サーバー→クライアント）: サイドボード画面が**開いた時点**のデッキ（変更前）を含む。**使用しない。**
- `ClientMessageType_SubmitDeckResp`（クライアント→サーバー）: プレイヤーがサイドボード画面で変更を**確定した時点**のデッキを含む。実際のサイドボーディング後のデッキ。**こちらを使用。**

サンプルデータでの確認結果は以下の通り。

- 2ゲームマッチ（ゲーム1で勝ちきった場合）: `SubmitDeckResp` は発火しない
- 2ゲームマッチ（ゲーム2まで行く場合）: `SubmitDeckResp` は1回（ゲーム2用）
- 3ゲームマッチ: `SubmitDeckResp` は2回（ゲーム2用・ゲーム3用）

Surveil が `submit_deck_resps` フィールドとして schema_version=4 JSON に出力する（`submit_deck_resps[0]` = ゲーム2用、`submit_deck_resps[1]` = ゲーム3用）。ゲーム1はマッチ開始時の top-level `deck_grp_ids` / `sideboard_grp_ids` を使用する。

schema_version=2/3 には対応しない。schema_version=4 以降のみ対応する。

---

## 設計方針の決定事項

| 項目 | 決定内容 |
|------|---------|
| 差分の定義 | サイドイン = ゲーム1のメインにはなく今ゲームのメインにあるカード（マルチセット差分）。サイドアウト = ゲーム1のメインにあって今ゲームのメインにないカード |
| 保存形式 | `games` テーブルに `sideboard_in` / `sideboard_out` カラム（TEXT NULLABLE）を追加。JSON オブジェクト `{"カード名": 枚数, ...}` として保存。ゲーム1は NULL |
| カード名解決 | import 時に `mtga_cards` テーブルから grpId を名前に変換する。解決できない grpId は保存しない |
| エクスポート | AI エクスポートの各ゲームヘッダー直後にサイドイン/アウトのリストを出力（ゲーム2以降のみ） |
| 対戦詳細での表示 | `GameAccordion.vue` にサイドボード差分セクションを追加 |

---

## データフロー

```
Player.log
  └─ ClientMessageType_SubmitDeckResp (確定後デッキ)
       └─ Surveil 0.1.1 → submit_deck_resps[] in schema_version=4 JSON
            └─ gre_parser.py (parse_gre_json)
                 └─ GREGame.deck_grp_ids_per_game (game_number-2 でインデックス)
                      └─ import_service._convert_gre_result
                           └─ _calc_sideboard_diff (Counter ベース)
                                └─ games.sideboard_in / sideboard_out (DB)
```

---

## データモデル

### `games` テーブルへの追加

`sideboard_in` / `sideboard_out` は TEXT NULLABLE。JSON オブジェクト形式（`{"カード名": 枚数}`）。ゲーム1は NULL。

### Surveil JSON `submit_deck_resps` フィールド（schema_version=4）

各要素: `{"deck_grp_ids": [...], "sideboard_grp_ids": [...]}` — `ClientMessageType_SubmitDeckResp` の発火順。

---

## エッジケース

| ケース | 対応 |
|--------|------|
| MTGO インポート | `sideboard_in` / `sideboard_out` は NULL のまま |
| schema_version=2/3 インポート | NULL のまま |
| ゲーム1（サイドボーディングなし） | `sideboard_in` / `sideboard_out` は NULL |
| サイドボード差分がゼロ（前ゲームと同一デッキ） | `{}` として保存（NULL ではなく空オブジェクト）。エクスポートでは出力しない |
| grpId が `mtga_cards` で未解決 | そのカードのエントリを無視し、他のカードのみで差分を構成する |
| `submit_deck_resps` がゲーム数より少ない | 存在する分だけ保存し、対応がないゲームは NULL のまま |
| 既存インポート済みデータ | 遡及適用しない。カラムは NULL のまま |

---

## 変更ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `backend/models/core.py` | `Game` モデルに `sideboard_in` / `sideboard_out` カラム追加 |
| `backend/database.py` | マイグレーション（`games.sideboard_in` / `sideboard_out` カラム追加） |
| `backend/parser/gre_parser.py` | top-level `submit_deck_resps` 読み込み（schema_version=4）、`GREGame` に `deck_grp_ids_per_game` / `sideboard_grp_ids_per_game` フィールド追加 |
| `backend/services/import_service.py` | schema_version=4 ルーティング追加、`_convert_gre_result` でサイドボード差分算出 |
| `backend/app/routers/matches.py` | AI エクスポートにサイドボーディングセクション追加、`GameSummary` に `sideboard_in` / `sideboard_out` 追加 |
| `frontend/src/api/matches.ts` | `GameSummary` に `sideboard_in` / `sideboard_out` フィールド追加 |
| `frontend/src/components/GameAccordion.vue` | サイドボード差分表示セクション追加 |
| `surveil/src/parser.py` | `ClientMessageType_SubmitDeckResp` の捕捉・`submit_deck_resps` 出力 |
| `surveil/src/storage.py` | `schema_version=4`、`submit_deck_resps` フィールド追加 |
