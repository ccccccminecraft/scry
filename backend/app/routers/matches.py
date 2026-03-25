"""
GET    /api/matches                                  - 対戦履歴一覧
GET    /api/matches/{match_id}                       - 対戦詳細
GET    /api/matches/{match_id}/games/{game_id}/actions - アクションログ
PATCH  /api/matches/{match_id}/players/{player_name} - デッキ名・ゲームプラン更新
DELETE /api/matches/all                              - 全データ削除（開発用）
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.core import Match, MatchPlayer, Game, Mulligan, Action
from models.decklist import DeckVersion, Deck

router = APIRouter()


@router.delete("/matches/all")
def delete_all_matches(db: Session = Depends(get_db)):
    """全対戦データを削除する（開発用）。"""
    db.query(Action).delete()
    db.query(Mulligan).delete()
    db.query(Game).delete()
    db.query(MatchPlayer).delete()
    db.query(Match).delete()
    db.commit()
    return {"status": "cleared"}


@router.get("/matches")
def list_matches(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    player: str | None = Query(default=None),
    opponent: str | None = Query(default=None),
    deck_ids: list[int] = Query(default=[]),
    decks: list[str] = Query(default=[]),
    version_id: int | None = Query(default=None),
    opponent_decks: list[str] = Query(default=[]),
    format: str | None = Query(default=None),
    date_from: str | None = Query(default=None, description="YYYY-MM-DD"),
    date_to: str | None = Query(default=None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    q = db.query(Match)

    if player:
        player_sub = (
            db.query(MatchPlayer.match_id)
            .filter(MatchPlayer.player_name == player)
            .subquery()
        )
        q = q.filter(Match.id.in_(player_sub))

    if opponent:
        opp_sub = (
            db.query(MatchPlayer.match_id)
            .filter(MatchPlayer.player_name == opponent)
            .subquery()
        )
        q = q.filter(Match.id.in_(opp_sub))

    if version_id and len(deck_ids) == 1:
        ver_sub = (
            db.query(MatchPlayer.match_id)
            .filter(
                MatchPlayer.player_name == player,
                MatchPlayer.deck_version_id == version_id,
            )
            .subquery()
        )
        q = q.filter(Match.id.in_(ver_sub))
    elif deck_ids:
        deck_sub = (
            db.query(MatchPlayer.match_id)
            .join(DeckVersion, DeckVersion.id == MatchPlayer.deck_version_id)
            .filter(
                MatchPlayer.player_name == player,
                DeckVersion.deck_id.in_(deck_ids),
            )
            .subquery()
        )
        q = q.filter(Match.id.in_(deck_sub))
    elif decks:
        deck_sub = (
            db.query(MatchPlayer.match_id)
            .filter(
                MatchPlayer.player_name == player,
                MatchPlayer.deck_name.in_(decks),
            )
            .subquery()
        )
        q = q.filter(Match.id.in_(deck_sub))

    if opponent_decks:
        opp_deck_filter = [MatchPlayer.deck_name.in_(opponent_decks)]
        if player:
            opp_deck_filter.append(MatchPlayer.player_name != player)
        opp_deck_sub = (
            db.query(MatchPlayer.match_id)
            .filter(*opp_deck_filter)
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

    total = q.count()

    from sqlalchemy.orm import selectinload
    rows = (
        q
        .order_by(Match.played_at.desc())
        .offset(offset)
        .limit(limit)
        .options(
            selectinload(Match.players)
            .selectinload(MatchPlayer.deck_version)
            .selectinload(DeckVersion.deck)
        )
        .all()
    )

    def _display_deck_name(p: MatchPlayer) -> str | None:
        if p.deck_version is not None:
            return p.deck_version.deck.name
        return p.deck_name

    matches = []
    for m in rows:
        sorted_players = sorted(m.players, key=lambda p: p.seat)
        matches.append({
            "match_id": m.id,
            "date": m.played_at.isoformat(),
            "players": [p.player_name for p in sorted_players],
            "decks": [_display_deck_name(p) for p in sorted_players],
            "match_winner": m.match_winner,
            "game_count": m.game_count,
            "format": m.format,
        })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "matches": matches,
    }


def _export_filter_params():
    """エクスポート用フィルターパラメーターの共通定義（関数で共有）。"""


@router.get("/matches/export/count")
def export_count(
    player: str = Query(...),
    opponent: str | None = Query(default=None),
    deck_ids: list[int] = Query(default=[]),
    decks: list[str] = Query(default=[]),
    version_id: int | None = Query(default=None),
    opponent_decks: list[str] = Query(default=[]),
    format: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """エクスポート対象マッチ数を返す。"""
    from app.routers.stats import _build_match_id_list
    match_ids = _build_match_id_list(db, player, opponent, deck_ids, opponent_decks, format, date_from, date_to, decks, version_id)
    return {"count": len(match_ids)}


@router.get("/matches/export")
def export_matches(
    player: str = Query(...),
    opponent: str | None = Query(default=None),
    deck_ids: list[int] = Query(default=[]),
    decks: list[str] = Query(default=[]),
    version_id: int | None = Query(default=None),
    opponent_decks: list[str] = Query(default=[]),
    format: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    include_summary: bool = Query(default=True),
    include_deck_stats: bool = Query(default=True),
    include_card_stats: bool = Query(default=True),
    include_deck_list: bool = Query(default=True),
    include_matches: bool = Query(default=True),
    include_actions: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=1000),
    no_limit: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """対戦データを Markdown 形式でエクスポートする。"""
    from app.routers.stats import _build_match_id_list, _calc_deck_stats

    match_ids = _build_match_id_list(db, player, opponent, deck_ids, opponent_decks, format, date_from, date_to, decks, version_id)
    # デッキ表示名（Markdownヘッダー用）: deck_ids の名前 + decks をまとめる
    deck_id_names = [db.get(Deck, did).name for did in deck_ids if db.get(Deck, did)]
    deck_label = "、".join(deck_id_names + list(decks)) or None
    effective_limit = None if no_limit else limit
    # デッキリスト出力用バージョンIDリスト
    if version_id:
        output_version_ids = [version_id]
    elif deck_ids:
        output_version_ids = []
        for did in deck_ids:
            latest = db.query(DeckVersion).filter(DeckVersion.deck_id == did).order_by(DeckVersion.version_number.desc()).first()
            if latest:
                output_version_ids.append(latest.id)
    else:
        output_version_ids = []
    opponent_deck_label = "、".join(opponent_decks) or None
    markdown = _build_export_markdown(player, db, match_ids, effective_limit,
                                      opponent, deck_label, opponent_deck_label, format, date_from, date_to,
                                      version_ids=output_version_ids,
                                      include_summary=include_summary,
                                      include_deck_stats=include_deck_stats,
                                      include_card_stats=include_card_stats,
                                      include_deck_list=include_deck_list,
                                      include_matches=include_matches,
                                      include_actions=include_actions)

    from datetime import datetime as dt
    date_str = dt.now().strftime("%Y%m%d%H%M%S")
    filename = f"scry_export_{player}_{date_str}.md"
    return Response(
        content=markdown,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_export_markdown(
    player: str,
    db: Session,
    match_ids: list[str],
    limit: int | None,
    opponent: str | None,
    deck: str | None,
    opponent_deck: str | None,
    format_: str | None,
    date_from: str | None,
    date_to: str | None,
    version_ids: list[int] | None = None,
    include_summary: bool = True,
    include_deck_stats: bool = True,
    include_card_stats: bool = True,
    include_deck_list: bool = True,
    include_matches: bool = True,
    include_actions: bool = False,
) -> str:
    from datetime import datetime as dt
    from app.routers.stats import _calc_deck_stats

    now_str = dt.now().strftime("%Y-%m-%d %H:%M")
    total_count = len(match_ids)
    output_count = total_count if limit is None else min(limit, total_count)

    filter_parts = []
    if opponent:
        filter_parts.append(f"対戦相手={opponent}")
    if deck:
        filter_parts.append(f"使用デッキ={deck}")
    if opponent_deck:
        filter_parts.append(f"相手デッキ={opponent_deck}")
    if format_:
        filter_parts.append(f"フォーマット={format_}")
    if date_from:
        filter_parts.append(f"開始日={date_from}")
    if date_to:
        filter_parts.append(f"終了日={date_to}")
    filter_str = "、".join(filter_parts) if filter_parts else "なし（全データ）"

    lines = [
        f"# 対戦データ — {player}",
        "",
        f"エクスポート日時: {now_str}",
        f"フィルター: {filter_str}",
        f"対象マッチ数: {total_count} 件（直近 {output_count} 件を出力）",
        "",
        "---",
        "",
    ]

    if not match_ids:
        lines.append("*対象データなし*")
        return "\n".join(lines)

    # 統計計算（サマリー・デッキ別勝率・カード統計いずれかが必要な場合のみ実行）
    need_stats = include_summary or include_deck_stats or include_card_stats
    matches_all = db.query(Match).filter(Match.id.in_(match_ids)).all() if need_stats else []
    games_all = db.query(Game).filter(Game.match_id.in_(match_ids)).all() if need_stats else []
    game_ids = [g.id for g in games_all]

    # ── サマリー ──────────────────────────────────────────────────────────
    if include_summary:
        wins = sum(1 for m in matches_all if m.match_winner == player)
        losses = len(matches_all) - wins
        win_rate = wins / len(matches_all) if matches_all else 0.0
        total_games = len(games_all)
        first_games = [g for g in games_all if g.first_player == player]
        second_games = [g for g in games_all if g.first_player != player]
        first_wr = sum(1 for g in first_games if g.winner == player) / len(first_games) if first_games else 0.0
        second_wr = sum(1 for g in second_games if g.winner == player) / len(second_games) if second_games else 0.0
        avg_turns = sum(g.turns for g in games_all) / total_games if total_games else 0.0
        mul_game_ids = set(
            r[0] for r in db.query(Mulligan.game_id)
            .filter(Mulligan.game_id.in_(game_ids), Mulligan.player_name == player, Mulligan.count > 0)
            .distinct().all()
        )
        mulligan_rate = len(mul_game_ids) / total_games if total_games else 0.0
        lines += [
            "## サマリー",
            "",
            "| 項目 | 値 |",
            "|------|-----|",
            f"| 総マッチ数 | {len(matches_all)} |",
            f"| 勝利 / 敗北 | {wins} / {losses} |",
            f"| 勝率 | {win_rate:.1%} |",
            f"| 先手勝率 | {first_wr:.1%} |",
            f"| 後手勝率 | {second_wr:.1%} |",
            f"| 平均ターン数 | {avg_turns:.1f} |",
            f"| マリガン率 | {mulligan_rate:.1%} |",
            "",
        ]

    # ── デッキ別勝率 ──────────────────────────────────────────────────────
    if include_deck_stats:
        deck_stats = _calc_deck_stats(db, player, match_ids)
        if deck_stats:
            lines += [
                "## デッキ別勝率",
                "",
                "| デッキ | マッチ数 | 勝率 |",
                "|--------|---------|------|",
            ]
            for d in deck_stats:
                lines.append(f"| {d['deck_name']} | {d['matches']} | {d['win_rate']:.1%} |")
            lines.append("")

    # ── カード統計 ────────────────────────────────────────────────────────
    if include_card_stats:
        from app.routers.stats import _calc_card_stats
        self_cards = _calc_card_stats(db, player, game_ids, "self", limit=20)
        opp_cards  = _calc_card_stats(db, player, game_ids, "opponent", limit=20)
        if self_cards:
            lines += [
                "## カード統計（選択プレイヤー Top 20）",
                "",
                "| カード名 | 使用回数 | 登場ゲーム | 勝率 |",
                "|---------|---------|-----------|------|",
            ]
            for c in self_cards:
                lines.append(f"| {c['card_name']} | {c['play_count']} | {c['game_count']} | {c['win_rate']:.1%} |")
            lines.append("")
        if opp_cards:
            lines += [
                "## カード統計（対戦相手 Top 20）",
                "",
                "| カード名 | 使用回数 | 登場ゲーム | 選択プレイヤー勝率 |",
                "|---------|---------|-----------|-----------------|",
            ]
            for c in opp_cards:
                lines.append(f"| {c['card_name']} | {c['play_count']} | {c['game_count']} | {c['win_rate']:.1%} |")
            lines.append("")

    # ── デッキリスト ──────────────────────────────────────────────────────
    if include_deck_list:
        for vid in (version_ids or []):
            ver = db.get(DeckVersion, vid)
            if not ver:
                continue
            main_cards = [c for c in ver.cards if not c.is_sideboard]
            side_cards = [c for c in ver.cards if c.is_sideboard]
            if not main_cards and not side_cards:
                continue
            label = f"{ver.deck.name} v{ver.version_number}"
            if ver.memo:
                label += f" {ver.memo}"
            lines += [f"## デッキリスト: {label}", ""]
            if main_cards:
                lines += [f"### メインデッキ ({sum(c.quantity for c in main_cards)})", "",
                           "| 枚数 | カード名 |", "|------|---------|"]
                for c in sorted(main_cards, key=lambda x: x.card.name):
                    lines.append(f"| {c.quantity} | {c.card.name} |")
                lines.append("")
            if side_cards:
                lines += [f"### サイドボード ({sum(c.quantity for c in side_cards)})", "",
                           "| 枚数 | カード名 |", "|------|---------|"]
                for c in sorted(side_cards, key=lambda x: x.card.name):
                    lines.append(f"| {c.quantity} | {c.card.name} |")
                lines.append("")

    # ── 対戦一覧 ──────────────────────────────────────────────────────────
    if include_matches:
        lines += ["---", "", "## 対戦一覧", ""]
        q = (
            db.query(Match)
            .filter(Match.id.in_(match_ids))
            .order_by(Match.played_at.desc())
        )
        target_matches = q.limit(limit).all() if limit is not None else q.all()

        for i, m in enumerate(target_matches, 1):
            date_str = m.played_at.strftime("%Y-%m-%d %H:%M")
            fmt = m.format or "—"
            player_mp = next((p for p in m.players if p.player_name == player), None)
            opponent_mp = next((p for p in m.players if p.player_name != player), None)
            player_deck_name = player_mp.deck_name if player_mp else None
            opponent_name = opponent_mp.player_name if opponent_mp else "—"
            opponent_deck_name = opponent_mp.deck_name if opponent_mp else None
            sorted_games = sorted(m.games, key=lambda g: g.game_number)
            wins_g = sum(1 for g in sorted_games if g.winner == player)
            losses_g = len(sorted_games) - wins_g
            result = "勝利" if m.match_winner == player else "敗北"
            lines += [
                f"### [{i}] {date_str} — {fmt}",
                "",
                f"- **対戦相手**: {opponent_name}",
                f"- **使用デッキ**: {player_deck_name or '—'}",
                f"- **相手デッキ**: {opponent_deck_name or '—'}",
                f"- **結果**: {result} ({wins_g}-{losses_g})",
                "",
                "| ゲーム | 結果 | 先後 | ターン数 | マリガン |",
                "|--------|------|------|---------|---------|",
            ]
            for g in sorted_games:
                g_result = "勝利" if g.winner == player else "敗北"
                first_second = "先手" if g.first_player == player else "後手"
                mul_count = next((mul.count for mul in g.mulligans if mul.player_name == player), 0)
                mul_str = "なし" if mul_count == 0 else f"{mul_count}回"
                lines.append(f"| Game {g.game_number} | {g_result} | {first_second} | {g.turns} | {mul_str} |")
            lines.append("")

            if include_actions:
                for g in sorted_games:
                    actions = (
                        db.query(Action)
                        .filter(Action.game_id == g.id)
                        .order_by(Action.sequence)
                        .all()
                    )
                    if not actions:
                        continue
                    lines += [
                        f"#### Game {g.game_number} アクション詳細",
                        "",
                        "| ターン | プレイヤー | 種別 | カード | 対象 |",
                        "|--------|-----------|------|--------|------|",
                    ]
                    for a in actions:
                        lines.append(
                            f"| {a.turn} | {a.player_name} | {a.action_type}"
                            f" | {a.card_name or '—'} | {a.target_name or '—'} |"
                        )
                    lines.append("")

    return "\n".join(lines)


def _bulk_assign_query(db: Session, player: str, format_: str | None, deck_name: str | None, date_from: str | None, date_to: str | None):
    """一括適用フィルターに合致する MatchPlayer クエリを返す。"""
    q = (
        db.query(MatchPlayer)
        .join(Match, Match.id == MatchPlayer.match_id)
        .filter(MatchPlayer.player_name == player)
    )
    if format_:
        q = q.filter(Match.format == format_)
    if deck_name:
        q = q.filter(MatchPlayer.deck_name == deck_name)
    if date_from:
        q = q.filter(Match.played_at >= datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc))
    if date_to:
        dt_to = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1)
        q = q.filter(Match.played_at < dt_to)
    return q


@router.get("/matches/bulk-assign-deck-version/count")
def bulk_assign_count(
    player: str = Query(...),
    format: str | None = Query(default=None),
    deck_name: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    overwrite: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """一括適用対象の件数を返す。"""
    q = _bulk_assign_query(db, player, format, deck_name, date_from, date_to)
    if not overwrite:
        q = q.filter(MatchPlayer.deck_version_id.is_(None))
    return {"count": q.count()}


class BulkAssignBody(BaseModel):
    deck_version_id: int
    player: str
    format: str | None = None
    deck_name: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    overwrite: bool = False


@router.post("/matches/bulk-assign-deck-version")
def bulk_assign_deck_version(body: BulkAssignBody, db: Session = Depends(get_db)):
    """フィルター条件に合致する対戦にデッキバージョンを一括適用する。"""
    if db.get(DeckVersion, body.deck_version_id) is None:
        raise HTTPException(status_code=404, detail="DeckVersion not found")
    q = _bulk_assign_query(db, body.player, body.format, body.deck_name, body.date_from, body.date_to)
    if not body.overwrite:
        q = q.filter(MatchPlayer.deck_version_id.is_(None))
    rows = q.all()
    for mp in rows:
        mp.deck_version_id = body.deck_version_id
    db.commit()
    return {"updated": len(rows)}


@router.get("/matches/latest-date")
def get_latest_match_date(source: str | None = None, db: Session = Depends(get_db)):
    """最新の played_at を返す。source を指定するとそのソースのみを対象にする。"""
    from sqlalchemy import func
    q = db.query(func.max(Match.played_at))
    if source:
        q = q.filter(Match.source == source)
    latest = q.scalar()
    return {"latest_date": latest.isoformat() if latest else None}


@router.get("/matches/{match_id}")
def get_match(match_id: str, db: Session = Depends(get_db)):
    """対戦詳細を返す。"""
    m = db.get(Match, match_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Match not found")

    sorted_players = sorted(m.players, key=lambda p: p.seat)
    player_names = [p.player_name for p in sorted_players]

    games = []
    for g in sorted(m.games, key=lambda g: g.game_number):
        # マリガン: 両プレイヤー分を補完（0回でも含む）
        mul_map: dict[str, int] = {name: 0 for name in player_names}
        for mul in g.mulligans:
            mul_map[mul.player_name] = mul.count
        games.append({
            "game_id": g.id,
            "game_number": g.game_number,
            "winner": g.winner,
            "turns": g.turns,
            "first_player": g.first_player,
            "mulligans": mul_map,
        })

    return {
        "match_id": m.id,
        "date": m.played_at.isoformat(),
        "players": [
            {
                "player_name": p.player_name,
                "deck_name": p.deck_name,
                "game_plan": p.game_plan,
                "deck_version_id": p.deck_version_id,
                "deck_version_label": (
                    f"{p.deck_version.deck.name} v{p.deck_version.version_number}"
                    if p.deck_version is not None else None
                ),
            }
            for p in sorted_players
        ],
        "match_winner": m.match_winner,
        "format": m.format,
        "games": games,
    }


@router.get("/matches/{match_id}/games/{game_id}/actions")
def get_actions(match_id: str, game_id: int, db: Session = Depends(get_db)):
    """ゲームのアクションログを返す。"""
    game = db.get(Game, game_id)
    if game is None or game.match_id != match_id:
        raise HTTPException(status_code=404, detail="Game not found")

    actions = (
        db.query(Action)
        .filter(Action.game_id == game_id)
        .order_by(Action.sequence)
        .all()
    )

    return {
        "game_id": game_id,
        "actions": [
            {
                "turn": a.turn,
                "phase": a.phase,
                "active_player": a.active_player,
                "player": a.player_name,
                "action_type": a.action_type,
                "card_name": a.card_name,
                "target_name": a.target_name,
                "sequence": a.sequence,
            }
            for a in actions
        ],
    }


class DeckVersionBody(BaseModel):
    deck_version_id: int


@router.put("/matches/{match_id}/players/{player_name}/deck-version")
def put_deck_version(
    match_id: str,
    player_name: str,
    body: DeckVersionBody,
    db: Session = Depends(get_db),
):
    """使用デッキバージョンを設定する。"""
    mp = (
        db.query(MatchPlayer)
        .filter(MatchPlayer.match_id == match_id, MatchPlayer.player_name == player_name)
        .first()
    )
    if mp is None:
        raise HTTPException(status_code=404, detail="Player not found")
    if db.get(DeckVersion, body.deck_version_id) is None:
        raise HTTPException(status_code=404, detail="DeckVersion not found")
    mp.deck_version_id = body.deck_version_id
    db.commit()
    return {"status": "updated"}


@router.delete("/matches/{match_id}/players/{player_name}/deck-version")
def delete_deck_version(
    match_id: str,
    player_name: str,
    db: Session = Depends(get_db),
):
    """使用デッキバージョンの紐づけを解除する。"""
    mp = (
        db.query(MatchPlayer)
        .filter(MatchPlayer.match_id == match_id, MatchPlayer.player_name == player_name)
        .first()
    )
    if mp is None:
        raise HTTPException(status_code=404, detail="Player not found")
    mp.deck_version_id = None
    db.commit()
    return {"status": "updated"}


class PatchPlayerBody(BaseModel):
    deck_name: str | None = None
    game_plan: str | None = None


@router.patch("/matches/{match_id}/players/{player_name}")
def patch_player(
    match_id: str,
    player_name: str,
    body: PatchPlayerBody,
    db: Session = Depends(get_db),
):
    """デッキ名・ゲームプランを更新する。"""
    mp = (
        db.query(MatchPlayer)
        .filter(MatchPlayer.match_id == match_id, MatchPlayer.player_name == player_name)
        .first()
    )
    if mp is None:
        raise HTTPException(status_code=404, detail="Player not found")

    if body.deck_name is not None:
        mp.deck_name = body.deck_name or None
    if body.game_plan is not None:
        mp.game_plan = body.game_plan or None

    db.commit()
    return {"player_name": mp.player_name, "deck_name": mp.deck_name, "game_plan": mp.game_plan}
