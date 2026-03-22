from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    health, import_, matches, stats, decks, settings, analysis,
    presets, backup, deletion, decklist, surveil_import, admin, auto_import,
)
from database import init_db

logger = logging.getLogger(__name__)


def _run_auto_import() -> int:
    """同期関数: スレッドプールで実行される。有効な場合にスキャンを実行し、次の間隔(秒)を返す。"""
    from database import SessionLocal
    from services.auto_import_service import AutoImportService, DEFAULT_INTERVAL_SEC
    db = SessionLocal()
    try:
        service = AutoImportService(db)
        interval = service.get_interval()
        if service.is_enabled():
            service.run_once()
        return interval
    except Exception as e:
        logger.error("Auto-import run failed: %s", e)
        return DEFAULT_INTERVAL_SEC
    finally:
        db.close()


async def _auto_import_loop() -> None:
    """バックグラウンド自動インポートループ。起動直後は少し待ってから開始する。"""
    await asyncio.sleep(10)  # DB 初期化が完了するまで待機
    while True:
        loop = asyncio.get_event_loop()
        interval = await loop.run_in_executor(None, _run_auto_import)
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from app.seed import seed_initial_data
    from database import get_db
    db = next(get_db())
    try:
        seed_initial_data(db)
    except Exception as e:
        logger.warning("seed_initial_data failed: %s", e)
    finally:
        db.close()

    task = asyncio.create_task(_auto_import_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Scry", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:18432", "file://", "null"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(import_.router, prefix="/api")
app.include_router(matches.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(decks.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(presets.router, prefix="/api")
app.include_router(backup.router, prefix="/api")
app.include_router(deletion.router, prefix="/api")
app.include_router(decklist.router, prefix="/api")
app.include_router(surveil_import.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(auto_import.router, prefix="/api")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=18432)
