"""
GET  /api/settings          - 設定取得
PUT  /api/settings          - 設定更新
DELETE /api/settings/api-key - APIキー削除
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.cache import Setting

router = APIRouter()


def get_api_key(db: Session) -> str | None:
    """DB → 環境変数の順で API キーを返す。"""
    s = db.get(Setting, "anthropic_api_key")
    if s and s.value:
        return s.value
    return os.environ.get("ANTHROPIC_API_KEY") or None


class SettingsInput(BaseModel):
    llm_provider: str | None = None
    api_key: str | None = None
    quick_import_folder: str | None = None
    default_player: str | None = None


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    provider = db.get(Setting, "llm_provider")
    folder = db.get(Setting, "quick_import_folder")
    default_player = db.get(Setting, "default_player")
    return {
        "llm_provider": provider.value if provider else "claude",
        "api_key_configured": get_api_key(db) is not None,
        "quick_import_folder": folder.value if folder else None,
        "default_player": default_player.value if default_player else None,
    }


@router.put("/settings")
def put_settings(body: SettingsInput, db: Session = Depends(get_db)):
    if body.llm_provider is not None:
        s = db.get(Setting, "llm_provider")
        if s:
            s.value = body.llm_provider
        else:
            db.add(Setting(key="llm_provider", value=body.llm_provider))

    if body.api_key is not None:
        s = db.get(Setting, "anthropic_api_key")
        if s:
            s.value = body.api_key
        else:
            db.add(Setting(key="anthropic_api_key", value=body.api_key))

    # quick_import_folder: 空文字 or None で削除、文字列で保存
    if "quick_import_folder" in body.model_fields_set:
        s = db.get(Setting, "quick_import_folder")
        if not body.quick_import_folder:
            if s:
                db.delete(s)
        elif s:
            s.value = body.quick_import_folder
        else:
            db.add(Setting(key="quick_import_folder", value=body.quick_import_folder))

    if "default_player" in body.model_fields_set:
        s = db.get(Setting, "default_player")
        if not body.default_player:
            if s:
                db.delete(s)
        elif s:
            s.value = body.default_player
        else:
            db.add(Setting(key="default_player", value=body.default_player))

    db.commit()
    return {"ok": True}


@router.delete("/settings/api-key", status_code=204)
def delete_api_key(db: Session = Depends(get_db)):
    s = db.get(Setting, "anthropic_api_key")
    if s:
        db.delete(s)
        db.commit()
