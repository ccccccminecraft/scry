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
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from models.cache import Setting, MtgaCounterType

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
async def sync_mtga_cards(file: UploadFile, db: Session = Depends(get_db)):
    """
    Electron が読んだ MTGA CardDatabase のファイル内容を受け取り、mtga_cards テーブルを更新する。
    ファイルパスの共有ではなくアップロード方式にすることで、Windows のパス解決の差異を回避する。
    """
    content = await file.read()
    logger.info(
        "MTGA CardDatabase sync: %d bytes received, first 16: %s",
        len(content), content[:16].hex() if content else "empty",
    )
    _SQLITE_MAGIC = b"SQLite format 3\x00"
    if len(content) < 16 or content[:16] != _SQLITE_MAGIC:
        raise HTTPException(
            status_code=400,
            detail=f"受信データが SQLite ではありません ({len(content)} バイト, 先頭: {content[:16].hex() if content else 'empty'})",
        )
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mtga') as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        card_count, counter_count = _sync_from_mtga_db(tmp_path, db)
        db.commit()
        return {"synced": card_count, "counters_synced": counter_count, "source": "upload"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("MTGA CardDatabase sync failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def _sync_from_mtga_db(db_path: Path, db: Session) -> tuple[int, int]:
    """
    MTGA の Raw_CardDatabase SQLite からカード名とカウンター種別名を抽出して upsert する。

    カード名:
    - Formatted=1 の Localizations_enUS を使用（新旧セット両対応）
    - <nobr> 等の HTML タグを除去して純粋なカード名にする
    - IsPrimaryCard=1 のみ対象（トークン等の派生カードを除外）

    カウンター種別:
    - Enums テーブルの Type='CounterType' を Localizations_enUS と結合して取得
    - 同様に Formatted=1 + タグ除去で正規化
    """
    conn = _sqlite3.connect(str(db_path))
    try:
        card_rows = conn.execute(
            """
            SELECT c.GrpId, l.Loc, c.ExpansionCode
            FROM Cards c
            JOIN Localizations_enUS l ON c.TitleId = l.LocId
            WHERE l.Formatted = 1
              AND c.IsPrimaryCard = 1
            """
        ).fetchall()

        counter_rows = conn.execute(
            """
            SELECT e.Value, l.Loc
            FROM Enums e
            JOIN Localizations_enUS l ON e.LocId = l.LocId
            WHERE e.Type = 'CounterType'
              AND l.Formatted = 1
            """
        ).fetchall()
    finally:
        conn.close()

    now = datetime.now(timezone.utc).isoformat()

    # ── カード名 upsert ──────────────────────────────────────────────────────────
    arena_map: dict[int, tuple[str, str]] = {}  # arena_id → (card_name, expansion_code)
    for grp_id, raw_name, expansion_code in card_rows:
        name = _TAG_RE.sub("", raw_name).strip()
        if name:
            arena_map[grp_id] = (name, expansion_code or "")

    db.execute(
        text(
            "INSERT OR REPLACE INTO mtga_cards (arena_id, card_name, expansion_code, fetched_at)"
            " VALUES (:arena_id, :card_name, :expansion_code, :fetched_at)"
        ),
        [
            {"arena_id": aid, "card_name": name, "expansion_code": exp, "fetched_at": now}
            for aid, (name, exp) in arena_map.items()
        ],
    )

    # ── カウンター種別 upsert ────────────────────────────────────────────────────
    counter_map: dict[int, str] = {}  # counter_type_id → name
    for counter_type_id, raw_name in counter_rows:
        name = _TAG_RE.sub("", raw_name).strip()
        if name and counter_type_id not in counter_map:  # 重複は先勝ち
            counter_map[counter_type_id] = name

    db.execute(
        text(
            "INSERT OR REPLACE INTO mtga_counter_types (counter_type_id, name, fetched_at)"
            " VALUES (:counter_type_id, :name, :fetched_at)"
        ),
        [
            {"counter_type_id": cid, "name": name, "fetched_at": now}
            for cid, name in counter_map.items()
        ],
    )

    # 同期日時を settings に保存
    setting = db.get(Setting, _MTGA_SYNC_KEY)
    if setting:
        setting.value = now
    else:
        db.add(Setting(key=_MTGA_SYNC_KEY, value=now))
    db.flush()

    logger.info(
        "MTGA CardDatabase sync completed: %d cards, %d counter types upserted",
        len(arena_map), len(counter_map),
    )
    return len(arena_map), len(counter_map)
