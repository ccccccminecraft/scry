import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.decklist import Card, Deck, DeckVersion, DeckVersionCard
from services.card_image_service import fill_scryfall_ids, get_card_image

router = APIRouter()

# ---------------------------------------------------------------------------
# パーサー
# ---------------------------------------------------------------------------

_SIDEBOARD_MARKER = re.compile(r'^(sideboard:?|sb:|サイドボード)$', re.IGNORECASE)
_CARD_LINE = re.compile(r'^(\d+)x?\s+(.+)$')
_SB_PREFIX = re.compile(r'^SB:\s*(\d+)x?\s+(.+)$', re.IGNORECASE)


def _parse_text(text: str) -> list[dict]:
    results = []
    sideboard = False
    for line_num, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('//'):
            continue
        # SB: 4 Card Name プレフィックス形式
        m = _SB_PREFIX.match(line)
        if m:
            results.append({
                "card_name": m.group(2).strip(),
                "quantity": int(m.group(1)),
                "is_sideboard": True,
                "mtgo_id": None,
            })
            continue
        # セクション区切り
        if _SIDEBOARD_MARKER.match(line):
            sideboard = True
            continue
        # 通常カード行
        m = _CARD_LINE.match(line)
        if m:
            name = m.group(2).strip()
            if not name:
                raise ValueError(f"Parse error at line {line_num}: empty card name")
            results.append({
                "card_name": name,
                "quantity": int(m.group(1)),
                "is_sideboard": sideboard,
                "mtgo_id": None,
            })
        else:
            raise ValueError(f"Parse error at line {line_num}: {line!r}")
    return results


def _parse_dek(content: bytes) -> list[dict]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML: {e}")
    cards = root.findall("Cards")
    if not cards:
        raise ValueError("No <Cards> elements found in .dek file")
    results = []
    for elem in cards:
        name = elem.get("Name")
        quantity = elem.get("Quantity")
        if not name or quantity is None:
            continue
        sideboard = elem.get("Sideboard", "false").lower() == "true"
        cat_id = elem.get("CatID")
        results.append({
            "card_name": name.strip(),
            "quantity": int(quantity),
            "is_sideboard": sideboard,
            "mtgo_id": int(cat_id) if cat_id else None,
        })
    return results


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _get_or_create_card(db: Session, card_name: str, mtgo_id: int | None) -> Card:
    """cards テーブルからカードを取得または新規作成する。"""
    if mtgo_id is not None:
        card = db.query(Card).filter(Card.mtgo_id == mtgo_id).first()
        if card:
            return card
    else:
        card = db.query(Card).filter(Card.name == card_name, Card.mtgo_id.is_(None)).first()
        if card:
            return card
    card = Card(name=card_name, mtgo_id=mtgo_id)
    db.add(card)
    db.flush()
    return card


def _version_to_summary(v: DeckVersion) -> dict:
    main_count = sum(c.quantity for c in v.cards if not c.is_sideboard)
    side_count = sum(c.quantity for c in v.cards if c.is_sideboard)
    return {
        "id": v.id,
        "version_number": v.version_number,
        "memo": v.memo,
        "registered_at": v.registered_at.isoformat(),
        "main_count": main_count,
        "side_count": side_count,
        "is_archived": bool(v.is_archived),
    }


def _version_to_detail(v: DeckVersion) -> dict:
    def entry(vc: DeckVersionCard) -> dict:
        return {
            "card_name": vc.card.name,
            "quantity": vc.quantity,
            "scryfall_id": vc.card.scryfall_id,
        }
    main = [entry(vc) for vc in v.cards if not vc.is_sideboard]
    sideboard = [entry(vc) for vc in v.cards if vc.is_sideboard]
    return {**_version_to_summary(v), "main": main, "sideboard": sideboard}


def _save_version(db: Session, deck_id: int, memo: str, parsed: list[dict]) -> DeckVersion:
    """パース済みカードリストからバージョンを作成する。"""
    main_cards = [p for p in parsed if not p["is_sideboard"]]
    if not main_cards:
        raise HTTPException(status_code=400, detail="Main deck is empty")

    max_ver = db.query(func.max(DeckVersion.version_number)).filter(
        DeckVersion.deck_id == deck_id
    ).scalar() or 0

    version = DeckVersion(
        deck_id=deck_id,
        version_number=max_ver + 1,
        memo=memo or None,
        registered_at=datetime.now(),
    )
    db.add(version)
    db.flush()

    for p in parsed:
        card = _get_or_create_card(db, p["card_name"], p["mtgo_id"])
        db.add(DeckVersionCard(
            deck_version_id=version.id,
            card_id=card.id,
            quantity=p["quantity"],
            is_sideboard=p["is_sideboard"],
        ))
    db.commit()
    db.refresh(version)
    return version


# ---------------------------------------------------------------------------
# デッキ CRUD
# ---------------------------------------------------------------------------

class DeckInput(BaseModel):
    name: str
    format: Optional[str] = None


def _deck_to_dict(deck: Deck) -> dict:
    active_versions = [v for v in deck.versions if not v.is_archived]
    latest = None
    if active_versions:
        v = max(active_versions, key=lambda x: x.version_number)
        latest = {
            "id": v.id,
            "version_number": v.version_number,
            "memo": v.memo,
            "registered_at": v.registered_at.isoformat(),
        }
    return {
        "id": deck.id,
        "name": deck.name,
        "format": deck.format,
        "created_at": deck.created_at.isoformat(),
        "is_archived": bool(deck.is_archived),
        "latest_version": latest,
    }


@router.get("/decklist/decks")
def list_decks(
    archived: bool = Query(default=False),
    format: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(Deck).filter(Deck.is_archived == archived)
    if format:
        q = q.filter(Deck.format == format)
    decks = q.order_by(Deck.created_at.desc()).all()
    return [_deck_to_dict(d) for d in decks]


@router.post("/decklist/decks")
def create_deck(body: DeckInput, db: Session = Depends(get_db)):
    deck = Deck(name=body.name.strip(), format=body.format or None, created_at=datetime.now())
    db.add(deck)
    db.commit()
    db.refresh(deck)
    return _deck_to_dict(deck)


@router.put("/decklist/decks/{deck_id}")
def update_deck(deck_id: int, body: DeckInput, db: Session = Depends(get_db)):
    deck = db.get(Deck, deck_id)
    if not deck:
        raise HTTPException(status_code=404)
    deck.name = body.name.strip()
    deck.format = body.format or None
    db.commit()
    db.refresh(deck)
    return _deck_to_dict(deck)


@router.delete("/decklist/decks/{deck_id}")
def delete_deck(deck_id: int, db: Session = Depends(get_db)):
    deck = db.get(Deck, deck_id)
    if not deck:
        raise HTTPException(status_code=404)
    db.delete(deck)
    db.commit()
    return {"ok": True}


@router.post("/decklist/decks/{deck_id}/archive")
def archive_deck(deck_id: int, db: Session = Depends(get_db)):
    deck = db.get(Deck, deck_id)
    if not deck:
        raise HTTPException(status_code=404)
    deck.is_archived = True
    db.commit()
    return _deck_to_dict(deck)


@router.post("/decklist/decks/{deck_id}/unarchive")
def unarchive_deck(deck_id: int, db: Session = Depends(get_db)):
    deck = db.get(Deck, deck_id)
    if not deck:
        raise HTTPException(status_code=404)
    deck.is_archived = False
    db.commit()
    return _deck_to_dict(deck)


# ---------------------------------------------------------------------------
# バージョン CRUD
# ---------------------------------------------------------------------------

@router.get("/decklist/decks/{deck_id}/versions")
def list_versions(deck_id: int, include_archived: bool = Query(default=True), db: Session = Depends(get_db)):
    if not db.get(Deck, deck_id):
        raise HTTPException(status_code=404)
    q = db.query(DeckVersion).filter(DeckVersion.deck_id == deck_id)
    if not include_archived:
        q = q.filter(DeckVersion.is_archived == False)
    versions = q.order_by(DeckVersion.version_number.desc()).all()
    return [_version_to_summary(v) for v in versions]


@router.get("/decklist/decks/{deck_id}/versions/{version_id}")
def get_version(deck_id: int, version_id: int, db: Session = Depends(get_db)):
    v = db.query(DeckVersion).filter(
        DeckVersion.id == version_id, DeckVersion.deck_id == deck_id
    ).first()
    if not v:
        raise HTTPException(status_code=404)
    return _version_to_detail(v)


class VersionTextInput(BaseModel):
    memo: Optional[str] = None
    text: str


@router.post("/decklist/decks/{deck_id}/versions")
def create_version_text(
    deck_id: int,
    body: VersionTextInput,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if not db.get(Deck, deck_id):
        raise HTTPException(status_code=404)
    try:
        parsed = _parse_text(body.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    version = _save_version(db, deck_id, body.memo or "", parsed)
    card_ids = [vc.card_id for vc in version.cards]
    background_tasks.add_task(fill_scryfall_ids, card_ids)
    return _version_to_detail(version)


@router.post("/decklist/decks/{deck_id}/versions/import")
async def create_version_dek(
    deck_id: int,
    background_tasks: BackgroundTasks,
    memo: str = Form(default=""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not db.get(Deck, deck_id):
        raise HTTPException(status_code=404)
    content = await file.read()
    try:
        parsed = _parse_dek(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    version = _save_version(db, deck_id, memo, parsed)
    card_ids = [vc.card_id for vc in version.cards]
    background_tasks.add_task(fill_scryfall_ids, card_ids)
    return _version_to_detail(version)


@router.put("/decklist/decks/{deck_id}/versions/{version_id}")
def update_version(
    deck_id: int,
    version_id: int,
    body: VersionTextInput,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    v = db.query(DeckVersion).filter(
        DeckVersion.id == version_id, DeckVersion.deck_id == deck_id
    ).first()
    if not v:
        raise HTTPException(status_code=404)
    try:
        parsed = _parse_text(body.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    main_cards = [p for p in parsed if not p["is_sideboard"]]
    if not main_cards:
        raise HTTPException(status_code=400, detail="Main deck is empty")

    # 既存カードリストを削除して再登録
    for vc in list(v.cards):
        db.delete(vc)
    db.flush()

    v.memo = body.memo or None
    for p in parsed:
        card = _get_or_create_card(db, p["card_name"], p["mtgo_id"])
        db.add(DeckVersionCard(
            deck_version_id=v.id,
            card_id=card.id,
            quantity=p["quantity"],
            is_sideboard=p["is_sideboard"],
        ))
    db.commit()
    db.refresh(v)

    card_ids = [vc.card_id for vc in v.cards]
    background_tasks.add_task(fill_scryfall_ids, card_ids)
    return _version_to_detail(v)


@router.delete("/decklist/decks/{deck_id}/versions/{version_id}")
def delete_version(deck_id: int, version_id: int, db: Session = Depends(get_db)):
    v = db.query(DeckVersion).filter(
        DeckVersion.id == version_id, DeckVersion.deck_id == deck_id
    ).first()
    if not v:
        raise HTTPException(status_code=404)
    db.delete(v)
    db.commit()
    return {"ok": True}


@router.post("/decklist/decks/{deck_id}/versions/{version_id}/archive")
def archive_version(deck_id: int, version_id: int, db: Session = Depends(get_db)):
    v = db.query(DeckVersion).filter(
        DeckVersion.id == version_id, DeckVersion.deck_id == deck_id
    ).first()
    if not v:
        raise HTTPException(status_code=404)
    v.is_archived = True
    db.commit()
    return _version_to_summary(v)


@router.post("/decklist/decks/{deck_id}/versions/{version_id}/unarchive")
def unarchive_version(deck_id: int, version_id: int, db: Session = Depends(get_db)):
    v = db.query(DeckVersion).filter(
        DeckVersion.id == version_id, DeckVersion.deck_id == deck_id
    ).first()
    if not v:
        raise HTTPException(status_code=404)
    v.is_archived = False
    db.commit()
    return _version_to_summary(v)


# ---------------------------------------------------------------------------
# カード画像
# ---------------------------------------------------------------------------

@router.get("/cards/{scryfall_id}/image")
async def get_image(scryfall_id: str, size: str = "small"):
    if size not in ("small", "normal"):
        size = "small"
    try:
        path = await get_card_image(scryfall_id, size)
        return FileResponse(str(path), media_type="image/jpeg")
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch image from Scryfall")
