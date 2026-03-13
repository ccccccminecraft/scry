from datetime import datetime, timezone
from sqlalchemy.orm import Session
from models.cache import Setting
from models.analysis import PromptTemplate, QuestionSet, QuestionItem

DEFAULT_PROMPT = """\
あなたはMagic: The Gatheringの対戦分析エキスパートです。
以下のプレイヤー統計データをもとに、ユーザーの質問に日本語で答えてください。

回答の方針:
- 統計データに含まれる具体的な数値を根拠として示してください
- 結論 → 根拠 → 改善提案 の順で回答してください
- データにない情報（デッキリスト・相手のプレイング等）については「データがないため不明」と伝えてください
- 回答は簡潔にまとめ、要点を箇条書きで示してください

## 対象プレイヤー
{player_name}

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
        db.flush()
        for i, text in enumerate(DEFAULT_QUESTIONS, start=1):
            db.add(QuestionItem(
                question_set_id=qs.id,
                text=text,
                display_order=i,
            ))
