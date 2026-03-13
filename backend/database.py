from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = "sqlite:////database/mtgo.db"

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
