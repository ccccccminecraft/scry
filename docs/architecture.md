# システムアーキテクチャ

MTGOおよびMTGAの対戦ログを記録・分析するデスクトップアプリ（Electron + FastAPI）。

---

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| デスクトップ | Electron（contextIsolation: true） |
| フロントエンド | Vue 3 + TypeScript + Vite |
| グラフ | vue-echarts（ECharts） |
| HTTP クライアント | axios（`frontend/src/api/client.ts`） |
| バックエンド | FastAPI（Python） |
| ORM | SQLAlchemy 2.x |
| DB | SQLite（`database/mtgo.db`） |
| ビルド | electron-builder（Windows インストーラー） |

---

## コンポーネント構成

```
Electron
  ├── Main Process（electron/main.ts）
  │     ├── IPC ハンドラー（ファイル選択・スキャン等）
  │     └── 本番時: backend.exe をサブプロセスとして起動
  │
  └── Renderer Process
        └── Vue 3 アプリ（localhost:5173 or dist/index.html）
              └── axios → FastAPI（localhost:18432）

FastAPI（backend/）
  ├── app/routers/        エンドポイント定義
  ├── models/             SQLAlchemy モデル
  ├── services/           ビジネスロジック
  ├── parser/             ログパーサー
  └── database/           DB 接続・init_db()

SQLite（database/mtgo.db）
```

---

## 環境別構成

### 開発環境

```
ホスト
├── Electron（npm run dev:electron）
│     └── localhost:5173 に接続
└── Docker Compose
      ├── frontend コンテナ（Vite dev server :5173）
      │     volume: ./frontend:/app
      └── backend コンテナ（uvicorn --reload :18432）
            volume: ./backend:/app, ./database:/database
```

> **注意**: backend コンテナはホストのファイルシステムにアクセスできない（volume 外）。
> Surveil 監視フォルダスキャンなどのファイルシステム操作は Electron（Main Process）側で行う。

### 本番環境

```
Windows PC
└── ScrySetup.exe
      └── Electron アプリ
            ├── dist/index.html（Vue ビルド済み）
            └── resources/backend.exe（PyInstaller）
                  └── localhost:18432 でリッスン
```

起動シーケンス: Electron 起動 → backend.exe をspawn → `/api/health` ポーリング → loadFile

---

## Electron IPC API（preload.ts）

`contextBridge.exposeInMainWorld('electronAPI', { ... })` で公開。

| メソッド | 説明 |
|---------|------|
| `selectDatFile()` | .dat ファイル選択ダイアログ → パス返却 |
| `selectJsonFile()` | .json ファイル選択ダイアログ → パス返却 |
| `scanFolder()` | ディレクトリ選択 → Match_GameLog_*.dat を再帰スキャン → `{folderPath, files[]}` |
| `scanFolderQuick(folderPath)` | ダイアログなしで .dat スキャン → `{path, mtime}[]` |
| `scanSurveilFolder(folderPath)` | ダイアログなしで .json スキャン → `{path, name, mtime, size}[]` |
| `readDatFile(filePath)` | ファイルを Buffer として読み込み（.dat / .json 両対応） |

---

## データフロー

### MTGOログインポート

```
.dat ファイル（ユーザーが選択 or ドロップ or フォルダスキャン）
  │
  ▼ Electron IPC でファイル読み込み（readDatFile）
  │ またはドロップの場合は HTML5 File API で直接取得
  ▼
POST /api/import（multipart/form-data）
  │
  ▼ parser/mtgo_parser.py（バイナリ解析）
  ▼ ImportService（フォーマット判定・DB 保存）
SQLite
```

### MTGAログインポート（Surveil）

```
Surveil 出力ファイル（{match_id}.json）
  │
  ├── 手動（ドロップ / ファイル選択）
  │     ▼ POST /api/import/surveil
  │
  └── フォルダ監視（「全て取り込む」ボタン）
        ▼ Electron: scanSurveilFolder → ファイル一覧取得
        ▼ GET /api/import/surveil/imported-ids → 取り込み済みID取得
        ▼ 差分ファイルを readDatFile で読み込み
        ▼ POST /api/import/surveil（ファイルごと）

schema_version=3（現行）:
  ▼ gre_parser.py → GREParseResult（grpId 未解決）
  ▼ ScryfallClient.fetch_by_arena_ids() → grpId → card_name 解決
      ├── mtga_cards キャッシュ（DB）
      └── obj_name_map フォールバック（トークン・基本土地）
  ▼ SurveilImportService._save() → DB 保存
  ▼ _sync_deck_from_import() → デッキ自動登録（Deck / DeckVersion 作成 or スキップ）
  ▼ _infer_format_from_deck() → フォーマット推定

schema_version=2（後方互換）:
  ▼ surveil_parser.py → SurveilParseResult → SurveilImportService._save()
```

### 自動インポート（バックグラウンドスケジューラー）

FastAPI 起動時に asyncio バックグラウンドタスクとして常駐するスケジューラー。

```
FastAPI 起動
  ▼ lifespan イベントでスケジューラータスク開始
  │
  ループ（設定間隔ごと、デフォルト 30 秒）
  │
  ├── auto_import_enabled が false → スキップ
  │
  ├── MTGO スキャン
  │     ▼ quick_import_folder 設定取得
  │     ▼ DB の既存 match_id セットと差分比較（mtime ベース）
  │     ▼ ImportService で新ファイルをインポート
  │
  └── MTGA スキャン
        ▼ surveil_folder 設定取得
        ▼ DB の既存 match_id セットと差分比較
        ▼ SurveilImportService で新ファイルをインポート
              ▼ デッキ自動登録（_sync_deck_from_import）も実行

最終実行日時・結果 → DB（settings テーブル）に保存
  ▼ GET /api/import/auto-import/status で取得可能
```

> **開発環境（Docker）の注意**: バックエンドコンテナはホストのファイルシステムにアクセスできないため、
> MTGO / Surveil フォルダを `docker-compose.yml` の volume に追加するか、
> フォルダパスを `/database/...` 以下にマウントしたパスで指定する必要がある。
> 本番環境（backend.exe）ではネイティブアクセスなので制約なし。

### AI 分析

```
SQLite（試合データ）
  ▼ 統計集計クエリ
  ▼ Markdown エクスポート生成（GET /api/matches/export）
  ▼ ユーザーがクリップボードにコピー or ファイル保存 → 外部 AI へ貼り付け
```

または

```
POST /api/analysis/chat（SSE ストリーミング）
  ▼ DB から統計集計 → システムプロンプト生成
  ▼ LLM API（Claude / OpenAI）呼び出し
  ▼ SSE でフロントエンドにストリーミング
```

### API キー管理

```
PUT /api/settings（APIキー含む）
  └── APIキー（anthropic_api_key）・llm_provider 等 → SQLite settings テーブルに平文保存
      環境変数 ANTHROPIC_API_KEY も参照（DB 優先）
```

---

## ディレクトリ構成

```
scry/
├── frontend/
│   ├── electron/
│   │   ├── main.ts          Electron Main Process・IPC ハンドラー
│   │   └── preload.ts       contextBridge 公開 API
│   └── src/
│       ├── api/             axios クライアント・型定義
│       ├── components/      共通コンポーネント
│       ├── composables/     useToast 等
│       ├── views/           画面コンポーネント（*View.vue）
│       └── electron.d.ts    electronAPI 型定義
├── backend/
│   ├── app/
│   │   ├── main.py          FastAPI アプリ・ルーター登録
│   │   └── routers/         エンドポイント定義
│   ├── models/
│   │   ├── core.py          Match / MatchPlayer / Game / Action / Mulligan
│   │   ├── decklist.py      Card / Deck / DeckVersion / DeckVersionCard
│   │   ├── analysis.py      AnalysisSession / AnalysisMessage / PromptTemplate / QuestionSet
│   │   └── cache.py         Setting / CardLegality / MtgaCard
│   ├── services/
│   │   ├── import_service.py   ImportService / SurveilImportService
│   │   └── scryfall_client.py  Scryfall API クライアント（カード名・レガリティ取得）
│   ├── parser/
│   │   ├── mtgo_parser.py      MTGO .dat バイナリパーサー
│   │   ├── surveil_parser.py   Surveil 出力ファイル パーサー（schema_version: 2）
│   │   └── gre_parser.py       GRE メッセージパーサー（schema_version: 3）
│   └── database.py          DB 接続・init_db()（ALTER TABLE マイグレーション含む）
├── database/
│   └── mtgo.db              SQLite DB ファイル
└── docs/                    本ドキュメント群
```

---

## パーサー概要

詳細は [parser.md](parser.md) を参照。

### MTGOパーサー（`parser/mtgo_parser.py`）

- .dat ファイルはバイナリ形式。.NET DateTime.Ticks 基準の日時を含む
- プレイヤー名プレフィックス `@P` を除去しながらパース
- カード ID は MTGO 内部 ID → Scryfall `/cards/named?exact=` でカード名解決
- フォーマット判定: `card_legality` テーブルを参照（未キャッシュは Scryfall API で取得）

### Surveil パーサー（`parser/surveil_parser.py`）

- `schema_version: 2` の JSON を処理（後方互換として維持）
- 17 種類のイベントタイプを解析し、action_type にマッピング
- フォーマット判定: デッキのメインカード名（基本土地除く）から Scryfall で判定

### GRE パーサー（`parser/gre_parser.py`）

- `schema_version: 3` の Surveil 出力ファイルを処理
- `gre_messages` 内の `GameStateMessage` アノテーションを解析してアクションを抽出
- grpId はこのパーサーでは解決せず、呼び出し元（`SurveilImportService`）が一括解決する
- `GREParseResult.all_grp_ids`：デッキ＋全アクションの grpId セット（バッチ解決用）
- `GREParseResult.obj_name_map`：gameObjects から合成したフォールバック名マップ
  - 対象：`GameObjectType_Token`（"Warrior Token" 等）、基本土地 alt-art（"Forest" 等）
  - 除外：その他の `GameObjectType_Card`（サブタイプ ≠ カード名のため合成しない）

---

## カード名解決（MTGA）

grpId（MTGA 内部カード ID）→ カード名の解決は以下の優先順位で行う。

| 優先順位 | 手段 | 対象 |
|---------|------|------|
| 1 | `mtga_cards` テーブル（キャッシュ） | 解決済みの全 grpId |
| 2 | Scryfall `GET /cards/arena/{id}` | 正規カード |
| 3 | `obj_name_map`（gameObjects から合成） | トークン・基本土地 alt-art |
| 4 | null | 相手の非公開情報・Scryfall 未収録の新セットカード等 |

### 今後の改善計画（未実装）

Scryfall `Bulk Data API`（`/bulk-data/default-cards`）を定期同期することで、
個別 API 呼び出しを不要にし、新セットカードの収録ラグを短縮する予定。
- 解決不能なケース（非常に新しいカード等）が残る場合は MTGA 公式 CDN データを補助的に利用する方針。
