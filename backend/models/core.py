from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

if TYPE_CHECKING:
    from models.decklist import DeckVersion


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    played_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    match_winner: Mapped[str] = mapped_column(Text, nullable=False)
    game_count: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="mtgo")

    players: Mapped[list["MatchPlayer"]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )
    games: Mapped[list["Game"]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )


class MatchPlayer(Base):
    __tablename__ = "match_players"
    __table_args__ = (
        Index("ix_match_players_player_name", "player_name"),
        Index("ix_match_players_deck_name", "deck_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(Text, ForeignKey("matches.id"), nullable=False)
    player_name: Mapped[str] = mapped_column(Text, nullable=False)
    seat: Mapped[int] = mapped_column(Integer, nullable=False)
    deck_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    game_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    deck_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    deck_version_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("deck_versions.id", ondelete="SET NULL"), nullable=True
    )

    match: Mapped["Match"] = relationship(back_populates="players")
    deck_version: Mapped[Optional["DeckVersion"]] = relationship()


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        Index("ix_games_match_id", "match_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(Text, ForeignKey("matches.id"), nullable=False)
    game_number: Mapped[int] = mapped_column(Integer, nullable=False)
    winner: Mapped[str] = mapped_column(Text, nullable=False)
    turns: Mapped[int] = mapped_column(Integer, nullable=False)
    first_player: Mapped[str] = mapped_column(Text, nullable=False)

    match: Mapped["Match"] = relationship(back_populates="games")
    mulligans: Mapped[list["Mulligan"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    actions: Mapped[list["Action"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )


class Mulligan(Base):
    __tablename__ = "mulligans"
    __table_args__ = (
        Index("ix_mulligans_game_id", "game_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    player_name: Mapped[str] = mapped_column(Text, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)

    game: Mapped["Game"] = relationship(back_populates="mulligans")


class Action(Base):
    __tablename__ = "actions"
    __table_args__ = (
        Index("ix_actions_game_id", "game_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=False)
    active_player: Mapped[str] = mapped_column(Text, nullable=False, default="")
    player_name: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    card_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str | None] = mapped_column(Text, nullable=True)

    game: Mapped["Game"] = relationship(back_populates="actions")
