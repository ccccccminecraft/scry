"""
GET /api/stats/players   - プレイヤー一覧
GET /api/stats/opponents - 対戦相手一覧
GET /api/stats           - サマリー統計
GET /api/stats/cards     - カード別統計
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case, distinct
from sqlalchemy.orm import Session

from database import get_db
from models.core import Match, MatchPlayer, Game, Mulligan, Action

router = APIRouter()


@router.get("/stats/players")
def get_players(db: Session = Depends(get_db)):
    """プレイヤー名の一覧を試合数の多い順で返す。"""
    from sqlalchemy import func
    rows = (
        db.query(MatchPlayer.player_name, func.count().label("match_count"))
        .group_by(MatchPlayer.player_name)
        .order_by(func.count().desc())
        .all()
    )
    return {"players": [r[0] for r in rows]}


@router.get("/stats/opponents")
def get_opponents(
    player: str = Query(...),
    db: Session = Depends(get_db),
):
    """指定プレイヤーの対戦相手一覧を返す。"""
    # player が参加したマッチに存在する他のプレイヤー
    player_matches = (
        db.query(MatchPlayer.match_id)
        .filter(MatchPlayer.player_name == player)
        .subquery()
    )
    rows = (
        db.query(MatchPlayer.player_name)
        .filter(
            MatchPlayer.match_id.in_(player_matches),
            MatchPlayer.player_name != player,
        )
        .distinct()
        .order_by(MatchPlayer.player_name)
        .all()
    )
    return {"opponents": [r[0] for r in rows]}


@router.get("/stats/opponent-decks")
def get_opponent_decks(
    player: str = Query(...),
    opponent: str | None = Query(default=None),
    format: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """指定プレイヤーの対戦相手が使用したデッキ一覧を返す。"""
    player_matches = (
        db.query(MatchPlayer.match_id)
        .filter(MatchPlayer.player_name == player)
        .subquery()
    )
    q = (
        db.query(MatchPlayer.deck_name)
        .join(Match, Match.id == MatchPlayer.match_id)
        .filter(
            MatchPlayer.match_id.in_(player_matches),
            MatchPlayer.player_name != player,
            MatchPlayer.deck_name.isnot(None),
        )
    )
    if opponent:
        q = q.filter(MatchPlayer.player_name == opponent)
    if format:
        q = q.filter(Match.format == format)
    rows = q.distinct().order_by(MatchPlayer.deck_name).all()
    return {"opponent_decks": [r[0] for r in rows]}


@router.get("/stats/player-decks")
def get_player_decks(
    player: str = Query(...),
    format: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """指定プレイヤー自身が使用したデッキ一覧を返す。"""
    q = (
        db.query(MatchPlayer.deck_name)
        .join(Match, Match.id == MatchPlayer.match_id)
        .filter(
            MatchPlayer.player_name == player,
            MatchPlayer.deck_name.isnot(None),
        )
    )
    if format:
        q = q.filter(Match.format == format)
    rows = q.distinct().order_by(MatchPlayer.deck_name).all()
    return {"player_decks": [r[0] for r in rows]}


@router.get("/stats/formats")
def get_formats(db: Session = Depends(get_db)):
    """インポート済みマッチのフォーマット一覧を返す。"""
    rows = (
        db.query(Match.format)
        .filter(Match.format.isnot(None))
        .distinct()
        .order_by(Match.format)
        .all()
    )
    return {"formats": [r[0] for r in rows]}


def _build_match_id_list(
    db: Session,
    player: str,
    opponent: str | None,
    deck: str | None,
    opponent_deck: str | None,
    format: str | None,
    date_from: str | None,
    date_to: str | None,
) -> list[str]:
    """フィルター条件に合致するマッチIDリストを返す。"""
    from datetime import datetime, timezone, timedelta

    q = db.query(Match.id).join(
        MatchPlayer, MatchPlayer.match_id == Match.id
    ).filter(MatchPlayer.player_name == player)

    if opponent:
        opp_sub = (
            db.query(MatchPlayer.match_id)
            .filter(MatchPlayer.player_name == opponent)
            .subquery()
        )
        q = q.filter(Match.id.in_(opp_sub))

    if deck:
        deck_sub = (
            db.query(MatchPlayer.match_id)
            .filter(
                MatchPlayer.player_name == player,
                MatchPlayer.deck_name == deck,
            )
            .subquery()
        )
        q = q.filter(Match.id.in_(deck_sub))

    if opponent_deck:
        opp_deck_sub = (
            db.query(MatchPlayer.match_id)
            .filter(
                MatchPlayer.player_name != player,
                MatchPlayer.deck_name == opponent_deck,
            )
            .subquery()
        )
        q = q.filter(Match.id.in_(opp_deck_sub))

    if format:
        q = q.filter(Match.format == format)

    if date_from:
        q = q.filter(Match.played_at >= datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc))

    if date_to:
        dt_to = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1)
        q = q.filter(Match.played_at < dt_to)

    return [r[0] for r in q.all()]


@router.get("/stats")
def get_stats(
    player: str = Query(...),
    opponent: str | None = Query(default=None),
    deck: str | None = Query(default=None),
    opponent_deck: str | None = Query(default=None),
    format: str | None = Query(default=None),
    date_from: str | None = Query(default=None, description="YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="YYYY-MM-DD"),
    history_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """サマリー統計を返す。"""

    match_id_list = _build_match_id_list(db, player, opponent, deck, opponent_deck, format, date_from, date_to)
    match_ids_sub = (
        db.query(Match.id)
        .filter(Match.id.in_(match_id_list))
        .subquery()
    )

    # 対象マッチ一覧（played_at 昇順）
    matches = (
        db.query(Match)
        .filter(Match.id.in_(match_id_list))
        .order_by(Match.played_at.asc())
        .all()
    )

    total_matches = len(matches)
    if total_matches == 0:
        return _empty_stats()

    wins = sum(1 for m in matches if m.match_winner == player)
    win_rate = wins / total_matches

    # ── ゲーム集計 ────────────────────────────────────────────────────
    match_id_list = [m.id for m in matches]

    games = (
        db.query(Game)
        .filter(Game.match_id.in_(match_id_list))
        .all()
    )

    total_games = len(games)
    avg_turns = (sum(g.turns for g in games) / total_games) if total_games else 0

    # 先手・後手勝率
    first_games = [g for g in games if g.first_player == player]
    second_games = [g for g in games if g.first_player != player]
    first_win_rate = (
        sum(1 for g in first_games if g.winner == player) / len(first_games)
        if first_games else 0.0
    )
    second_win_rate = (
        sum(1 for g in second_games if g.winner == player) / len(second_games)
        if second_games else 0.0
    )

    # マリガン率（1回以上マリガンしたゲームの割合）
    game_ids = [g.id for g in games]
    mulligan_game_ids = set(
        r[0]
        for r in db.query(Mulligan.game_id)
        .filter(
            Mulligan.game_id.in_(game_ids),
            Mulligan.player_name == player,
            Mulligan.count > 0,
        )
        .distinct()
        .all()
    )
    mulligan_rate = len(mulligan_game_ids) / total_games if total_games else 0.0

    # ── 勝率推移（直近 history_size 件）────────────────────────────────
    recent = matches[-history_size:]
    win_rate_history = [
        {
            "date": m.played_at.isoformat(),
            "match_index": i + 1,
            "won": m.match_winner == player,
        }
        for i, m in enumerate(recent)
    ]

    # ── デッキ別勝率 ──────────────────────────────────────────────────
    deck_stats = _calc_deck_stats(db, player, match_id_list)

    return {
        "total_matches": total_matches,
        "win_rate": win_rate,
        "avg_turns": avg_turns,
        "mulligan_rate": mulligan_rate,
        "first_play_win_rate": first_win_rate,
        "second_play_win_rate": second_win_rate,
        "win_rate_history": win_rate_history,
        "deck_stats": deck_stats,
    }


def _calc_deck_stats(db: Session, player: str, match_id_list: list[str]) -> list[dict]:
    """デッキ別の試合数と勝率を返す。"""
    rows = (
        db.query(MatchPlayer.deck_name, Match.match_winner)
        .join(Match, Match.id == MatchPlayer.match_id)
        .filter(
            MatchPlayer.match_id.in_(match_id_list),
            MatchPlayer.player_name == player,
            MatchPlayer.deck_name.isnot(None),
        )
        .all()
    )

    deck_map: dict[str, dict] = {}
    for deck_name, winner in rows:
        if deck_name not in deck_map:
            deck_map[deck_name] = {"matches": 0, "wins": 0}
        deck_map[deck_name]["matches"] += 1
        if winner == player:
            deck_map[deck_name]["wins"] += 1

    return [
        {
            "deck_name": name,
            "matches": d["matches"],
            "win_rate": d["wins"] / d["matches"],
        }
        for name, d in sorted(deck_map.items(), key=lambda x: -x[1]["matches"])
    ]


def _calc_card_stats(
    db: Session,
    player: str,
    game_ids: list[int],
    perspective: str,
    limit: int = 20,
) -> list[dict]:
    """game_ids を対象にカード別統計を集計する。勝率は常に player 視点。"""
    if not game_ids:
        return []

    if perspective == "opponent":
        player_filter = Action.player_name != player
    else:
        player_filter = Action.player_name == player

    rows = (
        db.query(
            Action.card_name,
            func.count(Action.id).label("play_count"),
            func.count(distinct(Action.game_id)).label("game_count"),
        )
        .filter(
            Action.game_id.in_(game_ids),
            player_filter,
            Action.action_type.in_(["play", "cast"]),
            Action.card_name.isnot(None),
        )
        .group_by(Action.card_name)
        .order_by(func.count(Action.id).desc())
        .limit(limit)
        .all()
    )

    card_names = [r[0] for r in rows]
    play_count_map = {r[0]: r[1] for r in rows}
    game_count_map = {r[0]: r[2] for r in rows}

    if not card_names:
        return []

    game_rows = (
        db.query(Action.card_name, Action.game_id, Game.winner)
        .join(Game, Game.id == Action.game_id)
        .filter(
            Action.game_id.in_(game_ids),
            player_filter,
            Action.action_type.in_(["play", "cast"]),
            Action.card_name.in_(card_names),
        )
        .distinct(Action.card_name, Action.game_id)
        .all()
    )

    win_map: dict[str, dict] = {name: {"total": 0, "wins": 0} for name in card_names}
    seen: set[tuple] = set()
    for card_name, game_id, winner in game_rows:
        key = (card_name, game_id)
        if key in seen:
            continue
        seen.add(key)
        win_map[card_name]["total"] += 1
        if winner == player:
            win_map[card_name]["wins"] += 1

    cards = []
    for name in card_names:
        total = win_map[name]["total"]
        wins = win_map[name]["wins"]
        cards.append({
            "card_name": name,
            "play_count": play_count_map[name],
            "game_count": game_count_map[name],
            "win_rate": wins / total if total else 0.0,
        })
    return cards


@router.get("/stats/cards")
def get_card_stats(
    player: str = Query(...),
    opponent: str | None = Query(default=None),
    deck: str | None = Query(default=None),
    opponent_deck: str | None = Query(default=None),
    format: str | None = Query(default=None),
    date_from: str | None = Query(default=None, description="YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="YYYY-MM-DD"),
    limit: int = Query(default=20, ge=1, le=100),
    perspective: str = Query(default="self", description="self or opponent"),
    db: Session = Depends(get_db),
):
    """カード別統計（play/cast のみ）を返す。perspective=self で自分、opponent で相手のカードを集計。"""
    match_id_list = _build_match_id_list(db, player, opponent, deck, opponent_deck, format, date_from, date_to)

    if not match_id_list:
        return {"cards": []}

    game_ids = [
        r[0] for r in db.query(Game.id).filter(Game.match_id.in_(match_id_list)).all()
    ]

    cards = _calc_card_stats(db, player, game_ids, perspective, limit)
    return {"cards": cards}


def _empty_stats() -> dict:
    return {
        "total_matches": 0,
        "win_rate": 0.0,
        "avg_turns": 0.0,
        "mulligan_rate": 0.0,
        "first_play_win_rate": 0.0,
        "second_play_win_rate": 0.0,
        "win_rate_history": [],
        "deck_stats": [],
    }
