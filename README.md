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

### 1. Python バックエンドを exe 化

```bash
cd backend
pip install pyinstaller
pyinstaller --onefile --name backend --collect-all keyring app/main.py
# → backend/dist/backend.exe が生成される
```

### 2. Electron アプリをビルド

```bash
cd frontend
npm run build          # Vite で Vue をビルド
npm run build:electron # electron-builder で Windows installer を生成
# → frontend/dist_electron/ScrySetup.exe が生成される
```

---

## ディレクトリ構成

```
scry/
├── docker-compose.yml
├── frontend/                      # Electron + Vue 3 + TypeScript
│   ├── Dockerfile                 # Docker 用（Vite dev server）
│   ├── electron/
│   │   ├── main.ts                # Electron メインプロセス
│   │   └── preload.ts             # IPC ブリッジ（contextIsolation）
│   ├── src/
│   │   ├── main.ts                # Vue エントリーポイント
│   │   ├── App.vue                # ルートコンポーネント
│   │   ├── router/                # Vue Router
│   │   ├── views/                 # 各画面コンポーネント
│   │   └── electron.d.ts          # window.electronAPI の型定義
│   ├── electron-builder.yml       # electron-builder 設定
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json              # Vue / src 用
│   └── tsconfig.electron.json     # electron/ 用（commonjs）
├── backend/                       # Python FastAPI
│   ├── Dockerfile                 # Docker 用（uvicorn）
│   ├── __version__.py             # バージョン管理
│   ├── app/
│   │   ├── main.py                # FastAPI アプリ・起動設定
│   │   └── routers/               # エンドポイント定義
│   ├── parser/
│   │   └── log_parser.py          # MTGOLogParser
│   ├── database.py                # SQLAlchemy 設定・セッション
│   └── requirements.txt
├── database/                      # SQLite ファイル置き場（永続化）
└── docs/                          # 設計ドキュメント
    ├── 01_architecture.md
    ├── 02_tech-stack.md
    ├── 03_api-design.md
    ├── 04_parser-design.md
    ├── 05_db-design.md
    ├── 06_screen-design.md
    ├── 07_analysis-design.md
    ├── 08_build-distribution.md
    └── 09_dev-setup.md
```

---

## AI 分析用エクスポートの活用

「エクスポート」画面から対戦データを Markdown ファイルとしてエクスポートし、AI サービスに貼り付けて分析できます。

### エクスポート時の推奨設定

| 目的 | 詳細レベル | 推奨件数 |
|------|-----------|---------|
| 全体傾向の把握 | サマリーのみ | 全件 |
| デッキ・マッチアップ分析 | マッチ一覧あり | 50〜200件 |
| プレイング改善 | アクション詳細あり | 20〜50件 |

### 推奨プロンプト例

#### 総合分析

```
添付のファイルは私のMagic: The Gatheringの対戦履歴データです。
以下の観点で分析してください。

1. 全体的な勝率と傾向
2. 勝敗に影響している要因（デッキ、先後手、マリガン回数など）
3. 改善が見込める点と強みとして活かせる点
4. 優先的に取り組むべき課題

できるだけ具体的な数値を根拠にした分析をお願いします。
```

#### デッキ改善

```
添付ファイルの対戦データをもとに、使用デッキの改善点を分析してください。

- 使用デッキごとの勝率比較
- 勝ちパターン・負けパターンの共通点
- 相性の良い対面・悪い対面の整理
- デッキ選択やサイドボード戦略の改善提案

具体的な対戦例を引用しながら説明してください。
```

#### 特定マッチアップの分析

```
添付ファイルの対戦データを確認してください。
[相手デッキ名] との対戦に絞って分析をお願いします。

- この対面の勝率と傾向
- 勝てた試合・負けた試合の違い
- 先手・後手による影響
- 有効なプレイライン・避けるべきプレイの傾向
- 次にこのデッキと当たったときのアドバイス
```

#### プレイング分析（アクション詳細あり）

```
添付ファイルには各ゲームのターン別アクションログが含まれています。
プレイングの質という観点で分析してください。

- 典型的なゲームの進行パターン
- 勝ちゲームと負けゲームでのアクションの違い（ターン数、プレイ順序など）
- マナカーブの使い方に関する傾向
- 特定のカードが勝敗に与えている影響
- プレイングミスが疑われるパターンがあれば指摘してください
```

#### 先手・後手の影響分析

```
添付の対戦データから、先手・後手が勝率に与える影響を分析してください。

- 先手/後手の全体勝率
- デッキ別の先手/後手勝率の違い
- 先手が有利なマッチアップ・後手でも勝てるマッチアップの特定
- 先手/後手でプレイスタイルを変えるべき点の提案
```

#### フォローアップ（初回分析後に使用）

```
# 深掘り
上記の分析で触れた「[気になるポイント]」についてさらに詳しく教えてください。
具体的な対戦例があれば引用してください。

# 練習プランの作成
分析結果をもとに、今後2週間で取り組むべき具体的な練習プランを作ってください。
デッキ調整・プレイング改善・マッチアップ研究の優先順位もつけてください。

# 仮説の検証
「[自分の仮説、例：マリガンしすぎている気がする]」という点について、
データを使って検証してください。
```

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
