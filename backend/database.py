import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def _get_database_url() -> str:
    # 環境変数で明示指定されている場合はそちらを優先（Docker開発環境）
    if url := os.environ.get("DATABASE_URL"):
        return url
    # Windows 本番環境: %APPDATA%\Scry\mtgo.db
    if sys.platform == "win32":
        db_dir = Path(os.environ["APPDATA"]) / "Scry"
    else:
        db_dir = Path("/database")
    db_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_dir / 'mtgo.db'}"


DATABASE_URL = _get_database_url()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """起動時にテーブルを自動生成する。スキーマ変更があったテーブルは再作成する。"""
    import models  # noqa: F401 — Base.metadata にテーブルを登録するために必要

    with engine.connect() as conn:
        from sqlalchemy import text, inspect
        inspector = inspect(engine)

        # card_legality: multiverse_id PK → card_name PK へのスキーマ移行
        if "card_legality" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("card_legality")}
            if "multiverse_id" in cols:
                conn.execute(text("DROP TABLE card_legality"))
                conn.commit()

        # actions: active_player / target_name 列の追加
        if "actions" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("actions")}
            if "active_player" not in cols:
                conn.execute(text("ALTER TABLE actions ADD COLUMN active_player TEXT NOT NULL DEFAULT ''"))
                conn.commit()
            if "target_name" not in cols:
                conn.execute(text("ALTER TABLE actions ADD COLUMN target_name TEXT"))
                conn.commit()

        # deck_definition_cards: is_exclude 列の追加
        if "deck_definition_cards" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("deck_definition_cards")}
            if "is_exclude" not in cols:
                conn.execute(text("ALTER TABLE deck_definition_cards ADD COLUMN is_exclude INTEGER NOT NULL DEFAULT 0"))
                conn.commit()

        # decks / deck_versions: is_archived 列の追加
        if "decks" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("decks")}
            if "is_archived" not in cols:
                conn.execute(text("ALTER TABLE decks ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT 0"))
                conn.commit()
            if "tile_scryfall_id" not in cols:
                conn.execute(text("ALTER TABLE decks ADD COLUMN tile_scryfall_id TEXT"))
                conn.commit()

        if "deck_versions" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("deck_versions")}
            if "is_archived" not in cols:
                conn.execute(text("ALTER TABLE deck_versions ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT 0"))
                conn.commit()

        # mtga_cards: expansion_code 列の追加
        if "mtga_cards" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("mtga_cards")}
            if "expansion_code" not in cols:
                conn.execute(text("ALTER TABLE mtga_cards ADD COLUMN expansion_code TEXT"))
                conn.commit()

        # mtga_counter_types: 新規テーブル（create_all で自動作成されるため migration 不要）
        # ※ 既存 DB との互換性のため init_db で create_all を呼ぶことで対応済み

        # matches: source 列の追加
        if "matches" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("matches")}
            if "source" not in cols:
                conn.execute(text("ALTER TABLE matches ADD COLUMN source TEXT NOT NULL DEFAULT 'mtgo'"))
                conn.commit()

        # match_players: deck_json 列の追加
        if "match_players" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("match_players")}
            if "deck_json" not in cols:
                conn.execute(text("ALTER TABLE match_players ADD COLUMN deck_json TEXT"))
                conn.commit()

        # actions: phase 列の追加
        if "actions" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("actions")}
            if "phase" not in cols:
                conn.execute(text("ALTER TABLE actions ADD COLUMN phase TEXT"))
                conn.commit()

        # analysis_sessions: フィルター列の追加
        if "analysis_sessions" in inspector.get_table_names():
            cols = {c["name"] for c in inspector.get_columns("analysis_sessions")}
            for col in ("filter_opponent", "filter_deck", "filter_opponent_deck",
                        "filter_format", "filter_date_from", "filter_date_to"):
                if col not in cols:
                    conn.execute(text(f"ALTER TABLE analysis_sessions ADD COLUMN {col} TEXT"))
                    conn.commit()

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI の Depends で使用する DB セッションジェネレーター。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
