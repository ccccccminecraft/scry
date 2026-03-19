# 詳細設計: デッキ構築管理機能

## 概要

デッキリストをバージョン管理する独立した機能。
各デッキは複数のバージョン（連番 + 任意メモ）を持ち、バージョンごとにメインデッキ・サイドボードのカードリストを管理する。
カード情報はマスタテーブルで正規化し、カード画像は Scryfall CDN から取得してローカルにキャッシュする。
試合との連携は本機能の完成後に別途設計する。

---

## 対象ファイル

| ファイル | 種別 |
|---------|------|
| `backend/models/decklist.py` | 新規作成 |
| `backend/models/__init__.py` | 編集（モデル登録） |
| `backend/app/routers/decklist.py` | 新規作成 |
| `backend/app/main.py` | 編集（ルーター登録） |
| `backend/services/card_image_service.py` | 新規作成 |
| `frontend/src/api/decklist.ts` | 新規作成 |
| `frontend/src/views/DeckBuilderView.vue` | 新規作成 |
| `frontend/src/router/index.ts` | 編集（ルート追加） |
| `frontend/src/components/GlobalNav.vue` | 編集（ナビ項目追加） |

---

## DB 設計

### テーブル構成

```
cards（カードマスタ）
├── id           INTEGER PK AUTOINCREMENT
├── name         TEXT NOT NULL          ← 正規カード名（版が異なれば複数レコードが存在し得る）
├── scryfall_id  TEXT UNIQUE NULL       ← Scryfall UUID（版ごとにユニーク・未解決時は NULL）
├── mtgo_id      INTEGER UNIQUE NULL    ← MTGO CatID（.dek の CatID 属性・テキスト入力由来は NULL）
└── image_url    TEXT NULL              ← Scryfall CDN URL（文字列のみ保存）

decks
├── id           INTEGER PK AUTOINCREMENT
├── name         TEXT NOT NULL
├── format       TEXT NULL
└── created_at   DATETIME NOT NULL

deck_versions
├── id              INTEGER PK AUTOINCREMENT
├── deck_id         INTEGER FK → decks.id (CASCADE DELETE)
├── version_number  INTEGER NOT NULL   ← デッキ内で 1 始まりの連番
├── memo            TEXT NULL
└── registered_at   DATETIME NOT NULL

deck_version_cards（中間テーブル）
├── id              INTEGER PK AUTOINCREMENT
├── deck_version_id INTEGER FK → deck_versions.id (CASCADE DELETE)
├── card_id         INTEGER FK → cards.id
├── quantity        INTEGER NOT NULL
└── is_sideboard    BOOLEAN NOT NULL DEFAULT 0
```

### リレーション

```
decks 1 ─── * deck_versions 1 ─── * deck_version_cards * ─── 1 cards
```

- デッキ削除 → バージョンを CASCADE DELETE → deck_version_cards を CASCADE DELETE
- `cards` は削除しない（他デッキからも参照されるため）
- `version_number` はデッキ内でユニーク（同一 `deck_id` で重複不可）

### cards テーブルにおける版の管理方針

同名カードでも版（プリント）が異なる場合は別レコードとして管理する。

| 入力方法 | レコードの識別方法 | 版の精度 |
|---------|-----------------|---------|
| テキスト入力 | カード名で検索・登録（`mtgo_id = NULL`） | Scryfall のデフォルト版 |
| `.dek` インポート | `CatID`（`mtgo_id`）で検索・登録 | MTGO で使用した版 |

- テキスト入力由来のカードは `mtgo_id = NULL` のレコードとして管理する
- `.dek` 由来のカードは `mtgo_id` を持つレコードとして管理し、テキスト入力由来レコードとは別に扱う
- 同じカード名でも `mtgo_id` の有無で別レコードになるため、デッキ内で使用した版の画像を正確に表示できる

### 既存テーブルとの関係

| テーブル | 役割 | 共通キー |
|---------|------|---------|
| `card_legality` | フォーマット合法性判定（インポート時） | `card_name` |
| `cards` | デッキ管理用カードマスタ（画像URL等） | `name` |

両テーブルはカード名をキーとして JOIN 可能だが、用途が異なるため独立して管理する。

---

## カード画像設計

### 画像ソース

Scryfall CDN（`cards.scryfall.io`）を使用する。業界標準であり、ほぼすべての主要 MTG ツール（Moxfield・Archidekt・17lands 等）が採用している。

**利用する画像サイズ**

| サイズ | 解像度 | 用途 |
|--------|--------|------|
| `small` | 146×204 JPG | カードリスト・サムネイル表示 |
| `normal` | 488×680 JPG | カード詳細・ホバープレビュー |

### ローカルキャッシュパス

| 環境 | キャッシュディレクトリ |
|------|----------------------|
| 開発環境（Docker） | `/database/image_cache/{small\|normal}/` |
| 本番環境（Windows） | `%APPDATA%\Scry\image_cache\{small\|normal}\` |

DB ファイル（`mtgo.db`）と同じディレクトリ配下に置くことで、バックアップ・移行時に一括管理できる。

```
開発環境（Docker volume: /database/）
└── /database/
    ├── mtgo.db
    └── image_cache/
        ├── small/
        │   └── {scryfall_id}.jpg
        └── normal/
            └── {scryfall_id}.jpg

本番環境（Windows: %APPDATA%\Scry\）
└── %APPDATA%\Scry\
    ├── mtgo.db
    └── image_cache\
        ├── small\
        │   └── {scryfall_id}.jpg
        └── normal\
            └── {scryfall_id}.jpg
```

キャッシュディレクトリのパスは `database.py` の `_get_database_url()` と同じロジックで導出する。

### `backend/services/card_image_service.py` の責務

- 環境（開発/本番）に応じたキャッシュディレクトリパスの解決
- ローカルキャッシュの有無確認と、なければ Scryfall CDN からの取得・保存
- カード名を Scryfall API に問い合わせて `scryfall_id` と `image_url` を取得し `cards` テーブルに保存（テキスト入力由来カードの補完）
- MTGO CatID を Scryfall API に問い合わせて `scryfall_id` と `image_url` を取得し `cards` テーブルに保存（`.dek` 由来カードの補完）

### カード画像取得 API

#### `GET /api/cards/{scryfall_id}/image`

**クエリパラメータ**

| パラメータ | デフォルト | 説明 |
|-----------|-----------|------|
| `size` | `small` | `small` または `normal` |

**処理フロー**

```
1. ローカルキャッシュに {size}/{scryfall_id}.jpg が存在するか確認
   ├─ 存在する → キャッシュファイルをそのまま返す
   └─ 存在しない → Scryfall CDN から取得してキャッシュに保存してから返す
```

**レスポンス**

| 項目 | 値 |
|------|-----|
| Content-Type | `image/jpeg` |
| ボディ | JPEG 画像バイナリ |

**エラー**

| 状況 | レスポンス |
|------|-----------|
| `scryfall_id` が不明 | 404 |
| Scryfall CDN 取得失敗 | 502 |

**Scryfall API 利用規約の遵守**

- `api.scryfall.com`（カードデータ取得）: リクエスト間隔 50〜100ms、10 req/sec 以下
- `cards.scryfall.io`（画像CDN）: レート制限なし
- 画像はローカルキャッシュに保存してよい（再配信・ホスティングは禁止）

---

## API 設計

### デッキ CRUD

#### `GET /api/decklist/decks`

デッキ一覧を返す。各デッキの最新バージョン情報も含む。

**レスポンス**

```json
[
  {
    "id": 1,
    "name": "UR Prowess",
    "format": "modern",
    "created_at": "2024-06-01T12:00:00",
    "latest_version": {
      "id": 3,
      "version_number": 3,
      "memo": "MH3後調整",
      "registered_at": "2024-06-15T09:00:00"
    }
  }
]
```

---

#### `POST /api/decklist/decks`

デッキを新規作成する。

**リクエスト**

```json
{ "name": "UR Prowess", "format": "modern" }
```

**レスポンス**: 作成したデッキオブジェクト

---

#### `PUT /api/decklist/decks/{deck_id}`

デッキの名前・フォーマットを更新する。

**リクエスト**

```json
{ "name": "UR Prowess", "format": "modern" }
```

---

#### `DELETE /api/decklist/decks/{deck_id}`

デッキとすべてのバージョン・中間テーブルレコードを削除する。
`cards` テーブルは削除しない。

---

### バージョン CRUD

#### `GET /api/decklist/decks/{deck_id}/versions`

バージョン一覧（カードリストは含まない）。

**レスポンス**

```json
[
  {
    "id": 1,
    "version_number": 1,
    "memo": "初期リスト",
    "registered_at": "2024-05-01T10:00:00",
    "main_count": 60,
    "side_count": 15
  }
]
```

---

#### `GET /api/decklist/decks/{deck_id}/versions/{version_id}`

バージョン詳細（カードリスト含む）。
各カードエントリには `card_name`・`quantity`・`scryfall_id`（未取得の場合は null）を含む。
フロントエンドは `scryfall_id` を使って `/api/cards/{scryfall_id}/image` を呼び出す。

**レスポンス**

```json
{
  "id": 2,
  "version_number": 2,
  "memo": "MH3後調整",
  "registered_at": "2024-06-15T09:00:00",
  "main": [
    { "card_name": "Lightning Bolt", "quantity": 4, "scryfall_id": "e3285e6b-..." },
    { "card_name": "Dragon's Rage Channeler", "quantity": 4, "scryfall_id": "5a4eee58-..." }
  ],
  "sideboard": [
    { "card_name": "Consign to Memory", "quantity": 4, "scryfall_id": "7e3fa7b1-..." }
  ]
}
```

---

#### `POST /api/decklist/decks/{deck_id}/versions`

新バージョンを作成する。カードリストはテキスト形式または `.dek` ファイルで入力。

**リクエスト（テキスト形式）**

```json
{
  "memo": "MH3後調整",
  "source": "text",
  "text": "4 Lightning Bolt\n4 Dragon's Rage Channeler\n...\n\nSideboard\n4 Consign to Memory"
}
```

**リクエスト（.dek ファイル）**

`multipart/form-data`

| フィールド | 内容 |
|-----------|------|
| `memo` | バージョンメモ（省略可） |
| `file` | `.dek` ファイル |

**処理フロー（テキスト形式）**

```
1. テキストをパースしてカードリストを取得（カード名・枚数・サイドボード区分）
2. カード名ごとに cards テーブルを検索（mtgo_id IS NULL のレコードを対象）
   ├─ 存在する → card_id を取得
   └─ 存在しない → cards に新規登録（scryfall_id・mtgo_id・image_url は未取得状態）
3. version_number を計算（該当デッキの現在の最大値 + 1）
4. バージョンレコードを登録
5. カードリストを一括登録（card_id を使用）
6. 作成したバージョン詳細を返す
7. scryfall_id 未取得カードをバックグラウンドで非同期補完（後述）
```

**処理フロー（.dek ファイル）**

```
1. XML をパースしてカードリストを取得（カード名・枚数・サイドボード区分・CatID）
2. CatID ごとに cards テーブルを検索（mtgo_id で検索）
   ├─ 存在する → card_id を取得
   └─ 存在しない → cards に新規登録（mtgo_id に CatID をセット、scryfall_id・image_url は未取得状態）
3. version_number を計算（該当デッキの現在の最大値 + 1）
4. バージョンレコードを登録
5. カードリストを一括登録（card_id を使用）
6. 作成したバージョン詳細を返す
7. scryfall_id 未取得カードをバックグラウンドで非同期補完（後述）
```

**エラー**

| 状況 | レスポンス |
|------|-----------|
| テキストのパース失敗 | 400（エラー行番号を含むメッセージ） |
| .dek が不正な XML / 想定外の構造 | 400 |
| メインデッキ 0 枚 | 400 |

---

#### `PUT /api/decklist/decks/{deck_id}/versions/{version_id}`

バージョンのメモとカードリストを更新する。
既存のカードリストを全件削除した後、新しい内容で再登録する。
入力形式はテキスト形式のみ対応。

---

#### `DELETE /api/decklist/decks/{deck_id}/versions/{version_id}`

バージョンとそのカードリストを削除する。
削除後に `version_number` の振り直しは行わない（欠番を許容）。

---

### Scryfall ID 補完フロー

バージョン保存後、`scryfall_id` が未取得のカードをバックグラウンドで非同期補完する。
レスポンスの返却をブロックしない。

入力方法によって Scryfall API の呼び出し方が異なる。

```
バージョン保存完了後（バックグラウンド）
    │
    ▼ 今回保存したバージョンの cards の中で scryfall_id が未取得のレコードを抽出
    │
    ▼ 各カードに対して:
    │
    ├─ mtgo_id あり（.dek 由来）
    │   Scryfall API に MTGO CatID で問い合わせ
    │     → 使用した版の scryfall_id と image_url を取得
    │     → cards テーブルを更新
    │
    └─ mtgo_id なし（テキスト入力由来）
        Scryfall API にカード名で問い合わせ
          → デフォルト版の scryfall_id と image_url を取得
          → cards テーブルを更新
    │
    ▼ レート制限遵守のため次のリクエストまで 50ms 待機
```

---

### .dek パーサー仕様

`.dek` ファイルは XML 形式。`<Cards>` 要素を走査し、以下の属性からカード情報を取り出す。

| 属性 | 取得内容 |
|------|---------|
| `Name` | カード名 |
| `Quantity` | 枚数 |
| `Sideboard` | `"true"` の場合はサイドボード |
| `CatID` | MTGO カタログ ID（版の特定に使用） |

XML として不正なファイル、または `<Cards>` 要素が存在しない場合はエラーとする。

---

### テキストパーサー仕様

以下の入力フォーマットに対応する。

**カード行の形式**

| 形式 | 例 |
|------|----|
| 枚数 + 半角スペース + カード名 | `4 Lightning Bolt` |
| 枚数 + `x` + 半角スペース + カード名 | `4x Lightning Bolt` |

**サイドボード区切り**（大文字小文字不問）

`Sideboard` / `Sideboard:` / `SB:` / `サイドボード`
区切り行以降のカードをサイドボードとして扱う。

**スキップする行**

- `//` で始まるコメント行
- 空行（サイドボード区切りとして解釈されない限り）

**パース例**

```
4 Lightning Bolt              → メイン, 4枚
4x Ragavan, Nimble Pilferer   → メイン, 4枚
// comment                    → スキップ

Sideboard                     ← サイド区切り
4 Veil of Summer              → サイドボード, 4枚
SB: 2 Spell Pierce            → サイドボード, 2枚
```

---

## フロントエンド設計

### 画面構成: `DeckBuilderView.vue`

3ペイン構成とする。

```
┌──────────────┬───────────────────┬───────────────────────────┐
│ デッキ一覧   │ バージョン一覧    │ カードリスト              │
│              │                   │                           │
│ + 新規作成   │ + 新規バージョン  │ メインデッキ (60)         │
│              │                   │  [画像] 4 Lightning Bolt  │
│ UR Prowess   │ v3  MH3後調整     │  [画像] 4 DRC             │
│  Modern      │  2024-06-15  選択 │  ...                      │
│              │                   │                           │
│ Amulet Titan │ v2  稲妻4枚採用   │ サイドボード (15)         │
│  Modern      │  2024-05-10       │  [画像] 4 Consign to ...  │
│              │                   │  ...                      │
│ ...          │ v1  初期リスト    │                           │
│              │  2024-04-01       │               [ 編集 ]    │
└──────────────┴───────────────────┴───────────────────────────┘
```

- **左ペイン**: デッキ一覧。選択中のデッキをハイライト。「+ 新規作成」ボタン
- **中ペイン**: 選択デッキのバージョン一覧（新しい順）。「+ 新規バージョン」ボタン
- **右ペイン**: 選択バージョンのカードリスト。`small` 画像をカード名左に表示。「編集」ボタン

**カード画像の表示**

- `scryfall_id` が取得済みのカードは `/api/cards/{scryfall_id}/image?size=small` から画像を表示する
- `scryfall_id` が未取得のカードはプレースホルダー画像を表示する

---

### バージョン作成・編集モーダル

```
┌──────────────────────────────────────────────┐
│ バージョン v3 を作成                          │
│                                              │
│ メモ: [MH3後調整              ]              │
│                                              │
│ 入力方法: ○ テキスト貼り付け  ○ .dek ファイル │
│                                              │
│ ┌──────────────────────────────────────────┐ │
│ │ 4 Lightning Bolt                         │ │
│ │ 4 Dragon's Rage Channeler                │ │
│ │ ...                                      │ │
│ │                                          │ │
│ │ Sideboard                                │ │
│ │ 4 Consign to Memory                      │ │
│ └──────────────────────────────────────────┘ │
│                                              │
│               [ キャンセル ]  [ 保存 ]        │
└──────────────────────────────────────────────┘
```

`.dek` ファイル選択時はテキストエリアの代わりにファイル選択 UI を表示する。

---

### `frontend/src/api/decklist.ts` の責務

デッキ・バージョン・カード画像に関する API 呼び出しをまとめるモジュール。

**デッキ操作**

- デッキ一覧の取得
- デッキの新規作成・更新・削除

**バージョン操作**

- バージョン一覧の取得（カードリストなし）
- バージョン詳細の取得（カードリスト含む）
- バージョンの新規作成（テキスト形式 / `.dek` ファイル）
- バージョンの更新・削除

**カード画像**

- `scryfall_id` とサイズを受け取り、画像取得 API の URL を返す

---

## ナビゲーション

`GlobalNav.vue` に「デッキ管理」項目を追加する。
ルートパス: `/deck-builder`
位置: 既存ナビ項目の末尾（設定の手前）

---

## エラーハンドリング

| ケース | 対処 |
|--------|------|
| デッキ名が空 | 保存ボタン無効化 |
| テキストパース失敗 | モーダル内にエラー行を赤表示 |
| .dek ファイル不正 | Toast「有効な .dek ファイルを選択してください」 |
| メインデッキ 0 枚 | Toast「メインデッキが空です」 |
| カード画像取得失敗 | プレースホルダー画像を表示（サイレント） |
| デッキ削除 | ConfirmDialog で確認 |
| バージョン削除 | ConfirmDialog で確認 |

---

## 動作確認手順

1. デッキ作成: 「+ 新規作成」→ 名前・フォーマット入力 → 一覧に表示されること
2. バージョン作成（テキスト）: テキスト貼り付け → 保存 → カードリストが正しく表示されること
3. バージョン作成（.dek）: `UR_Prowess.dek` をインポート → 60枚 + SB15枚が正しく登録されること
4. カード画像（テキスト）: バージョン保存後しばらく待つ → Scryfall デフォルト版の `small` 画像が表示されること
5. カード画像（.dek）: バージョン保存後しばらく待つ → `CatID` から特定した版の画像が表示されること
6. 版の区別: 同名カードをテキスト入力と `.dek` インポートで登録した場合、`cards` テーブルに別レコードが存在すること
7. 画像キャッシュ: `/database/image_cache/small/` 配下に `.jpg` が生成されていること
8. バージョン編集: カードを変更して保存 → 内容が反映されること
9. バージョン追加: 2つ目のバージョンを作成 → `v2` として登録されること
10. デッキ削除: 削除後にバージョン・中間テーブルレコードも消えること（`cards` は残ること）
11. パースエラー: 不正なテキスト入力 → エラーが表示されること
