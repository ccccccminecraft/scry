"""
GET /api/import/auto-import/status - スケジューラー状態取得
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.cache import Setting
from services.auto_import_service import DEFAULT_INTERVAL_SEC

router = APIRouter()


def _get(db: Session, key: str) -> str | None:
    s = db.get(Setting, key)
    return s.value if s else None


@router.get("/import/auto-import/status")
def get_auto_import_status(db: Session = Depends(get_db)):
    """スケジューラーの有効状態・最終実行情報を返す。"""
    enabled_val = _get(db, "auto_import_enabled")
    interval_val = _get(db, "auto_import_interval_sec")
    last_run = _get(db, "auto_import_last_run_at")
    last_result_raw = _get(db, "auto_import_last_result")

    try:
        interval = max(10, int(interval_val)) if interval_val else DEFAULT_INTERVAL_SEC
    except ValueError:
        interval = DEFAULT_INTERVAL_SEC

    last_result = None
    if last_result_raw:
        try:
            last_result = json.loads(last_result_raw)
        except Exception:
            pass

    return {
        "enabled": enabled_val == "true",
        "interval_sec": interval,
        "last_run_at": last_run,
        "last_result": last_result,
    }
