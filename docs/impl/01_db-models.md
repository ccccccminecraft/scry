# 詳細設計: DBモデル定義

## 対象ファイル

| ファイル | 種別 | 内容 |
|----------|------|------|
| `backend/models/__init__.py` | 新規 | モデル一括エクスポート |
| `backend/models/core.py` | 新規 | matches / match_players / games / mulligans / actions |
| `backend/models/cache.py` | 新規 | settings / card_legality |
| `backend/models/analysis.py` | 新規 | prompt_templates / question_sets / question_items / analysis_sessions / analysis_messages |
| `backend/database.py` | 編集 | Base をモデルから参照できるよう import 追加 |
| `backend/app/main.py` | 編集 | startup で init_db() を呼ぶ（既存） + seed_initial_data() を追加 |

---

## モデル定義

### `backend/models/core.py`

```python
from datetime import datetime
from sqlalchemy import Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    played_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    match_winner: Mapped[str] = mapped_column(Text, nullable=False)
    game_count: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str | None] = mapped_column(Text, nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    players: Mapped[list["MatchPlayer"]] = relationship(back_populates="match", cascade="all, delete-orphan")
    games: Mapped[list["Game"]] = relationship(back_populates="match", cascade="all, delete-orphan")


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

    match: Mapped["Match"] = relationship(back_populates="players")


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
    mulligans: Mapped[list["Mulligan"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    actions: Mapped[list["Action"]] = relationship(back_populates="game", cascade="all, delete-orphan")


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
    player_name: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    card_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    game: Mapped["Game"] = relationship(back_populates="actions")
```

---

### `backend/models/cache.py`

```python
from datetime import datetime
from sqlalchemy import Integer, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class CardLegality(Base):
    __tablename__ = "card_legality"
    __table_args__ = (
        Index("ix_card_legality_card_name", "card_name"),
    )

    multiverse_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_name: Mapped[str] = mapped_column(Text, nullable=False)
    standard: Mapped[str] = mapped_column(Text, nullable=False)
    pioneer: Mapped[str] = mapped_column(Text, nullable=False)
    modern: Mapped[str] = mapped_column(Text, nullable=False)
    pauper: Mapped[str] = mapped_column(Text, nullable=False)
    legacy: Mapped[str] = mapped_column(Text, nullable=False)
    vintage: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

---

### `backend/models/analysis.py`

```python
from datetime import datetime
from sqlalchemy import Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


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
    question_set_id: Mapped[int] = mapped_column(Integer, ForeignKey("question_sets.id"), nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    prompt_template: Mapped["PromptTemplate | None"] = relationship(back_populates="sessions")
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
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("analysis_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    session: Mapped["AnalysisSession"] = relationship(back_populates="messages")
```

---

### `backend/models/__init__.py`

```python
from backend.models.core import Match, MatchPlayer, Game, Mulligan, Action
from backend.models.cache import Setting, CardLegality
from backend.models.analysis import (
    PromptTemplate, QuestionSet, QuestionItem,
    AnalysisSession, AnalysisMessage,
)

__all__ = [
    "Match", "MatchPlayer", "Game", "Mulligan", "Action",
    "Setting", "CardLegality",
    "PromptTemplate", "QuestionSet", "QuestionItem",
    "AnalysisSession", "AnalysisMessage",
]
```

---

## 初期データ投入

### `backend/app/seed.py`（新規）

```python
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.models.cache import Setting
from backend.models.analysis import PromptTemplate, QuestionSet, QuestionItem

DEFAULT_PROMPT = """\
あなたはMagic: The Gatheringのコーチです。
以下のプレイヤー「{player_name}」の対戦統計を分析し、改善点やプレイの傾向をアドバイスしてください。

## 統計データ
{stats_text}
"""

DEFAULT_QUESTIONS = [
    "私のプレイの傾向を教えてください",
    "先手・後手の勝率の差について分析してください",
    "マリガンの影響について詳しく教えてください",
    "改善できるポイントを教えてください",
    "直近の勝率推移を分析してください",
]


def seed_initial_data(db: Session) -> None:
    """初期データを投入する。既に存在する場合はスキップ。"""
    _seed_settings(db)
    _seed_prompt_template(db)
    _seed_question_set(db)
    db.commit()


def _seed_settings(db: Session) -> None:
    if db.get(Setting, "llm_provider") is None:
        db.add(Setting(key="llm_provider", value="claude"))


def _seed_prompt_template(db: Session) -> None:
    existing = db.query(PromptTemplate).filter_by(is_default=1).first()
    if existing is None:
        db.add(PromptTemplate(
            name="デフォルト",
            content=DEFAULT_PROMPT,
            is_default=1,
            created_at=datetime.now(timezone.utc),
        ))


def _seed_question_set(db: Session) -> None:
    existing = db.query(QuestionSet).filter_by(is_default=1).first()
    if existing is None:
        now = datetime.now(timezone.utc)
        qs = QuestionSet(name="基本分析セット", is_default=1, created_at=now)
        db.add(qs)
        db.flush()  # qs.id を確定させる
        for i, text in enumerate(DEFAULT_QUESTIONS, start=1):
            db.add(QuestionItem(question_set_id=qs.id, text=text, display_order=i))
```

---

## `database.py` の変更点

`init_db()` の前にモデルを import することで `Base.metadata` にテーブルが登録される。

```python
# backend/database.py の init_db() を以下に変更
def init_db() -> None:
    import backend.models  # noqa: F401 — テーブル登録のために import が必要
    Base.metadata.create_all(bind=engine)
```

---

## `app/main.py` の変更点

startup イベントで seed を実行する。

```python
@app.on_event("startup")
def on_startup() -> None:
    init_db()
    from backend.app.seed import seed_initial_data
    from backend.database import get_db
    db = next(get_db())
    try:
        seed_initial_data(db)
    finally:
        db.close()
```

---

## エラーハンドリング

| ケース | 対応 |
|--------|------|
| DB ファイルのディレクトリが存在しない | `init_db()` 前に `os.makedirs` で作成 |
| `create_all()` 失敗 | 例外をそのまま raise（起動失敗として扱う） |
| `seed_initial_data()` 失敗 | ログ出力後、起動は継続（初期データなしでも動作可） |

---

## 動作確認手順

1. Docker で backend コンテナを起動する（`docker compose up backend`）
2. コンテナログに `Application startup complete.` が表示されることを確認
3. `database/mtgo.db` が生成されていることを確認
4. SQLite クライアントでテーブルが作成されていることを確認：
   ```bash
   sqlite3 database/mtgo.db ".tables"
   # 期待値: actions  analysis_messages  analysis_sessions  card_legality
   #          games  match_players  matches  mulligans  prompt_templates
   #          question_items  question_sets  settings
   ```
5. 初期データを確認：
   ```bash
   sqlite3 database/mtgo.db "SELECT * FROM settings;"
   # → llm_provider|claude
   sqlite3 database/mtgo.db "SELECT name, is_default FROM prompt_templates;"
   # → デフォルト|1
   sqlite3 database/mtgo.db "SELECT name, is_default FROM question_sets;"
   # → 基本分析セット|1
   sqlite3 database/mtgo.db "SELECT display_order, text FROM question_items ORDER BY display_order;"
   # → 5件の定型質問
   ```
