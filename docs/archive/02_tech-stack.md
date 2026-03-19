# 技術スタック選定

## 一覧

| レイヤー | 採用技術 | バージョン |
|----------|----------|------------|
| デスクトップ | Electron | 最新安定版 |
| フロントエンド | Vue 3 | 3.x |
| ビルドツール | Vite | 6.x |
| 言語（フロント） | TypeScript | 5.x（strict モード） |
| グラフ | ECharts + vue-echarts | 最新安定版 |
| バックエンド | FastAPI | 0.x |
| 言語（バック） | Python | 3.11+ |
| ASGI サーバー | uvicorn | 最新安定版 |
| ORM | SQLAlchemy | 2.x |
| DB | SQLite | - |
| 開発環境 | Docker Compose | v2 |
| パッケージング | PyInstaller + electron-builder | - |
| LLM API | Claude API / OpenAI API | - |
| LLM SDK | anthropic / openai（Python） | 最新安定版 |
| シークレット管理 | keyring（Python） | 最新安定版 |

---

## 選定理由

### Electron

- Web 技術（HTML/CSS/JS）でデスクトップ GUI を構築できる
- Windows / Mac クロスプラットフォーム対応
- Node.js との統合により、ファイルシステムアクセスが容易
- **代替案**: Tauri（Rust ベース、軽量だが学習コストが高い）

### Vue 3 + Vite + TypeScript

- コンポーネントベースの UI 開発が容易
- Vite による高速な HMR（ホットリロード）
- TypeScript strict モードで型安全性を確保
- **代替案**: React（エコシステムが大きいが、Vue のほうがシンプル）

### FastAPI（Python）

- MTGO ログのパース処理を Python で実装するため、バックエンドも Python に統一
- async 対応・自動 OpenAPI ドキュメント生成
- **代替案**: Flask（シンプルだが async サポートが弱い）

### SQLite

- 外部 DB サーバー不要でスタンドアロン配布に適している
- 対戦ログのデータ量であれば性能上の問題なし
- **代替案**: PostgreSQL（スケーラブルだがサーバーが必要）

### Docker Compose（開発環境のみ）

- 開発者間で環境を統一できる
- Python venv・Node.js バージョン管理が不要
- 本番配布には不使用（PyInstaller + electron-builder で解決）

### PyInstaller

- Python 実行環境ごと単一 exe にバンドルできる
- 配布先に Python インストール不要
- **代替案**: cx_Freeze（PyInstaller のほうが実績が多い）

---

### ECharts + vue-echarts

- 折れ線・棒グラフ程度の現状要件に加え、将来的な拡張（デッキ別分析・カード別統計等）にも対応できる
- `vue-echarts` により Vue 3 コンポーネントとして簡潔に利用できる
- **代替案**: Chart.js（軽量だが拡張性が低い）/ D3.js（自由度が高すぎて今回の用途にはオーバースペック）

---

### LLM API（Claude API / OpenAI API）

- **デフォルト: Claude API**（ユーザーが設定画面で OpenAI API に変更可能）
- バックエンド（Python）から `anthropic` または `openai` SDK を使って呼び出す
- API キーはユーザーが取得・設定する（アプリ側では管理しない）
- **代替案**: ローカル LLM（Ollama）は配布の複雑さ・ハードウェア要件の観点で採用しない

### keyring（シークレット管理）

- API キーを OS のセキュアストレージに保存する
  - Windows: Credential Manager
  - Mac: Keychain
- `keyring.set_password("scry", "llm_api_key", api_key)` で保存
- `keyring.get_password("scry", "llm_api_key")` で取得
- SQLite には保存しない（平文・暗号化問わず）
- PyInstaller バンドル時は `--collect-all keyring` オプションが必要
