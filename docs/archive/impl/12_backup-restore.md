# 詳細設計: データベースバックアップ・リストア

## 概要

SQLite データベース（`mtgo.db`）のバックアップダウンロードおよびリストア（復元）機能。
設定画面に専用セクションを追加する。

---

## 対象ファイル

| ファイル | 種別 |
|---------|------|
| `backend/app/routers/backup.py` | 新規作成 |
| `backend/app/main.py` | 編集（ルーター登録） |
| `frontend/src/api/backup.ts` | 新規作成 |
| `frontend/src/views/SettingsView.vue` | 編集（UIセクション追加） |

---

## API 設計

### `GET /api/backup`

現在の SQLite データベースファイルをそのままダウンロードする。

**レスポンス**

| 項目 | 値 |
|------|----|
| Content-Type | `application/octet-stream` |
| Content-Disposition | `attachment; filename=scry_backup_YYYYMMDD_HHMMSS.db` |
| ボディ | SQLite ファイルのバイナリ |

**処理フロー**

```
1. database.py から DB ファイルパスを取得
2. ファイルが存在することを確認
3. FileResponse でそのまま返す
```

**エラー**

| 状況 | レスポンス |
|------|-----------|
| DB ファイルが存在しない | 404 |

---

### `POST /api/restore`

アップロードされた SQLite ファイルで現在の DB を置き換える。

**リクエスト**

- `multipart/form-data`
- フィールド名: `file`（`.db` ファイル）

**レスポンス**

```json
{ "ok": true }
```

**処理フロー**

```
1. アップロードされたファイルを受け取る
2. SQLite ファイルの妥当性を検証
   - 先頭16バイトが "SQLite format 3\000" であることを確認
   - 不正な場合は 400 エラー
3. 現在の DB を自動バックアップ
   - パス: {db_dir}/mtgo_prerestore_{YYYYMMDD_HHMMSS}.db
4. SQLAlchemy エンジンの接続プールを破棄（engine.dispose()）
5. sqlite3 モジュールの backup API で DB を置き換え
   - src: アップロードファイル（一時保存）
   - dst: 現在の mtgo.db
6. engine.dispose() で接続プールを再初期化
7. { "ok": true } を返す
```

**エラー**

| 状況 | レスポンス |
|------|-----------|
| SQLite ファイルでない | 400 `Invalid SQLite file` |
| ファイル書き込み失敗 | 500 |

---

## フロントエンド設計

### `frontend/src/api/backup.ts`

```typescript
// バックアップファイルのダウンロード
export async function downloadBackup(): Promise<void>

// DB をリストア（ファイルアップロード）
export async function restoreBackup(file: File): Promise<void>
```

`downloadBackup` は Blob を受け取り `<a>` タグ経由でダウンロードする。

### `SettingsView.vue` — 追加セクション

「アプリケーション」セクション内に配置する。

```
[ バックアップをダウンロード ]

ファイルを選択  （未選択）  [ リストア ]
```

- リストアは ConfirmDialog で確認を取ってから実行する
- リストア完了後は `window.location.reload()` でページを再読み込みする
  （DB が置き換わるためアプリ状態をリセットする必要があるため）

---

## エラーハンドリング

| ケース | 対処 |
|--------|------|
| バックアップ API エラー | Toast でエラー表示 |
| SQLite 以外のファイルをリストア | Toast「有効な .db ファイルを選択してください」 |
| リストア中に DB 書き込み失敗 | Toast でエラー表示（自動バックアップは残る） |

---

## 動作確認手順

1. バックアップ: 「バックアップをダウンロード」クリック → `.db` ファイルがダウンロードされること
2. リストア: ダウンロードした `.db` ファイルを選択 → 確認ダイアログ → 実行 → 再読み込み後にデータが同じであること
3. 不正ファイル: `.txt` ファイル等を選択してリストア → エラーメッセージが表示されること
4. リストア前自動バックアップ: リストア後に `{db_dir}/mtgo_prerestore_*.db` が生成されていること
