from datetime import datetime
from sqlalchemy import Integer, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class MtgaCard(Base):
    """MTGA grpId（arena_id）→ カード名のキャッシュ。"""
    __tablename__ = "mtga_cards"

    arena_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_name: Mapped[str] = mapped_column(Text, nullable=False)
    expansion_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class CardLegality(Base):
    __tablename__ = "card_legality"

    card_name: Mapped[str] = mapped_column(Text, primary_key=True)
    standard: Mapped[str] = mapped_column(Text, nullable=False)
    pioneer: Mapped[str] = mapped_column(Text, nullable=False)
    modern: Mapped[str] = mapped_column(Text, nullable=False)
    pauper: Mapped[str] = mapped_column(Text, nullable=False)
    legacy: Mapped[str] = mapped_column(Text, nullable=False)
    vintage: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
