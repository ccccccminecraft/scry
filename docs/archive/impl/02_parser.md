# 詳細設計: MTGOログパーサー

## 対象ファイル

| ファイル | 種別 | 内容 |
|----------|------|------|
| `backend/parser/log_parser.py` | 編集 | MTGOLogParser 全メソッドの実装 |
| `backend/parser/__init__.py` | 新規 | ParseError・MTGOLogParser のエクスポート |
| `backend/tests/__init__.py` | 新規 | 空ファイル |
| `backend/tests/test_log_parser.py` | 新規 | pytest ユニットテスト |
| `docs/sample_data/` | 新規 | 統合テスト用サンプル .dat ファイル置き場 |

---

## 型定義

`log_parser.py` 冒頭に `TypedDict` で定義する。

```python
from typing import TypedDict

class ActionDict(TypedDict):
    turn: int
    player: str
    action_type: str
    card_name: str           # カードなしの場合は空文字 ""
    multiverse_id: int | None

class MulliganDict(TypedDict):
    player_name: str
    count: int               # マリガン回数

class GameDict(TypedDict):
    game_number: int
    winner: str
    turns: int
    first_player: str
    mulligans: list[MulliganDict]
    actions: list[ActionDict]

class ParseResult(TypedDict):
    match_id: str
    players: list[str]       # [プレイヤーA, プレイヤーB]（joined順）
    match_winner: str
    games: list[GameDict]

class EventDict(TypedDict):
    timestamp: datetime
    message: str
```

> **注**: `mulligans` の設計書定義は `dict[str, int]` だが、
> DB 保存時のループ処理が自然になるよう `list[MulliganDict]` に変更する。
> `ImportService` 側でこの形式を前提として処理する。

---

## バイナリ構造の定数定義

```python
MAGIC_BYTES      = b'\x01\x00'
HEADER_ID_LEN    = 0x24          # 36
SEPARATOR        = b'\x04\x00'
AT_P_PREFIX      = b'\x40\x50'  # "@P"
FILETIME_EPOCH_DIFF = 116_444_736_000_000_000  # 1601-01-01 → 1970-01-01 の差（100ns単位）
```

---

## ヘッダー構造

```
オフセット  サイズ  内容
0           2       マジックバイト [01 00]
2           1       マッチID長 (= 0x24 = 36)
3           36      マッチID (UTF-8)
39          2       区切り [04 00]
41          1       マッチID長 (= 36)
42          36      マッチID (UTF-8、同一値)
78          2       パディング（未使用）
─────────────────────────────────────────
合計        80 bytes
```

---

## イベントレコード構造

```
オフセット  サイズ  内容
0           8       タイムスタンプ（Windows FILETIME、リトルエンディアン）
8           1       固定 0x00
9           1       メッセージ長 L（@P プレフィックス 2バイトを含む）
10          2       "@P" プレフィックス（0x40 0x50）
12          L-2     メッセージ本文（UTF-8）
─────────────────────────────────────────
合計        10 + L bytes
```

> **長さフィールドの注意**: L は "@P" の 2 バイトを含む。
> 実際のメッセージ本文は `data[12 : 10 + L]` で取得する。

---

## 正規表現パターン一覧

```python
import re

# カード参照: @[CardName@:multiverseId,permanentId:@]
RE_CARD = re.compile(r'@\[([^@]+)@:(\d+),\d+:@\]')

# ゲーム制御
RE_JOINED       = re.compile(r'^(.+) joined the game\.$')
RE_FIRST_PLAYER = re.compile(r'^(.+) chooses to play first\.$')
RE_WINS_GAME    = re.compile(r'^(.+) wins the game\.$')
RE_LOSES_GAME   = re.compile(r'^(.+) loses the game\.$')
RE_WINS_MATCH   = re.compile(r'^(.+) wins the match \d+-\d+\.')
RE_TIED_MATCH   = re.compile(r'^Match Tied \d+-\d+\.')
RE_LEADS_MATCH  = re.compile(r'^(.+) leads the match \d+-\d+\.')

# ターン
RE_TURN         = re.compile(r'^Turn (\d+): (.+)$')

# マリガン
RE_MULLIGAN     = re.compile(r'^(.+) mulligans to \w+ cards\.$')

# アクション種別（順番通りに試行する）
ACTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'^(.+) plays @\['),             'play'),
    (re.compile(r'^(.+) casts @\['),             'cast'),
    (re.compile(r'^(.+) activates an ability of @\['), 'activate'),
    (re.compile(r'^(.+) puts triggered ability from @\['), 'trigger'),
    (re.compile(r'^(.+) is being attacked by @\['), 'attack'),
    (re.compile(r'^(.+) draws? (a card|\d+ cards)'), 'draw'),
    (re.compile(r'^(.+) discards @\['),           'discard'),
    (re.compile(r'^(.+) reveals @\['),            'reveal'),
    (re.compile(r'^(.+) puts .+ counter on'),     'add_counter'),
    (re.compile(r'^(.+) removes .+ counter'),     'remove_counter'),
    (re.compile(r'^(.+) mulligans to \w+ cards\.$'), 'mulligan'),
]
```

---

## メソッド別実装詳細

### `parse_file(filepath: str) -> ParseResult`

```
1. open(filepath, 'rb') でバイナリ読み込み
   └── FileNotFoundError はそのまま raise
2. _parse_match_header(data) でマッチIDを取得
3. _read_events(data) でイベントリストを取得
4. _split_games(events) でゲームブロックに分割
5. 各ゲームブロックを _parse_game(block, game_number) でパース
6. match_winner・players を確定して ParseResult を構築して返す
```

**players の取得**:
`_read_events` 後、全イベントから `RE_JOINED` にマッチする行を先頭2件取得し、
マッチ順に `players` リストを構築する。

**match_winner の確定**:
全イベントを順に走査し、`RE_WINS_MATCH` にマッチしたプレイヤー名を使用する。
マッチしない場合（タイ等）は `games[-1].winner` を使用する。

---

### `_parse_match_header(data: bytes) -> str`

```
1. data[0:2] == MAGIC_BYTES でなければ ParseError
2. id_len = data[2]
3. match_id = data[3 : 3 + id_len].decode('utf-8')
4. match_id を返す
```

> ヘッダー全体の長さチェック（80バイト未満なら ParseError）も行う。

---

### `_read_events(data: bytes) -> list[EventDict]`

```python
offset = 80  # ヘッダーをスキップ
events = []

while offset < len(data):
    # 残りが最小レコードサイズ（10バイト）未満なら終了
    if offset + 10 > len(data):
        break

    # タイムスタンプ（8バイト、リトルエンディアン）
    ts_raw = int.from_bytes(data[offset:offset+8], 'little')
    timestamp = _filetime_to_datetime(ts_raw)

    # 固定 0x00 をスキップ
    offset += 9

    # メッセージ長（@P を含む）
    msg_len = data[offset]
    offset += 1

    # @P プレフィックスをスキップ（2バイト）
    offset += 2

    # メッセージ本文
    body_len = msg_len - 2
    if offset + body_len > len(data):
        raise ParseError("Unexpected end of file in event body")
    message = data[offset : offset + body_len].decode('utf-8', errors='replace')
    offset += body_len

    events.append({"timestamp": timestamp, "message": message})

return events
```

**`_filetime_to_datetime(ts: int) -> datetime`**:

```python
unix_ts = (ts - FILETIME_EPOCH_DIFF) / 10_000_000
return datetime.fromtimestamp(unix_ts, tz=timezone.utc)
```

---

### `_split_games(events: list[EventDict]) -> list[list[EventDict]]`

ゲーム境界の検出ロジック：

```
state = BETWEEN_GAMES  # または IN_GAME / GAME_ENDING

BETWEEN_GAMES:
  RE_JOINED にマッチ → current_block = [event], state = IN_GAME

IN_GAME:
  current_block に event を追加
  RE_WINS_GAME または RE_LOSES_GAME にマッチ → state = GAME_ENDING

GAME_ENDING:
  current_block に event を追加
  RE_LEADS_MATCH / RE_WINS_MATCH / RE_TIED_MATCH にマッチ
    → blocks.append(current_block), state = BETWEEN_GAMES
```

終了後、`len(blocks) < 1` なら `ParseError`。

> **NOTE**: `GAME_ENDING` 状態でスコア行が現れる前に次の `joined the game.` が来る
> ケースは設計書上想定していないが、安全のため `IN_GAME` と同じく `joined` を無視する。

---

### `_parse_game(events: list[EventDict], game_number: int) -> GameDict`

```
初期化:
  first_player = ""
  winner = ""
  turns = 0
  current_turn = 0
  mulligan_counts: dict[str, int] = {}  # player_name → count
  actions: list[ActionDict] = []
  sequence_in_turn = 0
  players_in_game: list[str] = []  # joined の順に追加

イベント走査:
  RE_JOINED       → players_in_game に追加（重複なし）
  RE_FIRST_PLAYER → first_player = マッチグループ
  RE_MULLIGAN     → mulligan_counts[player] += 1
  RE_TURN         → current_turn = int(グループ1), sequence_in_turn = 0
  RE_WINS_GAME    → winner = マッチグループ
  RE_LOSES_GAME   → winner = players_in_game の中でマッチグループ以外のプレイヤー

  アクション判定（_parse_action を呼ぶ）:
    ACTION_PATTERNS のいずれかにマッチ → actions に追加
    sequence_in_turn += 1

後処理:
  mulligans = [
      {"player_name": p, "count": c}
      for p, c in mulligan_counts.items()
  ]
  # マリガン0のプレイヤーは mulligans に含めない

返す GameDict:
  game_number, winner, turns=current_turn,
  first_player, mulligans, actions
```

---

### `_parse_action(message: str, turn: int, sequence: int, players: list[str]) -> ActionDict | None`

```
1. ACTION_PATTERNS を順に試行
2. マッチしたパターンの action_type を取得
3. player_name: マッチグループ1（ただし players リストに含まれるか確認）
4. card_name, multiverse_id: RE_CARD で message からカード参照を抽出
   - マッチあり: card_name = グループ1, multiverse_id = int(グループ2)
   - マッチなし: card_name = "", multiverse_id = None
5. いずれのパターンにもマッチしない → None を返す（無視するメッセージ）

返す ActionDict:
  turn, player=player_name, action_type, card_name, multiverse_id, sequence
```

> **player_name の検証**: メッセージ先頭部分がプレイヤー名と一致するか確認する。
> 一致しない場合はそのアクションをスキップする（システムメッセージ等の誤検知防止）。

---

### `_extract_card_name(message: str) -> tuple[str, int | None]`

```python
m = RE_CARD.search(message)
if m:
    return m.group(1), int(m.group(2))
return "", None
```

> `_parse_action` の内部処理として使用するため、戻り値はタプルに変更。

---

## ファイル構成

```python
# backend/parser/log_parser.py

import re
import struct
from datetime import datetime, timezone
from typing import TypedDict

# 定数定義
# TypedDict 定義
# 正規表現パターン定義

class ParseError(Exception):
    pass

class MTGOLogParser:
    def parse_file(...)
    def _parse_match_header(...)
    def _read_events(...)
    def _filetime_to_datetime(...)  # staticmethod
    def _split_games(...)
    def _parse_game(...)
    def _parse_action(...)
    def _extract_card_name(...)    # staticmethod
```

---

## エラー処理まとめ

| ケース | 例外 | 発生箇所 |
|--------|------|---------|
| ファイルが存在しない | `FileNotFoundError` | `parse_file` |
| ファイルが空（80バイト未満） | `ParseError` | `_parse_match_header` |
| マジックバイトが不正 | `ParseError` | `_parse_match_header` |
| イベントボディが途中切断 | `ParseError` | `_read_events` |
| ゲームブロックが0件 | `ParseError` | `_split_games` |
| UTF-8 デコードエラー | 無視（`errors='replace'`） | `_read_events` |

---

## テストファイル構成

```python
# backend/tests/test_log_parser.py

import pytest
from backend.parser.log_parser import MTGOLogParser, ParseError

# ─── Fixtures ────────────────────────────────────────

@pytest.fixture
def parser():
    return MTGOLogParser()

def make_header(match_id: str = "01564d49-9b3b-4bd4-a879-09bc7a91e602") -> bytes:
    """正常なヘッダーバイト列を生成する"""
    mid = match_id.encode('utf-8')
    return (
        b'\x01\x00'
        + bytes([len(mid)])
        + mid
        + b'\x04\x00'
        + bytes([len(mid)])
        + mid
        + b'\x00\x00'
    )

def make_event(message: str, ts: int = 132_000_000_000_000_000) -> bytes:
    """正常なイベントレコードバイト列を生成する"""
    body = message.encode('utf-8')
    msg_len = len(body) + 2  # @P プレフィックス分
    return (
        ts.to_bytes(8, 'little')
        + b'\x00'
        + bytes([msg_len])
        + b'\x40\x50'
        + body
    )

# ─── カテゴリ2: 個別メソッドテスト ───────────────────

class TestParseMatchHeader:
    def test_valid_header(self, parser): ...
    def test_invalid_magic_bytes(self, parser): ...

class TestReadEvents:
    def test_single_event(self, parser): ...
    def test_message_length_matches(self, parser): ...

class TestSplitGames:
    def test_two_games(self, parser): ...
    def test_three_games(self, parser): ...
    def test_no_games_raises(self, parser): ...

class TestParseGame:
    def test_first_player(self, parser): ...
    def test_no_mulligan(self, parser): ...
    def test_mulligan_twice(self, parser): ...
    def test_turn_count(self, parser): ...
    def test_winner_wins_game(self, parser): ...
    def test_winner_loses_game(self, parser): ...

class TestParseAction:
    def test_play_land(self, parser): ...
    def test_cast_spell(self, parser): ...
    def test_activate(self, parser): ...
    def test_attack(self, parser): ...
    def test_draw(self, parser): ...
    def test_mulligan(self, parser): ...

class TestExtractCardName:
    def test_valid_card_ref(self, parser): ...
    def test_no_card_ref(self, parser): ...
    def test_multiple_card_refs(self, parser): ...

# ─── カテゴリ3: 異常系 ────────────────────────────────

class TestParseFileErrors:
    def test_file_not_found(self, parser): ...
    def test_empty_file(self, parser): ...
    def test_invalid_magic(self, parser): ...
    def test_truncated_binary(self, parser): ...
```

---

## 動作確認手順

1. Docker で backend コンテナに入る:
   ```bash
   docker compose exec backend bash
   ```
2. pytest を実行する:
   ```bash
   cd /app
   pytest tests/test_log_parser.py -v
   ```
3. 実 `.dat` ファイルがある場合は統合テストも実行:
   ```bash
   pytest tests/test_log_parser.py -v -k "integration"
   ```
4. 簡易動作確認（Python REPL）:
   ```python
   from backend.parser.log_parser import MTGOLogParser
   parser = MTGOLogParser()
   result = parser.parse_file("/path/to/Match_GameLog_xxx.dat")
   print(result["match_id"])
   print(len(result["games"]))
   ```
