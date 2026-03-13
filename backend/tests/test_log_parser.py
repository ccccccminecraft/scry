import pytest
from parser.log_parser import MTGOLogParser, ParseError

MATCH_ID = "01564d49-9b3b-4bd4-a879-09bc7a91e602"
PLAYER_A = "PlayerA"
PLAYER_B = "PlayerB"


# ─── Fixtures / ヘルパー ────────────────────────────────────────────────────

@pytest.fixture
def parser():
    return MTGOLogParser()


def make_header(match_id: str = MATCH_ID) -> bytes:
    """正常なヘッダーバイト列を生成する（78バイト: 6 + 2 * 36）"""
    mid = match_id.encode("utf-8")
    return (
        b"\x01\x00"
        + bytes([len(mid)])
        + mid
        + b"\x04\x00"
        + bytes([len(mid)])
        + mid
    )


def make_event(message: str, ts: int = 132_000_000_000_000_000) -> bytes:
    """正常なイベントレコードバイト列を生成する"""
    body = message.encode("utf-8")
    msg_len = len(body) + 2  # @P プレフィックス分
    return (
        ts.to_bytes(8, "little")
        + b"\x00"
        + bytes([msg_len])
        + b"\x40\x50"
        + body
    )


def make_game_events(
    player_a: str = PLAYER_A,
    player_b: str = PLAYER_B,
    winner: str = PLAYER_A,
    game_num: int = 1,
    first_player: str = PLAYER_A,
    mulligans: list[str] | None = None,
    extra_events: list[str] | None = None,
) -> list[str]:
    """1ゲーム分のイベントメッセージリストを生成する"""
    events = [
        f"{player_a} joined the game.",
        f"{player_b} joined the game.",
        f"{first_player} chooses to play first.",
        "Turn 1: PlayerA",
    ]
    for player in (mulligans or []):
        events.append(f"{player} mulligans to six cards.")
    if extra_events:
        events.extend(extra_events)
    events.append(f"{winner} wins the game.")
    loser = player_b if winner == player_a else player_a
    score = "1-0" if game_num == 1 else "2-0"
    events.append(f"{winner} leads the match {score}.")
    return events


def build_dat(messages: list[str]) -> bytes:
    """ヘッダー + イベント列のバイト列を生成する"""
    data = make_header()
    for msg in messages:
        data += make_event(msg)
    return data


# ─── カテゴリ1: _parse_match_header ─────────────────────────────────────────

class TestParseMatchHeader:
    def test_valid_header(self, parser):
        data = make_header(MATCH_ID) + b"\x00" * 100
        result = parser._parse_match_header(data)
        assert result == MATCH_ID

    def test_invalid_magic_bytes(self, parser):
        data = b"\x02\x00" + make_header(MATCH_ID)[2:]
        with pytest.raises(ParseError):
            parser._parse_match_header(data)

    def test_too_short(self, parser):
        # id_len=36 → header_size=78、それより短いデータで ParseError
        with pytest.raises(ParseError):
            parser._parse_match_header(b"\x01\x00\x24" + b"\x00" * 10)


# ─── カテゴリ2: _read_events ─────────────────────────────────────────────────

class TestReadEvents:
    def test_single_event(self, parser):
        data = make_header() + make_event("Hello world")
        events = parser._read_events(data)
        assert len(events) == 1
        assert events[0]["message"] == "Hello world"

    def test_message_length_matches(self, parser):
        msg = "Turn 1: PlayerA"
        data = make_header() + make_event(msg)
        events = parser._read_events(data)
        assert events[0]["message"] == msg

    def test_multiple_events(self, parser):
        msgs = ["event one", "event two", "event three"]
        data = make_header()
        for m in msgs:
            data += make_event(m)
        events = parser._read_events(data)
        assert [e["message"] for e in events] == msgs

    def test_truncated_body_raises(self, parser):
        header = make_header()
        # body_len=10 と宣言するが実際は5バイトしかない
        bad_event = (
            (132_000_000_000_000_000).to_bytes(8, "little")
            + b"\x00"
            + bytes([12])   # msg_len = 12 → body_len = 10
            + b"\x40\x50"
            + b"hello"      # 5バイトしかない
        )
        with pytest.raises(ParseError):
            parser._read_events(header + bad_event)


# ─── カテゴリ3: _split_games ─────────────────────────────────────────────────

class TestSplitGames:
    def _make_events(self, messages: list[str]):
        from datetime import datetime, timezone
        ts = datetime(2020, 1, 1, tzinfo=timezone.utc)
        return [{"timestamp": ts, "message": m} for m in messages]

    def test_two_games(self, parser):
        msgs = (
            make_game_events(winner=PLAYER_A, game_num=1)
            + make_game_events(winner=PLAYER_A, game_num=2)
        )
        # ゲーム2のleadsをwins matchに変更
        msgs[-1] = f"{PLAYER_A} wins the match 2-0."
        events = self._make_events(msgs)
        blocks = parser._split_games(events)
        assert len(blocks) == 2

    def test_one_game(self, parser):
        msgs = make_game_events(winner=PLAYER_A, game_num=1)
        msgs[-1] = f"{PLAYER_A} wins the match 1-0."
        events = self._make_events(msgs)
        blocks = parser._split_games(events)
        assert len(blocks) == 1

    def test_no_games_raises(self, parser):
        events = self._make_events(["some random message", "another message"])
        with pytest.raises(ParseError):
            parser._split_games(events)


# ─── カテゴリ4: _parse_game ──────────────────────────────────────────────────

class TestParseGame:
    def _make_events(self, messages: list[str]):
        from datetime import datetime, timezone
        ts = datetime(2020, 1, 1, tzinfo=timezone.utc)
        return [{"timestamp": ts, "message": m} for m in messages]

    def test_first_player(self, parser):
        msgs = make_game_events(first_player=PLAYER_B)
        events = self._make_events(msgs)
        game = parser._parse_game(events, 1)
        assert game["first_player"] == PLAYER_B

    def test_no_mulligan(self, parser):
        msgs = make_game_events()
        events = self._make_events(msgs)
        game = parser._parse_game(events, 1)
        assert game["mulligans"] == []

    def test_mulligan_once(self, parser):
        msgs = make_game_events(mulligans=[PLAYER_A])
        events = self._make_events(msgs)
        game = parser._parse_game(events, 1)
        assert len(game["mulligans"]) == 1
        assert game["mulligans"][0]["player_name"] == PLAYER_A
        assert game["mulligans"][0]["count"] == 1

    def test_mulligan_twice(self, parser):
        msgs = make_game_events(mulligans=[PLAYER_A, PLAYER_A])
        events = self._make_events(msgs)
        game = parser._parse_game(events, 1)
        assert game["mulligans"][0]["count"] == 2

    def test_turn_count(self, parser):
        extra = ["Turn 2: PlayerA", "Turn 3: PlayerA", "Turn 4: PlayerA"]
        msgs = make_game_events(extra_events=extra)
        events = self._make_events(msgs)
        game = parser._parse_game(events, 1)
        assert game["turns"] == 4

    def test_winner_wins_game(self, parser):
        msgs = make_game_events(winner=PLAYER_A)
        events = self._make_events(msgs)
        game = parser._parse_game(events, 1)
        assert game["winner"] == PLAYER_A

    def test_winner_loses_game(self, parser):
        # loses game → 負けたのが PLAYER_B → 勝者は PLAYER_A
        msgs = [
            f"{PLAYER_A} joined the game.",
            f"{PLAYER_B} joined the game.",
            f"{PLAYER_A} chooses to play first.",
            "Turn 1: PlayerA",
            f"{PLAYER_B} loses the game.",
            f"{PLAYER_A} wins the match 1-0.",
        ]
        events = self._make_events(msgs)
        game = parser._parse_game(events, 1)
        assert game["winner"] == PLAYER_A

    def test_game_number(self, parser):
        msgs = make_game_events()
        events = self._make_events(msgs)
        game = parser._parse_game(events, 3)
        assert game["game_number"] == 3


# ─── カテゴリ5: _parse_action ────────────────────────────────────────────────

CARD_REF = "@[Lightning Bolt@:439219,12345:@]"
PLAYERS = [PLAYER_A, PLAYER_B]


class TestParseAction:
    def test_play_land(self, parser):
        msg = f"{PLAYER_A} plays {CARD_REF}."
        result = parser._parse_action(msg, 1, PLAYERS, sequence=1)
        assert result is not None
        assert result["action_type"] == "play"
        assert result["player"] == PLAYER_A
        assert result["card_name"] == "Lightning Bolt"
        assert result["multiverse_id"] == 439219
        assert result["sequence"] == 1

    def test_cast_spell(self, parser):
        msg = f"{PLAYER_A} casts {CARD_REF}."
        result = parser._parse_action(msg, 2, PLAYERS, sequence=2)
        assert result is not None
        assert result["action_type"] == "cast"

    def test_activate(self, parser):
        msg = f"{PLAYER_B} activates an ability of {CARD_REF}."
        result = parser._parse_action(msg, 1, PLAYERS)
        assert result is not None
        assert result["action_type"] == "activate"

    def test_attack(self, parser):
        msg = f"{PLAYER_A} is being attacked by {CARD_REF}."
        result = parser._parse_action(msg, 3, PLAYERS)
        assert result is not None
        assert result["action_type"] == "attack"

    def test_draw(self, parser):
        msg = f"{PLAYER_A} draws a card."
        result = parser._parse_action(msg, 1, PLAYERS)
        assert result is not None
        assert result["action_type"] == "draw"
        assert result["card_name"] == ""
        assert result["multiverse_id"] is None

    def test_mulligan_action(self, parser):
        msg = f"{PLAYER_A} mulligans to six cards."
        result = parser._parse_action(msg, 0, PLAYERS)
        assert result is not None
        assert result["action_type"] == "mulligan"

    def test_unknown_message_returns_none(self, parser):
        msg = "Game 1 has started."
        result = parser._parse_action(msg, 1, PLAYERS)
        assert result is None

    def test_non_player_skipped(self, parser):
        msg = "SomeOtherEntity casts @[Counterspell@:1001,2:@]."
        result = parser._parse_action(msg, 1, PLAYERS)
        assert result is None


# ─── カテゴリ6: _extract_card_name ──────────────────────────────────────────

class TestExtractCardName:
    def test_valid_card_ref(self, parser):
        msg = f"PlayerA casts {CARD_REF}."
        name, mid = parser._extract_card_name(msg)
        assert name == "Lightning Bolt"
        assert mid == 439219

    def test_no_card_ref(self, parser):
        name, mid = parser._extract_card_name("PlayerA draws a card.")
        assert name == ""
        assert mid is None

    def test_multiple_card_refs_returns_first(self, parser):
        card2 = "@[Island@:2,99:@]"
        msg = f"PlayerA plays {CARD_REF} and {card2}."
        name, mid = parser._extract_card_name(msg)
        assert name == "Lightning Bolt"
        assert mid == 439219


# ─── カテゴリ7: parse_file 異常系 ────────────────────────────────────────────

class TestParseFileErrors:
    def test_file_not_found(self, parser, tmp_path):
        with pytest.raises(FileNotFoundError):
            parser.parse_file(str(tmp_path / "nonexistent.dat"))

    def test_empty_file(self, parser, tmp_path):
        f = tmp_path / "empty.dat"
        f.write_bytes(b"")
        with pytest.raises(ParseError):
            parser.parse_file(str(f))

    def test_invalid_magic(self, parser, tmp_path):
        f = tmp_path / "bad.dat"
        f.write_bytes(b"\x02\x00" + b"\x00" * 78)
        with pytest.raises(ParseError):
            parser.parse_file(str(f))

    def test_truncated_binary(self, parser, tmp_path):
        f = tmp_path / "truncated.dat"
        f.write_bytes(make_header()[:40])
        with pytest.raises(ParseError):
            parser.parse_file(str(f))

    def test_valid_single_game(self, parser, tmp_path):
        msgs = make_game_events(winner=PLAYER_A)
        msgs[-1] = f"{PLAYER_A} wins the match 1-0."
        data = build_dat(msgs)
        f = tmp_path / "game.dat"
        f.write_bytes(data)
        result = parser.parse_file(str(f))
        assert result["match_id"] == MATCH_ID
        assert result["match_winner"] == PLAYER_A
        assert len(result["games"]) == 1
        assert result["players"] == [PLAYER_A, PLAYER_B]
