"""
POST /api/import       - .dat ファイル単体インポート
POST /api/import/batch - .dat ファイル一括インポート
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from services.import_service import ImportService
import services.import_status as import_status

router = APIRouter()


@router.get("/import/status")
def get_import_status():
    """インポート処理の現在の進捗状態を返す。フロントエンドからポーリングで使用する。"""
    return import_status.get_status()


@router.post("/import/cancel")
def cancel_import():
    """進行中のインポートにキャンセルフラグを立てる。"""
    import_status.request_cancel()
    return {"ok": True}


@router.post("/import")
async def import_one(file: UploadFile, db: Session = Depends(get_db)):
    """
    .dat ファイルを1件パースして DB に保存する。

    - status="imported" / "skipped" → 200
    - status="error" → 400
    """
    import_status.reset_log()
    data = await file.read()
    service = ImportService(db)
    result = service.import_one(data, file.filename or "")

    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["reason"] or "Import failed")

    return result


@router.post("/import/batch")
async def import_batch(files: list[UploadFile], db: Session = Depends(get_db)):
    """
    複数の .dat ファイルを順次処理する。
    1件のエラーは他のファイルに影響しない。
    """
    import_status.reset_log()
    service = ImportService(db)
    results = []
    imported = skipped = errors = 0

    for upload in files:
        data = await upload.read()
        result = service.import_one(data, upload.filename or "")

        entry: dict = {"name": upload.filename or "", "status": result["status"]}
        if result["status"] == "imported":
            entry["match_id"] = result["match_id"]
            imported += 1
        elif result["status"] == "skipped":
            entry["reason"] = result["reason"]
            skipped += 1
        else:
            entry["reason"] = result["reason"]
            errors += 1

        results.append(entry)

    return {
        "total": len(files),
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "results": results,
    }
