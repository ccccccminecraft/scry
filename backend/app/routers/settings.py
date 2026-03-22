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
    min_player_matches: int | None = None
    min_deck_matches: int | None = None
    auto_import_enabled: bool | None = None
    auto_import_interval_sec: int | None = None
    onboarding_completed: bool | None = None


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    provider = db.get(Setting, "llm_provider")
    folder = db.get(Setting, "quick_import_folder")
    default_player = db.get(Setting, "default_player")
    min_player = db.get(Setting, "min_player_matches")
    min_deck = db.get(Setting, "min_deck_matches")
    auto_enabled = db.get(Setting, "auto_import_enabled")
    auto_interval = db.get(Setting, "auto_import_interval_sec")
    onboarding = db.get(Setting, "onboarding_completed")
    return {
        "llm_provider": provider.value if provider else "claude",
        "api_key_configured": get_api_key(db) is not None,
        "quick_import_folder": folder.value if folder else None,
        "default_player": default_player.value if default_player else None,
        "min_player_matches": int(min_player.value) if min_player else 1,
        "min_deck_matches": int(min_deck.value) if min_deck else 1,
        "auto_import_enabled": auto_enabled.value == "true" if auto_enabled else False,
        "auto_import_interval_sec": int(auto_interval.value) if auto_interval else 30,
        "onboarding_completed": onboarding.value == "1" if onboarding else False,
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

    if body.min_player_matches is not None:
        s = db.get(Setting, "min_player_matches")
        val = str(max(0, body.min_player_matches))
        if s:
            s.value = val
        else:
            db.add(Setting(key="min_player_matches", value=val))

    if body.min_deck_matches is not None:
        s = db.get(Setting, "min_deck_matches")
        val = str(max(0, body.min_deck_matches))
        if s:
            s.value = val
        else:
            db.add(Setting(key="min_deck_matches", value=val))

    if body.auto_import_enabled is not None:
        s = db.get(Setting, "auto_import_enabled")
        val = "true" if body.auto_import_enabled else "false"
        if s:
            s.value = val
        else:
            db.add(Setting(key="auto_import_enabled", value=val))

    if body.auto_import_interval_sec is not None:
        s = db.get(Setting, "auto_import_interval_sec")
        val = str(max(10, body.auto_import_interval_sec))
        if s:
            s.value = val
        else:
            db.add(Setting(key="auto_import_interval_sec", value=val))

    if body.onboarding_completed is not None:
        s = db.get(Setting, "onboarding_completed")
        val = "1" if body.onboarding_completed else "0"
        if s:
            s.value = val
        else:
            db.add(Setting(key="onboarding_completed", value=val))

    db.commit()
    return {"ok": True}


@router.delete("/settings/api-key", status_code=204)
def delete_api_key(db: Session = Depends(get_db)):
    s = db.get(Setting, "anthropic_api_key")
    if s:
        db.delete(s)
        db.commit()
