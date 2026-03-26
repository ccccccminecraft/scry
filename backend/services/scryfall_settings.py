from __future__ import annotations

from sqlalchemy.orm import Session

from models.cache import Setting


def is_scryfall_enabled(db: Session) -> bool:
    """DB の scryfall_enabled 設定を返す。レコードがなければデフォルト False。"""
    s = db.get(Setting, "scryfall_enabled")
    return s.value == "true" if s else False
