# DB 設計

## 概要

- DB: SQLite
- ファイルパス: `database/mtgo.db`
- ORM: SQLAlchemy 2.x

> **API キーは SQLite に保存しない。**
> OS キーストア（Windows: Credential Manager / Mac: Keychain）に `keyring` ライブラリ経由で保存する。
> SQLite には非機密の設定値（LLM プロバイダー等）のみ保存する。

---

## ER 図

```
settings（独立）

card_legality（独立・Scryfall キャッシュ）

prompt_templates（独立）

question_sets
  │
  └──< question_items

analysis_sessions
  │
  └──< analysis_messages

matches
  │
  ├──< games
  │       │
  │       └──< actions
  │
  └──< match_players
            │
            └── deck_versions（nullable FK）

deck_definitions
  │
  └──< deck_definition_cards
```

---

## テーブル定義

### `settings`（アプリ設定）

非機密の設定値のみを管理する。API キーはここに保存しない。

| カラム | 型 | 制約 | 説明 |
|--------|----|------|------|
| `key` | TEXT | PRIMARY KEY | 設定キー |
| `value` | TEXT | NOT NULL | 設定値 |

**初期データ**

| key | value | 説明 |
|-----|-------|------|
| `llm_provider` | `"claude"` | 使用する LLM プロバイダー（`"claude"` / `"openai"`）。デフォルトは `"claude"` |

---

### `card_legality`（カードフォーマット適正キャッシュ）

Scryfall API のレスポンスをキャッシュする。インポート時に参照し、未取得カードのみ Scryfall にリクエストする。

| カラム | 型 | 制約 | 説明 |
|--------|----|------|------|
| `multiverse_id` | INTEGER | PRIMARY KEY | Scryfall multiverse ID |
| `card_name` | TEXT | NOT NULL | カード名 |
| `standard` | TEXT | NOT NULL | `legal` / `not_legal` / `banned` |
| `pioneer` | TEXT | NOT NULL | `legal` / `not_legal` / `banned` |
| `modern` | TEXT | NOT NULL | `legal` / `not_legal` / `banned` |
| `pauper` | TEXT | NOT NULL | `legal` / `not_legal` / `banned` |
| `legacy` | TEXT | NOT NULL | `legal` / `not_legal` / `banned` |
| `vintage` | TEXT | NOT NULL | `legal` / `not_legal` / `banned` |
| `fetched_at` | DATETIME | NOT NULL | Scryfall から取得した日時 |

**フォーマット判定ロジック（インポート時）**

1. マッチ内の全 `play` / `cast` アクションからカード名と `multiverse_id` を収集
2. `card_legality` テーブルを参照し、未キャッシュのカードのみ Scryfall API で取得・保存
3. 収集したカードの適正情報を集計し、最も限定的なフォーマット（全カードが `legal` な中で最も制限の厳しいもの）を `matches.format` に設定
4. 判定できない場合（基本土地のみ・アクションなし等）は `unknown` を設定

**フォーマット優先順位**（より制限が厳しい順）

`standard` > `pioneer` > `modern` > `pauper` > `legacy` > `vintage` > `unknown`

---

## Scryfall API 連携

### 概要

カードのフォーマット適正情報を Scryfall API から取得し、`card_legality` テーブルにキャッシュする。

### 使用エンドポイント

```
GET https://api.scryfall.com/cards/multiverse/{multiverse_id}
```

**レスポンス（抜粋）**

```json
{
  "name": "Lightning Bolt",
  "legalities": {
    "standard":  "not_legal",
    "pioneer":   "not_legal",
    "modern":    "legal",
    "pauper":    "legal",
    "legacy":    "legal",
    "vintage":   "legal"
  }
}
```

取得する情報: `name`（カード名確認用）、`legalities`（6フォーマット分）

### レート制限

Scryfall の利用規約に従い、**リクエスト間に 100ms 以上の間隔**を設ける（推奨: 10 req/sec 以下）。

1マッチのインポートで未キャッシュのカードが多い場合でも、順次リクエストで対応する。

### エラー時のフォールバック

| 状況 | 対応 |
|------|------|
| HTTP 404（カードが見つからない） | そのカードをスキップ（判定対象から除外） |
| ネットワークエラー / タイムアウト | そのカードをスキップ |
| 全カードがスキップされた | `matches.format = "unknown"` |

エラーが発生してもインポート処理は中断しない。フォーマット判定が不完全な場合は `unknown` を設定する。

### キャッシュ有効期限

`fetched_at` による有効期限チェックは**初期フェーズでは行わない**。

一度キャッシュされたカードは永続的に再利用する（カードのフォーマット適正は頻繁に変わらないため）。将来的なフォーマット変更への対応は拡張候補とする。

---

### `matches`（対戦）

| カラム | 型 | 制約 | 説明 |
|--------|----|------|------|
| `id` | TEXT | PRIMARY KEY | マッチ ID（ログから抽出） |
| `played_at` | DATETIME | NOT NULL | 対戦日時 |
| `match_winner` | TEXT | NOT NULL | 勝者プレイヤー名 |
| `game_count` | INTEGER | NOT NULL | ゲーム数 |
| `format` | TEXT | | フォーマット（`standard` / `pioneer` / `modern` / `pauper` / `legacy` / `vintage` / `unknown`） |
| `imported_at` | DATETIME | NOT NULL | インポート日時 |

---

### `match_players`（対戦参加プレイヤー）

| カラム | 型 | 制約 | 説明 |
|--------|----|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | - |
| `match_id` | TEXT | FK → matches.id | 対戦ID |
| `player_name` | TEXT | NOT NULL | プレイヤー名 |
| `seat` | INTEGER | NOT NULL | 席順（1 or 2） |
| `deck_name` | TEXT | | 使用デッキ名（ユーザーが手動タグ付け、NULL 可） |
| `game_plan` | TEXT | | ゲームプラン（`aggro` / `midrange` / `control` / `combo` / `unknown`、NULL 可） |
| `deck_version_id` | INTEGER | FK → deck_versions.id（NULL 可、SET NULL） | 紐づけたデッキバージョン（未設定は NULL） |

---

### `games`（ゲーム）

| カラム | 型 | 制約 | 説明 |
|--------|----|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | - |
| `match_id` | TEXT | FK → matches.id | 対戦ID |
| `game_number` | INTEGER | NOT NULL | ゲーム番号（1始まり） |
| `winner` | TEXT | NOT NULL | ゲーム勝者プレイヤー名 |
| `turns` | INTEGER | NOT NULL | 総ターン数 |
| `first_player` | TEXT | NOT NULL | 先手プレイヤー名 |

---

### `mulligans`（マリガン）

| カラム | 型 | 制約 | 説明 |
|--------|----|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | - |
| `game_id` | INTEGER | FK → games.id | ゲームID |
| `player_name` | TEXT | NOT NULL | プレイヤー名 |
| `count` | INTEGER | NOT NULL | マリガン回数 |

---

### `actions`（アクション）

| カラム | 型 | 制約 | 説明 |
|--------|----|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | - |
| `game_id` | INTEGER | FK → games.id | ゲームID |
| `turn` | INTEGER | NOT NULL | ターン番号 |
| `player_name` | TEXT | NOT NULL | アクション実行プレイヤー |
| `action_type` | TEXT | NOT NULL | アクション種別（下記一覧参照） |
| `card_name` | TEXT | | カード名（なければ NULL） |
| `sequence` | INTEGER | NOT NULL | ターン内の順番 |

> `multiverse_id` はパーサー出力には含まれるが、`actions` テーブルには保存しない。`ImportService` がフォーマット推定のために一時使用した後、破棄する（詳細は `04_parser-design.md` 参照）。

---

## `actions.action_type` 値一覧

| 値 | 日本語名 | 対応するメッセージパターン |
|----|---------|--------------------------|
| `play` | 土地プレイ | `plays @[...]` |
| `cast` | 呪文唱える | `casts @[...]` |
| `activate` | 起動型能力 | `activates an ability of @[...]` |
| `trigger` | 誘発型能力 | `puts triggered ability from @[...]` |
| `attack` | 攻撃 | `is being attacked by @[...]` |
| `draw` | ドロー | `draws a card / draws N cards` |
| `discard` | 捨てる | `discards @[...]` |
| `reveal` | 公開 | `reveals @[...]` |
| `add_counter` | カウンター追加 | `puts ... counter on` |
| `remove_counter` | カウンター除去 | `removes ... counter` |
| `mulligan` | マリガン | `mulligans to N cards.` |

---

## インデックス

| テーブル | カラム | 理由 |
|----------|--------|------|
| `games` | `match_id` | 対戦詳細取得のため |
| `actions` | `game_id` | ゲームアクション取得のため |
| `match_players` | `player_name` | プレイヤー別集計のため |
| `match_players` | `deck_name` | デッキ別集計のため |
| `mulligans` | `game_id` | ゲーム別マリガン取得のため |
| `card_legality` | `card_name` | カード名検索のため |
| `question_items` | `question_set_id` | セット別質問取得のため |
| `analysis_sessions` | `player_name` | プレイヤー別セッション一覧のため |
| `analysis_messages` | `session_id` | セッション別メッセージ取得のため |

---

## 初期マイグレーション方針

- SQLAlchemy の `Base.metadata.create_all()` で起動時に自動生成
- マイグレーション管理ツール（Alembic）は初期フェーズでは不使用

---

### `prompt_templates`（プロンプトテンプレート）

AI チャット時に使用するシステムプロンプトのテンプレートを管理する。

| カラム | 型 | 制約 | 説明 |
|--------|----|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | - |
| `name` | TEXT | NOT NULL | テンプレート名 |
| `content` | TEXT | NOT NULL | システムプロンプト本文（`{player_name}` / `{stats_text}` プレースホルダーを含む） |
| `is_default` | INTEGER | NOT NULL DEFAULT 0 | デフォルトとして使用するか（1 = デフォルト、0以外は1件のみ） |
| `created_at` | DATETIME | NOT NULL | 作成日時 |

**初期データ**: `05_db-design.md` の「システムプロンプト（デフォルト）」の内容を1件投入する。

---

### `question_sets`（質問セット）

チャット画面に常時表示する定型質問のセットを管理する。

| カラム | 型 | 制約 | 説明 |
|--------|----|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | - |
| `name` | TEXT | NOT NULL | セット名 |
| `is_default` | INTEGER | NOT NULL DEFAULT 0 | デフォルトとして使用するか（1 = デフォルト、0以外は1件のみ） |
| `created_at` | DATETIME | NOT NULL | 作成日時 |

---

### `question_items`（定型質問）

質問セットに属する個々の定型質問。

| カラム | 型 | 制約 | 説明 |
|--------|----|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | - |
| `question_set_id` | INTEGER | FK → question_sets.id | 所属セット |
| `text` | TEXT | NOT NULL | 質問文 |
| `display_order` | INTEGER | NOT NULL | 表示順（昇順） |

**初期データ（基本分析セット）**

| display_order | text |
|--------------|------|
| 1 | 私のプレイの傾向を教えてください |
| 2 | 先手・後手の勝率の差について分析してください |
| 3 | マリガンの影響について詳しく教えてください |
| 4 | 改善できるポイントを教えてください |
| 5 | 直近の勝率推移を分析してください |

---

### `analysis_sessions`（AI チャットセッション）

AI 分析画面での会話セッションを管理する。

| カラム | 型 | 制約 | 説明 |
|--------|----|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | - |
| `player_name` | TEXT | NOT NULL | 対象プレイヤー名 |
| `prompt_template_id` | INTEGER | FK → prompt_templates.id（NULL 許容） | 使用したテンプレート（削除済みの場合 NULL） |
| `title` | TEXT | NOT NULL | セッションタイトル（最初のユーザーメッセージを 50 文字で切り出し） |
| `created_at` | DATETIME | NOT NULL | セッション開始日時 |
| `updated_at` | DATETIME | NOT NULL | 最終メッセージ日時 |

---

### `analysis_messages`（AI チャットメッセージ）

セッション内の個々のメッセージを管理する。

| カラム | 型 | 制約 | 説明 |
|--------|----|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | - |
| `session_id` | INTEGER | FK → analysis_sessions.id | 所属セッション |
| `role` | TEXT | NOT NULL | `user` または `assistant` |
| `content` | TEXT | NOT NULL | メッセージ本文 |
| `display_order` | INTEGER | NOT NULL | セッション内の順番（1始まり） |
| `created_at` | DATETIME | NOT NULL | メッセージ日時 |

---

---

### `deck_definitions`（デッキ定義）

デッキアーキタイプの識別定義を管理する。`player_name` が NULL の場合は全プレイヤー共通の定義。

| カラム | 型 | 制約 | 説明 |
|--------|----|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | - |
| `player_name` | TEXT | NULL 可 | プレイヤー固有定義の場合はプレイヤー名、共通定義の場合は NULL |
| `deck_name` | TEXT | NOT NULL | デッキ名（例: `"Spirits"`, `"Burn"`） |
| `format` | TEXT | NULL 可 | 適用フォーマット（NULL = 問わず） |
| `threshold` | INTEGER | NOT NULL DEFAULT 2 | マッチ判定に必要な最低シグネチャカード枚数 |

---

### `deck_definition_cards`（デッキ定義カード）

デッキ定義に紐付くシグネチャカードおよび除外カードを管理する。

| カラム | 型 | 制約 | 説明 |
|--------|----|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | - |
| `definition_id` | INTEGER | FK → deck_definitions.id | 所属デッキ定義 |
| `card_name` | TEXT | NOT NULL | カード名（英語） |
| `is_exclude` | INTEGER | NOT NULL DEFAULT 0 | 除外カードフラグ（0 = シグネチャカード、1 = 除外カード） |

**デッキ判定ロジック**

1. 除外カード（`is_exclude = 1`）が1枚でも使用カードに含まれていればその定義をスキップ
2. シグネチャカード（`is_exclude = 0`）の一致枚数が `threshold` 以上であればマッチと判定
3. 複数定義がマッチした場合の優先順位: 一致枚数が多い > プレイヤー固有定義 > 登録順が早い

---

## AI分析キャッシュについて

**キャッシュテーブルは設けない。**

チャット開始のたびに統計集計クエリを実行してシステムプロンプトを生成する。
100〜200マッチ程度のデータ量では集計処理は数十ミリ秒以内に収まるため、
キャッシュによる複雑化（無効化ロジック・陳腐化リスク）を避けシンプルな設計を優先する。
