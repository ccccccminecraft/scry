# DB スキーマ

- DB: SQLite（`database/mtgo.db`）
- ORM: SQLAlchemy 2.x（`backend/models/` 配下）
- マイグレーション: `Base.metadata.create_all()` + `init_db()` の ALTER TABLE で追加カラムを適用

---

## ER 図

```
settings            （独立）
card_legality       （独立・Scryfall キャッシュ）

matches
  ├──< match_players ──── deck_versions（nullable FK）
  └──< games
         ├──< actions
         └──< mulligans

decks
  └──< deck_versions
         └──< deck_version_cards ──── cards

deck_definitions
  └──< deck_definition_cards

prompt_templates    （独立）
question_sets
  └──< question_items
analysis_sessions ──── prompt_templates（nullable FK）
  └──< analysis_messages
```

---

## テーブル定義

### `settings`

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `key` | TEXT | PK | 設定キー |
| `value` | TEXT | NOT NULL | 設定値 |

主なキー: `llm_provider`, `anthropic_api_key`, `default_player`, `quick_import_folder`, `surveil_folder`, `min_player_matches`, `min_deck_matches`

---

### `card_legality`

Scryfall API レスポンスのキャッシュ。カード名で引く。

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `card_name` | TEXT | PK | カード名（英語） |
| `standard` | TEXT | NOT NULL | `legal` / `not_legal` / `banned` |
| `pioneer` | TEXT | NOT NULL | 同上 |
| `modern` | TEXT | NOT NULL | 同上 |
| `pauper` | TEXT | NOT NULL | 同上 |
| `legacy` | TEXT | NOT NULL | 同上 |
| `vintage` | TEXT | NOT NULL | 同上 |
| `fetched_at` | DATETIME | NOT NULL | 取得日時 |

フォーマット判定優先順位: `standard > pioneer > modern > pauper > legacy > vintage`
banned カードは legal 扱い（プレイ時点では合法だった可能性）。

---

### `matches`

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | TEXT | PK | マッチ ID（ログから抽出） |
| `played_at` | DATETIME | NOT NULL | 対戦日時 |
| `match_winner` | TEXT | NOT NULL | 勝者プレイヤー名 |
| `game_count` | INTEGER | NOT NULL | ゲーム数 |
| `format` | TEXT | NULL | フォーマット（standard / pioneer / modern / pauper / legacy / vintage / unknown） |
| `imported_at` | DATETIME | NOT NULL | インポート日時 |
| `source` | TEXT | NOT NULL DEFAULT 'mtgo' | インポート元（`mtgo` / `mtga`） |

---

### `match_players`

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | INTEGER | PK AUTOINCREMENT | - |
| `match_id` | TEXT | FK → matches.id | 対戦 ID |
| `player_name` | TEXT | NOT NULL | プレイヤー名 |
| `seat` | INTEGER | NOT NULL | 席順（1 or 2） |
| `deck_name` | TEXT | NULL | 使用デッキ名（手動タグ） |
| `game_plan` | TEXT | NULL | ゲームプラン（aggro / midrange / control / combo） |
| `deck_json` | TEXT | NULL | MTGA デッキリスト JSON（source=mtga の場合のみ） |
| `deck_version_id` | INTEGER | FK → deck_versions.id（SET NULL） | 紐づけたデッキバージョン |

インデックス: `player_name`, `deck_name`

---

### `games`

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | INTEGER | PK AUTOINCREMENT | - |
| `match_id` | TEXT | FK → matches.id | 対戦 ID |
| `game_number` | INTEGER | NOT NULL | ゲーム番号（1始まり） |
| `winner` | TEXT | NOT NULL | ゲーム勝者プレイヤー名 |
| `turns` | INTEGER | NOT NULL | 総ターン数 |
| `first_player` | TEXT | NOT NULL | 先手プレイヤー名 |

インデックス: `match_id`

---

### `mulligans`

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | INTEGER | PK AUTOINCREMENT | - |
| `game_id` | INTEGER | FK → games.id | ゲーム ID |
| `player_name` | TEXT | NOT NULL | プレイヤー名 |
| `count` | INTEGER | NOT NULL | マリガン回数 |

インデックス: `game_id`

---

### `actions`

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | INTEGER | PK AUTOINCREMENT | - |
| `game_id` | INTEGER | FK → games.id | ゲーム ID |
| `turn` | INTEGER | NOT NULL | ターン番号 |
| `active_player` | TEXT | NOT NULL DEFAULT '' | アクティブプレイヤー（手番のプレイヤー） |
| `player_name` | TEXT | NOT NULL | アクション実行プレイヤー |
| `action_type` | TEXT | NOT NULL | アクション種別（下記参照） |
| `card_name` | TEXT | NULL | カード名 |
| `target_name` | TEXT | NULL | 対象カード名 |
| `sequence` | INTEGER | NOT NULL | ターン内の順番 |
| `phase` | TEXT | NULL | フェーズ（MTGA のみ: main1 / main2 / combat 等） |

インデックス: `game_id`

**action_type 値一覧**

| 値 | 意味 | MTGO | MTGA |
|----|------|:----:|:----:|
| `play` | 土地プレイ | ✓ | ✓ |
| `cast` | 呪文を唱える | ✓ | ✓ |
| `activate` | 起動型能力 | ✓ | ✓ |
| `trigger` | 誘発型能力 | ✓ | ✓ |
| `attack` | 攻撃 | ✓ | ✓ |
| `block` | ブロック | | ✓ |
| `draw` | ドロー | ✓ | ✓ |
| `discard` | 捨てる | ✓ | ✓ |
| `mill` | ミル | | ✓ |
| `damage` | ダメージ | | ✓ |
| `reveal` | 公開 | ✓ | |
| `add_counter` | カウンター追加 | ✓ | |
| `remove_counter` | カウンター除去 | ✓ | |
| `mulligan` | マリガン | ✓ | ✓ |

---

### `cards`

Scryfall 画像キャッシュおよびデッキリストで使用。

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | INTEGER | PK AUTOINCREMENT | - |
| `name` | TEXT | NOT NULL | カード名（英語） |
| `scryfall_id` | TEXT | UNIQUE NULL | Scryfall カード ID |
| `mtgo_id` | INTEGER | UNIQUE NULL | MTGO カタログ ID（.dek インポート時） |
| `image_url` | TEXT | NULL | Scryfall 画像 URL |

テキスト入力 → `mtgo_id=NULL`、`.dek` インポート → `mtgo_id=CatID`。
`scryfall_id` はバックグラウンドで非同期解決（50ms 間隔で Scryfall API）。

---

### `decks`

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | INTEGER | PK AUTOINCREMENT | - |
| `name` | TEXT | NOT NULL | デッキ名 |
| `format` | TEXT | NULL | フォーマット |
| `created_at` | DATETIME | NOT NULL | 作成日時 |
| `is_archived` | BOOLEAN | NOT NULL DEFAULT false | アーカイブ済みフラグ |

---

### `deck_versions`

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | INTEGER | PK AUTOINCREMENT | - |
| `deck_id` | INTEGER | FK → decks.id | 所属デッキ |
| `version_number` | INTEGER | NOT NULL | バージョン番号（デッキ内で連番） |
| `memo` | TEXT | NULL | メモ |
| `registered_at` | DATETIME | NOT NULL | 登録日時 |
| `is_archived` | BOOLEAN | NOT NULL DEFAULT false | アーカイブ済みフラグ |

制約: UNIQUE(`deck_id`, `version_number`)
インデックス: `deck_id`

---

### `deck_version_cards`

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | INTEGER | PK AUTOINCREMENT | - |
| `deck_version_id` | INTEGER | FK → deck_versions.id | 所属バージョン |
| `card_id` | INTEGER | FK → cards.id | カード |
| `quantity` | INTEGER | NOT NULL | 枚数 |
| `is_sideboard` | BOOLEAN | NOT NULL DEFAULT false | サイドボードフラグ |

インデックス: `deck_version_id`

---

### `deck_definitions`

デッキアーキタイプの自動識別定義。

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | INTEGER | PK AUTOINCREMENT | - |
| `player_name` | TEXT | NULL | プレイヤー固有定義（NULL = 全共通） |
| `deck_name` | TEXT | NOT NULL | デッキ名 |
| `format` | TEXT | NULL | 適用フォーマット（NULL = 問わず） |
| `threshold` | INTEGER | NOT NULL DEFAULT 2 | 判定に必要な最低シグネチャカード枚数 |

---

### `deck_definition_cards`

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | INTEGER | PK AUTOINCREMENT | - |
| `definition_id` | INTEGER | FK → deck_definitions.id | 所属定義 |
| `card_name` | TEXT | NOT NULL | カード名（英語） |
| `is_exclude` | INTEGER | NOT NULL DEFAULT 0 | 除外カードフラグ（1 = 除外） |

判定ロジック: 除外カード含む → スキップ。シグネチャカード一致数 ≥ threshold → マッチ。

---

### `prompt_templates`

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | INTEGER | PK AUTOINCREMENT | - |
| `name` | TEXT | NOT NULL | テンプレート名 |
| `content` | TEXT | NOT NULL | システムプロンプト本文 |
| `is_default` | INTEGER | NOT NULL DEFAULT 0 | デフォルトフラグ（1件のみ） |
| `created_at` | DATETIME | NOT NULL | 作成日時 |

---

### `question_sets` / `question_items`

AI 分析画面の定型質問を管理。

**question_sets**

| カラム | 型 | 制約 |
|--------|-----|------|
| `id` | INTEGER | PK AUTOINCREMENT |
| `name` | TEXT | NOT NULL |
| `is_default` | INTEGER | NOT NULL DEFAULT 0 |
| `created_at` | DATETIME | NOT NULL |

**question_items**

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | INTEGER | PK AUTOINCREMENT | - |
| `question_set_id` | INTEGER | FK → question_sets.id | 所属セット |
| `text` | TEXT | NOT NULL | 質問文 |
| `display_order` | INTEGER | NOT NULL | 表示順（昇順） |

インデックス: `question_set_id`

---

### `analysis_sessions`

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | INTEGER | PK AUTOINCREMENT | - |
| `player_name` | TEXT | NOT NULL | 対象プレイヤー名 |
| `prompt_template_id` | INTEGER | FK → prompt_templates.id（NULL 可） | 使用テンプレート |
| `title` | TEXT | NOT NULL | セッションタイトル |
| `filter_opponent` | TEXT | NULL | フィルター: 相手プレイヤー |
| `filter_deck` | TEXT | NULL | フィルター: 自デッキ名 |
| `filter_opponent_deck` | TEXT | NULL | フィルター: 相手デッキ名 |
| `filter_format` | TEXT | NULL | フィルター: フォーマット |
| `filter_date_from` | TEXT | NULL | フィルター: 開始日 |
| `filter_date_to` | TEXT | NULL | フィルター: 終了日 |
| `created_at` | DATETIME | NOT NULL | 作成日時 |
| `updated_at` | DATETIME | NOT NULL | 最終更新日時 |

インデックス: `player_name`

---

### `analysis_messages`

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | INTEGER | PK AUTOINCREMENT | - |
| `session_id` | INTEGER | FK → analysis_sessions.id | 所属セッション |
| `role` | TEXT | NOT NULL | `user` / `assistant` |
| `content` | TEXT | NOT NULL | メッセージ本文 |
| `display_order` | INTEGER | NOT NULL | セッション内順番（1始まり） |
| `created_at` | DATETIME | NOT NULL | メッセージ日時 |

インデックス: `session_id`
