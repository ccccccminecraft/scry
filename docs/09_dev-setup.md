# 開発環境セットアップ・動作確認

## 前提環境

| 項目 | 要件 |
|------|------|
| OS | Windows 11（WSLg 標準搭載） |
| WSL2 ディストリビューション | Ubuntu 22.04 推奨 |
| Docker Desktop | WSL2 バックエンドで動作していること |
| Node.js | WSL2 内に 20+ インストール済み |

---

## 初回セットアップ（一度だけ実行）

### 1. Electron 用 Linux システムライブラリのインストール

WSL2 内で以下を実行する。

```bash
sudo apt update
sudo apt install -y libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 \
  libcups2t64 libdrm2 libxkbcommon0 libxcomposite1 \
  libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2t64 \
  libgtk-3-0t64
```

> Ubuntu 24.04 では一部パッケージ名に `t64` サフィックスが付く。`apt` が `t64` 版を自動選択する場合はそちらを使用する。

### 2. 日本語フォントのインストール

```bash
sudo apt install -y fonts-noto-cjk
```

### 3. フロントエンドの依存パッケージインストール

```bash
cd /path/to/scry/frontend
npm install
```

### 4. バックエンドの依存パッケージインストール

```bash
cd /path/to/scry/backend
pip install -r requirements.txt
```

---

## 開発サーバーの起動

### ステップ 1: Docker で Vite dev server + FastAPI を起動

```bash
cd /path/to/scry
docker compose up
```

起動確認：

| サービス | URL | 確認方法 |
|---------|-----|---------|
| Vite dev server | http://localhost:5173 | ブラウザでアクセス可能 |
| FastAPI | http://localhost:8000 | 次のコマンドで確認 |

```bash
curl http://localhost:8000/api/health
# → {"status":"ok","version":"0.1.0"} が返れば OK
```

### ステップ 2: 別ターミナルで Electron を起動

```bash
cd /path/to/scry/frontend
npm run dev:electron
```

`wait-on` が http://localhost:5173 の応答を待ってから Electron ウィンドウが開く。

---

## 動作確認チェックリスト

### 開発環境

- [ ] `docker compose up` → frontend（:5173）と backend（:8000）が起動する
- [ ] `curl http://localhost:8000/api/health` → `{"status":"ok","version":"0.1.0"}` が返る
- [ ] `npm run dev:electron` → Electron ウィンドウ（1200×800）が起動する
- [ ] ホーム画面に「✅ Backend connected」が表示される
- [ ] ホーム画面に「✅ Backend connected」が緑色で表示される
- [ ] FastAPI を停止した状態で `npm run dev:electron` を起動すると「❌ Backend not connected」が赤色で表示される

### TypeScript コンパイル確認

```bash
cd /path/to/scry/frontend

# Vue / src の型チェック
npx vue-tsc --noEmit

# electron/ の型チェック＆コンパイル
npx tsc -p tsconfig.electron.json
# → dist-electron/main.js, dist-electron/preload.js が生成される
```

---

## 開発サーバーの停止

```bash
# Docker サービスの停止
docker compose down

# Electron はウィンドウを閉じるか Ctrl+C で停止
```

---

## ホットリロードの挙動

| 変更箇所 | 反映方法 |
|---------|---------|
| `src/` 以下（Vue コンポーネント等） | Vite の HMR により自動反映 |
| `electron/main.ts` / `electron/preload.ts` | `tsc -p tsconfig.electron.json` 後、Electron を再起動 |
| `backend/` 以下（Python） | uvicorn の `--reload` により自動反映 |

---

## トラブルシューティング

### Electron ウィンドウが開かない

WSLg が有効になっているか確認する。

```bash
# WSLg が有効であれば DISPLAY 環境変数が設定されている
echo $DISPLAY
# → :0 などが表示されれば OK
```

### 「Backend not connected」が表示される

```bash
# Docker コンテナが起動しているか確認
docker compose ps

# バックエンドのログを確認
docker compose logs backend
```

### `npm run dev:electron` が Electron を起動しない

`wait-on` が http://localhost:5173 を待機中の場合、Docker の frontend コンテナが起動していない可能性がある。

```bash
docker compose logs frontend
```

### Electron の依存ライブラリが不足している場合

```bash
# エラーメッセージに含まれるライブラリ名を確認して追加インストール
sudo apt install -y <ライブラリ名>
```
