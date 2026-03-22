# Scry

Magic Online（MTGO）の対戦ログ（`.dat`）を解析・AI 分析する Windows デスクトップアプリ。

> **アプリの使い方は [`GUIDE.md`](GUIDE.md) を参照してください。**
> このドキュメントは開発者向けのセットアップ・ビルド手順です。

---

## 機能概要

- `.dat` ファイルのインポート（単体 / フォルダ一括スキャン）
- 対戦履歴・ゲーム詳細の閲覧
- 統計ダッシュボード（勝率・マリガン率・先手後手分析・デッキ別分析等）
- AI チャット分析（Claude API）

---

## 必要な環境

### 開発環境

| ツール | バージョン | 備考 |
|--------|-----------|------|
| Windows 11 | - | WSLg（GUI）対応 |
| WSL2 | Ubuntu 22.04 / 24.04 | |
| Docker Desktop | 最新安定版 | WSL2 バックエンドを有効化 |
| Node.js | 20+ | WSL2 内にインストール |
| Python | 3.11+ | WSL2 内にインストール |

### 配布ビルド環境（Windows ホスト側）

| ツール | バージョン |
|--------|-----------|
| Node.js | 20+ |
| Python | 3.11+ |

---

## 開発環境のセットアップ

詳細手順は [`docs/09_dev-setup.md`](docs/09_dev-setup.md) を参照。

### 1. 初回セットアップ

```bash
# Electron 用 Linux システムライブラリ（Ubuntu 24.04）
sudo apt update
sudo apt install -y fonts-noto-cjk libnspr4 libnss3 \
  libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libdrm2 \
  libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
  libxrandr2 libgbm1 libasound2t64 libgtk-3-0t64

# フロントエンド依存パッケージ
cd frontend && npm install

# バックエンド依存パッケージ
cd ../backend && pip install -r requirements.txt
```

### 2. 開発サーバーの起動

```bash
# ターミナル①: Docker で Vite dev server + FastAPI を起動
cd /path/to/scry
docker compose up

# ターミナル②: Electron を起動（WSLg で GUI 表示）
cd frontend
npm run dev:electron
```

起動後、Electron ウィンドウに「✅ Backend connected」と表示されれば正常動作。

---

## 配布ビルド手順

> **Windows ホスト上で実行する**（WSL2 では Windows 向け exe を生成できない）。

### 前提条件

```bash
pip install pyinstaller
cd frontend && npm install --legacy-peer-deps
```

### ビルド実行

以下の順序で各ステップを実行する。

**ステップ 1: バックエンド (PyInstaller)**

```bash
cd backend
python -m PyInstaller --onefile --name backend --collect-all keyring app/main.py --clean
```

出力: `backend/dist/backend.exe`

**ステップ 2: フロントエンド (Vite)**

```bash
cd frontend
npm run build
```

出力: `frontend/dist/`

**ステップ 3: Electron パッケージング**

```bash
cd frontend
npm run build:electron
```

出力: `frontend/dist_electron/ScrySetup.exe`

---

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| デスクトップ | Electron |
| フロントエンド | Vue 3 + TypeScript + Vite |
| グラフ | ECharts + vue-echarts |
| バックエンド | Python 3.11 / FastAPI / uvicorn |
| DB | SQLite / SQLAlchemy 2.x |
| AI 分析 | Claude API |
| API キー管理 | SQLite（ローカルデータベース） |
| 開発環境 | Docker Compose + WSL2 |
| 配布 | PyInstaller + electron-builder（Windows installer） |
