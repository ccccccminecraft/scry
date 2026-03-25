import asyncio
import json
import os
import sys
from datetime import datetime, timezone
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


def _extract_card_cache_fields(data: dict) -> dict:
    """Scryfall レスポンスから card_cache 保存用フィールドを抽出する。"""
    is_dfc = "card_faces" in data

    # mana_cost: 空文字列は NULL に正規化
    mana_cost = data.get("mana_cost") or None

    # card_faces の抽出（DFC / Room / Battle）
    card_faces_json = None
    if is_dfc:
        faces = []
        for face in data.get("card_faces", []):
            face_data: dict = {
                "name": face.get("name", ""),
                "mana_cost": face.get("mana_cost") or None,
                "type_line": face.get("type_line", ""),
                "oracle_text": face.get("oracle_text"),
            }
            if face.get("power") is not None:
                face_data["power"] = face["power"]
            if face.get("toughness") is not None:
                face_data["toughness"] = face["toughness"]
            if face.get("defense") is not None:
                face_data["defense"] = face["defense"]
            faces.append(face_data)
        card_faces_json = json.dumps(faces, ensure_ascii=False)

    loyalty = data.get("loyalty")

    return {
        "name": data.get("name", ""),
        "mana_cost": mana_cost,
        "cmc": float(data.get("cmc", 0.0)),
        "type_line": data.get("type_line", ""),
        "oracle_text": data.get("oracle_text") if not is_dfc else None,
        "power": data.get("power"),
        "toughness": data.get("toughness"),
        "loyalty": str(loyalty) if loyalty is not None else None,
        "colors": json.dumps(data.get("colors", []), ensure_ascii=False),
        "keywords": json.dumps(data.get("keywords", []), ensure_ascii=False),
        "produced_mana": json.dumps(data["produced_mana"], ensure_ascii=False) if data.get("produced_mana") else None,
        "card_faces": card_faces_json,
    }


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
            "_raw": data,
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
            "_raw": data,
        }


async def fill_scryfall_ids(card_ids: list[int]) -> None:
    """バックグラウンドタスク: scryfall_id が未取得のカードを補完し、card_cache も更新する。"""
    from models.decklist import Card
    from models.cache import CardCache
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
                    scryfall_id = result["scryfall_id"]
                    existing = (
                        db.query(Card)
                        .filter(Card.scryfall_id == scryfall_id)
                        .first()
                    )
                    if existing is None:
                        card.scryfall_id = scryfall_id
                        card.image_url = result["image_url"]
                        db.commit()
                    elif existing.id != card.id:
                        from models.decklist import DeckVersionCard
                        db.query(DeckVersionCard).filter(
                            DeckVersionCard.card_id == card.id
                        ).update({"card_id": existing.id})
                        db.delete(card)
                        db.commit()

                    # card_cache への保存（未登録の場合のみ）
                    raw = result.get("_raw")
                    if raw and not db.get(CardCache, scryfall_id):
                        fields = _extract_card_cache_fields(raw)
                        db.add(CardCache(
                            scryfall_id=scryfall_id,
                            fetched_at=datetime.now(timezone.utc),
                            **fields,
                        ))
                        db.commit()

            except Exception:
                pass
            await asyncio.sleep(0.05)
    finally:
        db.close()
