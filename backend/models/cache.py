from datetime import datetime
from sqlalchemy import Float, Integer, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from database import Base



class MtgaCard(Base):
    """MTGA grpId（arena_id）→ カード名のキャッシュ。"""
    __tablename__ = "mtga_cards"

    arena_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_name: Mapped[str] = mapped_column(Text, nullable=False)
    expansion_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class MtgaCounterType(Base):
    """MTGA counter_type ID → カウンター名のキャッシュ（Raw_CardDatabase の Enums テーブルから同期）。"""
    __tablename__ = "mtga_counter_types"

    counter_type_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class CardCache(Base):
    """Scryfall カードデータのキャッシュ（カード辞書エクスポート用）。"""
    __tablename__ = "card_cache"

    scryfall_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    mana_cost: Mapped[str | None] = mapped_column(Text, nullable=True)
    cmc: Mapped[float] = mapped_column(Float, nullable=False)
    type_line: Mapped[str] = mapped_column(Text, nullable=False)
    oracle_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    power: Mapped[str | None] = mapped_column(Text, nullable=True)
    toughness: Mapped[str | None] = mapped_column(Text, nullable=True)
    loyalty: Mapped[str | None] = mapped_column(Text, nullable=True)
    colors: Mapped[str] = mapped_column(Text, nullable=False)       # JSON 配列文字列
    keywords: Mapped[str] = mapped_column(Text, nullable=False)     # JSON 配列文字列
    produced_mana: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON 配列文字列
    card_faces: Mapped[str | None] = mapped_column(Text, nullable=True)     # JSON 配列文字列
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CardCacheMiss(Base):
    """Scryfall で解決できなかったカード名の記録。fetch-missing でスキップするために使用。"""
    __tablename__ = "card_cache_miss"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    failed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    miss_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


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
