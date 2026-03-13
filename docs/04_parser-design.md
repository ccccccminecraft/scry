# パーサー設計

## 概要

Magic Online（MTGO）の対戦ログファイル（`.dat`）を解析し、構造化データとして返すモジュール。

---

## .dat ファイル仕様

### ファイル形式

- **エンコーディング**: バイナリ形式（メッセージ本文は UTF-8）
- **構造**: 固定ヘッダー + イベントレコードの連続
- **1ファイル = 1マッチ分**（複数ゲームを含む）

---

### ファイル構造

#### ヘッダー

```
[01 00]                     # 固定マジックバイト
[24]                        # マッチID長 (= 0x24 = 36)
[match_id: 36 bytes UTF-8]  # 例: "01564d49-9b3b-4bd4-a879-09bc7a91e602"
[04 00]                     # 固定区切り
[24]                        # マッチID長 (= 36)
[match_id: 36 bytes UTF-8]  # 同じマッチIDが繰り返される
[2 bytes]                   # 未使用パディング
```

#### イベントレコード（繰り返し）

```
[8 bytes]   タイムスタンプ（Windows FILETIME、リトルエンディアン）
[1 byte]    0x00（固定）
[1 byte]    メッセージ長（@P プレフィックス含む）
[2 bytes]   0x40 0x50（= "@P" プレフィックス、固定）
[N bytes]   メッセージ本文（UTF-8）
```

#### タイムスタンプ

- 8バイト、リトルエンディアン 64bit 整数
- Windows FILETIME 形式（1601-01-01 からの 100ナノ秒単位）
- `datetime` への変換: `(value - 116444736000000000) / 10_000_000` → Unix timestamp

---

### メッセージフォーマット

各イベントはプレイヤー名で始まるテキスト行。

#### カード参照

カード名は以下の形式で埋め込まれる：

```
@[CardName@:multiverseId,permanentId:@]

例: @[Slickshot Show-Off@:248406,428:@]
    CardName       = "Slickshot Show-Off"
    multiverseId   = 248406  （Scryfall等のカードID）
    permanentId    = 428     （ゲーム内のオブジェクトID）
```

---

### イベント種別一覧

#### マッチ・ゲーム制御

| メッセージパターン | 意味 |
|-------------------|------|
| `{player} rolled a {n}.` | ダイスロール（先手決め） |
| `{player} joined the game.` | ゲーム開始（ゲームの区切りとして使用） |
| `{player} chooses to play first.` | 先手選択 |
| `{player} begins the game with {n} cards in hand.` | ゲーム開始時の手札枚数 |
| `{player} wins the game.` | ゲーム勝利 |
| `{player} loses the game.` | ゲーム敗北（コンシード等）。勝者 = もう一方のプレイヤー |
| `{player} leads the match {W}-{L}` | ゲーム間スコア表示（ゲーム境界の検出に使用可） |
| `{player} wins the match {W}-{L}` | マッチ勝利 |
| `Match Tied {N}-{N}` | タイ（2本先取制での1-1） |

#### マリガン

| メッセージパターン | 意味 |
|-------------------|------|
| `{player} mulligans to {n} cards.` | マリガン宣言 |
| `{player} puts {n} cards on the bottom of their library and begins the game with {n} cards in hand.` | マリガン後の手札確定 |

#### ターン進行

| メッセージパターン | 意味 |
|-------------------|------|
| `Turn {n}: {player}` | ターン開始 |
| `{player} skips their draw step.` | ドローステップスキップ（先手1ターン目） |

#### アクション

| メッセージパターン | action_type |
|-------------------|-------------|
| `{player} plays @[{card}...]` | `play`（土地プレイ） |
| `{player} casts @[{card}...]` | `cast`（呪文唱える） |
| `{player} activates an ability of @[{card}...]` | `activate` |
| `{player} puts triggered ability from @[{card}...]` | `trigger` |
| `{player} is being attacked by @[{card}...]` | `attack` |
| `{player} draws a card` / `{player} draws {n} cards` | `draw` |
| `{player} discards @[{card}...]` | `discard` |
| `{player} reveals @[{card}...]` | `reveal` |
| `{player} removes ... counter` | `remove_counter` |
| `{player} puts ... counter on` | `add_counter` |

---

### ゲーム境界の検出

同一マッチ内のゲーム（Game 1, 2, 3）は以下のパターンで区切られる：

```
[ゲームN 終了]
  {player} wins the game.          ← ゲーム終了（通常勝利）
  または
  {player} loses the game.         ← ゲーム終了（コンシード等）
                                     ※ 勝者 = もう一方のプレイヤー

  {player} leads the match {W}-{L} ← 中間スコア表示（必ず存在）
  （稀に残余イベントが入る場合あり、例: "{player} draws their next card."）

[ゲームN+1 開始]
  {player} joined the game.        ← 新ゲームの開始マーカー（1行目）
  {player} joined the game.        ← 2行目（両プレイヤー）
  {player} chooses to play first.
  {player} begins the game with ...
```

マッチ終了は以下で検出：
- `{player} wins the match {W}-{L}`
- `Match Tied {N}-{N}`（2本先取での 1-1 タイ）

### サイドボードについて

**サイドボードのイベントはログに記録されない**（MTGOの仕様）。

ゲーム2以降でデッキ構成が変わる可能性はあるが、ログ上では「joined the game.」から次ゲームが始まるだけで、サイドボード操作の記録は存在しない。パーサーでの特別な処理は不要。

---

## クラス設計

### `MTGOLogParser`

```python
class MTGOLogParser:
    def parse_file(self, filepath: str) -> dict:
        """
        .dat ファイルを読み込み、構造化データを返す

        Parameters
        ----------
        filepath : str
            .dat ファイルのパス

        Returns
        -------
        dict
            下記「出力データ構造」参照

        Raises
        ------
        FileNotFoundError
            ファイルが存在しない場合
        ParseError
            ファイルフォーマットが不正な場合
        """
        pass

    def _read_events(self, data: bytes) -> list[dict]:
        """バイナリデータからイベントレコード列を抽出する"""
        pass

    def _parse_match_header(self, data: bytes) -> str:
        """ヘッダーからマッチIDを抽出する"""
        pass

    def _split_games(self, events: list[dict]) -> list[list[dict]]:
        """イベント列を joined the game. を区切りとしてゲームごとに分割する"""
        pass

    def _parse_game(self, events: list[dict], game_number: int) -> dict:
        """1ゲーム分のイベント列をパースする"""
        pass

    def _parse_action(self, message: str, turn: int) -> dict:
        """1メッセージをアクション dict に変換する"""
        pass

    def _extract_card_name(self, message: str) -> str:
        """メッセージ中の @[CardName@:...:@] からカード名を抽出する"""
        pass
```

---

## 出力データ構造

```python
{
    "match_id": str,          # マッチID（UUID形式）
    "players": [str, str],    # [プレイヤーA, プレイヤーB]
    "match_winner": str,      # マッチの勝者プレイヤー名
    "games": [
        {
            "game_number": int,      # ゲーム番号（1始まり）
            "winner": str,           # ゲーム勝者
            "turns": int,            # 総ターン数
            "first_player": str,     # 先手プレイヤー名
            "mulligans": {
                "<player>": int      # プレイヤーごとのマリガン回数
            },
            "actions": [
                {
                    "turn": int,             # ターン番号
                    "player": str,           # アクション実行プレイヤー
                    "action_type": str,      # アクション種別（下記一覧参照）
                    "card_name": str,        # カード名（なければ空文字）
                    "multiverse_id": int     # Scryfall multiverse ID（なければ None）
                }
            ]
        }
    ]
}
```

---

## パース処理フロー

```
1. ファイルをバイナリで読み込む
      │
      ▼
2. フォーマット検証（マジックバイト 01 00 で始まるか）
      │ 不正 → ParseError を raise
      ▼
3. ヘッダーからマッチIDを抽出
      │
      ▼
4. イベントレコードを順次読み取る
   [8byte timestamp][0x00][length][0x40 0x50][message]
      │
      ▼
5. "joined the game." を区切りにゲームブロックへ分割
      │
      ▼
6. 各ゲームブロックをパース
   ├── "chooses to play first." → first_player
   ├── "mulligans to N cards."  → mulligans カウント
   ├── "Turn N: {player}"       → 現在ターン番号を更新
   ├── アクション行             → _parse_action() で action_type / card_name を抽出
   ├── "wins the game."         → winner = そのプレイヤー
   └── "loses the game."        → winner = もう一方のプレイヤー
      │
      ▼
7. "wins the match" / "Match Tied" → match_winner を確定
      │
      ▼
8. 構造化 dict を返す
```

---

## インポートサービス（`ImportService`）

`MTGOLogParser` の出力を受け取り、DB 保存とフォーマット推定を行うサービス層。

### 処理フロー

```
1. MTGOLogParser.parse_file() で構造化データを取得
      │
      ▼
2. matches テーブルに重複チェック（match_id が既存か）
      │ 重複 → status="skipped" を返して終了
      ▼
3. matches / match_players / games / mulligans / actions を DB に保存
      │
      ▼
4. フォーマット推定
   a. 全ゲームの play / cast アクションから multiverse_id を収集
   b. card_legality テーブルで未キャッシュの multiverse_id を特定
   c. 未キャッシュ分を Scryfall API で取得し card_legality に保存
      （100ms インターバルで順次リクエスト）
   d. 全カードの legalities を集計し format を決定
      → 全カードが legal なフォーマットのうち最も制限の厳しいものを採用
      → 判定不能（カードなし / 全スキップ）なら "unknown"
      │
      ▼
5. matches.format を更新
      │
      ▼
6. status="imported", format=<判定結果> を返す
```

### multiverse_id の取得元と保存方針

`multiverse_id` は `.dat` ファイルのカード参照部分 `@[CardName@:multiverseId,permanentId:@]` から抽出し、`_parse_action()` の出力に含める。

```python
{
    "turn": int,
    "player": str,
    "action_type": str,
    "card_name": str,
    "multiverse_id": int | None   # カード参照がある場合のみ設定、なければ None
}
```

**`multiverse_id` は DB の `actions` テーブルには保存しない。**

`ImportService` がフォーマット推定のためだけに一時的に使用し（Scryfall API 呼び出し・`card_legality` テーブルへのキャッシュ保存）、処理完了後は破棄する。`card_name` による集計（カード別統計）には `multiverse_id` は不要なため、`actions` テーブルへの追加は行わない。

---

## エラー定義

```python
class ParseError(Exception):
    """ログファイルのパースに失敗した場合"""
    pass
```

---

## ユニットテスト設計

テストファイル: `backend/tests/test_log_parser.py`
フレームワーク: `pytest`

---

### カテゴリ1: `parse_file()` 統合テスト（正常系）

| # | テストケース | 検証内容 |
|---|------------|---------|
| 1 | 2-0 マッチ | `games` が2件、`match_winner` が正しい |
| 2 | 2-1 マッチ | `games` が3件、中間スコア後に正しく勝者が決まる |
| 3 | マリガンあり（1回） | `mulligans[player] = 1` |
| 4 | マリガンあり（2回） | `mulligans[player] = 2` |
| 5 | 両者マリガンあり | 各プレイヤーのマリガン回数が独立して正しい |
| 6 | コンシード（`loses the game.`） | 勝者 = もう一方のプレイヤー |
| 7 | ダイス再ロール（同点） | プレイヤー情報・ゲーム構造に影響しない |
| 8 | 先手1ターン目スキップ（`skips their draw step.`） | ターン数カウントが正しい |

---

### カテゴリ2: 個別メソッドテスト

#### `_read_events()`

| # | テストケース | 期待結果 |
|---|------------|---------|
| 9 | 正常なバイナリ | イベントリストが返る |
| 10 | 長さフィールドが実際のメッセージ長と一致 | 全メッセージが欠損なく取得できる |

#### `_parse_match_header()`

| # | テストケース | 期待結果 |
|---|------------|---------|
| 11 | 正常ヘッダー | match_id（UUID）が返る |
| 12 | マジックバイトが `\x01\x00` 以外 | `ParseError` |

#### `_split_games()`

| # | テストケース | 期待結果 |
|---|------------|---------|
| 13 | 2ゲームのイベント列 | リスト長 = 2 |
| 14 | 3ゲームのイベント列 | リスト長 = 3 |
| 15 | `joined the game.` が1件しかない | `ParseError` |

#### `_parse_game()`

| # | テストケース | 期待結果 |
|---|------------|---------|
| 16 | `chooses to play first.` あり | `first_player` が正しい |
| 17 | `begins the game with seven cards` | `mulligans = 0` |
| 18 | `mulligans to five cards.` が2回 | `mulligans = 2` |
| 19 | `Turn N: {player}` が複数 | `turns` が正しくカウントされる |
| 20 | `wins the game.` で終了 | `winner` が正しい |
| 21 | `loses the game.` で終了 | `winner` = もう一方のプレイヤー |

#### `_parse_action()`

| # | テストケース | 期待結果 |
|---|------------|---------|
| 22 | `plays @[Mountain@:...]` | `action_type="play"`, `card_name="Mountain"` |
| 23 | `casts @[Lightning Bolt@:...]` | `action_type="cast"`, `card_name="Lightning Bolt"` |
| 24 | `activates an ability of @[...]` | `action_type="activate"` |
| 25 | `is being attacked by @[...]` | `action_type="attack"` |
| 26 | `draws a card` | `action_type="draw"`, `card_name=""` |
| 27 | `mulligans to six cards.` | `action_type="mulligan"` |

#### `_extract_card_name()`

| # | テストケース | 期待結果 |
|---|------------|---------|
| 28 | `@[Slickshot Show-Off@:248406,428:@]` | `"Slickshot Show-Off"` |
| 29 | カード参照なしのメッセージ | `""` |
| 30 | メッセージ中に複数カード参照 | 先頭のカード名を返す |

---

### カテゴリ3: 異常系

| # | テストケース | 期待結果 |
|---|------------|---------|
| 31 | 存在しないファイルパス | `FileNotFoundError` |
| 32 | 空ファイル | `ParseError` |
| 33 | テキストファイル（非バイナリ） | `ParseError` |
| 34 | バイナリ途中切断（truncated） | `ParseError` |

---

### テストデータ方針

- カテゴリ1（統合テスト）: `docs/sample_data/` の実ファイルを使用
- カテゴリ2・3（単体テスト）: テスト内でバイナリデータをインラインで構築する（`pytest` の `fixture` として定義）

---

## TODO

- [ ] テストの実装（実装フェーズで対応）
