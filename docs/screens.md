# 画面設計

## 画面一覧

| パス | コンポーネント | 概要 |
|------|--------------|------|
| `/` | HomeView | ホーム・バックエンド接続確認 |
| `/import` | ImportView | ログインポート（MTGO / MTGA タブ） |
| `/matches` | MatchListView | 対戦履歴一覧 |
| `/matches/:match_id` | MatchDetailView | 対戦詳細・アクションログ |
| `/stats` | StatsView | 統計ダッシュボード |
| `/decks` | DeckDefinitionsView | アーキタイプ定義管理（自動識別ルール） |
| `/analysis` | AnalysisView | AI チャット分析 |
| `/export` | AIExportView | AI 用 Markdown エクスポート |
| `/deck-builder` | DeckBuilderView | デッキ構築管理（バージョン・カードビュー） |
| `/settings` | SettingsView | 設定・データ管理（バックアップ/削除） |
| `/presets` | PresetsView | プロンプトテンプレート・質問セット管理 |
| `/presets/templates/new` 他 | PromptTemplateEditView / QuestionSetEditView | 編集サブ画面 |

---

## 画面遷移

グローバルナビゲーション（左サイドバー）からどの画面へも直接遷移可能。

```
HomeView
  └──► ImportView（インポート完了後 → MatchListView）

MatchListView
  └──► MatchDetailView（行クリック）

AnalysisView / AIExportView
  └──► SettingsView（APIキー未設定時）

PresetsView
  ├──► PromptTemplateEditView
  └──► QuestionSetEditView
```

---

## 各画面詳細

### HomeView（`/`）

- `GET /api/health` でバックエンド接続確認
- 成功: 「✅ Backend connected」/ 失敗: 「❌ Backend not connected」

---

### ImportView（`/import`）

MTGO / MTGA（Surveil）の2タブ構成。

**MTGO タブ**

- クイックインポート: フォルダ登録 + `scanFolderQuick` IPC で mtime 判定して新ファイルのみ取り込む
- フォルダ一括取り込み: `scanFolder` IPC でファイル一覧 → チェックボックス選択 → 順次 POST
- ドラッグ＆ドロップ / ファイル選択: 単体インポート
- 使用API: `POST /api/import`

**MTGA タブ**

- 監視フォルダ登録（`PUT /api/import/surveil/folder`）
- `scanSurveilFolder` IPC + `GET /api/import/surveil/imported-ids` で pending 判定・表示
- 「全て取り込む」: pending ファイルを `readDatFile` で読み込み → 順次 `POST /api/import/surveil`
- ドラッグ＆ドロップ / ファイル選択（.json）: 単体インポート

**共通状態遷移**: idle → importing（プログレスバー） → batch_result（件数表示）

---

### MatchListView（`/matches`）

- `GET /api/matches` で一覧取得（50件/ページ）
- フィルター: プレイヤー・相手・デッキ・フォーマット・日付範囲
- 行クリックで MatchDetailView へ

---

### MatchDetailView（`/matches/:match_id`）

- `GET /api/matches/{match_id}` で詳細取得
- プレイヤーごとにデッキ名（インライン編集）・ゲームプランドロップダウン（`PATCH` で即時保存）
- デッキバージョン紐づけ: デッキ一覧モーダルでバージョン選択 → `PUT /deck-version`
- ゲームごとにアクションログをアコーディオン展開（`GET /games/{id}/actions`、初回のみ取得）
- ActionLog コンポーネントでターン別・フェーズ別に整形表示

---

### StatsView（`/stats`）

- フィルター: プレイヤー（必須）・相手・自デッキ・相手デッキ・フォーマット・日付範囲
- `GET /api/stats` で集計統計（勝率・マリガン率・ターン数・先手後手別等）
- `GET /api/stats/cards` で相手カード出現統計
- グラフ: vue-echarts（勝率推移・先手後手比較・マリガン別勝率・デッキ別勝率）
- プレイヤードロップダウン: `GET /api/stats/players`（試合数順ソート）

---

### DeckDefinitionsView（`/decks`）— アーキタイプ定義

- デッキアーキタイプの自動識別ルール管理
- シグネチャカード・除外カード・閾値を設定
- `POST /api/decks/apply-definitions` で既存マッチへ一括適用
- AI 自動生成（`POST /api/deck-definitions/generate`）・JSON インポート/エクスポート対応

---

### AnalysisView（`/analysis`）

- APIキー未設定時は設定画面へ誘導
- プレイヤー選択・プロンプトテンプレート選択
- フィルター（相手・デッキ・フォーマット・日付）→ セッション保存時に `filter_*` カラムへ記録
- セッション履歴バー（`GET /api/analysis/sessions?player=xxx`）でタブ切り替え
- `POST /api/analysis/chat`（SSE）でストリーミング表示
- 定型質問セット（`GET /api/question-sets`）からワンクリック送信

---

### AIExportView（`/export`）

- フィルター指定で対戦データを Markdown 形式でエクスポート
- `GET /api/matches/export/count` で対象件数プレビュー
- `GET /api/matches/export` で Markdown 取得 → クリップボードコピー or ファイル保存
- 詳細レベル選択: summary / matches / actions
- デッキリスト・カード統計の埋め込みオプション

---

### DeckBuilderView（`/deck-builder`）— デッキリスト

- デッキ一覧（`GET /api/decklist/decks`）
- デッキ作成・編集・アーカイブ（論理削除）・完全削除
- バージョン管理: テキスト入力 or `.dek` ファイルインポート
- カードビュー: Scryfall 画像グリッド + 枚数オーバーレイ（`GET /api/cards/{scryfall_id}/image`）
- バージョンアーカイブ（論理削除）・復元対応

---

### SettingsView（`/settings`）

**設定セクション**
- デフォルトプレイヤー設定
- LLM プロバイダー（Claude / OpenAI）・API キー登録・削除
- 統計表示の最低試合数（プレイヤー・デッキ別）

**データ管理セクション**
- DBバックアップ（`GET /api/backup` → ファイルダウンロード）
- DBリストア（`POST /api/restore` → ファイルアップロード）
- データ削除:
  - 全試合データ削除（`DELETE /api/matches/all`）
  - 期間指定削除（`DELETE /api/matches/range`）
  - 完全リセット（`DELETE /api/reset`）
- 削除系はテキスト入力確認ダイアログ（TypeToConfirmDialog）で誤操作防止

---

### PresetsView（`/presets`）

- プロンプトテンプレート一覧・新規作成・デフォルト設定
- 質問セット一覧・新規作成・デフォルト設定
- デフォルト項目は削除不可（ボタン非活性）

---

## デザインテーマ

MTGO ライクなライトテーマ（羊皮紙・くすみ系）。

| 用途 | カラー |
|------|--------|
| 背景 | `#f0ece0` |
| サーフェス | `#faf7f0` |
| ボーダー | `#c8b89a` |
| アクセント | `#4a6fa5` |
| テキスト（メイン） | `#2c2416` |
| テキスト（サブ） | `#7a6a55` |
| 成功 | `#5a7a4a` |
| エラー | `#a03030` |

初期ウィンドウサイズ: 1200×800（リサイズ可能）。
