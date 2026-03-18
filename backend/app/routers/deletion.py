from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import engine, get_db, init_db
from models.core import Match

router = APIRouter()


class DateRangeRequest(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None


@router.delete("/matches")
def delete_all_matches(db: Session = Depends(get_db)):
    matches = db.query(Match).all()
    count = len(matches)
    for m in matches:
        db.delete(m)
    db.commit()
    return {"deleted": count}


@router.delete("/matches/range")
def delete_matches_by_range(body: DateRangeRequest, db: Session = Depends(get_db)):
    q = db.query(Match)
    if body.date_from:
        q = q.filter(Match.played_at >= body.date_from)
    if body.date_to:
        from datetime import datetime, time
        end_dt = datetime.combine(body.date_to, time.max)
        q = q.filter(Match.played_at <= end_dt)
    matches = q.all()
    count = len(matches)
    for m in matches:
        db.delete(m)
    db.commit()
    return {"deleted": count}


@router.delete("/reset")
def reset_database():
    import models  # noqa: F401

    engine.dispose()
    try:
        from database import Base
        Base.metadata.drop_all(bind=engine)
        init_db()
    finally:
        engine.dispose()
    return {"ok": True}
