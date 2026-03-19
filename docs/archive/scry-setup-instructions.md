# Scry — 開発環境セットアップ指示書

## あなたの役割
このドキュメントの指示に従い、Scryの開発環境をゼロからセットアップしてください。

---

## プロジェクト概要

Magic Online（MTGO）の対戦ログ（`.dat`ファイル）を解析し、勝率・プレイパターンをAIで分析するデスクトップアプリを開発する。

---

## 技術スタック

| レイヤー | 技術 |
|---|---|
| デスクトップ | Electron |
| フロントエンド | Vue 3 + TypeScript + Vite |
| バックエンド | Python 3.11+ / FastAPI |
| DB | SQLite（better-sqlite3 / Python側はsqlalchemy） |
| クロスプラットフォーム | Windows / Mac 両対応 |

---

## ディレクトリ構成

```
scry/
├── frontend/
│   ├── electron/
│   │   └── main.ts          # Electronメインプロセス（Python起動も担当）
│   ├── src/
│   │   ├── App.vue
│   │   ├── main.ts
│   │   └── views/
│   │       └── HomeView.vue
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPIエントリポイント
│   │   ├── routers/
│   │   │   └── health.py
│   │   └── models/
│   ├── parser/
│   │   └── log_parser.py    # MTGOログパーサー（スタブのみ）
│   ├── database.py          # SQLite接続管理
│   └── requirements.txt
├── database/                # SQLiteファイル置き場（自動生成）
└── README.md
```

---

## セットアップ手順

### 1. プロジェクトルートの作成

```bash
mkdir scry && cd scry
git init
```

### 2. フロントエンド（Electron + Vue 3）

```bash
mkdir frontend && cd frontend
npm create vite@latest . -- --template vue-ts
npm install
npm install --save-dev electron electron-builder concurrently wait-on
npm install axios
```

#### `frontend/electron/main.ts` の要件
- アプリ起動時に `backend/` の Python FastAPI を **サブプロセス** として起動する
- 起動コマンド:
  - Windows: `python backend/app/main.py`
  - Mac/Linux: `python3 backend/app/main.py`
- アプリ終了時（`app.on('before-quit')`）にPythonプロセスをkillする
- ウィンドウサイズは `1200 x 800`

#### `frontend/package.json` のスクリプト要件
```json
{
  "scripts": {
    "dev": "vite",
    "dev:electron": "concurrently \"vite\" \"wait-on http://localhost:5173 && electron .\"",
    "build": "vite build",
    "build:electron": "electron-builder"
  }
}
```

#### `frontend/src/views/HomeView.vue` の要件
- 画面表示時に `GET http://localhost:8000/api/health` を呼び出す
- 成功時: 「✅ Backend connected」と緑色で表示
- 失敗時: 「❌ Backend not connected」と赤色で表示
- シンプルなレイアウトで問題なし

---

### 3. バックエンド（Python FastAPI）

```bash
cd ../backend
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate
pip install fastapi uvicorn sqlalchemy aiofiles
pip freeze > requirements.txt
```

#### `backend/app/main.py` の要件
- FastAPIアプリを `uvicorn` で起動（ポート `8000`）
- CORS設定: `http://localhost:5173`（Vite開発サーバー）を許可
- `routers/health.py` をインクルード

#### `backend/app/routers/health.py` の要件
```python
GET /api/health
→ {"status": "ok", "version": "0.1.0"}
```

#### `backend/parser/log_parser.py` の要件
- 現時点では **スタブのみ** 実装する
- 以下のクラス・関数の定義だけ作成し、中身は `pass` または `TODO` コメントでよい

```python
class MTGOLogParser:
    def parse_file(self, filepath: str) -> dict:
        """
        .datファイルを読み込み、以下の構造のdictを返す（予定）
        {
            "match_id": str,
            "players": [str, str],
            "games": [
                {
                    "winner": str,
                    "turns": int,
                    "first_player": str,
                    "mulligans": {player: count},
                    "actions": [{"turn": int, "player": str, "action": str, "card": str}]
                }
            ],
            "match_winner": str
        }
        """
        pass
```

#### `backend/database.py` の要件
- SQLAlchemyでSQLiteに接続
- DBファイルパス: `../database/mtgo.db`
- 現時点では接続確認のみでOK（テーブル定義は後回し）

---

### 4. README.md の作成

以下を含めること：
- プロジェクト概要
- 必要な環境（Node.js 20+, Python 3.11+）
- 開発サーバーの起動方法
- ディレクトリ構成の説明

---

## 完了確認チェックリスト

以下がすべて動作することを確認してください。

- [ ] `cd frontend && npm run dev:electron` でElectronウィンドウが開く
- [ ] `cd backend && uvicorn app.main:app --reload` でFastAPIが起動する
- [ ] `http://localhost:8000/api/health` にアクセスして `{"status":"ok"}` が返る
- [ ] ElectronアプリのHome画面に「✅ Backend connected」が表示される

---

## 補足・注意事項

- Electronの `contextIsolation` は `true`、`nodeIntegration` は `false` で設定すること（セキュリティのベストプラクティス）
- Pythonの仮想環境（venv）はGitignoreに追加すること
- `database/mtgo.db` もGitignoreに追加すること
- TypeScriptの strict モードは有効にすること
