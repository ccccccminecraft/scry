"""
surveil_parser.py - Surveil JSON (MTGA) → 内部データ構造変換

Surveil が生成した schema_version=2 の JSON を解析して
SurveilImportService が受け取る形式に変換する。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, TypedDict

SCHEMA_VERSION = 2

_BASIC_LANDS = frozenset({
    "Plains", "Island", "Swamp", "Mountain", "Forest",
    "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp",
    "Snow-Covered Mountain", "Snow-Covered Forest", "Wastes",
})

# スキップするイベント種別（Action テーブルに保存しない）
_SKIP_EVENTS = frozenset({
    "turn_start", "phase_change",
    "ability_mana", "ability_resolved",
    "resolve", "life_change",
})

# event_type → action_type
_EVENT_TO_ACTION: dict[str, str] = {
    "cast":              "cast",
    "play_land":         "play",
    "draw":              "draw",
    "discard":           "discard",
    "mulligan":          "mulligan",
    "attack":            "attack",
    "block":             "block",
    "ability_activated": "activate",
    "ability_triggered": "trigger",
    "mill":              "mill",
    "damage":            "damage",
}


class ParseError(Exception):
    pass


class SurveilGameAction(TypedDict):
    turn: int
    phase: str
    active_player: str
    player: str
    action_type: str
    card_name: str | None
    target_name: str | None
    sequence: int


class SurveilGame(TypedDict):
    game_number: int
    winner: str
    turns: int
    first_player: str
    mulligans: list[dict]
    actions: list[SurveilGameAction]


class SurveilParseResult(TypedDict):
    match_id: str
    source: Literal["mtga"]
    players: list[str]
    self_seat_id: int
    self_player: str
    match_winner: str
    played_at: datetime
    deck_main: dict[str, int]
    deck_sideboard: dict[str, int]
    games: list[SurveilGame]


def parse_surveil_json(data: dict) -> SurveilParseResult:
    """
    Surveil JSON dict を SurveilParseResult に変換する。
    不正なデータの場合は ParseError を送出する。
    """
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ParseError(f"Unsupported schema_version: {version} (expected {SCHEMA_VERSION})")

    match_id = data.get("match_id", "")
    if not match_id:
        raise ParseError("match_id is missing")

    source = data.get("source", "")
    if source != "mtga":
        raise ParseError(f"Unexpected source: {source!r}")

    players: list[str] = data.get("players", [])
    self_seat_id: int = data.get("self_seat_id", 1)
    match_winner: str = data.get("match_winner", "")

    played_at_str = data.get("played_at", "")
    try:
        played_at = datetime.fromisoformat(played_at_str)
    except (ValueError, TypeError):
        played_at = datetime.now(tz=timezone.utc)

    deck = data.get("deck", {})
    deck_main: dict[str, int] = deck.get("main", {})
    deck_sideboard: dict[str, int] = deck.get("sideboard", {})

    # self_seat_id (1-indexed) → プレイヤー名
    self_player = (
        players[self_seat_id - 1]
        if 0 < self_seat_id <= len(players)
        else (players[0] if players else "")
    )

    games = [_parse_game(g) for g in data.get("games", [])]

    return SurveilParseResult(
        match_id=match_id,
        source="mtga",
        players=players,
        self_seat_id=self_seat_id,
        self_player=self_player,
        match_winner=match_winner,
        played_at=played_at,
        deck_main=deck_main,
        deck_sideboard=deck_sideboard,
        games=games,
    )


def _parse_game(game_data: dict) -> SurveilGame:
    """1ゲームのイベントリストを Action 形式のリストに変換する。"""
    active_player = ""
    actions: list[SurveilGameAction] = []

    for event in game_data.get("events", []):
        event_type = event.get("event_type", "")

        # turn_start から active_player を追跡
        if event_type == "turn_start":
            active_player = event.get("active_player", active_player)
            continue

        if event_type in _SKIP_EVENTS:
            continue

        action_type = _EVENT_TO_ACTION.get(event_type)
        if action_type is None:
            continue

        card_name, target_name, player = _extract_fields(event, event_type)

        # draw: card_name なし（相手の非公開ドロー）はスキップ
        if event_type == "draw" and not card_name:
            continue

        actions.append(SurveilGameAction(
            turn=event.get("turn", 0),
            phase=event.get("phase", ""),
            active_player=active_player,
            player=player,
            action_type=action_type,
            card_name=card_name or None,
            target_name=target_name or None,
            sequence=event.get("seq", 0),
        ))

    mulligans = [
        {"player_name": m.get("player_name", ""), "count": m.get("count", 0)}
        for m in game_data.get("mulligans", [])
    ]

    return SurveilGame(
        game_number=game_data.get("game_number", 1),
        winner=game_data.get("winner", ""),
        turns=game_data.get("turns", 0),
        first_player=game_data.get("first_player", ""),
        mulligans=mulligans,
        actions=actions,
    )


def _extract_fields(
    event: dict, event_type: str
) -> tuple[str | None, str | None, str]:
    """イベントから (card_name, target_name, player) を抽出する。"""
    player: str = event.get("player", "")

    if event_type == "cast":
        targets = event.get("targets", [])
        target_name = _resolve_target_name(targets[0]) if targets else None
        return event.get("card_name"), target_name, player

    if event_type in ("play_land", "draw", "discard", "mill"):
        return event.get("card_name"), None, player

    if event_type == "mulligan":
        return None, None, player

    if event_type == "attack":
        return event.get("card_name"), event.get("target_player"), player

    if event_type == "block":
        blocking = event.get("blocking", [])
        target_name = _resolve_target_name(blocking[0]) if blocking else None
        return event.get("card_name"), target_name, player

    if event_type in ("ability_activated", "ability_triggered"):
        raw = event.get("source_card") or event.get("source_grp_id")
        card_name = str(raw) if raw is not None else None
        return card_name, None, player

    if event_type == "damage":
        raw = event.get("source_card") or event.get("source_grp_id")
        card_name = str(raw) if raw is not None else None
        raw_target = (
            event.get("target_player")
            or event.get("target_card")
            or event.get("target_grp_id")
        )
        target_name = str(raw_target) if raw_target is not None else None
        return card_name, target_name, player

    return None, None, player


def _resolve_target_name(target: dict) -> str | None:
    """targets / blocking リストの要素から表示用文字列を返す。"""
    return (
        target.get("player")
        or target.get("card_name")
        or (str(target["grp_id"]) if "grp_id" in target else None)
    )


def get_non_basic_card_names(deck_main: dict[str, int]) -> list[str]:
    """フォーマット推定に使うカード名（基本土地を除く）を返す。"""
    return [name for name in deck_main if name not in _BASIC_LANDS]
