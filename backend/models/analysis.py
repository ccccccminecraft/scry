from datetime import datetime
from sqlalchemy import Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    sessions: Mapped[list["AnalysisSession"]] = relationship(back_populates="prompt_template")


class QuestionSet(Base):
    __tablename__ = "question_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    items: Mapped[list["QuestionItem"]] = relationship(
        back_populates="question_set",
        order_by="QuestionItem.display_order",
        cascade="all, delete-orphan",
    )


class QuestionItem(Base):
    __tablename__ = "question_items"
    __table_args__ = (
        Index("ix_question_items_question_set_id", "question_set_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_set_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("question_sets.id"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

    question_set: Mapped["QuestionSet"] = relationship(back_populates="items")


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"
    __table_args__ = (
        Index("ix_analysis_sessions_player_name", "player_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("prompt_templates.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    filter_opponent: Mapped[str | None] = mapped_column(Text, nullable=True)
    filter_deck: Mapped[str | None] = mapped_column(Text, nullable=True)
    filter_opponent_deck: Mapped[str | None] = mapped_column(Text, nullable=True)
    filter_format: Mapped[str | None] = mapped_column(Text, nullable=True)
    filter_date_from: Mapped[str | None] = mapped_column(Text, nullable=True)
    filter_date_to: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    prompt_template: Mapped["PromptTemplate | None"] = relationship(
        back_populates="sessions"
    )
    messages: Mapped[list["AnalysisMessage"]] = relationship(
        back_populates="session",
        order_by="AnalysisMessage.display_order",
        cascade="all, delete-orphan",
    )


class AnalysisMessage(Base):
    __tablename__ = "analysis_messages"
    __table_args__ = (
        Index("ix_analysis_messages_session_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("analysis_sessions.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    session: Mapped["AnalysisSession"] = relationship(back_populates="messages")
