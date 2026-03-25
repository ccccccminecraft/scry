# カードデータ未取得補完 設計ドキュメント

## 概要

AIExportView のカード辞書タブに「未取得カードデータを取得」ボタンを追加する。現在のフィルター条件に合致する試合のアクションに登場したカードのうち `card_cache` に未登録のものを Scryfall API から一括取得してキャッシュに保存する機能。

Scryfall に存在しないカード名（トークン・MTGA 合成名等）は `card_cache_miss` テーブルで管理し、無駄な再試行を防ぐ。失敗リストは AIExportView（フィルタースコープ）と SettingsView（全体）の2段階でリセットできる。

---

## 実装ステータス

実装済み

---

## 背景・動機

`card_cache` はデッキビルダーで scryfall_id を解決するタイミングにのみ自動蓄積される。デッキビルダーを使わずにインポートした MTGO / MTGA 対戦ログには `card_cache` に存在しないカードが多数含まれる可能性がある。

MTGA ログでは `Action.card_name` の一部がトークン名や基本土地の合成名（`obj_name_map` 由来）であり、これらは Scryfall に存在しない。毎回取得を試みると API コールを無駄に消費するため、一度失敗したカード名は `card_cache_miss` テーブルに記録してスキップする。

---

## 設計方針の決定事項

| 項目 | 決定内容 |
|------|---------|
| 機能の配置 | AIExportView のカード辞書タブ（フィルター内） |
| 取得対象のスコープ | 現在のフィルター条件に合致する試合に登場したカードのうち `card_cache` 未登録 かつ `card_cache_miss` 未登録のもの |
| 取得方法 | Scryfall `/cards/named?exact=`（`card_image_service` の既存ロジックを再利用） |
| レート制限対応 | 50ms スリープ（既存実装と同一） |
| 通信方式 | SSE（Server-Sent Events）ストリーミング + フロントエンド側プログレスバー |
| 永続失敗の管理 | `card_cache_miss` テーブルに記録。以降の fetch-missing でスキップ |
| リセット手段 | ① AIExportView: 現在フィルター内のミスをリセット ② SettingsView: 全件リセット |
| scryfall_enabled 連携 | `scryfall_enabled=false` のときはボタンを無効化 |

---

## データモデル

### 新規テーブル: `card_cache_miss`

| カラム | 型 | 説明 |
|--------|-----|------|
| `name` | TEXT (PK) | `Action.card_name` の値（例: `"Treasure"`, `"A-Prosperity"`） |
| `failed_at` | DATETIME | 最後に失敗した日時 |
| `miss_count` | INT | 累計失敗回数 |

**ライフサイクル:**

- fetch-missing で Scryfall が解決不能 → upsert（`failed_at` 更新・`miss_count` インクリメント）
- fetch-missing で取得成功 → `card_cache_miss` から削除（新セットリリース後に名前が追加された場合を考慮）
- リセット操作 → 対象 name を DELETE

`miss_count` は現時点ではリセット判断には使わないが、将来的なポリシー（N回以上失敗は永久スキップ等）に向けて記録する。

---

## カウント定義

`GET /api/matches/export/card-dictionary/count` のレスポンスを以下に変更する。

| フィールド | 意味 |
|-----------|------|
| `total` | フィルター内の試合に登場したユニークカード名の総数 |
| `cached` | `card_cache` に登録済みの数 |
| `fetchable` | `card_cache` 未登録 かつ `card_cache_miss` 未登録（取得ボタンの対象件数） |
| `miss` | `card_cache_miss` に登録済み（既知の失敗・現状は取得不能） |

`total = cached + fetchable + miss` の関係が成り立つ。カード辞書エクスポートで `（データ未取得）` になるのは `fetchable + miss` 件。

---

## バックエンド

### エンドポイント一覧

| メソッド | パス | 説明 |
|---------|------|------|
| `GET` | `/api/matches/export/card-dictionary/count` | カウント取得（既存、レスポンス変更） |
| `GET` | `/api/matches/export/card-dictionary` | カード辞書 Markdown 取得（既存、変更なし） |
| `POST` | `/api/matches/export/card-dictionary/fetch-missing` | 未取得カードの一括取得（新規） |
| `POST` | `/api/matches/export/card-dictionary/reset-miss` | フィルタースコープの失敗リストリセット（新規） |
| `GET` | `/api/settings/card-cache-miss/count` | 失敗リスト全件数取得（新規、Settings 用） |
| `DELETE` | `/api/settings/card-cache-miss` | 失敗リスト全件削除（新規、Settings 用） |

---

### `GET /api/matches/export/card-dictionary/count`（変更）

クエリパラメータは既存フィルターと同一。

フィルター内の試合に登場する全ユニークカード名を収集し、`card_cache`・`card_cache_miss` それぞれとの突き合わせによって `total / cached / fetchable / miss` の4値を返す。

DFC の面名マッチングについては後述の「カード名マッチングの考慮」を参照。

---

### `POST /api/matches/export/card-dictionary/fetch-missing`

クエリパラメータは既存フィルターと同一。レスポンスは `text/event-stream`（SSE）で進捗をストリーミングする。

**SSE イベント形式:**

各カード処理後に進捗イベントを1件送出する。フィールドは以下の通り。

| フィールド | 型 | 説明 |
|---|---|---|
| `done` | int | 処理済み件数（成功 + 失敗の合計） |
| `total` | int | 取得対象の総件数 |
| `fetched` | int | 取得成功件数（累積） |
| `failed` | int | 失敗件数（累積） |
| `complete` | bool | 最終イベントのみ `true` |
| `failed_names` | string[] | 最終イベントのみ含む |

すべてのカードを処理し終えたら `complete: true` を付けた最終イベントを送出して接続を閉じる。

**処理フロー:**

1. フィルター条件に合致する試合のアクションから `card_name` が NULL でないユニークなカード名を収集する
2. `card_cache` および `card_cache_miss` に登録済みの名前を除外し、取得対象リストを作成する
3. 対象が0件の場合は `complete: true` の最終イベントのみ送出して終了する
4. 取得対象リストの各カード名に対して Scryfall `/cards/named?exact=` を呼び出す（50ms 間隔）
   - **取得成功**: `card_cache` に保存する。`card_cache_miss` に登録されていた場合は削除する
   - **取得失敗 (404 等)**: `card_cache_miss` に upsert する（`failed_at` 更新・`miss_count` インクリメント）
   - **ネットワークエラー**: miss には記録しない（一時的な障害と区別するため）。失敗件数にカウントのみ
   - 各カード処理後に進捗イベントを送出する
5. 全件処理後に `complete: true` を含む最終イベントを送出して接続を閉じる

`scryfall_enabled=false` の場合は処理を行わず `403` を返す。

---

### `POST /api/matches/export/card-dictionary/reset-miss`

クエリパラメータは既存フィルターと同一。レスポンスは削除件数を返す。

フィルター条件に合致する試合のアクションに登場したカード名のうち、`card_cache_miss` に登録されているものをすべて削除する。削除後は次回 fetch-missing でそれらのカード名が再試行対象になる。

---

### `GET /api/settings/card-cache-miss/count`

`card_cache_miss` テーブルの全件数を返す。SettingsView の表示用。

---

### `DELETE /api/settings/card-cache-miss`

`card_cache_miss` テーブルを全件削除する。レスポンスは削除件数を返す。

---

### カード名マッチングの考慮（DFC）

`card_cache.name` は Scryfall の `name` フィールド（`"Delver of Secrets // Insectile Aberration"` 形式）で保存される。`Action.card_name` は面名のみ（`"Delver of Secrets"` または `"Insectile Aberration"`）になることがある。

キャッシュ済み判定は、完全一致のほかに「`action_name + " //"` で始まる `card_cache.name` が存在する」という面名プレフィックスマッチも行う。`card_cache_miss` は `Action.card_name` そのままで記録するため完全一致でよい。

---

## フロントエンド

### AIExportView カード辞書タブ レイアウト

```
[対象: 87種類（うちデータ未取得: 17種類）]
（取得可能: 5種類 / 既知の失敗: 12種類）  ← miss > 0 のときのみ表示

[未取得カードを取得 (5件)]  [失敗リストをリセット (12件)]

← 取得中のみ表示 →
[████████░░░░░░░░░░░░] 3 / 5件  ← プログレスバー

[カード辞書をエクスポート]
```

#### 各ボタンの活性条件

| ボタン | 活性条件 |
|--------|---------|
| 未取得カードを取得 | `fetchable > 0` かつ `scryfall_enabled` かつ `player` 設定済み かつ 操作中でない |
| 失敗リストをリセット | `miss > 0` かつ `player` 設定済み かつ 操作中でない |
| カード辞書をエクスポート | `player` 設定済み かつ ダウンロード中でない |

#### プログレスバーの表示仕様

取得ボタンを押した瞬間から表示し、SSE ストリームの最終イベント受信後に非表示にする。

| 要素 | 内容 |
|------|------|
| バー | `done / total` の割合で塗りつぶす |
| テキスト | 「N / M件」（N = done、M = total） |
| 表示タイミング | `fetching === true` の間のみ表示 |

#### 状態表示

| 状態 | 「未取得カードを取得」ボタン |
|------|--------------------------|
| 通常 | 「未取得カードを取得 (N件)」 |
| `scryfall_enabled=false` | 非表示（または「Scryfall連携が無効です」注記） |
| 取得中 | 「取得中…」・無効化（プログレスバーを別途表示） |
| 完了（失敗なし） | トースト「23件取得しました」 |
| 完了（失敗あり） | トースト「23件取得しました（失敗: 2件 → 失敗リストに追加）」 |

| 状態 | 「失敗リストをリセット」ボタン |
|------|------------------------------|
| 通常 | 「失敗リストをリセット (N件)」 |
| リセット中 | 「リセット中…」無効化 |
| 完了 | トースト「失敗リストを12件リセットしました」→ `loadCardCount()` 再取得 |

---

### SettingsView の変更

カード辞書セクションを追加し、`card_cache_miss` の全件数と全リセットボタンを配置する。

```
カード辞書
  失敗リスト: 34件  [すべてリセット]
```

件数は SettingsView マウント時に取得する。「すべてリセット」実行後は件数を再取得して表示を更新する。確認ダイアログは不要（SettingsView 内の他の軽量操作と揃える）。

---

### API 関数の変更・追加

**`frontend/src/api/matches.ts`**

- `CardDictionaryCount` 型: `missing` を廃止し `fetchable`（旧 missing）と `miss` に分離
- `streamFetchMissingCardData(filters, onProgress, onComplete, onError)`: `POST .../fetch-missing` を `fetch` API（axios ではなく）で呼び出し、SSE ストリームをパースする。各イベント受信時に `onProgress(done, total, fetched, failed)` を呼び出し、`complete: true` イベント受信時に `onComplete(result)` を呼び出す。axios はストリーミングに対応していないため Fetch API を使用する
- `resetCardCacheMiss(filters)`: `POST .../reset-miss` を呼び出し、削除件数を返す

**`frontend/src/api/settings.ts`**

- `fetchCardCacheMissCount()`: `GET .../card-cache-miss/count` を呼び出し、全件数を返す
- `deleteAllCardCacheMiss()`: `DELETE .../card-cache-miss` を呼び出し、削除件数を返す

---

## エッジケース

| ケース | 対応 |
|--------|------|
| 全カードが cached | `fetchable=0` かつ `miss=0` → 両ボタン非表示 |
| `fetchable=0` かつ `miss>0` | 取得ボタンは非表示、リセットボタンのみ表示 |
| Scryfall 404（トークン名等） | `card_cache_miss` に記録。次回以降スキップ |
| ネットワークエラー | エラートースト表示。途中まで取得済みのカードは保存される。エラー分は miss に記録しない。フロントエンドはストリーム切断を検知してプログレスバーを非表示にする |
| リセット後に再 fetch-missing | miss が削除されるため再試行対象になる |
| miss 登録済みカードが取得成功 | 取得成功時に `card_cache_miss` から削除する |
| DFC 面名 vs `//` 形式 | キャッシュ済み判定に面名プレフィックスマッチを使用 |
| 同時実行 | フロントエンド側のボタン無効化で防止。バックエンドは冪等 |
| `scryfall_enabled=false` | 取得ボタン非活性。バックエンドでも `403` を返す |

---

## 変更ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `backend/models/cache.py` | `CardCacheMiss` モデル追加（`card_cache_miss` テーブル: name / failed_at / miss_count） |
| `backend/models/__init__.py` | `CardCacheMiss` を imports・`__all__` に追加 |
| `backend/app/routers/matches.py` | `fetch-missing`・`reset-miss` エンドポイント追加。`count` エンドポイントのレスポンス型変更（`missing` → `fetchable` + `miss`） |
| `backend/app/routers/settings.py` | `card-cache-miss/count`・`card-cache-miss` (DELETE) エンドポイント追加 |
| `frontend/src/api/matches.ts` | `CardDictionaryCount` 型変更・`streamFetchMissingCardData()`・`resetCardCacheMiss()` 追加 |
| `frontend/src/api/settings.ts` | `fetchCardCacheMissCount()`・`deleteAllCardCacheMiss()` 追加 |
| `frontend/src/views/AIExportView.vue` | カード辞書タブに取得ボタン・プログレスバー・リセットボタン・miss 件数表示を追加 |
| `frontend/src/views/SettingsView.vue` | カード辞書セクション（miss 件数 + 全リセットボタン）追加 |
