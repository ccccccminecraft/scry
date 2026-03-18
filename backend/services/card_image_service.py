import asyncio
import os
import sys
from pathlib import Path

import httpx

SCRYFALL_API = "https://api.scryfall.com"
SCRYFALL_CDN = "https://cards.scryfall.io"


def get_image_cache_dir() -> Path:
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("sqlite:///"):
        db_path = db_url[len("sqlite:///"):]
        return Path(db_path).parent / "image_cache"
    if sys.platform == "win32":
        base = Path(os.environ["APPDATA"]) / "Scry"
    else:
        base = Path("/database")
    return base / "image_cache"


async def get_card_image(scryfall_id: str, size: str = "small") -> Path:
    cache_dir = get_image_cache_dir() / size
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{scryfall_id}.jpg"

    if cache_path.exists():
        return cache_path

    url = f"{SCRYFALL_CDN}/{size}/front/{scryfall_id[0]}/{scryfall_id[1]}/{scryfall_id}.jpg"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        cache_path.write_bytes(response.content)

    return cache_path


async def _resolve_by_name(card_name: str) -> dict | None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{SCRYFALL_API}/cards/named",
            params={"exact": card_name},
        )
        if response.status_code != 200:
            return None
        data = response.json()
        image_uris = data.get("image_uris") or {}
        if not image_uris and "card_faces" in data:
            image_uris = (data["card_faces"][0].get("image_uris") or {})
        return {
            "scryfall_id": data.get("id"),
            "image_url": image_uris.get("normal"),
        }


async def _resolve_by_mtgo_id(mtgo_id: int) -> dict | None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"{SCRYFALL_API}/cards/mtgo/{mtgo_id}")
        if response.status_code != 200:
            return None
        data = response.json()
        image_uris = data.get("image_uris") or {}
        if not image_uris and "card_faces" in data:
            image_uris = (data["card_faces"][0].get("image_uris") or {})
        return {
            "scryfall_id": data.get("id"),
            "image_url": image_uris.get("normal"),
        }


async def fill_scryfall_ids(card_ids: list[int]) -> None:
    """バックグラウンドタスク: scryfall_id が未取得のカードを補完する。"""
    from models.decklist import Card
    from database import SessionLocal

    db = SessionLocal()
    try:
        cards = (
            db.query(Card)
            .filter(Card.id.in_(card_ids), Card.scryfall_id.is_(None))
            .all()
        )
        for card in cards:
            try:
                if card.mtgo_id is not None:
                    result = await _resolve_by_mtgo_id(card.mtgo_id)
                else:
                    result = await _resolve_by_name(card.name)

                if result and result.get("scryfall_id"):
                    existing = (
                        db.query(Card)
                        .filter(Card.scryfall_id == result["scryfall_id"])
                        .first()
                    )
                    if existing is None:
                        card.scryfall_id = result["scryfall_id"]
                        card.image_url = result["image_url"]
                        db.commit()
                    elif existing.id != card.id:
                        # 同一 scryfall_id を持つ Card が既に存在する（同カードの別印刷版など）
                        # DeckVersionCard の参照を既存カードに付け替えてからこのカード行を削除
                        from models.decklist import DeckVersionCard
                        db.query(DeckVersionCard).filter(
                            DeckVersionCard.card_id == card.id
                        ).update({"card_id": existing.id})
                        db.delete(card)
                        db.commit()
            except Exception:
                pass
            await asyncio.sleep(0.05)
    finally:
        db.close()
