"""
管理 API

POST /api/admin/sync-card-names        - Scryfall Bulk Data を同期して mtga_cards を更新
GET  /api/admin/sync-card-names/status - 最終同期日時を返す
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.cache import Setting
from services.scryfall_client import ScryfallClient

logger = logging.getLogger(__name__)
router = APIRouter()

_BULK_SYNC_KEY = "scryfall_bulk_updated_at"


@router.get("/admin/sync-card-names/status")
def get_sync_status(db: Session = Depends(get_db)):
    """最終 Scryfall Bulk Data 同期日時を返す。"""
    s = db.get(Setting, _BULK_SYNC_KEY)
    return {"last_synced_at": s.value if s else None}


@router.post("/admin/sync-card-names")
def sync_card_names(db: Session = Depends(get_db)):
    """
    Scryfall Bulk Data（default_cards）を同期して mtga_cards テーブルを更新する。

    完了まで数十秒かかる場合がある（~100MB ダウンロード）。
    """
    try:
        client = ScryfallClient(db)
        count = client.sync_bulk_data()
        db.commit()
        return {"synced": count}
    except Exception as e:
        logger.error("Scryfall bulk sync failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
