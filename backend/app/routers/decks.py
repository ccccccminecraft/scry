"""
GET    /api/deck-definitions              - デッキ定義一覧
POST   /api/deck-definitions              - デッキ定義作成
PUT    /api/deck-definitions/{id}         - デッキ定義更新
DELETE /api/deck-definitions/{id}         - デッキ定義削除
PATCH  /api/deck-bulk                     - デッキ名一括上書き
POST   /api/deck-definitions/import       - JSONからインポート
GET    /api/deck-definitions/export       - JSONにエクスポート
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import anthropic
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.core import Match, MatchPlayer
from models.deck import DeckDefinition, DeckDefinitionCard

router = APIRouter()


# ── スキーマ ─────────────────────────────────────────────────────────────────

class DeckDefinitionInput(BaseModel):
    player_name: str | None = None
    deck_name: str
    format: str | None = None
    threshold: int = 2
    cards: list[str]          # シグネチャカード名のリスト
    exclude_cards: list[str] = []  # 除外カード名のリスト


class DeckBulkInput(BaseModel):
    player_name: str
    deck_name: str
    last_n: int | None = None
    date_from: str | None = None  # YYYY-MM-DD
    date_to: str | None = None    # YYYY-MM-DD


class DeckGenerateInput(BaseModel):
    format: str | None = None   # "modern", "pioneer" etc.
    notes: str | None = None    # 追加指示


# ── ヘルパー ─────────────────────────────────────────────────────────────────

def _definition_to_dict(d: DeckDefinition) -> dict:
    return {
        "id": d.id,
        "player_name": d.player_name,
        "deck_name": d.deck_name,
        "format": d.format,
        "threshold": d.threshold,
        "cards": [c.card_name for c in d.cards if not c.is_exclude],
        "exclude_cards": [c.card_name for c in d.cards if c.is_exclude],
    }


# ── エンドポイント ────────────────────────────────────────────────────────────

@router.get("/deck-definitions")
def list_deck_definitions(db: Session = Depends(get_db)):
    """デッキ定義一覧を返す。共通定義（player_name=NULL）を先に、次にプレイヤー別を返す。"""
    rows = (
        db.query(DeckDefinition)
        .order_by(DeckDefinition.player_name.nullsfirst(), DeckDefinition.id)
        .all()
    )
    return {"definitions": [_definition_to_dict(d) for d in rows]}


@router.post("/deck-definitions", status_code=201)
def create_deck_definition(body: DeckDefinitionInput, db: Session = Depends(get_db)):
    """デッキ定義を作成する。"""
    d = DeckDefinition(
        player_name=body.player_name or None,
        deck_name=body.deck_name,
        format=body.format or None,
        threshold=body.threshold,
    )
    db.add(d)
    db.flush()
    for card_name in body.cards:
        db.add(DeckDefinitionCard(definition_id=d.id, card_name=card_name, is_exclude=False))
    for card_name in body.exclude_cards:
        db.add(DeckDefinitionCard(definition_id=d.id, card_name=card_name, is_exclude=True))
    db.commit()
    db.refresh(d)
    return _definition_to_dict(d)


@router.put("/deck-definitions/{definition_id}")
def update_deck_definition(
    definition_id: int, body: DeckDefinitionInput, db: Session = Depends(get_db)
):
    """デッキ定義を更新する。cards は全件洗い替え。"""
    d = db.get(DeckDefinition, definition_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Definition not found")

    d.player_name = body.player_name or None
    d.deck_name = body.deck_name
    d.format = body.format or None
    d.threshold = body.threshold

    # cards 洗い替え
    for c in list(d.cards):
        db.delete(c)
    db.flush()
    for card_name in body.cards:
        db.add(DeckDefinitionCard(definition_id=d.id, card_name=card_name, is_exclude=False))
    for card_name in body.exclude_cards:
        db.add(DeckDefinitionCard(definition_id=d.id, card_name=card_name, is_exclude=True))

    db.commit()
    db.refresh(d)
    return _definition_to_dict(d)


@router.delete("/deck-definitions/{definition_id}", status_code=204)
def delete_deck_definition(definition_id: int, db: Session = Depends(get_db)):
    """デッキ定義を削除する。"""
    d = db.get(DeckDefinition, definition_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Definition not found")
    db.delete(d)
    db.commit()


@router.patch("/deck-bulk")
def deck_bulk_update(body: DeckBulkInput, db: Session = Depends(get_db)):
    """指定プレイヤーの対象マッチのデッキ名を一括上書きする。"""
    q = (
        db.query(MatchPlayer)
        .join(Match, Match.id == MatchPlayer.match_id)
        .filter(MatchPlayer.player_name == body.player_name)
        .order_by(Match.played_at.desc())
    )

    if body.last_n is not None:
        # 直近N件のマッチIDを取得
        match_ids = [
            r[0]
            for r in db.query(Match.id)
            .join(MatchPlayer, MatchPlayer.match_id == Match.id)
            .filter(MatchPlayer.player_name == body.player_name)
            .order_by(Match.played_at.desc())
            .limit(body.last_n)
            .all()
        ]
        q = q.filter(MatchPlayer.match_id.in_(match_ids))

    if body.date_from:
        dt_from = datetime.fromisoformat(body.date_from).replace(tzinfo=timezone.utc)
        q = q.filter(Match.played_at >= dt_from)

    if body.date_to:
        dt_to = datetime.fromisoformat(body.date_to).replace(tzinfo=timezone.utc) + timedelta(days=1)
        q = q.filter(Match.played_at < dt_to)

    rows = q.all()
    for mp in rows:
        mp.deck_name = body.deck_name

    db.commit()
    return {"updated": len(rows)}


# ── Claude 生成 ───────────────────────────────────────────────────────────────

_GENERATE_SYSTEM = """\
You are an expert Magic: The Gathering deck analyst. Your task is to generate deck definitions for the Scry match-tracking application.

A deck definition consists of signature cards — the key cards that identify a deck archetype.
Guidelines:
- Choose 5–12 cards that are unique identifiers for the archetype (not generic staples like Lightning Bolt alone)
- Prefer cards that appear in 3+ copies in most builds of the deck
- Threshold is the minimum number of signature cards needed to identify the deck (usually 2–3)
- Card names must be in English and match the exact official card name

Respond with a JSON object in this exact schema:
{
  "definitions": [
    {
      "deck_name": "<archetype name in English>",
      "threshold": <integer 2-4>,
      "cards": ["<card name>", ...]
    },
    ...
  ]
}

Include 5–15 of the most prominent meta decks. Do not include any text outside the JSON object.
"""


@router.post("/deck-definitions/generate")
async def generate_deck_definitions(body: DeckGenerateInput, db: Session = Depends(get_db)):
    """
    Claude API を使ってデッキ定義を自動生成する。
    設定画面で登録した Anthropic API キーが必要。
    """
    from app.routers.settings import get_api_key
    api_key = get_api_key(db)
    if not api_key:
        raise HTTPException(status_code=503, detail="Anthropic API キーが設定されていません")

    fmt_label = body.format or "any format"
    user_msg = f"Generate deck definitions for Magic: The Gathering {fmt_label} metagame."
    if body.notes:
        user_msg += f"\n\nAdditional instructions: {body.notes}"

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=_GENERATE_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
    except anthropic.AuthenticationError as e:
        raise HTTPException(status_code=503, detail=f"Invalid Anthropic API key: {e}")
    except anthropic.APIStatusError as e:
        raise HTTPException(status_code=502, detail=f"Claude API error {e.status_code}: {e.message}")
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("generate_deck_definitions failed")
        raise HTTPException(status_code=502, detail=f"Unexpected error: {type(e).__name__}: {e}")

    import json as _json
    import logging
    _log = logging.getLogger(__name__)

    block_summary = [(block.type, getattr(block, "text", "")[:80] if block.type == "text" else "") for block in response.content]
    _log.info("Claude response blocks: %s", block_summary)

    text_content = next(
        (getattr(block, "text", None) for block in response.content if block.type == "text"),
        None,
    )
    if not text_content:
        types = [block.type for block in response.content]
        raise HTTPException(status_code=502, detail=f"Claude returned no text content. Block types: {types}")

    try:
        # JSON部分を抽出（余分なテキストがある場合に備える）
        start = text_content.find("{")
        end = text_content.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found")
        data = _json.loads(text_content[start:end])
    except (ValueError, _json.JSONDecodeError) as e:
        raise HTTPException(status_code=502, detail=f"Failed to parse Claude response: {e}")

    definitions = data.get("definitions", [])
    if not isinstance(definitions, list):
        raise HTTPException(status_code=502, detail="Invalid response structure from Claude")

    return {
        "version": "1.0",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "source": "Claude",
        "format": body.format,
        "definitions": definitions,
    }


# ── JSON Import / Export ──────────────────────────────────────────────────────

SUPPORTED_VERSIONS = {"1.0"}


@router.post("/deck-definitions/import")
async def import_deck_definitions(
    file: UploadFile = File(...),
    player_name: str | None = None,       # None = 共通定義
    on_conflict: str = "skip",            # "skip" or "overwrite"
    db: Session = Depends(get_db),
):
    """
    JSON ファイルからデッキ定義を一括インポートする。

    - player_name: 指定するとプレイヤー固有定義として登録（省略で共通定義）
    - on_conflict: 同名デッキが存在する場合の挙動（skip / overwrite）
    """
    import json

    content = await file.read()
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    version = data.get("version", "")
    if version not in SUPPORTED_VERSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported schema version: {version!r}")

    definitions = data.get("definitions")
    if not isinstance(definitions, list):
        raise HTTPException(status_code=400, detail="'definitions' must be an array")

    # ファイルのトップレベル format（各定義のデフォルト）
    file_format = data.get("format")

    imported = skipped = errors = 0

    for item in definitions:
        deck_name = item.get("deck_name", "").strip()
        cards = item.get("cards", [])

        if not deck_name or not isinstance(cards, list) or len(cards) == 0:
            errors += 1
            continue

        fmt = item.get("format", file_format) or None
        threshold = item.get("threshold", 2)
        if not isinstance(threshold, int) or threshold < 1:
            threshold = 2

        card_names = [c.strip() for c in cards if isinstance(c, str) and c.strip()]
        if not card_names:
            errors += 1
            continue

        exclude_names = [
            c.strip()
            for c in item.get("exclude_cards", [])
            if isinstance(c, str) and c.strip()
        ]

        # 同名・同プレイヤー・同フォーマットの既存定義を検索
        existing = (
            db.query(DeckDefinition)
            .filter(
                DeckDefinition.deck_name == deck_name,
                DeckDefinition.player_name == player_name,
                DeckDefinition.format == fmt,
            )
            .first()
        )

        if existing:
            if on_conflict == "skip":
                skipped += 1
                continue
            else:  # overwrite
                for c in list(existing.cards):
                    db.delete(c)
                db.flush()
                existing.threshold = threshold
                for card_name in card_names:
                    db.add(DeckDefinitionCard(definition_id=existing.id, card_name=card_name, is_exclude=False))
                for card_name in exclude_names:
                    db.add(DeckDefinitionCard(definition_id=existing.id, card_name=card_name, is_exclude=True))
                imported += 1
        else:
            d = DeckDefinition(
                player_name=player_name,
                deck_name=deck_name,
                format=fmt,
                threshold=threshold,
            )
            db.add(d)
            db.flush()
            for card_name in card_names:
                db.add(DeckDefinitionCard(definition_id=d.id, card_name=card_name, is_exclude=False))
            for card_name in exclude_names:
                db.add(DeckDefinitionCard(definition_id=d.id, card_name=card_name, is_exclude=True))
            imported += 1

    db.commit()
    return {"imported": imported, "skipped": skipped, "errors": errors}


@router.post("/decks/apply-definitions")
def apply_definitions(
    overwrite: bool = False,
    target_deck: str | None = None,
    target_format: str | None = None,
    db: Session = Depends(get_db),
):
    """
    デッキ定義を既存試合に後付け適用する。

    - overwrite=false: deck_name が NULL の MatchPlayer のみ対象
    - overwrite=true : 全 MatchPlayer を対象（既存のデッキ名も上書き）
    - target_deck 指定時: そのデッキ名の MatchPlayer のみ対象（常に上書き）
    - target_format 指定時: そのフォーマットの試合のみ対象
    """
    from sqlalchemy.orm import selectinload
    from models.core import Game, Action
    from services.import_service import ImportService

    svc = ImportService(db)

    q = db.query(MatchPlayer).options(
        selectinload(MatchPlayer.match)
        .selectinload(Match.games)
        .selectinload(Game.actions)
    )

    if target_deck is not None:
        # 指定デッキ名の試合のみ対象（常に上書き）
        q = q.filter(MatchPlayer.deck_name == target_deck)
    elif not overwrite:
        q = q.filter(MatchPlayer.deck_name.is_(None))

    if target_format is not None:
        q = q.join(Match, Match.id == MatchPlayer.match_id).filter(Match.format == target_format)

    match_players = q.all()

    updated = 0
    for mp in match_players:
        if mp.match is None:
            continue

        # 該当プレイヤーの play/cast カードのみ収集
        used_cards: set[str] = set()
        for game in mp.match.games:
            for action in game.actions:
                if (
                    action.action_type in ("play", "cast")
                    and action.card_name
                    and action.player_name == mp.player_name
                ):
                    used_cards.add(action.card_name)

        detected = svc._detect_deck(mp.player_name, used_cards, mp.match.format)
        if detected is not None and detected != mp.deck_name:
            mp.deck_name = detected
            updated += 1

    db.commit()
    return {"updated": updated, "skipped": len(match_players) - updated}


@router.get("/deck-definitions/export")
def export_deck_definitions(db: Session = Depends(get_db)):
    """現在のデッキ定義を JSON 形式でエクスポートする。"""
    rows = (
        db.query(DeckDefinition)
        .order_by(DeckDefinition.player_name.nullsfirst(), DeckDefinition.id)
        .all()
    )

    definitions = []
    for d in rows:
        entry: dict = {
            "deck_name": d.deck_name,
            "threshold": d.threshold,
            "cards": [c.card_name for c in d.cards if not c.is_exclude],
        }
        if d.format:
            entry["format"] = d.format
        exclude = [c.card_name for c in d.cards if c.is_exclude]
        if exclude:
            entry["exclude_cards"] = exclude
        definitions.append(entry)

    payload = {
        "version": "1.0",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "source": "Scry",
        "format": None,
        "definitions": definitions,
    }

    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": "attachment; filename=deck_definitions.json"},
    )
