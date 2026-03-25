# デッキ名表示優先順位 設計ドキュメント

## 概要

対戦履歴の一覧・詳細画面で表示するデッキ名について、デッキ管理（DeckBuilder）と紐づいている場合はそちらのデッキ名を優先して表示する。

---

## 背景・動機

現在、対戦履歴に表示されるデッキ名は `MatchPlayer.deck_name` から取得している。
これはデッキ定義（`DeckDefinition`）によって自動判定・付与された名前である。

一方、ユーザーが手動でデッキ管理（DeckBuilder）のデッキバージョンを試合に紐づけた場合（`MatchPlayer.deck_version_id`）、そのデッキの正式名称は `DeckVersion → Deck.name` に存在する。

この2つが異なる場合、デッキ管理側の名前が正しいにも関わらず、デッキ定義側の名前が表示されてしまう。

---

## データモデル

```
MatchPlayer
├── deck_name          ... デッキ定義による自動判定名（nullable）
└── deck_version_id    ... デッキ管理との紐づけ（nullable）
                              ↓
                         DeckVersion
                         └── deck_id → Deck.name  ← こちらを優先したい
```

---

## 表示優先順位

| 条件 | 表示するデッキ名 |
|------|----------------|
| `deck_version_id` が設定されている | `Deck.name`（デッキ管理のデッキ名） |
| `deck_version_id` が NULL | `MatchPlayer.deck_name`（デッキ定義による名前） |
| どちらも NULL / 未設定 | `null`（非表示） |

---

## 影響範囲

### バックエンド

#### `backend/app/routers/matches.py`

**1. 試合一覧 `GET /api/matches`**

レスポンスの `decks` フィールドの構築方法を変更する。

```python
# 変更前
"decks": [p.deck_name for p in sorted_players]

# 変更後
"decks": [
    p.deck_version.deck.name if p.deck_version else p.deck_name
    for p in sorted_players
]
```

`deck_version` リレーションを eager load する必要があるため、クエリに `selectinload` を追加する。

**2. 試合詳細 `GET /api/matches/{match_id}`**

レスポンスの `players[].deck_name` フィールドも同様に変更する。

```python
# 変更前
"deck_name": p.deck_name,

# 変更後
"deck_name": p.deck_version.deck.name if p.deck_version else p.deck_name,
```

詳細エンドポイントはすでに `deck_version` を参照しているため、変更コストは低い。

### フロントエンド

変更不要。`decks` / `deck_name` フィールドをそのまま使用しているため、バックエンドの変更のみで対応できる。

---

## 変更しない箇所

- **`MatchPlayer.deck_name` カラム自体**: 変更しない。デッキ定義による自動判定結果として保持し続ける。
- **統計・フィルターの `deck` パラメータ**: `MatchPlayer.deck_name` に対する WHERE のまま変更しない（デッキ管理名での絞り込みは既存の `deck_id` / `version_id` パラメータで対応）。
- **AI エクスポートのデッキ名**: `matches.py` の `_build_export_markdown()` 内でも `deck_name` を参照しているが、今回は対象外とする（別 issue で検討）。

---

## 修正ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `backend/app/routers/matches.py` | 一覧・詳細レスポンスのデッキ名を優先順位に従って返す |
