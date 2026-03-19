from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health, import_, matches, stats, decks, settings, analysis, presets, backup, deletion, decklist, surveil_import
from database import init_db

app = FastAPI(title="Scry", version="0.1.0")

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


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    from app.seed import seed_initial_data
    from database import get_db
    db = next(get_db())
    try:
        seed_initial_data(db)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("seed_initial_data failed: %s", e)
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=18432)
