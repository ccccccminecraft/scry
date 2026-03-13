# システムアーキテクチャ設計

## 概要

Magic Online（MTGO）の対戦ログ（`.dat`ファイル）を解析し、勝率・プレイパターンをAIで分析するデスクトップアプリ。

---

## コンポーネント構成

```
┌─────────────────────────────────────────────────┐
│ Electron（ホスト）                               │
│                                                  │
│  ┌──────────────────┐   ┌──────────────────┐    │
│  │ Renderer Process │   │  Main Process    │    │
│  │ (Vue 3 + Vite)   │   │  (electron/      │    │
│  │                  │◄──│   main.ts)       │    │
│  │ localhost:5173   │   │                  │    │
│  └────────┬─────────┘   └────────┬─────────┘    │
│           │ HTTP/axios           │ spawn         │
└───────────┼──────────────────────┼───────────────┘
            │                      │
            ▼                      ▼
┌───────────────────┐   ┌─────────────────────────┐
│ FastAPI Backend   │   │ Python Backend Process  │
│ localhost:8000    │   │ （本番時: backend.exe）   │
│                   │   └─────────────────────────┘
│ /api/health       │
│ /api/matches      │   ┌─────────────────────────┐
│ /api/stats        │──►│ SQLite                  │
│ /api/analysis     │   │ database/mtgo.db        │
│ /api/settings     │   └─────────────────────────┘
│                   │
│                   │   ┌─────────────────────────┐
│ /api/analysis ────┼──►│ LLM API（外部）          │
│                   │   │ Claude API / OpenAI API  │
└───────────────────┘   └─────────────────────────┘
```

---

## 環境別構成

### 開発環境（Docker Compose）

```
ホスト
├── Electron（npm run dev:electron）
│     └── localhost:5173 に接続
└── Docker Compose
      ├── frontend コンテナ（Vite dev server :5173）
      └── backend コンテナ（uvicorn :8000）
```

### 本番環境（配布 exe）

```
Windows PC
└── ScrySetup.exe を実行
      └── Electron アプリ
            ├── dist/index.html（Vue ビルド済み）
            └── resources/backend.exe（PyInstaller ビルド済み）
                  └── 起動後 localhost:8000 でリッスン
```

---

## 起動シーケンス

### 開発時

```
1. docker compose up
   → frontend コンテナ（Vite）起動
   → backend コンテナ（uvicorn）起動

2. npm run dev:electron（ホスト）
   → localhost:5173 が応答するまで待機（wait-on）
   → Electron ウィンドウ起動
   → localhost:5173 を loadURL
```

### 本番時

```
1. ユーザーが exe を起動
2. Electron Main Process 起動
3. resources/backend.exe をサブプロセスとして起動
4. localhost:8000 が応答するまでポーリング
5. 応答確認後、dist/index.html を loadFile
6. アプリ終了時（before-quit）に backend.exe を kill
```

---

## データフロー

### ログインポート

```
.dat ファイル（MTGO ログ）
  │
  ▼ ファイル選択（UI）
FastAPI /api/import
  │
  ▼ MTGOLogParser.parse_file()
構造化データ（dict）
  │
  ▼ SQLAlchemy
SQLite（mtgo.db）
  │
  ▼ /api/matches, /api/stats
Vue コンポーネント（表示・グラフ）
```

### AI 分析

```
SQLite（mtgo.db）
  │
  ▼ 統計集計クエリ
統計テキスト生成
  │
  ▼ LLM API 呼び出し（Claude API / OpenAI API）
     ※ ユーザーが設定画面で API キーを登録済みの場合のみ実行
  │
  ▼ 分析結果（summary / insights）
Vue コンポーネント（S06 AI 分析画面）
```

### API キー管理

```
ユーザーが S07 設定画面で API キーを入力
  │
  ▼ PUT /api/settings
FastAPI
  ├── API キー → OS キーストア（keyring）に保存
  │     Windows: Credential Manager
  │     Mac:     Keychain
  └── LLM プロバイダー設定 → SQLite（settings テーブル）に保存
  │
  ▼ /api/analysis 呼び出し時
FastAPI
  ├── keyring.get_password("scry", "llm_api_key") で API キー取得
  └── LLM API を呼び出し
```

---

## ファイルインポート UX フロー

### ファイル取得の3ルート

`contextIsolation: true` の制約上、Renderer から直接ファイルシステムにアクセスできない。
ファイルの取得方法によって処理ルートが異なる。

```
【ルート A】ファイル選択ボタン（単体）
Renderer
  │ ipcRenderer.invoke('select-dat-file')    ← preload.ts 経由
  ▼
Main Process
  │ dialog.showOpenDialog()                  ← ファイル選択ダイアログ
  │ fs.readFile(filePath)                    ← ファイル読み込み
  │ return { name, buffer: ArrayBuffer }
  ▼
Renderer
  │ new Blob([buffer]) → FormData に追加
  ▼
FastAPI POST /api/import

【ルート B】ドラッグ＆ドロップ（単体）
Renderer
  │ drop イベント → event.dataTransfer.files[0]
  │ File オブジェクトを FormData に追加       ← IPC 不要（HTML5 File API で直接取得）
  ▼
FastAPI POST /api/import

【ルート C】フォルダスキャン（一括）
Renderer
  │ ipcRenderer.invoke('scan-folder')        ← preload.ts 経由
  ▼
Main Process
  │ dialog.showOpenDialog({ properties: ['openDirectory'] })
  │ glob('**/Match_GameLog_*.dat', { cwd: folderPath })  ← 再帰検索
  │ return { files: [{ name, path }] }       ← ファイル一覧のみ返す（バッファは未読み込み）
  ▼
Renderer
  │ ファイル一覧を表示（チェックボックス付き）
  │ ユーザーが取り込むファイルを確認・選択
  │ 「インポート実行」クリック
  │
  │ ipcRenderer.invoke('read-dat-file', path) を選択ファイル分繰り返す
  ▼
Main Process（ファイルごと）
  │ fs.readFile(filePath) → ArrayBuffer
  ▼
Renderer
  │ POST /api/import を順次実行（プログレスバー更新）
  ▼
FastAPI POST /api/import（ファイルごと）
```

### MTGO ログのデフォルトフォルダパス

Windows では以下のパスにログが保存されることが多い。フォルダ選択ダイアログの初期パスとして設定する。

```
C:\Users\[ユーザー名]\AppData\Local\Apps\2.0\
```

ただし環境によってパスが異なるため、あくまで「ヒント」として表示し、ユーザーが変更できるようにする。

### スキャン対象ファイルのパターン

```
Match_GameLog_*.dat
例: Match_GameLog_1455b717-9154-45ea-bee9-a5193fa15468.dat
```

サブディレクトリを含む再帰検索を行う。

### preload.ts で公開する API

```typescript
// electron/preload.ts
contextBridge.exposeInMainWorld('electronAPI', {
  // ルート A: 単体ファイル選択
  selectDatFile: (): Promise<{ name: string; buffer: ArrayBuffer } | null> =>
    ipcRenderer.invoke('select-dat-file'),

  // ルート C: フォルダスキャン（ファイル一覧取得）
  scanFolder: (): Promise<{ name: string; path: string }[] | null> =>
    ipcRenderer.invoke('scan-folder'),

  // ルート C: スキャン結果からファイルを読み込み
  readDatFile: (filePath: string): Promise<{ name: string; buffer: ArrayBuffer }> =>
    ipcRenderer.invoke('read-dat-file', filePath),
})
```

### UI 状態遷移

```
[Idle]
  ドロップゾーン表示
  「ファイルを選択」ボタン / 「フォルダから取り込む」ボタン
  │
  ├── 「ファイルを選択」クリック → ダイアログ → ファイル選択
  │         ▼
  │   [FileSelected]  ← ルート A / B
  │   ファイル名表示 / 「インポート実行」ボタン有効
  │         │
  │         └── 「インポート実行」クリック
  │                   ▼
  │             [Importing]（単体）
  │             スピナー表示
  │
  ├── ファイルドロップ  →  [FileSelected]（同上）
  │
  └── 「フォルダから取り込む」クリック → フォルダ選択ダイアログ
            ▼
      [Scanning]  ← ルート C
      「スキャン中...」表示
            │
            ▼
      [ScanResult]
      見つかったファイル一覧（チェックボックス付き）
      「N件のログファイルが見つかりました」
      └── 「すべて選択」「インポート実行」ボタン
            │
            └── 「インポート実行」クリック
                      ▼
                [Importing]（一括）
                プログレスバー「N / M 件処理中...」
                      │
                      ▼
                [BatchResult]
                「✅ N件インポート済み / M件スキップ（重複）/ K件エラー」
```

### エラーケース

| エラー | メッセージ例 | 対処 |
|--------|-------------|------|
| 不正なファイル形式 | 「.dat ファイルを選択してください」 | FileSelected に戻る |
| パース失敗 | 「ログのフォーマットが認識できません」 | FileSelected に戻る |
| 重複インポート（単体） | 「このマッチはすでにインポート済みです」 | FileSelected に戻る |
| 重複インポート（一括） | スキップ扱いでカウント、エラーにはしない | BatchResult に件数を表示 |
| スキャン結果が0件 | 「対象ファイルが見つかりませんでした」 | Idle に戻る |
| サーバーエラー | 「インポートに失敗しました（500）」 | FileSelected に戻る |

---
