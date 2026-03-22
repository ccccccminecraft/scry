# デッキタイル（代表カード画像）設計書

## 概要

MTGA のデッキケースイラスト（`DeckTileId`）をデッキの代表カード画像として保存・表示する。
自動設定（MTGA インポート時）と手動設定（デッキ管理画面）の両方に対応する。

---

## データフロー

### 自動設定（MTGA インポート経由）

```
Player.log
  ▼ EventSetDeckV2: Summary.DeckTileId (grpId)
  ▼ Surveil parser.py: deck_tile_id として抽出
  ▼ storage.py: JSON に "deck_tile_id": 12345 を出力
  ▼ gre_parser.py: GREParseResult.deck_tile_id
  ▼ import_service._sync_deck_from_import():
      grpId → mtga_cards テーブルでカード名解決
      カード名 → cards テーブルで scryfall_id 取得 or 作成
      scryfall_id → decks.tile_scryfall_id に保存
  ▼ DeckBuilderView / StatsView でサムネイル表示
```

### 手動設定（デッキ管理画面）

```
DeckBuilderView: デッキ編集モーダル
  ▼ 「代表カードを選択」ボタン
  ▼ タイルピッカーモーダル:
      最新 DeckVersion のカード一覧を画像グリッドで表示
      カードをクリック → scryfall_id を選択
  ▼ PUT /api/decklist/decks/{deck_id} body: { tile_scryfall_id }
  ▼ decks.tile_scryfall_id を更新
```

---

## DB 変更

### `decks` テーブル: `tile_scryfall_id` カラム追加

```sql
ALTER TABLE decks ADD COLUMN tile_scryfall_id TEXT;
```

| カラム | 型 | 説明 |
|---|---|---|
| `tile_scryfall_id` | TEXT NULL | 代表カードの Scryfall ID。未設定は NULL |

- `cards.scryfall_id` との外部キーは設定しない（cards テーブルに存在しない scryfall_id でも保持できるようにするため）
- `tile_image_url` は保存しない。既存の `/api/cards/{scryfall_id}/image` エンドポイントで都度取得する

---

## バックエンド変更

### 1. Surveil `parser.py`

```python
# EventSetDeckV2 ハンドラー（変更前）
last_deck_name = summary.get("Name") or None

# 変更後
last_deck_name = summary.get("Name") or None
last_deck_tile_id = summary.get("DeckTileId") or None  # int または None
```

`_MatchContext` に `deck_tile_id: Optional[int] = None` を追加。
`MatchData` に `deck_tile_id: Optional[int] = None` を追加。

### 2. Surveil `storage.py`

```python
# _build_json() に追加
"deck_name": match.deck_name,
"deck_tile_id": match.deck_tile_id,   # ← 追加
```

### 3. `parser/gre_parser.py`

`GREParseResult` TypedDict に追加:
```python
deck_tile_id: Optional[int]   # EventSetDeckV2 Summary.DeckTileId
```

`parse_gre_json()` で:
```python
deck_tile_id = data.get("deck_tile_id")
```

### 4. `models/decklist.py`

```python
class Deck(Base):
    ...
    tile_scryfall_id: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### 5. `database.py`（マイグレーション）

```python
if "decks" in inspector.get_table_names():
    cols = {c["name"] for c in inspector.get_columns("decks")}
    if "tile_scryfall_id" not in cols:
        conn.execute(text("ALTER TABLE decks ADD COLUMN tile_scryfall_id TEXT"))
        conn.commit()
```

### 6. `services/import_service.py`

`_sync_deck_from_import()` のシグネチャに `deck_tile_id: int | None = None` を追加。

Deck 作成・更新時にタイル解決:
```python
def _resolve_tile(self, grp_id: int) -> str | None:
    """grpId → scryfall_id を解決する。mtga_cards 未同期の場合は None。"""
    from models.cache import MtgaCard
    row = self._db.query(MtgaCard).filter(MtgaCard.arena_id == grp_id).first()
    if row is None:
        return None
    # cards テーブルから scryfall_id を取得（なければ作成・バックグラウンド解決）
    card = self._get_or_create_card(row.card_name)
    return card.scryfall_id  # 未解決の場合は None（バックグラウンドで後から埋まる）
```

Deck の tile_scryfall_id は以下のタイミングで設定:
- **Deck 新規作成時**: `deck_tile_id` が解決できれば即時設定
- **既存 Deck 更新時**: `tile_scryfall_id` が NULL の場合のみ上書き（手動設定を尊重）

### 7. `app/routers/decklist.py`

**GET /api/decklist/decks レスポンスに `tile_scryfall_id` を追加:**

```python
def _deck_to_dict(deck: Deck) -> dict:
    return {
        "id": deck.id,
        "name": deck.name,
        "format": deck.format,
        "created_at": deck.created_at.isoformat(),
        "is_archived": deck.is_archived,
        "tile_scryfall_id": deck.tile_scryfall_id,   # ← 追加
        "latest_version": ...
    }
```

**PUT /api/decklist/decks/{deck_id} に `tile_scryfall_id` を追加:**

```python
class DeckUpdateInput(BaseModel):
    name: str | None = None
    format: str | None = None
    tile_scryfall_id: str | None = None   # ← 追加（空文字列で削除）
```

---

## フロントエンド変更

### 1. `DeckBuilderView.vue` — デッキ一覧ペイン

左ペインのデッキ項目にタイル画像を表示:

```
┌──────────────────────────────┐
│ [画像] ST 赤単 BO3           │  ← 左に小さいカード画像（32×44px 程度）
│        pioneer               │
└──────────────────────────────┘
```

- `tile_scryfall_id` がある場合: `/api/cards/{scryfall_id}/image` を `<img>` で表示
- ない場合: グレーのプレースホルダー（現状の表示と同じ）

### 2. `DeckBuilderView.vue` — デッキ編集モーダル

既存の編集モーダルに「代表カード」セクションを追加:

```
┌─────────────────────────────────────┐
│ デッキ名: [___________________]     │
│ フォーマット: [________▼]           │
│                                     │
│ 代表カード:                         │
│  [カード画像 or プレースホルダー]    │
│  [選択する]  [削除]                 │
└─────────────────────────────────────┘
```

「選択する」クリック → タイルピッカーモーダルを開く

### 3. タイルピッカーモーダル（新規コンポーネント）

`DeckTilePickerModal.vue` を新規作成:

- 選択中デッキの最新バージョンのカードを画像グリッドで表示
- `scryfall_id` がある（画像取得済み）カードのみ表示
- カードをクリック → 選択、モーダルを閉じる
- 保存は親コンポーネント（DeckBuilderView）が `PUT /api/decklist/decks/{id}` を呼ぶ

### 4. `StatsView.vue` / `FilterBar.vue`

デッキフィルタードロップダウンにサムネイルを追加:

```
┌─────────────────────┐
│ [画像] ST 赤単 BO3  │
│ [画像] UW コントロール │
│ [画像] 5色ニヴ      │
└─────────────────────┘
```

- `<select>` では画像を表示できないため、カスタムドロップダウンに変更が必要
- または: フィルター選択後に選択中デッキのタイルを FilterBar 内に小さく表示する（簡易案）

> **実装優先度**: デッキ管理画面のタイル表示（①②③）を先に実装し、統計画面（④）は後続とする

---

## API 変更まとめ

| エンドポイント | 変更内容 |
|---|---|
| `GET /api/decklist/decks` | レスポンスに `tile_scryfall_id` フィールドを追加 |
| `PUT /api/decklist/decks/{deck_id}` | リクエストに `tile_scryfall_id` フィールドを追加（空文字で NULL クリア） |
| `GET /api/cards/{scryfall_id}/image` | 既存エンドポイントをそのまま流用 |

---

## 実装ステップ

| # | 対象 | 内容 |
|---|---|---|
| 1 | Surveil `parser.py` | `DeckTileId` 抽出・`MatchData` に追加 |
| 2 | Surveil `storage.py` | `deck_tile_id` を JSON 出力に追加 |
| 3 | `gre_parser.py` | `GREParseResult` に `deck_tile_id` 追加 |
| 4 | `models/decklist.py` | `Deck.tile_scryfall_id` カラム追加 |
| 5 | `database.py` | `tile_scryfall_id` マイグレーション追加 |
| 6 | `import_service.py` | `_resolve_tile()` + `_sync_deck_from_import` 更新 |
| 7 | `decklist.py` router | GET/PUT レスポンス・リクエストに `tile_scryfall_id` 追加 |
| 8 | `DeckBuilderView.vue` | デッキ一覧サムネイル表示 |
| 9 | `DeckBuilderView.vue` | 編集モーダルに代表カードセクション追加 |
| 10 | `DeckTilePickerModal.vue` | タイルピッカーモーダル新規作成 |
| 11 | `StatsView.vue` / `FilterBar.vue` | 選択中デッキのタイル表示（簡易版） |

---

## 制約・注意点

- `DeckTileId` が実際の Player.log に存在するかは初回キャプチャで確認が必要。存在しない場合は手動設定のみ対応。
- `tile_scryfall_id` の解決は `mtga_cards` 同期済みの場合のみ自動設定。未同期時は NULL のまま（手動設定で補完）。
- 既存の Surveil JSON（保存済み）には `deck_tile_id` がないため、既存データは手動設定が必要。
- 手動設定した `tile_scryfall_id` は、後からインポートで上書きしない（既存 Deck で `tile_scryfall_id` が既に設定済みの場合はスキップ）。
