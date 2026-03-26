# ライフ推移トラッキング 設計ドキュメント

## 概要

MTGA の対戦ログからライフ変動イベントを取得し、各プレイヤーのライフ推移をダメージ発生ごとに DB に保存する。AI エクスポートのアクションログにライフ情報を付加することで、「何ターン目に詰め切れたか」「どのスペルが実質的に最もライフを削ったか」といった分析を可能にする。

---

## 実装ステータス

実装済み

---

## 背景・動機

現状の AI エクスポートにはアクションの記録（何をキャストしたか・誰が攻撃したか）は含まれているが、ライフの数値が含まれていない。そのため LLM は「そのターンに詰め切れたかどうか」「Mutagenic Growth を温存すべきだったか」といった判断を下せない。ライフ推移を付加することで対戦全体のテンポが可視化され、分析精度が根本的に向上する。

---

## 対象ログの範囲

MTGA 専用機能として実装する。MTGO のテキストログにはライフ情報が含まれていないため対応しない。MTGO インポート分のライフカラムは NULL のままとする。

schema_version=2（旧 Surveil 形式）と schema_version=3（GRE 形式）の両方に対応している。

---

## 設計方針の決定事項

| 項目 | 決定内容 |
|------|---------|
| 保存粒度 | ダメージ発生ごと（`AnnotationType_ModifiedLife` アノテーション1件 = 1レコード） |
| 保存形式 | 既存の `actions` テーブルに `life_total` カラム（INTEGER NULLABLE）を追加。`action_type = "life_change"` のレコードのみ値が入る |
| ライフの絶対値追跡 | パーサー内に `life_totals` 辞書（プレイヤー名 → 現在ライフ）を持ち、デルタ適用後の絶対値を記録する |
| 初期ライフ（schema_version=3） | GRE の `gameStateMessage.players[i].lifeTotal`（`systemSeatNumber` でプレイヤー特定）から取得する。まだ未初期化のプレイヤーにのみ適用し、二度目以降の gameStateMessage では上書きしない |
| 初期ライフ（schema_version=2） | `life_totals` 未登録のプレイヤーに対して 20 をデフォルトとして使用する |
| 対戦詳細での表示 | アクションログに `life_change` 行として表示する（副次実装） |

---

## データモデル

### `actions` テーブルへの追加

既存の `Action` モデルに `life_total` カラムを追加する。このカラムは `action_type = "life_change"` のレコードのみ値が入り、他のアクションタイプでは NULL となる。NULL 許容とすることで既存データへの遡及変更は不要。

型は INTEGER NULL。ライフが 0 以下になるケース（敗北直前）も整数値そのままで記録する。

### パーサー内のライフ追跡状態

**schema_version=3（`gre_parser.py`）**: `_GameContext` データクラスに `life_totals: dict[str, int]` フィールドを追加する。ゲームコンテキストのライフサイクルで保持され、ゲームをまたいで引き継がれない。

**schema_version=2（`surveil_parser.py`）**: `_parse_game` 関数内のローカル変数 `life_totals: dict[str, int]` として保持する。

---

## バックエンド

### schema_version=3 パーサー変更（`gre_parser.py`）

**初期ライフの取得**

`_handle_game_state` 内で `gsm.get("players", [])` を走査し、各プレイヤーの `systemSeatNumber` と `lifeTotal` を読み取る。`_seat_to_name()` でプレイヤー名に変換し、`game_ctx.life_totals` にまだキーが存在しない場合のみセットする（初回ゲームスタート時のみ初期化）。

**`_handle_life_change` の修正**

`ann.get("details")` から `"life"` キーのデルタ値を取得し、`ann.get("affectedIds")[0]` でシート番号を特定してプレイヤー名に変換する。`game_ctx.life_totals.get(player, 20)` で現在のライフを取得し、デルタを加算した新しい絶対値を `game_ctx.life_totals[player]` に更新する。`add_event` に `life_total=新しい絶対値` を追加する。

**`_SKIP_EVENT_TYPES` と `_EVENT_TO_ACTION` の変更**

`"life_change"` を `_SKIP_EVENT_TYPES` から除外し、`_EVENT_TO_ACTION` に `"life_change": "life_change"` を追加する。

**`_events_to_actions` の変更**

イベント処理ループ内で `et == "life_change"` の場合に `detail.get("life_total")` を取り出し、`GREGameAction` の `life_total` フィールドに渡す。`GREGameAction` TypedDict に `life_total: int | None` フィールドを追加する。

### schema_version=2 パーサー変更（`surveil_parser.py`）

`"life_change"` を `_SKIP_EVENTS` から除外し、`_EVENT_TO_ACTION` に追加する。`SurveilGameAction` TypedDict に `life_total: int | None` フィールドを追加する。

`_parse_game` 内でローカルの `life_totals` 辞書を保持し、`event_type == "life_change"` の場合に `event.get("delta", 0)` を取得してデルタ加算後の絶対値を算出・辞書を更新し、`SurveilGameAction` の `life_total` にセットする。

### インポートサービス変更（`import_service.py`）

`_convert_gre_result`（schema_version=3 の `GREParseResult` → `SurveilParseResult` 変換）内で `SurveilGameAction` を生成する際に `life_total=act.get("life_total")` を追加する。

`Action` モデルを生成する2箇所（schema_version=2 の `_import_v2` 相当と schema_version=3 経由の保存処理）それぞれに `life_total=act.get("life_total")` を追加する。

### エクスポート変更（`matches.py`）

AI エクスポートのアクションログ出力（Markdown テーブル形式）に「ライフ」列を追加する。`action_type = "life_change"` のレコードは `life_total` の値を表示し、他のアクションは `—` とする。アクションログ API レスポンス（`/api/matches/{id}/games/{id}/actions`）にも `life_total` フィールドを追加する。

---

## フロントエンド（対戦詳細への副次表示）

`ActionLog.vue` コンポーネントのアクションログ行表示において、`action_type = "life_change"` 行を薄赤背景（`.action-log__row--life`）で表示する。`♥ N` 形式でライフ絶対値を `action-log__life`（赤色）として行内に表示する。`ACTION_LABELS` に `life_change: 'ライフ変動'` を追加する。

`frontend/src/api/matches.ts` の `ActionEntry` インターフェースに `life_total: number | null` フィールドを追加する。

---

## エッジケース

| ケース | 対応 |
|--------|------|
| MTGO インポート | `life_total` は NULL のままとする。エクスポート出力にも `—` と表示される |
| ゲーム開始前に `gameStateMessage` が来ない | `life_totals` が未初期化のまま `life_change` が来た場合は 20 をデフォルトとして算出する |
| ライフ回復（デルタが正） | 通常のライフ変動と同様に記録する。絶対値が増加する |
| ライフが 0 以下 | そのまま記録する。ログの順序によっては終了直前に 0 になる可能性がある |
| 複数プレイヤーが同時にライフ変動 | アノテーションは1プレイヤーずつ個別に発火されるため、sequence 順に個別レコードとして保存される |
| 既存インポート済みデータ | 遡及適用しない。`life_total` カラムは NULL のまま |

---

## 変更ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `backend/models/core.py` | `Action` モデルに `life_total: int \| None` カラム追加 |
| `backend/database.py` | マイグレーション（`actions.life_total` カラム追加） |
| `backend/parser/gre_parser.py` | `GREGameAction` に `life_total` フィールド追加、`_GameContext` に `life_totals` 辞書追加、`_handle_game_state` で初期値取得、`_handle_life_change` で絶対値追跡・イベントに付加、`_SKIP_EVENT_TYPES` から除外・`_EVENT_TO_ACTION` に追加、`_events_to_actions` で `life_total` を `GREGameAction` に渡す |
| `backend/parser/surveil_parser.py` | `SurveilGameAction` に `life_total` フィールド追加、`_SKIP_EVENTS` から除外・`_EVENT_TO_ACTION` に追加、`_parse_game` でライフ追跡・`life_total` 付与 |
| `backend/services/import_service.py` | `_convert_gre_result` の `SurveilGameAction` 生成と `Action` 保存2箇所に `life_total` を追加 |
| `backend/app/routers/matches.py` | アクションログ API レスポンスと AI エクスポート Markdown テーブルに `life_total` / ライフ列を追加 |
| `frontend/src/api/matches.ts` | `ActionEntry` に `life_total: number \| null` フィールド追加 |
| `frontend/src/components/ActionLog.vue` | `life_change` 行の薄赤背景表示・`♥ N` 形式ライフ表示・`ACTION_LABELS` に追加 |
