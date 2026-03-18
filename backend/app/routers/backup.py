import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from database import engine, DATABASE_URL

router = APIRouter()

SQLITE_MAGIC = b"SQLite format 3\x00"


def _get_db_path() -> Path:
    # DATABASE_URL は "sqlite:///..." の形式
    path_str = DATABASE_URL.replace("sqlite:///", "")
    return Path(path_str)


@router.get("/backup")
def download_backup():
    db_path = _get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database file not found")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scry_backup_{timestamp}.db"

    return FileResponse(
        path=str(db_path),
        media_type="application/octet-stream",
        filename=filename,
    )


@router.post("/restore")
async def restore_backup(file: UploadFile = File(...)):
    content = await file.read()

    # SQLite ファイルの妥当性検証
    if not content[:16] == SQLITE_MAGIC:
        raise HTTPException(status_code=400, detail="Invalid SQLite file")

    db_path = _get_db_path()

    # リストア前の自動バックアップ
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prerestore_path = db_path.parent / f"mtgo_prerestore_{timestamp}.db"

    # 接続プールを破棄してファイルロックを解放
    engine.dispose()

    try:
        # アップロードデータを一時ファイルに保存
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        # 現在の DB を自動バックアップ
        if db_path.exists():
            with sqlite3.connect(str(db_path)) as src_conn:
                with sqlite3.connect(str(prerestore_path)) as bak_conn:
                    src_conn.backup(bak_conn)

        # アップロードファイルで DB を置き換え
        with sqlite3.connect(tmp_path) as src_conn:
            with sqlite3.connect(str(db_path)) as dst_conn:
                src_conn.backup(dst_conn)

    finally:
        # 一時ファイルを削除
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass
        # 接続プールを再初期化
        engine.dispose()

    return {"ok": True}
