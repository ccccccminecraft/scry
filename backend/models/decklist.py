from datetime import datetime
from sqlalchemy import Integer, Text, Boolean, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    scryfall_id: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    mtgo_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    deck_version_cards: Mapped[list["DeckVersionCard"]] = relationship(back_populates="card")


class Deck(Base):
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    versions: Mapped[list["DeckVersion"]] = relationship(
        back_populates="deck", cascade="all, delete-orphan"
    )


class DeckVersion(Base):
    __tablename__ = "deck_versions"
    __table_args__ = (
        UniqueConstraint("deck_id", "version_number"),
        Index("ix_deck_versions_deck_id", "deck_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deck_id: Mapped[int] = mapped_column(Integer, ForeignKey("decks.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    deck: Mapped["Deck"] = relationship(back_populates="versions")
    cards: Mapped[list["DeckVersionCard"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )


class DeckVersionCard(Base):
    __tablename__ = "deck_version_cards"
    __table_args__ = (
        Index("ix_deck_version_cards_version_id", "deck_version_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deck_version_id: Mapped[int] = mapped_column(Integer, ForeignKey("deck_versions.id"), nullable=False)
    card_id: Mapped[int] = mapped_column(Integer, ForeignKey("cards.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_sideboard: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    version: Mapped["DeckVersion"] = relationship(back_populates="cards")
    card: Mapped["Card"] = relationship(back_populates="deck_version_cards")
