"""
GET    /api/prompt-templates              - テンプレート一覧
GET    /api/question-sets                 - 質問セット一覧
GET    /api/analysis/sessions             - セッション一覧
GET    /api/analysis/sessions/{id}        - セッション詳細
DELETE /api/analysis/sessions/{id}        - セッション削除
POST   /api/analysis/chat                 - SSE チャット
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models.analysis import (
    AnalysisSession, AnalysisMessage, PromptTemplate, QuestionSet,
)
from models.core import Match, Game, Mulligan, Action
from app.routers.settings import get_api_key
from app.routers.stats import _build_match_id_list, _calc_deck_stats

router = APIRouter()
_log = logging.getLogger(__name__)


# ── 統計テキスト生成 ────────────────────────────────────────────────────────

def build_stats_text(
    player: str,
    db: Session,
    opponent: str | None = None,
    deck: str | None = None,
    deck_id: int | None = None,
    version_id: int | None = None,
    opponent_deck: str | None = None,
    format_: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> str:
    """プレイヤーの統計データをテキスト形式で返す。"""
    match_ids = _build_match_id_list(db, player, opponent, deck_id, opponent_deck, format_, date_from, date_to, deck=deck, version_id=version_id)
    if not match_ids:
        return f"（{player} のデータはありません）"

    matches = (
        db.query(Match)
        .filter(Match.id.in_(match_ids))
        .order_by(Match.played_at.asc())
        .all()
    )
    total_matches = len(matches)
    wins = sum(1 for m in matches if m.match_winner == player)
    win_rate = wins / total_matches

    format_counts: dict[str, int] = {}
    for m in matches:
        fmt = m.format or "unknown"
        format_counts[fmt] = format_counts.get(fmt, 0) + 1

    games = db.query(Game).filter(Game.match_id.in_(match_ids)).all()
    total_games = len(games)
    avg_turns = sum(g.turns for g in games) / total_games if total_games else 0.0

    first_games = [g for g in games if g.first_player == player]
    second_games = [g for g in games if g.first_player != player]
    first_wr = (
        sum(1 for g in first_games if g.winner == player) / len(first_games)
        if first_games else 0.0
    )
    second_wr = (
        sum(1 for g in second_games if g.winner == player) / len(second_games)
        if second_games else 0.0
    )

    game_ids = [g.id for g in games]
    mulligan_game_ids = set(
        r[0] for r in db.query(Mulligan.game_id)
        .filter(
            Mulligan.game_id.in_(game_ids),
            Mulligan.player_name == player,
            Mulligan.count > 0,
        )
        .distinct().all()
    )
    mulligan_rate = len(mulligan_game_ids) / total_games if total_games else 0.0

    deck_stats = _calc_deck_stats(db, player, match_ids)

    card_rows = (
        db.query(Action.card_name, func.count(Action.id).label("cnt"))
        .filter(
            Action.game_id.in_(game_ids),
            Action.player_name == player,
            Action.action_type.in_(["play", "cast"]),
            Action.card_name.isnot(None),
        )
        .group_by(Action.card_name)
        .order_by(func.count(Action.id).desc())
        .limit(5)
        .all()
    )

    filter_parts = []
    if opponent:
        filter_parts.append(f"対戦相手: {opponent}")
    if deck:
        filter_parts.append(f"使用デッキ: {deck}")
    if opponent_deck:
        filter_parts.append(f"相手デッキ: {opponent_deck}")
    if format_:
        filter_parts.append(f"フォーマット: {format_}")
    if date_from:
        filter_parts.append(f"開始日: {date_from}")
    if date_to:
        filter_parts.append(f"終了日: {date_to}")

    lines = [
        f"【絞り込み条件】{', '.join(filter_parts)}" if filter_parts else "【絞り込み条件】なし（全データ）",
        f"総マッチ数: {total_matches}",
        f"使用フォーマット: {', '.join(f'{k}（{v}件）' for k, v in format_counts.items())}",
        f"勝率: {win_rate:.1%}",
        f"先手勝率: {first_wr:.1%} / 後手勝率: {second_wr:.1%}",
        f"平均ターン数: {avg_turns:.1f}",
        f"マリガン率: {mulligan_rate:.1%}",
        "",
    ]
    if deck_stats:
        lines.append("デッキ別勝率:")
        for d in deck_stats:
            lines.append(f"  {d['deck_name']}: {d['matches']}試合 {d['win_rate']:.1%}")
        lines.append("")
    if card_rows:
        lines.append("よく使うカード TOP5:")
        for card_name, cnt in card_rows:
            lines.append(f"  {card_name}: {cnt}回使用")

    return "\n".join(lines)


# ── スキーマ ────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    player: str
    prompt_template_id: int | None = None
    session_id: int | None = None
    message: str
    history: list[dict] | None = None  # [{"role": "user"|"assistant", "content": "..."}]
    opponent: str | None = None
    deck: str | None = None
    deck_id: int | None = None
    version_id: int | None = None
    opponent_deck: str | None = None
    format: str | None = None
    date_from: str | None = None
    date_to: str | None = None


# ── エンドポイント ──────────────────────────────────────────────────────────

@router.get("/prompt-templates")
def list_prompt_templates(db: Session = Depends(get_db)):
    rows = (
        db.query(PromptTemplate)
        .order_by(PromptTemplate.is_default.desc(), PromptTemplate.id)
        .all()
    )
    return {
        "templates": [
            {"id": t.id, "name": t.name, "content": t.content, "is_default": bool(t.is_default)}
            for t in rows
        ]
    }


@router.get("/question-sets")
def list_question_sets(db: Session = Depends(get_db)):
    rows = (
        db.query(QuestionSet)
        .order_by(QuestionSet.is_default.desc(), QuestionSet.id)
        .all()
    )
    return {
        "question_sets": [
            {
                "id": qs.id,
                "name": qs.name,
                "is_default": bool(qs.is_default),
                "items": [
                    {"id": qi.id, "text": qi.text, "display_order": qi.display_order}
                    for qi in qs.items
                ],
            }
            for qs in rows
        ]
    }


@router.get("/analysis/sessions")
def list_sessions(player: str | None = None, db: Session = Depends(get_db)):
    q = db.query(AnalysisSession).order_by(AnalysisSession.updated_at.desc())
    if player:
        q = q.filter(AnalysisSession.player_name == player)
    rows = q.all()
    return {
        "sessions": [
            {
                "id": s.id,
                "player_name": s.player_name,
                "prompt_template_id": s.prompt_template_id,
                "title": s.title,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in rows
        ]
    }


@router.get("/analysis/sessions/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)):
    s = db.get(AnalysisSession, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": s.id,
        "player_name": s.player_name,
        "prompt_template_id": s.prompt_template_id,
        "title": s.title,
        "filter_opponent": s.filter_opponent,
        "filter_deck": s.filter_deck,
        "filter_opponent_deck": s.filter_opponent_deck,
        "filter_format": s.filter_format,
        "filter_date_from": s.filter_date_from,
        "filter_date_to": s.filter_date_to,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
        "messages": [
            {"id": m.id, "role": m.role, "content": m.content, "display_order": m.display_order}
            for m in s.messages
        ],
    }


@router.delete("/analysis/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, db: Session = Depends(get_db)):
    s = db.get(AnalysisSession, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(s)
    db.commit()


@router.post("/analysis/chat")
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    api_key = get_api_key(db)
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="APIキーが設定されていません。設定画面で入力してください。",
        )

    # プロンプトテンプレート取得
    if req.prompt_template_id:
        template = db.get(PromptTemplate, req.prompt_template_id)
    else:
        template = db.query(PromptTemplate).filter_by(is_default=1).first()

    stats_text = build_stats_text(
        req.player, db,
        opponent=req.opponent,
        deck=req.deck,
        deck_id=req.deck_id,
        version_id=req.version_id,
        opponent_deck=req.opponent_deck,
        format_=req.format,
        date_from=req.date_from,
        date_to=req.date_to,
    )
    if template:
        system_prompt = (
            template.content
            .replace("{player_name}", req.player)
            .replace("{stats_text}", stats_text)
        )
    else:
        system_prompt = (
            f"あなたはMagic: The Gatheringの対戦分析エキスパートです。"
            f"プレイヤー: {req.player}\n\n統計データ:\n{stats_text}"
        )

    messages: list[dict] = []
    if req.history:
        messages.extend(req.history)
    messages.append({"role": "user", "content": req.message})

    # ストリーミングジェネレーター用にリクエスト情報をキャプチャ
    player = req.player
    user_message = req.message
    session_id = req.session_id
    template_id = req.prompt_template_id
    f_opponent = req.opponent
    f_deck = req.deck
    f_opponent_deck = req.opponent_deck
    f_format = req.format
    f_date_from = req.date_from
    f_date_to = req.date_to

    async def generate():
        full_response = ""
        new_session_id = session_id

        try:
            client = anthropic.AsyncAnthropic(api_key=api_key)
            async with client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    full_response += text
                    yield f"data: {json.dumps({'delta': text}, ensure_ascii=False)}\n\n"
        except anthropic.AuthenticationError:
            yield f"data: {json.dumps({'error': 'APIキーが無効です'})}\n\n"
            return
        except Exception as e:
            _log.exception("chat stream error")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        # セッション保存（新しい DB セッションを使用）
        try:
            now = datetime.now(timezone.utc)
            save_db = SessionLocal()
            try:
                if new_session_id:
                    session = save_db.get(AnalysisSession, new_session_id)
                    if session is None:
                        new_session_id = None

                title = (user_message.split('\n')[0] or user_message)[:20]

                if new_session_id is None:
                    session = AnalysisSession(
                        player_name=player,
                        prompt_template_id=template_id,
                        title=title,
                        filter_opponent=f_opponent,
                        filter_deck=f_deck,
                        filter_opponent_deck=f_opponent_deck,
                        filter_format=f_format,
                        filter_date_from=f_date_from,
                        filter_date_to=f_date_to,
                        created_at=now,
                        updated_at=now,
                    )
                    save_db.add(session)
                    save_db.flush()
                    new_session_id = session.id
                else:
                    session.title = title
                    session.filter_opponent = f_opponent
                    session.filter_deck = f_deck
                    session.filter_opponent_deck = f_opponent_deck
                    session.filter_format = f_format
                    session.filter_date_from = f_date_from
                    session.filter_date_to = f_date_to
                    session.updated_at = now

                existing_count = (
                    save_db.query(AnalysisMessage)
                    .filter_by(session_id=new_session_id)
                    .count()
                )
                save_db.add(AnalysisMessage(
                    session_id=new_session_id,
                    role="user",
                    content=user_message,
                    display_order=existing_count + 1,
                    created_at=now,
                ))
                save_db.add(AnalysisMessage(
                    session_id=new_session_id,
                    role="assistant",
                    content=full_response,
                    display_order=existing_count + 2,
                    created_at=now,
                ))
                save_db.commit()
            finally:
                save_db.close()
        except Exception:
            _log.exception("session save error")

        yield f"data: {json.dumps({'done': True, 'session_id': new_session_id})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
