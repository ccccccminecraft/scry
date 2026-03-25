# Scryfall API トグル機能 設計ドキュメント

## 概要

設定画面に「Scryfall API を利用する」チェックボックスを追加する。
デフォルトは **OFF**。オフの場合、すべての Scryfall API 呼び出しをスキップする。

---

## 動機

- Scryfall API は外部サービスへの依存を生じさせるため、オフライン環境や通信制限環境でエラーが発生しやすい。
- インポート速度の大幅な向上が期待できる（フォーマット推定で数十件〜数百件の HTTP リクエストが発生するため）。
- 不要なユーザーにとっては Scryfall 依存を完全に排除できる。

---

## 現在の Scryfall API 利用箇所

| # | 機能 | ファイル | 呼び出し先 | タイミング |
|---|------|----------|------------|------------|
| 1 | MTGOインポート フォーマット推定 | `services/import_service.py` `_infer_format()` | `scryfall_client.fetch_legalities()` | インポート時（同期） |
| 2 | MTGAインポート フォーマット推定フォールバック | `services/import_service.py` `SurveilImportService._infer_format_from_deck()` | `scryfall_client.fetch_legalities()` | インポート時（同期） |
| 3 | カード名 → Scryfall ID 解決 | `services/card_image_service.py` `fill_scryfall_ids()` | `GET /cards/named` | デッキ登録後バックグラウンド（非同期） |
| 4 | MTGO ID → Scryfall ID 解決 | `services/card_image_service.py` `fill_scryfall_ids()` | `GET /cards/mtgo/{id}` | デッキ登録後バックグラウンド（非同期） |
| 5 | カード画像ダウンロード | `services/card_image_service.py` `get_card_image()` | Scryfall CDN | 画像表示時（非同期） |

---

## 新規設定キー

| キー | 型 | デフォルト | 説明 |
|------|----|-----------|------|
| `scryfall_enabled` | `"true"` / `"false"` | `"false"` | Scryfall API を利用するか |

---

## OFF 時の動作

| 機能 | OFF 時の挙動 |
|------|-------------|
| MTGOインポート フォーマット推定 | `"unknown"` で確定（Scryfall なし） |
| MTGAインポート フォーマット推定フォールバック | フォールバック呼び出しをスキップ（EventName / GRP ID 推定のみ） |
| カード Scryfall ID 解決 | バックグラウンドタスクを起動しない |
| カード画像ダウンロード | 404 を返す（フロントエンドはプレースホルダー表示） |

---

## 修正が必要なファイル

### バックエンド

#### `backend/app/routers/settings.py`
- `SettingsInput` に `scryfall_enabled: bool | None = None` を追加
- `GET /api/settings` レスポンスに `"scryfall_enabled": bool` を追加（デフォルト `False`）
- `PUT /api/settings` に `scryfall_enabled` の保存処理を追加

#### `backend/services/scryfall_settings.py` (新規)
- `is_scryfall_enabled(db: Session) -> bool` ヘルパー関数
- 設定値を DB から取得して bool を返す

#### `backend/services/import_service.py`
- `ImportService._infer_format()`: `scryfall_enabled=False` なら `fetch_legalities()` をスキップ
  - `db` を受け取り `is_scryfall_enabled()` を確認するか、呼び出し元で判定して引数で渡す
- `SurveilImportService._infer_format_from_deck()`: `scryfall_enabled=False` なら早期 return

#### `backend/app/routers/import_.py`
- `POST /api/import` (MTGO): `is_scryfall_enabled(db)` を確認し、`import_service.import_one(..., skip_format_inference=...)` に反映

#### `backend/app/routers/surveil_import.py`
- `POST /api/import/surveil`: `is_scryfall_enabled(db)` を確認し、`SurveilImportService` に渡す

#### `backend/app/routers/decklist.py`
- デッキ登録後の `fill_scryfall_ids()` バックグラウンドタスク呼び出し箇所: `is_scryfall_enabled(db)` が `False` なら起動しない

#### `backend/app/routers/decks.py` (画像エンドポイント)
- `GET /api/cards/{id}/image`: `is_scryfall_enabled(db)` が `False` なら 404 を返す

### フロントエンド

#### `frontend/src/api/settings.ts`
- `Settings` 型に `scryfall_enabled: boolean` を追加
- `updateSettings()` に `scryfall_enabled` を含める

#### `frontend/src/views/SettingsView.vue`
- 「基本設定」セクションに「Scryfall API を利用する」チェックボックスを追加
- チェックを外すと Scryfall 依存機能（フォーマット推定・カード画像）が無効になる旨の説明文を付ける

---

## UI イメージ（SettingsView）

```
┌─────────────────────────────────────────────────────┐
│ 基本設定                                              │
│                                                      │
│  デフォルトプレイヤー名: [___________________]        │
│                                                      │
│  □ Scryfall API を利用する                           │
│    オンにすると以下の機能が有効になります:             │
│    ・MTGOインポート時のフォーマット自動推定             │
│    ・デッキカードの画像自動取得                        │
│    ※ Scryfall API への通信が発生します。              │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## 実装方針

1. **グローバル設定を DB から読む**: 各エンドポイントで DB セッションが使えるため、`is_scryfall_enabled(db)` を呼んで判定する。
2. **既存の `skip_format_inference` フラグと併存**: MTGO インポート画面のチェックボックスはそのまま残す。グローバル OFF の場合は自動的に推定スキップ扱いになる（どちらか一方が True でスキップ）。
3. **画像エンドポイント**: OFF 時に 404 を返すことでフロントエンド側のプレースホルダー表示が既存ロジックのまま動作する。
4. **デフォルト OFF**: 既存ユーザーが初めて設定画面を開いたとき OFF になっているが、既存動作（Scryfall あり）を維持したい場合は ON にしてもらう。
   - 既存 DB に `scryfall_enabled` レコードがなければデフォルト `false` 扱い。

---

## 影響を受けない機能

- アーキタイプ定義の生成（AI による定義生成）
- アーキタイプ定義の適用（`/api/decks/apply-definitions`）
- MTGA カード同期（`mtga_cards` テーブル、別 API）
- 対戦履歴のインポート本体（カード名保存は Scryfall 無しでも行う）
