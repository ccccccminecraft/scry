# 詳細設計: データ削除機能

## 概要

設定画面に「データ削除」セクションを追加し、以下3種類の削除操作を提供する。

| 操作 | 説明 |
|------|------|
| 全試合データを削除 | matches / games / actions を全件削除。設定・デッキ定義・カード合法性は保持 |
| 期間を指定して削除 | 日付範囲を指定して該当する試合を削除 |
| 完全リセット | DB 全体を初期状態に戻す（全テーブルを削除） |

---

## 対象ファイル

| ファイル | 種別 |
|---------|------|
| `backend/app/routers/deletion.py` | 新規作成 |
| `backend/app/main.py` | 編集（ルーター登録） |
| `frontend/src/api/deletion.ts` | 新規作成 |
| `frontend/src/views/SettingsView.vue` | 編集（UIセクション追加） |
| `frontend/src/components/TypeToConfirmDialog.vue` | 新規作成 |

---

## API 設計

### `DELETE /api/matches`

全試合データを削除する。

**レスポンス**

```json
{ "deleted": 42 }
```

**処理フロー**

```
1. actions テーブルを全件削除
2. games テーブルを全件削除
3. match_players テーブルを全件削除
4. matches テーブルを全件削除
5. 削除件数（matches の件数）を返す
```

---

### `DELETE /api/matches/range`

指定した日付範囲の試合を削除する。

**リクエスト**

```json
{
  "date_from": "2024-01-01",
  "date_to":   "2024-03-31"
}
```

- `date_from` / `date_to` はともに省略可能
- 両方省略した場合は全件削除と同等

**レスポンス**

```json
{ "deleted": 5 }
```

**処理フロー**

```
1. date_from / date_to で matches を絞り込み
2. 該当 match の id リストを取得
3. actions → games → match_players → matches の順に削除
4. 削除件数を返す
```

---

### `DELETE /api/reset`

DB を完全リセットする。

**レスポンス**

```json
{ "ok": true }
```

**処理フロー**

```
1. engine.dispose() で接続プールを破棄
2. 全テーブルを DROP（Base.metadata.drop_all）
3. init_db() でテーブルを再作成
4. engine.dispose() で接続プールを再初期化
5. { "ok": true } を返す
```

---

## フロントエンド設計

### `frontend/src/api/deletion.ts`

```typescript
export async function deleteAllMatches(): Promise<number>
export async function deleteMatchesByRange(dateFrom?: string, dateTo?: string): Promise<number>
export async function resetDatabase(): Promise<void>
```

- 各関数は対応するエンドポイントを呼び出す
- `deleteAllMatches` / `deleteMatchesByRange` は削除件数（`deleted`）を返す

---

### `frontend/src/components/TypeToConfirmDialog.vue`

完全リセット専用の確認ダイアログ。GitHub の危険操作確認UI と同様に、指定テキストを入力するまで実行ボタンが無効になる。

**Props**

| Prop | 型 | 説明 |
|------|----|------|
| `visible` | `boolean` | 表示/非表示 |
| `confirmText` | `string` | 入力を求めるテキスト（例: `"削除する"`） |
| `message` | `string` | ダイアログ上部に表示する説明文 |

**Emits**

| Event | 説明 |
|-------|------|
| `confirm` | 入力一致 + 実行ボタンクリック時 |
| `cancel` | キャンセル時 |

**UI 構成**

```
┌─────────────────────────────────────────┐
│ ⚠️  この操作は取り消せません              │
│                                         │
│ {message}                               │
│                                         │
│ 確認のため「削除する」と入力してください  │
│ ┌─────────────────────────────────────┐ │
│ │                                     │ │
│ └─────────────────────────────────────┘ │
│                                         │
│         [ キャンセル ]  [ 実行 ]         │
│                        ↑ 入力一致時のみ有効 │
└─────────────────────────────────────────┘
```

---

### `SettingsView.vue` — 追加セクション

「データベース」セクションの下に「データ削除」セクションを追加する。

```
[ 全試合データを削除 ]

開始日: [____-__-__]  終了日: [____-__-__]  [ 期間指定で削除 ]

━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ 完全リセット ]   ← danger ボタン
```

- 全試合削除・期間指定削除は通常の `ConfirmDialog` で確認
- 完全リセットのみ `TypeToConfirmDialog` を使用
- 削除完了後:
  - 全試合削除・期間指定削除: Toast でメッセージ表示（「N 件の試合を削除しました」）
  - 完全リセット: Toast 表示後 `window.location.reload()`

---

## エラーハンドリング

| ケース | 対処 |
|--------|------|
| 削除対象が 0 件 | Toast「削除対象のデータがありませんでした」 |
| API エラー | Toast でエラー表示 |
| 期間の日付が不正 | 入力欄を赤枠にしてボタン無効化 |

---

## 動作確認手順

1. 全試合削除: ボタンクリック → 確認ダイアログ → 実行 → 対戦履歴が空になること
2. 期間指定削除: 日付を入力 → 実行 → 該当期間の試合のみ消えること
3. 完全リセット: ボタンクリック → TypeToConfirmDialog 表示 → 「削除する」入力前は実行ボタン無効 → 入力後に有効化 → 実行 → 再読み込み後にすべてのデータが消えること
4. 削除対象 0 件: 空の状態で全試合削除 → 「削除対象のデータがありませんでした」が表示されること
