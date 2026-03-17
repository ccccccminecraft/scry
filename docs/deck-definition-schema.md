# Deck Definition JSON Schema

Scry のデッキ定義インポート/エクスポートに使用する JSON フォーマット仕様。

---

## 概要

このフォーマットはデッキアーキタイプのシグネチャカード定義を記述するためのものです。
Scry 本体での手動管理・Claude API 生成・外部ツール（mtggoldfish-to-scry 等）の出力に共通して使用します。

`player_name`（プレイヤー固有 or 共通）はインポート時に Scry 側で指定するため、このファイルには含みません。

---

## トップレベル構造

```json
{
  "version": "1.0",
  "generated_at": "2025-01-01T00:00:00Z",
  "source": "MTGGoldfish",
  "format": "modern",
  "definitions": [ ... ]
}
```

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `version` | string | ✓ | スキーマバージョン（現在は `"1.0"`） |
| `generated_at` | string (ISO 8601) | ✓ | 生成日時 |
| `source` | string | ✓ | データ取得元（例: `"MTGGoldfish"`, `"Claude"`, `"manual"`） |
| `format` | string \| null | — | ファイル全体のデフォルトフォーマット。各定義で上書き可能 |
| `definitions` | Definition[] | ✓ | デッキ定義の配列 |

---

## Definition オブジェクト

```json
{
  "deck_name": "Spirits",
  "format": "modern",
  "threshold": 2,
  "cards": [
    "Supreme Phantom",
    "Mausoleum Wanderer",
    "Spectral Sailor",
    "Rattlechains",
    "Spell Queller",
    "Shacklegeist"
  ],
  "exclude_cards": [
    "Ragavan, Nimble Pilferer"
  ],
  "tags": ["aggro", "tribal"]
}
```

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `deck_name` | string | ✓ | デッキ名（例: `"Spirits"`, `"Burn"`, `"Humans"`） |
| `format` | string \| null | — | フォーマット（省略時はトップレベルの `format` を使用。両方省略で問わず） |
| `threshold` | integer | — | マッチ判定に必要な最低シグネチャカード枚数（省略時: `2`） |
| `cards` | string[] | ✓ | シグネチャカード名のリスト（英語カード名） |
| `exclude_cards` | string[] | — | 除外カード名のリスト（省略時: `[]`）。リスト内のカードが1枚でも使用されていた場合、この定義はマッチしない |
| `tags` | string[] | — | 将来のフィルタリング用タグ（例: `["aggro", "tribal"]`）。現バージョンでは無視される |

---

## フォーマット値

`format` フィールドに指定できる値：

| 値 | 説明 |
|---|---|
| `"standard"` | スタンダード |
| `"pioneer"` | パイオニア |
| `"modern"` | モダン |
| `"pauper"` | ポーパー |
| `"legacy"` | レガシー |
| `"vintage"` | ヴィンテージ |
| `null` または省略 | フォーマット問わず |

---

## ファイル例

```json
{
  "version": "1.0",
  "generated_at": "2025-01-01T00:00:00Z",
  "source": "MTGGoldfish",
  "format": "modern",
  "definitions": [
    {
      "deck_name": "Spirits",
      "threshold": 2,
      "cards": [
        "Supreme Phantom",
        "Mausoleum Wanderer",
        "Spectral Sailor",
        "Rattlechains",
        "Spell Queller",
        "Shacklegeist"
      ],
      "exclude_cards": [
        "Ragavan, Nimble Pilferer"
      ],
      "tags": ["aggro", "tribal"]
    },
    {
      "deck_name": "Burn",
      "threshold": 3,
      "cards": [
        "Goblin Guide",
        "Monastery Swiftspear",
        "Eidolon of the Great Revel",
        "Lightning Bolt",
        "Lava Spike",
        "Shard Volley"
      ],
      "tags": ["aggro", "burn"]
    },
    {
      "deck_name": "Humans",
      "threshold": 2,
      "cards": [
        "Thalia, Guardian of Thraben",
        "Thalia's Lieutenant",
        "Coppercoat Vanguard",
        "Recruiter of the Guard",
        "Phantasmal Image",
        "Reflector Mage"
      ],
      "tags": ["aggro", "tribal"]
    },
    {
      "deck_name": "Murktide",
      "threshold": 2,
      "cards": [
        "Murktide Regent",
        "Dragon's Rage Channeler",
        "Ragavan, Nimble Pilferer",
        "Consider",
        "Mishra's Bauble"
      ],
      "tags": ["tempo", "control"]
    },
    {
      "deck_name": "Amulet Titan",
      "threshold": 2,
      "cards": [
        "Primeval Titan",
        "Amulet of Vigor",
        "Summoner's Pact",
        "Arboreal Grazer",
        "Dryad of the Ilysian Grove"
      ],
      "tags": ["combo", "ramp"]
    }
  ]
}
```

---

## インポート時の挙動（Scry）

1. `version` を確認し、未対応バージョンの場合はエラーを表示する
2. `definitions` を順に処理し、`deck_name` と `cards` が存在するものだけ登録する
3. `format` は Definition 側を優先し、省略時はトップレベルの `format` を使用する
4. `threshold` 省略時はデフォルト値 `2` を使用する
5. `exclude_cards` 省略時は除外カードなしとして登録する
6. `tags` は現バージョンでは保存しない（将来のバージョンアップで対応）
7. インポート時にプレイヤー指定（固有 or 共通）をユーザーが選択する
8. 同名のデッキ定義が既に存在する場合は**スキップ or 上書き**をユーザーが選択できる

---

## エクスポート時の挙動（Scry）

- `source` は `"Scry"` 固定
- `generated_at` は出力時刻
- `format` はトップレベルでは `null`（各定義に個別に含める）
- `player_name` は出力しない（インポート先で再指定する想定）
- `exclude_cards` は1件以上ある定義のみ出力する（空の場合は省略）

---

## 外部ツール（scry-deck-harvester）との連携

外部ツールはこのスキーマに準拠した JSON を出力することで Scry と連携できます。
外部ツールの仕様については別途ドキュメントを作成します。

### 外部ツールが出力すべきもの

- `source`: ツール名（例: `"scry-deck-harvester"`）
- `deck_name`: アーキタイプ名（英語）
- `cards`: メタゲームの各デッキで最も頻繁に採用されるカード群（目安: 上位8〜15枚）
- `threshold`: デッキの特徴度に応じて `2`〜`4` 程度を推奨

---

## バージョン履歴

| バージョン | 変更内容 |
|---|---|
| 1.0 | 初版 |
| 1.0 (追記) | `exclude_cards` フィールドを追加。除外カードが使用されていた場合にデッキ定義をマッチさせない機能 |
