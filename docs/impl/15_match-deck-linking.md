# 15: 対戦履歴 ↔ デッキバージョン紐づけ

## 概要

対戦履歴の各プレイヤーに、デッキ構築管理で登録したデッキバージョンを紐づける機能。
`match_players` テーブルに `deck_version_id` カラムを追加し、手動で設定・解除できるようにする。

---

## 対象ファイル

### 新規作成

なし

### 編集

| ファイル | 変更内容 |
|----------|----------|
| `backend/models/core.py` | `MatchPlayer` に `deck_version_id` カラムと relationship を追加 |
| `backend/app/routers/matches.py` | PUT / DELETE エンドポイントを追加 |
| `frontend/src/api/matches.ts`（または相当ファイル） | API 呼び出し関数を追加 |
| `frontend/src/views/MatchDetailView.vue` | デッキバージョン設定 UI を追加 |

---

## DB 変更

### `match_players` テーブルへのカラム追加

| カラム | 型 | 制約 | 説明 |
|--------|----|------|------|
| `deck_version_id` | INTEGER | FK → `deck_versions.id`、NULL 可、ON DELETE SET NULL | 紐づけたデッキバージョン |

- `deck_versions` が削除された場合、`deck_version_id` は NULL に戻る（SET NULL）
- `init_db()` の `create_all()` による自動追加は**既存 DB には反映されない**ため、既存環境では DB ファイルを再作成するか手動で ALTER TABLE を実行する

---

## API

### PUT /api/matches/{match_id}/players/{player_name}/deck-version

- `match_id` と `player_name` で `MatchPlayer` を検索し、`deck_version_id` を更新する
- `deck_version_id` が存在しない場合は 404 を返す
- すでに別のバージョンが設定済みの場合は上書きする

### DELETE /api/matches/{match_id}/players/{player_name}/deck-version

- `deck_version_id` を NULL に設定する
- 対象レコードが存在しない場合は 404 を返す

---

## レスポンス形式の変更

`GET /api/matches/{match_id}` のレスポンスにデッキバージョン情報を追加する。

### players 配列の変更点

現状:
```
{ "player_name": "PlayerA", "deck_name": "Burn", "game_plan": "aggro" }
```

変更後:
```
{
  "player_name": "PlayerA",
  "deck_name": "Burn",
  "game_plan": "aggro",
  "deck_version_id": 3,
  "deck_version_label": "DeckName v2"  // deck.name + "v" + version_number、未設定時は null
}
```

---

## UI 設計

### 対戦詳細画面（MatchDetailView）

- 各プレイヤー行に「使用デッキ」欄を追加する
- 現在設定されているデッキバージョンがある場合はデッキ名＋バージョン番号を表示する
- 「設定」ボタンをクリックするとデッキ選択モーダルを開く
- 設定済みの場合は「解除」ボタンも表示する

### デッキ選択モーダルの操作フロー

1. デッキ一覧をプルダウンで選択する
2. 選択したデッキのバージョン一覧をプルダウンで選択する
3. 「設定」ボタンで確定する

---

## エラーハンドリング

| 状況 | 対応 |
|------|------|
| 存在しない match_id / player_name | 404 |
| 存在しない deck_version_id | 404 |
| 通信エラー | エラートーストを表示 |

---

## 動作確認手順

1. 対戦詳細画面を開く
2. 自分のプレイヤー行に「設定」ボタンが表示されることを確認する
3. デッキ・バージョンを選択して設定する
4. 設定したデッキバージョン名が表示されることを確認する
5. 「解除」ボタンで解除後、表示が消えることを確認する
6. `deck_versions` を削除した後、対戦詳細の該当欄が未設定に戻ることを確認する
