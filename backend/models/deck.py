from sqlalchemy import Integer, Text, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class DeckDefinition(Base):
    __tablename__ = "deck_definitions"
    __table_args__ = (
        Index("ix_deck_definitions_player_name", "player_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_name: Mapped[str | None] = mapped_column(Text, nullable=True)  # NULL = 共通定義
    deck_name: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    cards: Mapped[list["DeckDefinitionCard"]] = relationship(
        back_populates="definition", cascade="all, delete-orphan"
    )


class DeckDefinitionCard(Base):
    __tablename__ = "deck_definition_cards"
    __table_args__ = (
        Index("ix_deck_definition_cards_definition_id", "definition_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    definition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("deck_definitions.id"), nullable=False
    )
    card_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_exclude: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    definition: Mapped["DeckDefinition"] = relationship(back_populates="cards")
