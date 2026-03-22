# 自動インポート 設計書

## 概要

MTGO / MTGA（Surveil）の両フォルダを定期的にスキャンし、未インポートファイルを自動で取り込む。
バックエンド（FastAPI）のバックグラウンドタスクとして動作し、ブラウザが閉じていても機能する。

---

## 方針

- **アプローチ**: バックエンド asyncio バックグラウンドタスク（案B）
- **依存追加なし**: APScheduler 等の外部ライブラリを使わず、asyncio のみで実装
- **既存ロジック流用**: `ImportService` / `SurveilImportService` をそのまま呼び出す
- **設定**: `settings` テーブルに `auto_import_enabled` / `auto_import_interval_sec` を追加

---

## コンポーネント

### バックエンド

#### `services/auto_import_service.py`（新規）

```python
class AutoImportService:
    def run_once(self, db: Session) -> AutoImportResult
        # MTGO スキャン: quick_import_folder → ImportService
        # MTGA スキャン: surveil_folder → SurveilImportService
        # 結果を settings テーブルに保存
```

#### `app/lifespan.py` または `app/main.py`

FastAPI の `lifespan` コンテキストマネージャー内で asyncio タスクを起動。

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(auto_import_loop())
    yield
    task.cancel()

async def auto_import_loop():
    while True:
        await asyncio.sleep(interval_sec)
        # DB セッション取得 → AutoImportService.run_once()
```

#### `app/routers/auto_import.py`（新規）

| エンドポイント | 説明 |
|--------------|------|
| `GET /api/import/auto-import/status` | 最終実行日時・結果・設定値を返す |

設定変更（有効/無効・間隔）は既存の `PUT /api/settings` に `auto_import_enabled` / `auto_import_interval_sec` フィールドを追加して対応。

### フロントエンド

#### `SettingsView.vue`

- 自動インポートの有効/無効トグル
- スキャン間隔（秒）の入力
- 最終実行日時・結果の表示（`GET /api/import/auto-import/status` をポーリング）

---

## DB 変更

`settings` テーブルへの追加キー（既存の key-value 形式）:

| key | 型 | デフォルト | 説明 |
|-----|----|----------|------|
| `auto_import_enabled` | str (`"true"/"false"`) | `"false"` | 自動インポート有効フラグ |
| `auto_import_interval_sec` | str (数値) | `"30"` | スキャン間隔（秒） |
| `auto_import_last_run_at` | str (ISO8601) | null | 最終実行日時 |
| `auto_import_last_result` | str (JSON) | null | 最終実行結果 |

---

## スキャンロジック

### MTGO

1. `quick_import_folder` 設定を取得（未設定 → スキップ）
2. フォルダ内の `Match_GameLog_*.dat` を列挙
3. DB の `matches.id`（source="mtgo"）と差分比較
4. 新ファイルを `ImportService.import_file()` で取り込み

### MTGA（Surveil）

1. `surveil_folder` 設定を取得（未設定 → スキップ）
2. フォルダ内の `*.json` を列挙
3. DB の `matches.id`（source="mtga"）と差分比較
4. 新ファイルを `SurveilImportService.import_one()` で取り込み
   - デッキ自動登録（`_sync_deck_from_import`）も同時実行
   - Scryfall 画像解決は `fill_scryfall_ids` でバックグラウンド実行

---

## エラーハンドリング

- 個別ファイルの失敗はログに記録してスキップ（スケジューラーは停止しない）
- フォルダが存在しない場合はその回のスキャンをスキップ
- DB セッションエラー時はセッションをロールバックして次のサイクルへ

---

## 開発環境（Docker）での注意

バックエンドコンテナはホストのファイルシステムにアクセスできない。
MTGO / Surveil フォルダを使う場合は `docker-compose.yml` に volume を追加するか、
`/database/` 以下にシンボリックリンクまたはマウントする。

```yaml
# docker-compose.yml の backend サービスに追加例
volumes:
  - ./backend:/app
  - ./database:/database
  - /path/to/surveil/output:/surveil   # ← 追加
  - /path/to/mtgo/logs:/mtgo           # ← 追加
```

---

## 実装ステップ

1. `services/auto_import_service.py` 作成
2. `app/main.py` に lifespan + スケジューラーループ追加
3. `app/routers/auto_import.py` 作成（status エンドポイント）
4. `GET/PUT /api/settings` に `auto_import_enabled` / `auto_import_interval_sec` フィールド追加
5. `SettingsView.vue` に自動インポート設定 UI 追加
