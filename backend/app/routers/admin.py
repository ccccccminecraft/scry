"""
管理 API

GET  /api/admin/mtga-cards-folder      - MTGA カードDB フォルダパス取得
PUT  /api/admin/mtga-cards-folder      - MTGA カードDB フォルダパス設定
POST /api/admin/sync-mtga-cards        - MTGA CardDatabase から mtga_cards を更新
GET  /api/admin/sync-mtga-cards/status - 最終同期日時を返す
"""
from __future__ import annotations

import logging
import re
import sqlite3 as _sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from models.cache import Setting

logger = logging.getLogger(__name__)
router = APIRouter()

_MTGA_FOLDER_KEY = "mtga_cards_folder"
_MTGA_SYNC_KEY   = "mtga_cards_updated_at"

_TAG_RE = re.compile(r"<[^>]+>")


# ─── MTGA CardDatabase 同期 ───────────────────────────────────────────────────

class FolderInput(BaseModel):
    folder: str


@router.get("/admin/mtga-cards-folder")
def get_mtga_folder(db: Session = Depends(get_db)):
    """MTGA カードDB フォルダパスを返す。"""
    s = db.get(Setting, _MTGA_FOLDER_KEY)
    return {"folder": s.value if s else None}


@router.put("/admin/mtga-cards-folder")
def set_mtga_folder(body: FolderInput, db: Session = Depends(get_db)):
    """MTGA カードDB フォルダパスを設定する。"""
    s = db.get(Setting, _MTGA_FOLDER_KEY)
    if s:
        s.value = body.folder
    else:
        db.add(Setting(key=_MTGA_FOLDER_KEY, value=body.folder))
    db.commit()
    return {"ok": True}


@router.get("/admin/sync-mtga-cards/status")
def get_mtga_sync_status(db: Session = Depends(get_db)):
    """最終 MTGA CardDatabase 同期日時と設定フォルダを返す。"""
    folder_s = db.get(Setting, _MTGA_FOLDER_KEY)
    synced_s = db.get(Setting, _MTGA_SYNC_KEY)
    return {
        "folder": folder_s.value if folder_s else None,
        "last_synced_at": synced_s.value if synced_s else None,
    }


@router.post("/admin/sync-mtga-cards")
def sync_mtga_cards(db: Session = Depends(get_db)):
    """
    設定済みフォルダ内の Raw_CardDatabase_*.mtga を読み込み、
    mtga_cards テーブルを更新する。

    MTGA 公式データを使用するため Scryfall で未収録の新セットカードも解決できる。
    """
    folder_s = db.get(Setting, _MTGA_FOLDER_KEY)
    if not folder_s or not folder_s.value:
        raise HTTPException(status_code=400, detail="MTGA カードDB フォルダが設定されていません")

    folder = Path(folder_s.value)
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"フォルダが見つかりません: {folder_s.value}")

    # Raw_CardDatabase_*.mtga を検索（複数ある場合は最新のものを使用）
    candidates = sorted(
        folder.glob("Raw_CardDatabase_*.mtga"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise HTTPException(status_code=404, detail="Raw_CardDatabase_*.mtga が見つかりません")

    db_path = candidates[0]
    logger.info("MTGA CardDatabase sync: %s", db_path)

    try:
        count = _sync_from_mtga_db(db_path, db)
        db.commit()
        return {"synced": count, "source": db_path.name}
    except Exception as e:
        db.rollback()
        logger.error("MTGA CardDatabase sync failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


def _sync_from_mtga_db(db_path: Path, db: Session) -> int:
    """
    MTGA の Raw_CardDatabase SQLite から GrpId → カード名を抽出して mtga_cards に upsert する。

    - Formatted=1 の Localizations_enUS を使用（新旧セット両対応）
    - <nobr> 等の HTML タグを除去して純粋なカード名にする
    - IsPrimaryCard=1 のみ対象（トークン等の派生カードを除外）
    """
    conn = _sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            """
            SELECT c.GrpId, l.Loc, c.ExpansionCode
            FROM Cards c
            JOIN Localizations_enUS l ON c.TitleId = l.LocId
            WHERE l.Formatted = 1
              AND c.IsPrimaryCard = 1
            """
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    now = datetime.now(timezone.utc).isoformat()
    arena_map: dict[int, tuple[str, str]] = {}  # arena_id → (card_name, expansion_code)
    for grp_id, raw_name, expansion_code in rows:
        name = _TAG_RE.sub("", raw_name).strip()
        if name:
            arena_map[grp_id] = (name, expansion_code or "")

    upsert_rows = [
        {"arena_id": aid, "card_name": name, "expansion_code": exp, "fetched_at": now}
        for aid, (name, exp) in arena_map.items()
    ]
    db.execute(
        text(
            "INSERT OR REPLACE INTO mtga_cards (arena_id, card_name, expansion_code, fetched_at)"
            " VALUES (:arena_id, :card_name, :expansion_code, :fetched_at)"
        ),
        upsert_rows,
    )

    # 同期日時を settings に保存
    setting = db.get(Setting, _MTGA_SYNC_KEY)
    if setting:
        setting.value = now
    else:
        db.add(Setting(key=_MTGA_SYNC_KEY, value=now))
    db.flush()

    logger.info("MTGA CardDatabase sync completed: %d cards upserted", len(arena_map))
    return len(arena_map)
