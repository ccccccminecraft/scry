# ビルド・配布設計

## 概要

開発環境（Docker Compose）とは独立したビルドパイプラインで、Windows 向けスタンドアロン installer を生成する。

---

## 配布物の構成

```
ScrySetup.exe（Windows installer）
  └── インストール後
        └── Scry/
              ├── Scry.exe                  ← Electron アプリ本体
              └── resources/
                    ├── app.asar            ← Vue ビルド済み + Electron コード
                    └── backend.exe         ← PyInstaller でビルドした Python サーバー
```

---

## ビルドパイプライン

```
Step 1: Python バックエンドのビルド
  └── PyInstaller → backend/dist/backend.exe

Step 2: Vue フロントエンドのビルド
  └── vite build → frontend/dist/

Step 3: Electron アプリのパッケージング
  └── electron-builder → backend.exe を extraResources に含めて
                          Windows installer を生成
```

---

## Step 1: PyInstaller によるバックエンドビルド

```bash
cd backend
pip install pyinstaller
pyinstaller --onefile --name backend --collect-all keyring app/main.py
# → backend/dist/backend.exe が生成される
```

### PyInstaller オプション

| オプション | 説明 |
|------------|------|
| `--onefile` | 単一 exe ファイルにバンドル |
| `--name backend` | 出力ファイル名を `backend.exe` に指定 |
| `--noconsole` | コンソールウィンドウを非表示（本番時） |

### 注意事項

- 依存ライブラリ（FastAPI / uvicorn / SQLAlchemy 等）がすべてバンドルされる
- `--onefile` は起動時に一時ディレクトリに展開するため、初回起動が数秒かかる場合がある

---

## Step 2: Vite によるフロントエンドビルド

```bash
cd frontend
npm run build
# → frontend/dist/ に HTML/JS/CSS が生成される
```

---

## Step 3: electron-builder によるパッケージング

### `frontend/electron-builder.yml`

```yaml
appId: com.scry.app
productName: Scry
directories:
  output: dist_electron
files:
  - dist/**
  - electron/**
extraResources:
  - from: ../backend/dist/backend.exe
    to: backend.exe
win:
  target: nsis
  icon: assets/icon.ico
nsis:
  oneClick: false
  allowToChangeInstallationDirectory: true
```

### ビルドコマンド

```bash
cd frontend
npm run build:electron
# → frontend/dist_electron/ScrySetup.exe が生成される
```

---

## `electron/main.ts` の本番時挙動

```typescript
import { app, BrowserWindow } from 'electron'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'

const isDev = !app.isPackaged
let backendProcess: ChildProcess | null = null

function startBackend() {
  if (isDev) return  // 開発時は Docker が担当

  const backendPath = path.join(process.resourcesPath, 'backend.exe')
  backendProcess = spawn(backendPath, [], { detached: false })
}

app.on('before-quit', () => {
  backendProcess?.kill()
})
```

---

## 開発環境 vs 本番環境 の対応表

| 項目 | 開発環境 | 本番環境 |
|------|----------|----------|
| Vite dev server | Docker frontend コンテナ | Vite ビルド済み dist/ |
| FastAPI | Docker backend コンテナ | resources/backend.exe |
| Electron 起動 | `npm run dev:electron`（ホスト） | ScrySetup.exe |
| Python 管理 | Docker | PyInstaller バンドル |

---

## ビルド実行環境

- OS: **Windows ホスト**（electron-builder の Windows ビルドは Windows 上で実行）
- 必要ツール: Node.js 20+、Python 3.11+、pip（Windows 側にインストール）
- 開発は WSL2 で完結するため、Windows 側ツールは配布ビルド時のみ使用する

---

## アイコン仕様

`frontend/assets/icon.ico` として配置する。実装フェーズで作成する。

| 項目 | 仕様 |
|------|------|
| フォーマット | ICO（複数サイズ埋め込み） |
| 必須サイズ | 16x16 / 32x32 / 48x48 / 256x256 px |
| 用途 | タスクバー・スタートメニュー・インストーラー |

---

## 対応プラットフォーム

**初期リリース: Windows のみ**

| プラットフォーム | 状況 |
|----------------|------|
| Windows | 対応（NSIS installer） |
| Mac | 将来の拡張候補（`.dmg`） |

---

## コードサイニング

初期リリースではコードサイニング証明書を取得しない。

Windows SmartScreen の警告が表示される場合があるが、個人利用を想定しているため許容する。

---

## CI/CD

初期リリースではローカルビルドのみ対応する。自動化は将来の拡張候補とする。

---

## keyring バンドル確認手順（実装フェーズ）

`--collect-all keyring` でバックエンドプラグインが正しくバンドルされているか、ビルドした `backend.exe` で以下を確認する。

1. `backend.exe` を単体で起動する（PyInstaller の一時展開ディレクトリ以外に Python 環境がない状態で）
2. `PUT /api/settings` で API キーを登録する
3. タスクマネージャーまたは `credential manager` で Windows Credential Manager にキーが保存されていることを確認する
4. `GET /api/settings` で `api_key_configured: true` が返ることを確認する
5. アプリを再起動後も `api_key_configured: true` が維持されることを確認する

---

## TODO

- [ ] `assets/icon.ico` の作成（実装フェーズ）
- [ ] keyring の PyInstaller バンドル動作確認（実装フェーズ）
