"""
MTGOLogParser - MTGO .dat ファイルパーサー

詳細仕様: docs/04_parser-design.md
実装設計: docs/impl/02_parser.md
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TypedDict


# ─── 型定義 ──────────────────────────────────────────────────────────────────

class ActionDict(TypedDict):
    turn: int
    active_player: str
    player: str
    action_type: str
    card_name: str
    multiverse_id: int | None
    target_name: str | None
    sequence: int


class MulliganDict(TypedDict):
    player_name: str
    count: int


class GameDict(TypedDict):
    game_number: int
    winner: str
    turns: int
    first_player: str
    mulligans: list[MulliganDict]
    actions: list[ActionDict]


class ParseResult(TypedDict):
    match_id: str
    players: list[str]
    match_winner: str
    played_at: datetime
    games: list[GameDict]


class EventDict(TypedDict):
    timestamp: datetime
    message: str


# ─── 定数 ────────────────────────────────────────────────────────────────────

MAGIC_BYTES = b'\x01\x00'
HEADER_ID_LEN = 0x24  # 36
SEPARATOR = b'\x04\x00'
AT_P_PREFIX = b'\x40\x50'  # "@P"
DOTNET_EPOCH_DIFF = 621_355_968_000_000_000  # 0001-01-01 → 1970-01-01 差（100ns単位、.NET DateTime.Ticks）

# ─── 正規表現パターン ─────────────────────────────────────────────────────────

RE_CARD = re.compile(r'@\[([^@]+)@:(\d+),\d+:@\]')
RE_TARGETING = re.compile(r'\btargeting\s+(?:@\[([^@]+)@:[^@]+:@\]|([^,.(]+))')

RE_JOINED = re.compile(r'^(.+) joined the game\.$')
RE_FIRST_PLAYER = re.compile(r'^(.+) chooses to play first\.$')
RE_WINS_GAME = re.compile(r'^(.+) wins the game\.$')
RE_LOSES_GAME = re.compile(r'^(.+) loses the game\.$')
RE_WINS_MATCH = re.compile(r'^(.+) wins the match \d+-\d+\.')
RE_TIED_MATCH = re.compile(r'^Match Tied \d+-\d+\.')
RE_LEADS_MATCH = re.compile(r'^(.+) leads the match \d+-\d+\.')

RE_TURN = re.compile(r'^Turn (\d+): (.+)$')
RE_MULLIGAN = re.compile(r'^(.+) mulligans to \w+ cards\.$')

ACTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'^(.+) plays @\['),                       'play'),
    (re.compile(r'^(.+) casts @\['),                       'cast'),
    (re.compile(r'^(.+) activates an ability of @\['),     'activate'),
    (re.compile(r'^(.+) puts triggered ability from @\['), 'trigger'),
    (re.compile(r'^(.+) is being attacked by @\['),        'attack'),
    (re.compile(r'^(.+) draws? (a card|\d+ cards)'),       'draw'),
    (re.compile(r'^(.+) discards @\['),                    'discard'),
    (re.compile(r'^(.+) reveals @\['),                     'reveal'),
    (re.compile(r'^(.+) puts .+ counter on'),              'add_counter'),
    (re.compile(r'^(.+) removes .+ counter'),              'remove_counter'),
    (re.compile(r'^(.+) mulligans to \w+ cards\.$'),       'mulligan'),
]


# ─── 例外 ────────────────────────────────────────────────────────────────────

class ParseError(Exception):
    """ログファイルのパースに失敗した場合。"""
    pass


# ─── パーサー本体 ─────────────────────────────────────────────────────────────

class MTGOLogParser:
    """MTGO の対戦ログ（.dat）を解析して構造化データを返す。"""

    def parse_file(self, filepath: str) -> ParseResult:
        """
        .dat ファイルを読み込み、構造化データを返す。

        Parameters
        ----------
        filepath : str
            .dat ファイルのパス

        Raises
        ------
        FileNotFoundError
            ファイルが存在しない場合
        ParseError
            ファイルフォーマットが不正な場合
        """
        with open(filepath, 'rb') as f:
            data = f.read()
        return self.parse_bytes(data)

    def parse_bytes(self, data: bytes) -> ParseResult:
        """
        バイト列を受け取り、構造化データを返す。UploadFile からの直接処理に使用する。

        Raises
        ------
        ParseError
            ファイルフォーマットが不正な場合
        """
        match_id = self._parse_match_header(data)
        events = self._read_events(data)
        game_blocks = self._split_games(events)

        games: list[GameDict] = []
        for i, block in enumerate(game_blocks, start=1):
            games.append(self._parse_game(block, i))

        # players: joined the game の順に最大2件
        players: list[str] = []
        for ev in events:
            m = RE_JOINED.match(ev["message"])
            if m:
                name = m.group(1)
                if name.startswith('@P'):
                    name = name[2:]
                if name not in players:
                    players.append(name)
                if len(players) == 2:
                    break

        # match_winner: wins the match にマッチしたプレイヤー
        match_winner = ""
        for ev in events:
            m = RE_WINS_MATCH.match(ev["message"])
            if m:
                match_winner = m.group(1)
                break
        if not match_winner and games:
            match_winner = games[-1]["winner"]

        # played_at: 最初のイベントのタイムスタンプを使用
        played_at = events[0]["timestamp"] if events else datetime.now(tz=timezone.utc)

        return ParseResult(
            match_id=match_id,
            players=players,
            match_winner=match_winner,
            played_at=played_at,
            games=games,
        )

    def _parse_match_header(self, data: bytes) -> str:
        """ヘッダーからマッチ ID を抽出する。"""
        if len(data) < 3:
            raise ParseError("File too short to contain a valid header")
        if data[0:2] != MAGIC_BYTES:
            raise ParseError(f"Invalid magic bytes: {data[0:2]!r}")
        id_len = data[2]
        header_size = 6 + 2 * id_len
        if len(data) < header_size:
            raise ParseError("File too short to contain a valid header")
        match_id = data[3: 3 + id_len].decode('utf-8')
        return match_id

    def _read_events(self, data: bytes) -> list[EventDict]:
        """バイナリデータからイベントレコード列を抽出する。"""
        id_len = data[2]
        offset = 6 + 2 * id_len  # ヘッダーサイズを動的に計算（= 78 for id_len=36）
        events: list[EventDict] = []

        while offset < len(data):
            if offset + 10 > len(data):
                break

            ts_raw = int.from_bytes(data[offset:offset + 8], 'little')
            timestamp = self._filetime_to_datetime(ts_raw)

            offset += 9  # タイムスタンプ8バイト + 固定0x00

            # msg_len は LEB128 可変長整数（1バイトまたは2バイト）
            # 最上位ビットが1の場合は2バイト: (byte1 & 0x7F) | (byte2 << 7)
            if offset >= len(data):
                break
            first_byte = data[offset]
            offset += 1
            if first_byte & 0x80:
                if offset >= len(data):
                    break
                second_byte = data[offset]
                offset += 1
                msg_len = (first_byte & 0x7F) | (second_byte << 7)
            else:
                msg_len = first_byte

            if offset + msg_len > len(data):
                break  # ファイル末尾で切れた不完全なイベント

            message = data[offset: offset + msg_len].decode('utf-8', errors='replace')
            offset += msg_len

            # プレイヤー属きメッセージは "@P" で始まるので除去する
            while message.startswith('@P'):
                message = message[2:]

            if timestamp is None:
                continue  # 変換できないタイムスタンプは無視する

            events.append(EventDict(timestamp=timestamp, message=message))
        return events

    @staticmethod
    def _filetime_to_datetime(ts: int) -> datetime | None:
        """.NET DateTime.Ticks を UTC datetime に変換する。変換できない場合は None を返す。"""
        try:
            unix_ts = (ts - DOTNET_EPOCH_DIFF) / 10_000_000
            return datetime.fromtimestamp(unix_ts, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None

    def _split_games(self, events: list[EventDict]) -> list[list[EventDict]]:
        """イベント列をゲームごとのブロックに分割する。"""
        BETWEEN_GAMES = 0
        IN_GAME = 1
        GAME_ENDING = 2

        state = BETWEEN_GAMES
        blocks: list[list[EventDict]] = []
        current_block: list[EventDict] = []
        for ev in events:
            msg = ev["message"]

            if state == BETWEEN_GAMES:
                if RE_JOINED.match(msg):
                    current_block = [ev]
                    state = IN_GAME

            elif state == IN_GAME:
                current_block.append(ev)
                if RE_WINS_GAME.match(msg) or RE_LOSES_GAME.match(msg):
                    state = GAME_ENDING

            elif state == GAME_ENDING:
                current_block.append(ev)
                blocks.append(current_block)
                current_block = []
                state = BETWEEN_GAMES

        if len(blocks) < 1:
            raise ParseError("No game blocks found in log file")

        return blocks

    def _parse_game(self, events: list[EventDict], game_number: int) -> GameDict:
        """1ゲーム分のイベント列をパースする。"""
        first_player = ""
        winner = ""
        current_turn = 0
        current_turn_player = ""
        mulligan_counts: dict[str, int] = {}
        actions: list[ActionDict] = []
        players_in_game: list[str] = []
        sequence = 0

        for ev in events:
            msg = ev["message"]

            m = RE_JOINED.match(msg)
            if m:
                name = m.group(1)
                if name.startswith('@P'):
                    name = name[2:]
                if name not in players_in_game:
                    players_in_game.append(name)
                continue

            m = RE_FIRST_PLAYER.match(msg)
            if m:
                first_player = m.group(1)
                continue

            m = RE_MULLIGAN.match(msg)
            if m:
                player = m.group(1)
                mulligan_counts[player] = mulligan_counts.get(player, 0) + 1
                continue

            m = RE_TURN.match(msg)
            if m:
                current_turn = int(m.group(1))
                current_turn_player = m.group(2)
                continue

            m = RE_WINS_GAME.match(msg)
            if m:
                winner = m.group(1)
                continue

            m = RE_LOSES_GAME.match(msg)
            if m:
                loser = m.group(1)
                for p in players_in_game:
                    if p != loser:
                        winner = p
                        break
                continue

            sequence += 1
            new_actions = self._parse_action(msg, current_turn, current_turn_player, players_in_game, sequence)
            if new_actions:
                actions.extend(new_actions)
                # attack の複数展開分だけ sequence を追加消費する
                sequence += len(new_actions) - 1
            else:
                sequence -= 1

        mulligans: list[MulliganDict] = [
            MulliganDict(player_name=p, count=c)
            for p, c in mulligan_counts.items()
        ]
        return GameDict(
            game_number=game_number,
            winner=winner,
            turns=current_turn,
            first_player=first_player,
            mulligans=mulligans,
            actions=actions,
        )

    def _parse_action(
        self,
        message: str,
        turn: int,
        active_player: str,
        players: list[str],
        sequence: int = 0,
    ) -> list[ActionDict]:
        """1メッセージをアクション dict のリストに変換する。
        attack は複数クリーチャーを1件ずつ展開するため複数要素になる場合がある。
        マッチしない場合は空リストを返す。
        """
        for pattern, action_type in ACTION_PATTERNS:
            m = pattern.match(message)
            if m:
                if action_type == 'attack':
                    # "{defender} is being attacked by @[card1], @[card2], and @[card3]" の形式。
                    # group(1) は防御側。攻撃者はアクティブプレイヤー。
                    # 複数クリーチャーを1件ずつ展開する。
                    player_name = active_player
                    if players and player_name not in players:
                        return []
                    cards = self._extract_all_card_names(message)
                    if not cards:
                        cards = [("", None)]
                    return [
                        ActionDict(
                            turn=turn,
                            active_player=active_player,
                            player=player_name,
                            action_type=action_type,
                            card_name=card_name,
                            multiverse_id=multiverse_id,
                            target_name=None,
                            sequence=sequence + i,
                        )
                        for i, (card_name, multiverse_id) in enumerate(cards)
                    ]
                else:
                    player_name = m.group(1)
                    if players and player_name not in players:
                        return []
                    card_name, multiverse_id = self._extract_card_name(message)
                    target_name = (
                        self._extract_target(message)
                        if action_type in ('cast', 'activate', 'trigger')
                        else None
                    )
                    return [ActionDict(
                        turn=turn,
                        active_player=active_player,
                        player=player_name,
                        action_type=action_type,
                        card_name=card_name,
                        multiverse_id=multiverse_id,
                        target_name=target_name,
                        sequence=sequence,
                    )]
        return []

    @staticmethod
    def _extract_card_name(message: str) -> tuple[str, int | None]:
        """メッセージ中の最初の @[CardName@:...:@] からカード名と multiverse_id を抽出する。"""
        m = RE_CARD.search(message)
        if m:
            return m.group(1), int(m.group(2))
        return "", None

    @staticmethod
    def _extract_all_card_names(message: str) -> list[tuple[str, int | None]]:
        """メッセージ中の全 @[CardName@:...:@] をリストで返す。複数攻撃の展開に使用する。"""
        return [(m.group(1), int(m.group(2))) for m in RE_CARD.finditer(message)]

    @staticmethod
    def _extract_target(message: str) -> str | None:
        """'targeting ...' 部分から最初のターゲット名を抽出する。
        カード参照 (@[...@]) はカード名を、それ以外はプレイヤー名等をそのまま返す。
        """
        m = RE_TARGETING.search(message)
        if not m:
            return None
        # group(1): カード参照のカード名、group(2): プレイヤー名等のテキスト
        return (m.group(1) or m.group(2) or "").strip() or None
