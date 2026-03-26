# インポート中断機能 設計ドキュメント

## 実装ステータス

**実装済み（2026-03-25）**
- バックエンド・フロントエンドともに設計通りに実装済み
- 未決事項はいずれも解決済み（下記参照）

## 概要

インポート処理中に表示される中断ボタンを押すことで、処理を途中で止められるようにする。

---

## 背景・目的

- MTGO ログのインポートは Scryfall API を1枚ずつ呼び出すため、未キャッシュカードが多い場合に数十秒かかる
- 誤ってインポートを開始した場合や、処理が長すぎる場合に途中で止める手段がない
- 中断後は処理済みのファイルはそのまま保持し、未処理分のみスキップする

---

## 中断の粒度

中断が効くタイミングは2段階ある。

| 段階 | タイミング | 制御場所 |
|------|-----------|---------|
| ① ファイル間 | 1件のインポートが完了し、次のファイルに進む前 | フロントエンド（ループ内チェック） |
| ② ファイル内 | Scryfall API 呼び出しの1件ごと | バックエンド（フラグチェック） |

段階①のみだと、1ファイルの処理中（Scryfall が 50 枚取得中など）は中断が効かない。
段階②まで対応することで、Scryfall 取得の途中でも即座に止められる。

---

## 設計

### 全体フロー

```
[中断ボタン押下]
      │
      ├─ フロントエンド: cancelRequested = true
      │
      └─ POST /api/import/cancel
              │
              └─ バックエンド: cancel_requested フラグを立てる
                      │
                      └─ scryfall_client.fetch_legalities() のループ内でチェック
                              │
                              ├─ フラグが立っていれば早期 return（取得済み分を返す）
                              └─ フォーマット判定は取得済みカードのみで継続（不完全でも保存）
```

### 中断後の状態

| 状況 | 結果 |
|------|------|
| 処理済みファイル | 正常にインポートされた状態を保持 |
| 処理中ファイル（Scryfall 途中） | 取得済み分でフォーマット推定し保存（`unknown` になる場合あり） |
| 未処理ファイル | スキップ（インポートされない） |

「処理中ファイルを破棄してロールバックする」ことも検討したが、部分的でも保存されているほうが再インポートより有用と判断した。

---

## 変更ファイル一覧

### バックエンド

| ファイル | 変更内容 |
|---------|---------|
| `backend/services/import_status.py` | `cancel_requested` フラグの追加・セット・リセット関数を追加 |
| `backend/services/scryfall_client.py` | `fetch_legalities()` のループ内でキャンセルフラグをチェック、立っていれば早期 return |
| `backend/app/routers/import_.py` | `POST /api/import/cancel` エンドポイントを追加 |

### フロントエンド

| ファイル | 変更内容 |
|---------|---------|
| `frontend/src/api/import.ts` | `cancelImport()` 関数を追加 |
| `frontend/src/views/ImportView.vue` | 中断ボタン・`cancelRequested` ref・ループ内チェック・中断後の結果表示を追加 |

---

## API 仕様

### POST /api/import/cancel

インポート処理にキャンセルフラグを立てる。

- リクエストボディ: なし
- レスポンス: `{ "ok": true }`
- 副作用: `import_status.cancel_requested = True`

キャンセルフラグは次回インポート開始時（`reset_log()` 呼び出し時）に自動リセットされる。

---

## UI 仕様

### インポート中画面

```
インポート中... 2 / 10 件
[████████░░░░░░░░░░░░] 20%

[中断する]           ← 追加するボタン

[Match_GameLog_xxx.dat] 処理中...
  フォーマット推定中... (45 種のカード)
  Scryfall 取得中: 10 / 32
```

- 中断ボタンは `state === 'importing'` の間のみ表示
- ボタン押下後はボタンを無効化し「中断中...」に変更（二重押し防止）
- 中断が完了すると通常の batch_result 画面に遷移し、スキップ件数に未処理ファイル分が加算される

### 中断後の結果表示

通常の完了画面と同じ batch_result を表示し、上部に中断メッセージを追加する。

```
⚠️ インポートを中断しました

インポート済み  2 件
スキップ（重複） 1 件
中断スキップ    7 件   ← 未処理ファイル数
エラー          0 件
```

---

## 実装メモ

### キャンセルフラグのチェック箇所

`scryfall_client.py` の `fetch_legalities()` 内、各 API 呼び出しの前にチェックする。

```python
for i, name in enumerate(uncached):
    if import_status.is_cancel_requested():
        logger.info("Scryfall fetch cancelled at %d/%d", i, total_uncached)
        break
    card = self._fetch_one_by_name(name)
    ...
```

### フロントエンドのループ内チェック

```typescript
for (const target of targets) {
  if (cancelRequested.value) break   // ← 次ファイルに進む前にチェック
  // ... import処理 ...
}
```

### キャンセル済みファイルの扱い

ループを `break` した後、残りのファイルを `cancelled` ステータスとして results に追加し、
スキップ件数として集計する。

---

## 未決事項（解決済み）

- [x] 中断後の結果表示で「中断スキップ」を通常の「スキップ（重複）」と分けて表示するか → 別表示に決定
- [x] `batch_result` の型に `cancelled` ステータスを追加するか、`skipped` に統合するか → `cancelled` フィールドを追加済み
