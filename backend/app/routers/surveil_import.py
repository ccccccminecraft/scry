"""
Surveil JSON (MTGA) インポート API

POST /api/import/surveil             - JSON ファイルのアップロードインポート
GET  /api/import/surveil/folder      - 監視フォルダの取得
PUT  /api/import/surveil/folder      - 監視フォルダの設定
GET  /api/import/surveil/pending     - 未インポートファイル一覧
POST /api/import/surveil/scan        - pending を一括インポート
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.cache import Setting
from models.core import Match
from services.import_service import SurveilImportService

logger = logging.getLogger(__name__)
router = APIRouter()

_FOLDER_KEY = "surveil_folder"


# ─── フォルダ設定 ─────────────────────────────────────────────────────────────

@router.get("/import/surveil/folder")
def get_surveil_folder(db: Session = Depends(get_db)):
    """監視フォルダの設定値を返す。"""
    s = db.get(Setting, _FOLDER_KEY)
    return {"folder": s.value if s else None}


class FolderInput(BaseModel):
    folder: str


@router.put("/import/surveil/folder")
def set_surveil_folder(body: FolderInput, db: Session = Depends(get_db)):
    """監視フォルダを設定する。"""
    s = db.get(Setting, _FOLDER_KEY)
    if s:
        s.value = body.folder
    else:
        db.add(Setting(key=_FOLDER_KEY, value=body.folder))
    db.commit()
    return {"ok": True}


@router.delete("/import/surveil/folder", status_code=204)
def clear_surveil_folder(db: Session = Depends(get_db)):
    """監視フォルダの設定を解除する。"""
    s = db.get(Setting, _FOLDER_KEY)
    if s:
        db.delete(s)
        db.commit()


# ─── 取り込み済み ID 一覧 ──────────────────────────────────────────────────────

@router.get("/import/surveil/imported-ids")
def get_imported_ids(db: Session = Depends(get_db)):
    """DB に登録済みの MTGA match_id セットを返す（フロントエンド側 pending 判定用）。"""
    ids = [row[0] for row in db.query(Match.id).filter(Match.source == "mtga").all()]
    return {"ids": ids}


# ─── pending 一覧 ─────────────────────────────────────────────────────────────

@router.get("/import/surveil/pending")
def get_pending(db: Session = Depends(get_db)):
    """監視フォルダ内の未インポート JSON ファイル一覧を返す。"""
    s = db.get(Setting, _FOLDER_KEY)
    if not s or not s.value:
        raise HTTPException(status_code=400, detail="Surveil folder is not configured")

    folder = Path(s.value)
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"Directory not found: {s.value}")

    # DB に存在する match_id セット
    existing_ids: set[str] = {
        row[0] for row in db.query(Match.id).filter(Match.source == "mtga").all()
    }

    pending = []
    for p in sorted(folder.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        match_id = p.stem
        if match_id not in existing_ids:
            stat = p.stat()
            pending.append({
                "filename": p.name,
                "match_id": match_id,
                "mtime": stat.st_mtime,
                "size": stat.st_size,
            })

    return {"folder": s.value, "pending": pending, "total": len(pending)}


# ─── 一括インポート ───────────────────────────────────────────────────────────

@router.post("/import/surveil/scan")
def scan_and_import(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """監視フォルダの pending ファイルを全件インポートする。"""
    s = db.get(Setting, _FOLDER_KEY)
    if not s or not s.value:
        raise HTTPException(status_code=400, detail="Surveil folder is not configured")

    folder = Path(s.value)
    if not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"Directory not found: {s.value}")

    existing_ids: set[str] = {
        row[0] for row in db.query(Match.id).filter(Match.source == "mtga").all()
    }

    targets = [
        p for p in folder.glob("*.json")
        if p.stem not in existing_ids
    ]

    return _run_batch(targets, db, background_tasks)


# ─── 単体アップロード ─────────────────────────────────────────────────────────

@router.post("/import/surveil")
async def import_surveil_file(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Surveil JSON ファイルを1件アップロードしてインポートする。

    - status="imported" / "skipped" → 200
    - status="error" → 400
    """
    raw = await file.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    service = SurveilImportService(db)
    result = service.import_one(data, file.filename or "", background_tasks)

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["reason"] or "Import failed")

    return result


# ─── 内部ヘルパー ─────────────────────────────────────────────────────────────

def _run_batch(
    targets: list[Path],
    db: Session,
    background_tasks: BackgroundTasks | None = None,
) -> dict:
    """ファイルパスリストを順次インポートしてバッチ結果を返す。"""
    imported = skipped = errors = 0
    results = []

    for path in targets:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            results.append({"filename": path.name, "status": "error", "reason": str(e)})
            errors += 1
            continue

        # ファイルごとに新しいサービスインスタンス（独立トランザクション）
        service = SurveilImportService(db)
        result = service.import_one(data, path.name, background_tasks)

        entry: dict = {"filename": path.name, "status": result["status"]}
        if result["status"] == "imported":
            entry["match_id"] = result["match_id"]
            entry["format"] = result["format"]
            imported += 1
        elif result["status"] == "skipped":
            entry["reason"] = result["reason"]
            skipped += 1
        else:
            entry["reason"] = result["reason"]
            errors += 1

        results.append(entry)

    return {
        "total": len(targets),
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "results": results,
    }
