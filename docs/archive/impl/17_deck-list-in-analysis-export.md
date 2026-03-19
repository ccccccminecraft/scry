# 17: AI分析・エクスポートへのデッキリスト埋め込み

## 概要

バージョン指定フィルター（`version_id`）が設定されている場合に、デッキ管理で登録したデッキリスト（メインデッキ＋サイドボード）を AI 分析のシステムプロンプトとエクスポート Markdown に含める機能。

デッキリストが含まれることで、AI がカード選択・枚数配分・サイドボード構成についても具体的な分析を行えるようになる。

---

## 発動条件

`version_id` が指定されている場合のみデッキリストを出力する。`deck_id` のみ指定（バージョン未選択）の場合は対象外とする。

---

## 対象ファイル

### 新規作成

なし

### 編集

| ファイル | 変更内容 |
|----------|---------|
| `backend/app/routers/analysis.py` | `_build_deck_list_text` 追加、`build_stats_text` に追記 |
| `backend/app/routers/matches.py` | `_build_export_markdown` に `version_id` 引数追加、デッキリストセクション追加 |

---

## 共通ヘルパー

### `_build_deck_list_text(db, version_id) -> str`

`analysis.py` に追加する内部関数。

**処理フロー:**

1. `DeckVersion` を `version_id` で取得（存在しなければ空文字を返す）
2. 親 `Deck` の name と version_number・memo からヘッダーを生成
3. `DeckVersionCard` を `is_sideboard=False` / `True` で分けてリスト化
4. テキスト形式で組み立てて返す

**出力形式:**

```
【使用デッキリスト】
デッキ: Amulet Titan v2

メインデッキ (60):
4 Amulet of Vigor
4 Primeval Titan
4 Arboreal Grazer
...

サイドボード (15):
3 Boseiju, Who Endures
2 Engineered Explosives
...
```

---

## AI 分析（`analysis.py`）

### `build_stats_text` への追記

`version_id` が指定されている場合、`_build_deck_list_text` の結果を統計テキストの末尾に追記する。

```python
if version_id:
    deck_text = _build_deck_list_text(db, version_id)
    if deck_text:
        lines.append("")
        lines.append(deck_text)
```

Claude に渡すシステムプロンプトに統計データとともにデッキリストが含まれるため、以下のような分析が可能になる。

- カードの採用枚数の妥当性
- 勝率との相関（特定カードが多いバージョンで勝率が上がっているか）
- サイドボードの構成に関するアドバイス

---

## エクスポート（`matches.py`）

### `_build_export_markdown` の変更

引数に `version_id: int | None` を追加する。

`version_id` が指定されている場合、サマリーセクションとマッチ一覧の間にデッキリストセクションを挿入する。

**出力形式:**

```markdown
## デッキリスト: Amulet Titan v2

### メインデッキ (60)

| 枚数 | カード名 |
|------|---------|
| 4 | Amulet of Vigor |
| 4 | Primeval Titan |
...

### サイドボード (15)

| 枚数 | カード名 |
|------|---------|
| 3 | Boseiju, Who Endures |
...
```

### `export_matches` エンドポイントの変更

既存の `version_id` パラメーターを `_build_export_markdown` に渡すよう変更する。

---

## エラーハンドリング

| 状況 | 対応 |
|------|------|
| `version_id` に対応する DeckVersion が存在しない | デッキリストセクションをスキップして処理を続行 |
| カードが 0 件 | デッキリストセクションをスキップ |

---

## 動作確認手順

1. デッキ管理でデッキ・バージョンを登録し、対戦履歴に一括適用する
2. AI 分析画面でバージョンを選択して会話を開始する
3. AI の応答にデッキリストに基づいた言及が含まれることを確認する
4. エクスポート画面でバージョンを選択してダウンロードする
5. 出力された Markdown に「デッキリスト」セクションが含まれることを確認する
6. バージョン未選択（デッキのみ選択）の場合はデッキリストセクションが含まれないことを確認する
