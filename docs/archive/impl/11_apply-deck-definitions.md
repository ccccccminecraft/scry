# 詳細設計: デッキ定義の既存試合への後付け適用

## 概要

デッキ定義を追加・変更した後、すでにインポート済みの試合に対してデッキ名判定を再実行する機能。

---

## 対象ファイル

| ファイル | 変更種別 |
|---------|---------|
| `backend/app/routers/decks.py` | エンドポイント追加 |
| `frontend/src/views/DeckDefinitionsView.vue` | ボタン追加 |
| `frontend/src/api/decks.ts` | API関数追加 |

---

## バックエンド設計

### エンドポイント

```
POST /api/decks/apply-definitions
```

### リクエストパラメータ（クエリ）

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|-----------|-----|------|-----------|------|
| `overwrite` | bool | — | `false` | `false`: deck_name が NULL の試合のみ対象 / `true`: 既存のデッキ名も上書き |

### レスポンス

```json
{
  "updated": 42,
  "skipped": 186
}
```

### 処理フロー

```
1. overwrite に応じて対象 MatchPlayer を取得
   - false: deck_name IS NULL のみ
   - true: 全 MatchPlayer

2. MatchPlayer ごとに以下を実行
   a. 対応する Match.format を取得
   b. Match の全 Game の Action から play/cast カードを収集
   c. ImportService._detect_deck(player_name, used_cards, format) を呼び出す
   d. 判定結果が None でなく、かつ現在値と異なる場合に deck_name を更新

3. まとめて commit

4. updated / skipped カウントを返す
```

### 実装上の注意

- `ImportService._detect_deck()` を再利用する
- 1回のリクエストで全対象を処理する（件数が多い場合でも同期処理）
- commit は全件処理後に1回だけ行う

---

## フロントエンド設計

### 変更箇所

`DeckDefinitionsView.vue` のページ上部（またはヘッダー付近）に以下を追加。

```
[ デッキ定義を既存試合に適用 ▼ ]
  ├─ デッキ名未設定の試合のみ（推奨）
  └─ すべての試合（既存のデッキ名を上書き）
```

ボタン仕様:
- ドロップダウン付きボタン（2択）
- 実行中はローディング表示・ボタン無効化
- 完了後: `「42件更新しました」` のトーストを表示
- エラー時: エラートーストを表示

### API関数（`frontend/src/api/decks.ts` に追加）

```typescript
export async function applyDeckDefinitions(overwrite: boolean): Promise<{ updated: number; skipped: number }> {
  const res = await client.post('/api/decks/apply-definitions', null, {
    params: { overwrite },
  })
  return res.data
}
```

---

## 動作確認手順

1. デッキ定義が登録された状態で、deck_name が NULL の試合が存在することを確認
2. 「デッキ名未設定の試合のみ」で実行 → 更新件数がトーストに表示されることを確認
3. 対戦履歴を確認し、デッキ名が付与されていることを確認
4. 「すべての試合」で実行 → 既存のデッキ名が上書きされることを確認
5. デッキ定義にマッチしない試合は deck_name が変化しないことを確認
