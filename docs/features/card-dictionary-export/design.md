# カード辞書エクスポート 設計ドキュメント

## 概要

AI 用エクスポートに「カード辞書」タブを追加し、フィルター条件に合致する試合に登場したカードの詳細情報（マナコスト・タイプ・Oracle テキスト・スタッツ等）をテキストファイルとして出力する。LLM がカードの効果を把握した上で対戦ログを分析できるようにすることが目的。

---

## 実装ステータス

未実装（設計中）

---

## 背景・動機

AI 用エクスポートで出力した対戦ログを外部 LLM に分析させた際、LLM が各カードの効果を知らないために誤った分析を行うケースが多発した。カードの詳細情報を別ファイルとして提供することで、LLM がコンテキストを把握した上で分析できるようになる。

---

## 設計方針の決定事項

| 項目 | 決定内容 |
|------|---------|
| カードデータの保存先 | `cards` テーブルとは分離した専用テーブル（`card_cache`） |
| カードデータの取得方法 | Scryfall `/cards/named?exact=` から取得・キャッシュ |
| 出力形式 | 対戦ログとは別の独立したテキストファイル |
| 含めるカードの対象 | フィルター条件に合致する試合のアクションに登場したカード名の全ユニーク集合 |
| UI | AIExportView にタブを追加（フィルターバーを共有） |
| 未取得カードの出力 | カード名 + `（データ未取得）` 注記 |

---

## Scryfall レスポンスの調査結果

`/cards/named?exact=` で取得できる主要フィールドは以下の通り（全カードタイプ・サブタイプを網羅して調査済み）。

### 通常カード（Ragavan, Lightning Bolt, Wrenn and Six, Expressive Iteration）

| フィールド | 内容 | 例 |
|-----------|------|-----|
| `name` | カード名 | `"Ragavan, Nimble Pilferer"` |
| `mana_cost` | マナコスト記号列 | `"{R}"`, `"{R}{G}"` |
| `cmc` | マナ総量（浮動小数点） | `1.0`, `2.0` |
| `type_line` | タイプ行全文 | `"Legendary Creature — Monkey Pirate"` |
| `oracle_text` | Oracle テキスト | 能力テキスト全文 |
| `power` | パワー（文字列、クリーチャーのみ） | `"2"`, `"*"` |
| `toughness` | タフネス（文字列、クリーチャーのみ） | `"1"` |
| `loyalty` | 初期忠誠度（整数、PWのみ） | `3` |
| `colors` | 色配列 | `["R"]`, `["R","G"]` |
| `color_identity` | 色識別配列 | `["R","G"]` |
| `keywords` | キーワード能力配列 | `["Dash","Treasure"]` |

### 両面カード・Room・Battle（DFC 系）

トップレベルに `mana_cost` / `oracle_text` が存在せず `card_faces` 配列が存在する。

| カード種別 | 特記事項 |
|---|---|
| 通常 DFC（Delver of Secrets 等） | 表面に `mana_cost`・裏面は `mana_cost` 空文字 |
| Battle（Invasion of Alara 等） | 表面に `defense` フィールド、裏面は Sorcery 等 |
| Room（Dollmaker's Shop 等） | 両面とも `Enchantment — Room`、各面に独立した `mana_cost` |

### 土地固有フィールド

- `mana_cost`: `""` （空文字列）が返る。NULL として扱って保存する
- `produced_mana`: `["G"]` のように生成マナを配列で持つ

### エンチャント・サブタイプ（英雄譚・クラス・事件・カルトーシュ・部屋）

すべて `type_line` に含まれるだけで特別なフィールドなし（例: `"Enchantment — Class"`）。

### 同族（Kindred）

`type_line` に `"Kindred Instant — Shapeshifter"` のように含まれるだけ。特別なフィールドなし。

### 役割（Role）トークン

`is:token` フラグ付きのトークン。MTGO/MTGA のアクションログにカード名として登場しないため `card_cache` の対象外。

### 着陸船（Lander）

2025 年 3 月時点で Scryfall の `t:lander` 検索が 404 を返す（未収録または日本語訳が異なる可能性あり）。`type_line` に入ってくるだけのためスキーマへの影響なし。

### 保存対象外フィールド

`legalities`・`prices`・各種外部 ID（`tcgplayer_id` 等）・画像 URI は LLM 向けエクスポートには不要なため保存しない。

---

## データモデル

### 新規テーブル: `card_cache`

`cards` テーブルへの直接追加は行わない。`cards` テーブルはインポート時の重複チェック・scryfall_id 解決で頻繁にアクセスされ、大容量 TEXT カラムを同居させると不要な I/O が増加するため。

```
card_cache
  scryfall_id    TEXT  PRIMARY KEY    ← cards.scryfall_id への参照
  name           TEXT  NOT NULL       ← カード名（DFC/Room/Battle は "A // B" 形式）
  mana_cost      TEXT                 ← 土地は "" が返るため NULL 扱いに正規化して保存
  cmc            REAL  NOT NULL
  type_line      TEXT  NOT NULL
  oracle_text    TEXT                 ← DFC/Room/Battle は NULL（card_faces を参照）
  power          TEXT                 ← クリーチャー・機体（Vehicle）のみ
  toughness      TEXT                 ← 同上
  loyalty        TEXT                 ← プレインズウォーカーのみ（"*" 等に備え TEXT）
  colors         TEXT  NOT NULL       ← JSON 配列文字列: '["R","G"]'
  keywords       TEXT  NOT NULL       ← JSON 配列文字列: '["Flying","Haste"]'
  produced_mana  TEXT                 ← 土地のみ。JSON 配列文字列: '["G"]'
  card_faces     TEXT                 ← JSON 配列文字列（DFC / Room / Battle）、通常カードは NULL
  fetched_at     TEXT  NOT NULL       ← ISO 8601 タイムスタンプ
```

`card_faces` の各要素（JSON）。フェイスの種別によって持つフィールドが異なる。

```json
// クリーチャー面・通常 DFC
{ "name": "Delver of Secrets", "mana_cost": "{U}", "type_line": "Creature — Human Wizard",
  "oracle_text": "...", "power": "1", "toughness": "1" }

// Battle 面（defense フィールド）
{ "name": "Invasion of Alara", "mana_cost": "{W}{U}{B}{R}{G}", "type_line": "Battle — Siege",
  "oracle_text": "...", "defense": "7" }

// Battle 裏面（Sorcery 等）
{ "name": "Awaken the Maelstrom", "mana_cost": "", "type_line": "Sorcery",
  "oracle_text": "..." }

// Room 面（両面とも Enchantment — Room、各面に独立した mana_cost）
{ "name": "Dollmaker's Shop", "mana_cost": "{1}{W}", "type_line": "Enchantment — Room",
  "oracle_text": "..." }
```

**各カードタイプのフィールド対応表:**

| カードタイプ | mana_cost | oracle_text | power/toughness | loyalty | defense | card_faces |
|---|---|---|---|---|---|---|
| クリーチャー | ✅ | ✅ | ✅ | — | — | DFC のみ |
| 機体（Vehicle） | ✅ | ✅ | ✅（搭乗時） | — | — | — |
| PW | ✅ | ✅ | — | ✅ | — | — |
| Battle | ✅（表面） | — | — | — | card_faces 内 | ✅（必須） |
| インスタント/ソーサリー | ✅ | ✅ | — | — | — | Kindred 等 |
| エンチャント各種 | ✅ | ✅ | — | — | — | Room のみ |
| アーティファクト各種 | ✅ | ✅ | — | — | — | — |
| 土地 | `""` → NULL | ✅ | — | — | — | — |
| 同族（Kindred） | ✅ | ✅ | — | — | — | — |

---

## バックエンド

### カードデータ取得（バックグラウンドジョブ統合）

既存の `card_image_service.py` の `fill_scryfall_ids()` は `/cards/named?exact=` または `/cards/mtgo/{id}` を呼び出して scryfall_id を解決している。このレスポンスにカードデータが全て含まれているため、**同じリクエストの中で card_cache への保存も行う**。追加の API 呼び出しは発生しない。

処理の流れ:

1. Scryfall レスポンスから必要フィールドを抽出
2. `card_cache` テーブルへ upsert（既に存在する場合は上書きしない）
3. `scryfall_enabled=false` の場合はスキップ（scryfall_id 解決スキップと同じ条件）

既存の scryfall_id が解決済みで `card_cache` に未登録のカードへの遡及取得は今回のスコープ外とする（新規インポート分から順次蓄積）。

### 新規エンドポイント

#### `GET /api/matches/export/card-dictionary/count`

フィルター条件に合致する試合のアクションから抽出されるユニークなカード名の件数を返す。

クエリパラメータ: 既存の対戦フィルターと同一（`player`, `opponent`, `deck_ids`, `decks`, `version_id`, `opponent_decks`, `format`, `date_from`, `date_to`）

レスポンス:
```json
{
  "total": 87,
  "cached": 82,
  "missing": 5
}
```

#### `GET /api/matches/export/card-dictionary`

カード辞書を Markdown テキスト（text/plain）で返す。クエリパラメータは同上。

### カード名収集ロジック

```python
SELECT DISTINCT a.card_name
FROM actions a
JOIN games g ON a.game_id = g.id
JOIN matches m ON g.match_id = m.id
WHERE [フィルター条件]
  AND a.card_name IS NOT NULL
ORDER BY a.card_name
```

抽出したカード名について `card_cache` を JOIN してカードデータを取得する。`card_cache` に存在しないカードはカード名 + 「（データ未取得）」注記で出力する。

---

## 出力フォーマット

### 通常カード

```markdown
## Ragavan, Nimble Pilferer
マナコスト: {R}（CMC: 1）
タイプ: Legendary Creature — Monkey Pirate
P/T: 2/1
キーワード: Dash, Treasure
テキスト:
Whenever Ragavan deals combat damage to a player, create a Treasure token and exile the top card of that player's library. Until end of turn, you may cast that card.
Dash {1}{R} (You may cast this spell for its dash cost. If you do, it gains haste, and it's returned from the battlefield to its owner's hand at the beginning of the next end step.)
```

### プレインズウォーカー

```markdown
## Wrenn and Six
マナコスト: {R}{G}（CMC: 2）
タイプ: Legendary Planeswalker — Wrenn
初期忠誠度: 3
テキスト:
+1: Return up to one target land card from your graveyard to your hand.
−1: Wrenn and Six deals 1 damage to any target.
−7: You get an emblem with ...
```

### 両面カード（DFC）

```markdown
## Delver of Secrets // Insectile Aberration
タイプ: Creature — Human Wizard // Creature — Human Insect
キーワード: Flying, Transform
（両面カード）

表面 — Delver of Secrets
  マナコスト: {U}（CMC: 1）  P/T: 1/1
  テキスト: At the beginning of your upkeep, look at the top card of your library. You may reveal that card. If an instant or sorcery card is revealed this way, transform this creature.

裏面 — Insectile Aberration
  P/T: 3/2
  テキスト: Flying
```

### Battle カード

```markdown
## Invasion of Alara // Awaken the Maelstrom
タイプ: Battle — Siege // Sorcery
（バトル / 両面カード）

表面 — Invasion of Alara
  マナコスト: {W}{U}{B}{R}{G}（CMC: 5）  防衛: 7
  テキスト: When this Siege enters, exile cards from the top of your library...

裏面 — Awaken the Maelstrom
  テキスト: Awaken the Maelstrom is all colors...
```

### Room カード

```markdown
## Dollmaker's Shop // Porcelain Gallery
タイプ: Enchantment — Room // Enchantment — Room
（部屋 / 両面カード）

部屋1 — Dollmaker's Shop
  マナコスト: {1}{W}
  テキスト: ...

部屋2 — Porcelain Gallery
  マナコスト: {4}{W}{W}
  テキスト: ...
```

### 土地

```markdown
## Arid Mesa
タイプ: Land
テキスト:
{T}, Pay 1 life, Sacrifice this land: Search your library for a Mountain or Plains card, put it onto the battlefield, then shuffle.

## Forest
タイプ: Basic Land — Forest
生成マナ: {G}
テキスト:
({T}: Add {G}.)
```

### データ未取得カード

```markdown
## Ancient Stirrings
（データ未取得）
```

### ファイル全体の構成

```markdown
# カード辞書

対象カード: 87 種類（うちデータ未取得: 5 種類）

---

## Ancient Stirrings
（データ未取得）

---

## Chord of Calling
マナコスト: {X}{G}{G}{G}（CMC: 3）
タイプ: Sorcery
キーワード: Convoke
テキスト:
Convoke (...)
Search your library for a creature card, put it onto the battlefield, then shuffle.

---

（以降アルファベット順）
```

---

## フロントエンド

### AIExportView の変更

フィルターバーはタブの外側（上部）に配置し、両タブで共有する。

```
[フィルターバー]               ← 共有

[ 対戦ログ | カード辞書 ]      ← タブ切り替え

--- 対戦ログタブ（変更なし） ---
[対象: N件]
[出力内容チェックボックス × 6]
[件数上限]
[エクスポートボタン]

--- カード辞書タブ ---
[対象: N種類のカード（うちデータ未取得: M種類）]
[カード辞書をエクスポートボタン]
```

### 新規 API 関数（`frontend/src/api/matches.ts`）

```ts
export interface CardDictionaryCount {
  total: number
  cached: number
  missing: number
}

export async function fetchCardDictionaryCount(
  filters: MatchFilters
): Promise<CardDictionaryCount>

export async function fetchCardDictionary(
  filters: MatchFilters
): Promise<string>
```

### ダウンロードファイル名

```
scry_cards_{player}_{YYYYMMDDHHMMSS}.md
```

---

## エッジケース

| ケース | 対応 |
|--------|------|
| card_cache 未登録カード | カード名 + `（データ未取得）` を出力 |
| `scryfall_enabled=false` | キャッシュが溜まっていないためデータ未取得カードが多くなる。件数表示で通知 |
| 両面カード（DFC）・Room | `card_faces` を展開して表面・裏面を個別に出力 |
| Battle カード | `card_faces[0].defense` を「防衛」として出力 |
| 機体（Vehicle） | `power`/`toughness` あり。クリーチャーと同じ出力 |
| 土地 | `mana_cost` が空文字列 → マナコスト行を省略。`produced_mana` があれば出力 |
| 役割（Role）トークン | アクションログに登場しないため対象外 |
| MTGA デジタル専用カード | scryfall_id 未解決 → カード名 + `（データ未取得）` 出力 |
| `card_name IS NULL` のアクション | 収集対象外 |
| 着陸船（Lander） | `type_line` に含まれるだけ。スキーマ変更不要 |
| 基本土地（Plains, Island 等） | Scryfall に存在するためキャッシュ対象。出力に含める |

---

## 変更ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `backend/models.py` | `CardCache` モデル追加（`card_cache` テーブル: scryfall_id / name / mana_cost / cmc / type_line / oracle_text / power / toughness / loyalty / colors / keywords / produced_mana / card_faces / fetched_at） |
| `backend/database.py` | マイグレーション（`card_cache` テーブル作成） |
| `backend/services/card_image_service.py` | `fill_scryfall_ids()` 内で card_cache への保存を追加。土地の `mana_cost` 空文字を NULL 正規化、`defense` は `card_faces` JSON に含めて保存 |
| `backend/app/routers/matches.py` | `card-dictionary/count` と `card-dictionary` エンドポイント追加 |
| `frontend/src/api/matches.ts` | `fetchCardDictionaryCount()` / `fetchCardDictionary()` 追加 |
| `frontend/src/views/AIExportView.vue` | タブ切り替え UI 追加・カード辞書タブ実装 |
