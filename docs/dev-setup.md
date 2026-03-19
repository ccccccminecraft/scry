# 開発環境セットアップ

## 前提環境

| 項目 | 要件 |
|------|------|
| OS | Windows 11（WSL2 + WSLg） |
| WSL2 ディストリビューション | Ubuntu 22.04 / 24.04 |
| Docker Desktop | WSL2 バックエンドで動作していること |
| Node.js | WSL2 内に 20+ インストール済み |

---

## 初回セットアップ（一度だけ実行）

### 1. Electron 用 Linux システムライブラリ

```bash
sudo apt update
sudo apt install -y libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 \
  libcups2t64 libdrm2 libxkbcommon0 libxcomposite1 \
  libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2t64 libgtk-3-0t64
```

> Ubuntu 24.04 では一部パッケージ名に `t64` サフィックスが付く。

### 2. 日本語フォント

```bash
sudo apt install -y fonts-noto-cjk
```

### 3. フロントエンドの依存パッケージ

```bash
cd /path/to/scry/frontend
npm install
```

> `node_modules` はホストの `frontend/` に置くが、Docker コンテナ内では `/app/node_modules` として volume マウント除外されている。
> コンテナ内で追加パッケージが必要な場合は `docker compose exec frontend npm install <pkg>` を使う。

---

## 開発サーバーの起動

### ステップ 1: Docker で Vite + FastAPI を起動

```bash
cd /path/to/scry
docker compose up
```

| サービス | URL |
|---------|-----|
| Vite dev server | http://localhost:5173 |
| FastAPI | http://localhost:18432 |

接続確認:

```bash
curl http://localhost:18432/api/health
# → {"status":"ok","version":"0.1.0"}
```

### ステップ 2: 別ターミナルで Electron を起動

```bash
cd /path/to/scry/frontend
npm run dev:electron
```

`wait-on` が http://localhost:5173 の応答を待ってから Electron ウィンドウが開く。

---

## 停止

```bash
docker compose down   # Docker サービス停止
# Electron はウィンドウを閉じるか Ctrl+C
```

---

## ホットリロード

| 変更箇所 | 反映方法 |
|---------|---------|
| `src/` 以下（Vue コンポーネント等） | Vite HMR で自動反映 |
| `electron/main.ts` / `electron/preload.ts` | `npx tsc -p tsconfig.electron.json` 後、Electron 再起動 |
| `backend/` 以下（Python） | uvicorn `--reload` で自動反映 |

---

## TypeScript 型チェック

```bash
cd /path/to/scry/frontend

# Vue / src の型チェック
npx vue-tsc --noEmit

# electron/ の型チェック & コンパイル
npx tsc -p tsconfig.electron.json
# → dist-electron/main.js, dist-electron/preload.js が生成される
```

---

## トラブルシューティング

### Electron ウィンドウが開かない

WSLg が有効か確認する。

```bash
echo $DISPLAY   # → ":0" 等が表示されれば OK
```

### 「Backend not connected」が表示される

```bash
docker compose ps
docker compose logs backend
```

### `npm run dev:electron` が起動しない

`wait-on` が http://localhost:5173 を待機中の場合、frontend コンテナが未起動の可能性がある。

```bash
docker compose logs frontend
```

### Electron の依存ライブラリが不足

エラーメッセージのライブラリ名を確認して追加インストール。

```bash
sudo apt install -y <ライブラリ名>
```
