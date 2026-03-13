"""
GET    /api/prompt-templates          - テンプレート一覧
POST   /api/prompt-templates          - テンプレート作成
PUT    /api/prompt-templates/{id}     - テンプレート更新
DELETE /api/prompt-templates/{id}     - テンプレート削除

GET    /api/question-sets             - 質問セット一覧
POST   /api/question-sets             - 質問セット作成
PUT    /api/question-sets/{id}        - 質問セット更新
DELETE /api/question-sets/{id}        - 質問セット削除
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.analysis import PromptTemplate, QuestionSet, QuestionItem

router = APIRouter()


# ── 型定義 ──────────────────────────────────────────────────────────────────

class PromptTemplateInput(BaseModel):
    name: str
    content: str
    is_default: bool = False


class QuestionItemInput(BaseModel):
    text: str
    display_order: int


class QuestionSetInput(BaseModel):
    name: str
    is_default: bool = False
    items: list[QuestionItemInput]


# ── プロンプトテンプレート ────────────────────────────────────────────────

@router.get("/prompt-templates")
def list_prompt_templates(db: Session = Depends(get_db)):
    rows = db.query(PromptTemplate).order_by(PromptTemplate.id).all()
    return {"templates": [_tmpl_dict(t) for t in rows]}


@router.post("/prompt-templates", status_code=201)
def create_prompt_template(body: PromptTemplateInput, db: Session = Depends(get_db)):
    now = datetime.now(tz=timezone.utc)
    if body.is_default:
        db.query(PromptTemplate).update({"is_default": 0})
    t = PromptTemplate(
        name=body.name,
        content=body.content,
        is_default=1 if body.is_default else 0,
        created_at=now,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _tmpl_dict(t)


@router.put("/prompt-templates/{template_id}")
def update_prompt_template(
    template_id: int, body: PromptTemplateInput, db: Session = Depends(get_db)
):
    t = db.get(PromptTemplate, template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if body.is_default:
        db.query(PromptTemplate).filter(PromptTemplate.id != template_id).update({"is_default": 0})
    t.name = body.name
    t.content = body.content
    t.is_default = 1 if body.is_default else 0
    db.commit()
    db.refresh(t)
    return _tmpl_dict(t)


@router.delete("/prompt-templates/{template_id}", status_code=204)
def delete_prompt_template(template_id: int, db: Session = Depends(get_db)):
    t = db.get(PromptTemplate, template_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Template not found")
    if t.is_default:
        raise HTTPException(status_code=400, detail="デフォルトテンプレートは削除できません")
    db.delete(t)
    db.commit()


def _tmpl_dict(t: PromptTemplate) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "content": t.content,
        "is_default": bool(t.is_default),
    }


# ── 質問セット ──────────────────────────────────────────────────────────────

@router.get("/question-sets")
def list_question_sets(db: Session = Depends(get_db)):
    rows = db.query(QuestionSet).order_by(QuestionSet.id).all()
    return {"question_sets": [_qset_dict(q) for q in rows]}


@router.post("/question-sets", status_code=201)
def create_question_set(body: QuestionSetInput, db: Session = Depends(get_db)):
    now = datetime.now(tz=timezone.utc)
    if body.is_default:
        db.query(QuestionSet).update({"is_default": 0})
    qs = QuestionSet(
        name=body.name,
        is_default=1 if body.is_default else 0,
        created_at=now,
    )
    db.add(qs)
    db.flush()
    for item in body.items:
        db.add(QuestionItem(
            question_set_id=qs.id,
            text=item.text,
            display_order=item.display_order,
        ))
    db.commit()
    db.refresh(qs)
    return _qset_dict(qs)


@router.put("/question-sets/{set_id}")
def update_question_set(
    set_id: int, body: QuestionSetInput, db: Session = Depends(get_db)
):
    qs = db.get(QuestionSet, set_id)
    if qs is None:
        raise HTTPException(status_code=404, detail="QuestionSet not found")
    if body.is_default:
        db.query(QuestionSet).filter(QuestionSet.id != set_id).update({"is_default": 0})
    qs.name = body.name
    qs.is_default = 1 if body.is_default else 0
    # items を全件洗い替え
    db.query(QuestionItem).filter(QuestionItem.question_set_id == set_id).delete()
    for item in body.items:
        db.add(QuestionItem(
            question_set_id=set_id,
            text=item.text,
            display_order=item.display_order,
        ))
    db.commit()
    db.refresh(qs)
    return _qset_dict(qs)


@router.delete("/question-sets/{set_id}", status_code=204)
def delete_question_set(set_id: int, db: Session = Depends(get_db)):
    qs = db.get(QuestionSet, set_id)
    if qs is None:
        raise HTTPException(status_code=404, detail="QuestionSet not found")
    if qs.is_default:
        raise HTTPException(status_code=400, detail="デフォルト質問セットは削除できません")
    db.delete(qs)
    db.commit()


def _qset_dict(qs: QuestionSet) -> dict:
    return {
        "id": qs.id,
        "name": qs.name,
        "is_default": bool(qs.is_default),
        "items": [
            {"id": i.id, "text": i.text, "display_order": i.display_order}
            for i in qs.items
        ],
    }
