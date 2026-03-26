# サイドボード差分トラッキング 設計ドキュメント

## 概要

MTGA の対戦ログからゲーム間のサイドボーディング内容を取得し、各ゲーム開始時のサイドイン・サイドアウト差分を DB に保存する。AI エクスポートに付加することで「ゲーム2・3でのサイドボーディングが適切だったか」「投入したカードが実際に機能したか」といった分析を可能にする。

---

## 実装ステータス

実装済み

---

## 背景・動機

現状のエクスポートにはゲーム1のデッキリストのみが含まれており、ゲーム2・3でどのカードをサイドインしたかが記録されていない。BO3 フォーマットにおけるサイドボーディングはゲームプランの根幹であり、これが欠けると LLM は「なぜゲーム2でこの動きができなかったか」を正確に評価できない。

---

## 対象ログの範囲

MTGA 専用機能として実装する。

MTGA の Player.log には2種類のデッキ関連イベントが含まれる。

- `GREMessageType_SubmitDeckReq`（サーバー→クライアント）: サイドボード画面が**開いた時点**のデッキ（変更前）を含む。これはサイドボーディング前のデッキであり、実際のサイドボーディング後のデッキとは異なる。
- `ClientMessageType_SubmitDeckResp`（クライアント→サーバー）: プレイヤーがサイドボード画面で変更を**確定した時点**のデッキを含む。実際のサイドボーディング後のデッキが記録される。

サンプルデータでの確認結果は以下の通り。

- 2ゲームマッチ（ゲーム1で勝ちきった場合）: `SubmitDeckResp` は発火しない（サイドボード画面が開かれない）
- 2ゲームマッチ（ゲーム2まで行く場合）: `SubmitDeckResp` は1回（ゲーム2用）
- 3ゲームマッチ: `SubmitDeckResp` は2回（ゲーム2用・ゲーム3用）

Surveil が `submit_deck_resps` フィールドとして schema_version=4 JSON に出力する（`submit_deck_resps[0]` = ゲーム2用、`submit_deck_resps[1]` = ゲーム3用）。

ゲーム1はマッチ開始時の top-level `deck_grp_ids` / `sideboard_grp_ids` を使用する。

MTGO ログにはゲーム間のサイドボード情報が含まれないため対応しない。

schema_version=2/3（旧 Surveil 形式）にも対応しないこととする。schema_version=4 以降のみ対応する。

---

## 設計方針の決定事項

| 項目 | 決定内容 |
|------|---------|
| 差分の定義 | サイドイン = 前ゲームのメインにはなく今ゲームのメインにあるカード（マルチセット差分）。サイドアウト = 前ゲームのメインにあって今ゲームのメインにないカード |
| 保存形式 | `games` テーブルに `sideboard_in` / `sideboard_out` カラム（TEXT NULLABLE）を追加。JSON オブジェクト `{"カード名": 枚数, ...}` として保存。ゲーム1は NULL |
| カード名解決 | import 時に `mtga_cards` テーブルから grpId を名前に変換する。解決できない grpId は保存しない |
| エクスポート | AI エクスポートの各ゲームヘッダー直後にサイドイン/アウトのリストを出力（ゲーム2以降のみ） |
| 対戦詳細での表示 | GameAccordion コンポーネントにサイドボード差分セクションを追加（副次実装） |

---

## データモデル

### `games` テーブルへの追加

既存の `Game` モデルに2カラムを追加する。

`sideboard_in` は TEXT NULLABLE で、JSON オブジェクト形式でサイドインしたカード名と枚数を保存する。例として `{"Consign to Memory": 3, "Spell Pierce": 2}` のような形式。ゲーム1は NULL。

`sideboard_out` は同形式でサイドアウトしたカード名と枚数を保存する。ゲーム1は NULL。

サイドイン枚数とサイドアウト枚数は必ず一致する（メインとサイドの合計枚数が変わらないため）。

### Surveil JSON の `submit_deck_resps` フィールド（schema_version=4）

Surveil が出力する JSON の top-level に `submit_deck_resps` フィールドが追加された（schema_version=4）。各要素は `{"deck_grp_ids": [...], "sideboard_grp_ids": [...]}` を持ち、`ClientMessageType_SubmitDeckResp` の発火順に追記される。`submit_deck_resps[0]` = ゲーム2用、`submit_deck_resps[1]` = ゲーム3用。

---

## バックエンド

### パーサー変更（`gre_parser.py`）

**`submit_deck_resps` の読み込み**

`parse_gre_json` で top-level の `submit_deck_resps` を読み込む。ゲームの対応付けは `game_idx = game_number - 2`（ゲーム2 = index 0、ゲーム3 = index 1）。`GREGame` の `deck_grp_ids_per_game` / `sideboard_grp_ids_per_game` フィールドに格納する（ゲーム1は空リスト）。

**バージョンチェック**

`parse_gre_json` は `schema_version != 4` の JSON を拒否する（`ParseError` を送出）。

**差分の計算**

差分の計算は grpId レベルでは行わず、`import_service._convert_gre_result` で名前解決後に行う。

**`GREGame` TypedDict の変更**

`deck_grp_ids_per_game: list[int]` と `sideboard_grp_ids_per_game: list[int]` フィールドを追加する（ゲームに対応する SubmitDeckReq が存在しない場合は空リスト）。

### インポートサービス変更（`import_service.py`）

**`_convert_gre_result` の変更**

各ゲームを変換する際に `game["deck_grp_ids_per_game"]` と前のゲームの対応データを比較してサイドボード差分を算出する。

ゲーム1のメインデッキ基準は top-level の `gre_result["deck_grp_ids"]`。ゲーム2以降は前ゲームの `deck_grp_ids_per_game` と今ゲームの `deck_grp_ids_per_game` をマルチセット差分で比較する。

差分の算出には Python の `collections.Counter` を使い、今ゲームのメインにある枚数から前ゲームのメインにある枚数を引いた正の値をサイドインとして、負の値の絶対値をサイドアウトとして記録する。

`name_map`（grpId → カード名）で名前解決し、解決できない grpId は無視する。

結果は `{"カード名": 枚数}` の辞書として `SurveilGame` に `sideboard_in` / `sideboard_out` フィールドとして追加する。

**`_save` の変更（MTGA インポート保存処理）**

`Game` モデル生成時に `sideboard_in` / `sideboard_out` を `json.dumps()` で JSON 文字列化して保存する。NULL の場合は None のまま。

### エクスポート変更（`matches.py`）

AI エクスポートのゲームセクション出力において、ゲーム2以降でサイドボード差分が存在する場合に以下の内容をアクション詳細の前に出力する。`game.sideboard_in` / `game.sideboard_out` が NULL でない場合、JSON をパースしてカード名と枚数をリスト形式で出力する。

出力形式のイメージは以下の通り。

```
#### Game 2 サイドボーディング
サイドイン: Consign to Memory x3, Spell Pierce x2
サイドアウト: Violent Urge x2, Lava Dart x1
```

---

## フロントエンド（対戦詳細への副次表示）

`GameAccordion.vue` コンポーネントにサイドボード差分セクションを追加する。ゲーム2以降で `sideboard_in` / `sideboard_out` が存在する場合に「サイドイン: …」「サイドアウト: …」を表示する。

`MatchDetail` API レスポンスの `GameSummary` に `sideboard_in` / `sideboard_out` フィールドを追加する。

`frontend/src/api/matches.ts` の `GameSummary` インターフェースに対応フィールドを追加する。

---

## エッジケース

| ケース | 対応 |
|--------|------|
| MTGO インポート | `sideboard_in` / `sideboard_out` は NULL のまま |
| schema_version=2 インポート | NULL のまま |
| ゲーム1（サイドボーディングなし） | `sideboard_in` / `sideboard_out` は NULL |
| サイドボード差分がゼロ（前ゲームと同一デッキ） | `sideboard_in` / `sideboard_out` を `{}` として保存（NULL ではなく空オブジェクト）。エクスポートでは出力しない |
| grpId が `mtga_cards` で未解決 | そのカードのエントリを無視し、他のカードのみで差分を構成する |
| `submit_deck_resps` がゲーム数より少ない（ゲーム1のみ終わった場合） | 存在する分だけ保存し、対応がないゲームは NULL のまま |
| 既存インポート済みデータ | 遡及適用しない。カラムは NULL のまま |

---

## 変更ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `backend/models/core.py` | `Game` モデルに `sideboard_in: str \| None`・`sideboard_out: str \| None` カラム追加 |
| `backend/database.py` | マイグレーション（`games.sideboard_in`・`games.sideboard_out` カラム追加） |
| `backend/parser/gre_parser.py` | top-level `submit_deck_resps` 読み込み（schema_version=4）、`GREGame` に `deck_grp_ids_per_game` / `sideboard_grp_ids_per_game` フィールド追加 |
| `backend/services/import_service.py` | `_convert_gre_result` でサイドボード差分を算出し `SurveilGame` に付与、`Game` 保存時に `sideboard_in` / `sideboard_out` を保存 |
| `backend/app/routers/matches.py` | AI エクスポートにサイドボーディングセクション追加、`MatchDetail` API の `GameSummary` に `sideboard_in` / `sideboard_out` を追加 |
| `frontend/src/api/matches.ts` | `GameSummary` に `sideboard_in` / `sideboard_out` フィールド追加 |
| `frontend/src/components/GameAccordion.vue` | サイドボード差分表示セクション追加 |
