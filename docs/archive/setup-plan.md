# Scry セットアップ計画

## プロジェクト概要

Magic Online（MTGO）の `.dat` 対戦ログを解析・AI分析するデスクトップアプリ。

---

## 技術スタック

| レイヤー | 技術 |
|----------|------|
| デスクトップ | Electron |
| フロントエンド | Vue 3 + TypeScript + Vite |
| バックエンド | Python 3.11+ / FastAPI |
| DB | SQLite（sqlalchemy） |
| 開発環境 | Docker Compose |
| 配布 | PyInstaller + electron-builder（Windows installer） |

---

## 開発環境と配布の使い分け

| フェーズ | 方法 |
|----------|------|
| 開発時 | Docker Compose（Vite dev server + uvicorn） |
| 配布ビルド時 | PyInstaller → electron-builder → Windows installer |

### 開発時の構成

```
WSL2
├── Docker: Vite dev server（frontend コンテナ :5173）
├── Docker: FastAPI（backend コンテナ :8000）
└── Electron（npm run dev:electron）← WSLg 経由で GUI 表示
```

> **WSLg 前提**: Windows 11（WSLg 標準搭載）を使用する。
> Electron の GUI は WSLg が自動的に Windows 上に描画する。
> 初回セットアップ時に以下の Linux システムライブラリが必要：
> ```bash
> sudo apt install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 \
>   libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
>   libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2
> ```

### 配布時の構成

```
ユーザーの Windows PC
└── installer.exe を実行
      └── Electron アプリ
            ├── Vue ビルド済み HTML/JS（Vite の dist）
            └── resources/
                  └── backend.exe  ← PyInstaller で生成した Python サーバー
```

**実行時の流れ：**

```
ユーザーが exe 起動
  → Electron が起動
  → resources/backend.exe をサブプロセスとして起動（localhost:8000）
  → localhost:8000 への接続を確認してから UI を表示
```

---

## Step 1: Docker Compose 環境構築 ✅

作成するファイル：

| ファイル | 内容 |
|----------|------|
| `docker-compose.yml` | frontend / backend サービス定義 |
| `frontend/Dockerfile` | Node.js 22 ベース、Vite dev server 用 |
| `backend/Dockerfile` | Python 3.11 ベース、uvicorn 用 |

### docker-compose.yml の要件

- `frontend` サービス: ポート `5173` を公開、`frontend/` をボリュームマウント
- `backend` サービス: ポート `8000` を公開、`backend/` をボリュームマウント
- `database/` ボリュームを backend にマウント（SQLite ファイル永続化）
- ホットリロード対応（`--reload`）

---

## Step 2: フロントエンド（Electron + Vue 3 + TypeScript）

| 作業 | 詳細 |
|------|------|
| Viteプロジェクト作成 | `npm create vite@latest . -- --template vue-ts` |
| 依存パッケージ追加 | `electron`, `electron-builder`, `concurrently`, `wait-on`, `axios` |
| `electron/main.ts` 作成 | dev/本番判定、本番時は `resources/backend.exe` を起動、ウィンドウ 1200x800 |
| `package.json` スクリプト設定 | 下記参照 |
| `HomeView.vue` 作成 | `/api/health` を呼び出し、接続状態を表示 |

### package.json スクリプト

```json
{
  "scripts": {
    "dev": "vite --host",
    "dev:electron": "wait-on http://localhost:5173 && electron .",
    "build": "vite build",
    "build:electron": "electron-builder"
  }
}
```

> `dev` は Docker コンテナ内で実行。`dev:electron` はホストで実行。

### Electron セキュリティ設定

- `contextIsolation: true`
- `nodeIntegration: false`

### `electron/main.ts` の dev/本番 判定ロジック

```
isDev（app.isPackaged が false）の場合
  → loadURL("http://localhost:5173")
  → Python は Docker が管理するため起動不要

本番（app.isPackaged が true）の場合
  → resources/backend.exe をサブプロセスとして起動
  → localhost:8000 が応答するまで待機
  → loadFile(dist/index.html)
  → app 終了時に backend.exe を kill
```

---

## Step 3: バックエンド（Python FastAPI）

| 作業 | 詳細 |
|------|------|
| `app/main.py` 作成 | uvicorn起動、CORS許可（localhost:5173） |
| `routers/health.py` 作成 | `GET /api/health` → `{"status":"ok","version":"0.1.0"}` |
| `parser/log_parser.py` 作成 | `MTGOLogParser` スタブのみ |
| `database.py` 作成 | SQLAlchemy + SQLite接続確認のみ |
| `requirements.txt` 作成 | fastapi, uvicorn, sqlalchemy, aiofiles, pyinstaller |

---

## Step 4: README.md 作成

含める内容：

- プロジェクト概要
- 必要な環境（開発: Docker Desktop + Node.js 20+）
- 開発サーバーの起動方法（`docker compose up` + `npm run dev:electron`）
- 配布ビルド手順
- ディレクトリ構成の説明

---

## Step 5: .gitignore 設定

- `database/mtgo.db`
- `frontend/node_modules/`
- `frontend/dist/`
- `backend/dist/`
- `**/__pycache__/`
- `**/*.pyc`

---

## Step 6: 配布ビルド手順

> **配布ビルドは Windows ホスト上で実行する**（WSL2 では Windows 向け exe が生成できないため）。
> Windows 側に Node.js 20+、Python 3.11+、pip をインストールしておくこと。

### 6-1. バックエンドを PyInstaller で exe 化

```bash
cd backend
pip install pyinstaller
pyinstaller --onefile --name backend app/main.py
# → backend/dist/backend.exe が生成される
```

### 6-2. frontend の electron-builder 設定

`frontend/electron-builder.yml` で PyInstaller の出力を `extraResources` に含める：

```yaml
extraResources:
  - from: ../backend/dist/backend.exe
    to: backend.exe
```

### 6-3. Electron アプリをビルド

```bash
cd frontend
npm run build          # Vite で Vue をビルド
npm run build:electron # electron-builder で Windows installer 生成
# → frontend/dist_electron/ScrySetup.exe が生成される
```

---

## 完了確認チェックリスト

### 開発環境
- [ ] `docker compose up` → frontend（:5173）と backend（:8000）が起動する
- [ ] `GET http://localhost:8000/api/health` → `{"status":"ok"}` 返却
- [ ] `cd frontend && npm run dev:electron` → Electronウィンドウ起動
- [ ] Home画面に「✅ Backend connected」表示

### 配布ビルド
- [ ] `pyinstaller` で `backend/dist/backend.exe` が生成される
- [ ] `npm run build:electron` で Windows installer が生成される
- [ ] installer を実行するとアプリが起動し、「✅ Backend connected」が表示される

---

## ディレクトリ構成（最終形）

```
scry/
├── docker-compose.yml
├── frontend/
│   ├── Dockerfile
│   ├── electron/
│   │   └── main.ts
│   ├── src/
│   │   ├── App.vue
│   │   ├── main.ts
│   │   └── views/
│   │       └── HomeView.vue
│   ├── electron-builder.yml
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── backend/
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py
│   │   └── routers/
│   │       └── health.py
│   ├── parser/
│   │   └── log_parser.py
│   ├── database.py
│   └── requirements.txt
├── database/
├── docs/
│   ├── scry-setup-instructions.md
│   └── setup-plan.md
└── README.md
```
