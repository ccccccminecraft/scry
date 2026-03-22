"""
AutoImportService - MTGO / MTGA の自動インポートを担う。
バックグラウンドスケジューラーから定期的に呼び出される。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from models.cache import Setting
from models.core import Match
from services.import_service import ImportService, SurveilImportService

logger = logging.getLogger(__name__)

_KEY_ENABLED = "auto_import_enabled"
_KEY_INTERVAL = "auto_import_interval_sec"
_KEY_LAST_RUN = "auto_import_last_run_at"
_KEY_LAST_RESULT = "auto_import_last_result"
_KEY_MTGO_LAST_MTIME = "auto_import_mtgo_last_mtime"

DEFAULT_INTERVAL_SEC = 30


def _get(db: Session, key: str) -> str | None:
    s = db.get(Setting, key)
    return s.value if s else None


def _set(db: Session, key: str, value: str) -> None:
    s = db.get(Setting, key)
    if s:
        s.value = value
    else:
        db.add(Setting(key=key, value=value))


class AutoImportService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def is_enabled(self) -> bool:
        return _get(self._db, _KEY_ENABLED) == "true"

    def get_interval(self) -> int:
        val = _get(self._db, _KEY_INTERVAL)
        try:
            return max(10, int(val)) if val else DEFAULT_INTERVAL_SEC
        except ValueError:
            return DEFAULT_INTERVAL_SEC

    def run_once(self) -> dict:
        """MTGO / MTGA を1回スキャンしてインポートする。結果を DB に保存して返す。"""
        result = {
            "mtgo": {"imported": 0, "skipped": 0, "errors": 0},
            "mtga": {"imported": 0, "skipped": 0, "errors": 0},
        }

        try:
            self._scan_mtgo(result["mtgo"])
        except Exception as e:
            logger.error("Auto-import MTGO scan failed: %s", e)

        try:
            self._scan_mtga(result["mtga"])
        except Exception as e:
            logger.error("Auto-import MTGA scan failed: %s", e)

        now = datetime.now(tz=timezone.utc).isoformat()
        _set(self._db, _KEY_LAST_RUN, now)
        _set(self._db, _KEY_LAST_RESULT, json.dumps(result))
        self._db.commit()

        logger.info(
            "Auto-import done: MTGO=%s MTGA=%s",
            result["mtgo"],
            result["mtga"],
        )
        return result

    # ─── MTGO ───────────────────────────────────────────────────────────────

    def _scan_mtgo(self, counts: dict) -> None:
        folder_val = _get(self._db, "quick_import_folder")
        if not folder_val:
            return
        folder = Path(folder_val)
        if not folder.is_dir():
            logger.warning("Auto-import MTGO: folder not found: %s", folder_val)
            return

        # 前回スキャン時の最大 mtime より新しいファイルのみ対象
        last_mtime_val = _get(self._db, _KEY_MTGO_LAST_MTIME)
        last_mtime = float(last_mtime_val) if last_mtime_val else 0.0

        targets = [
            p for p in folder.glob("Match_GameLog_*.dat")
            if p.stat().st_mtime > last_mtime
        ]
        if not targets:
            return

        service = ImportService(self._db)
        new_max_mtime = last_mtime
        for path in sorted(targets, key=lambda p: p.stat().st_mtime):
            mtime = path.stat().st_mtime
            new_max_mtime = max(new_max_mtime, mtime)
            try:
                data = path.read_bytes()
                r = service.import_one(data, path.name)
                if r["status"] == "imported":
                    counts["imported"] += 1
                    logger.info("Auto-import MTGO: imported %s", path.name)
                elif r["status"] == "skipped":
                    counts["skipped"] += 1
                else:
                    counts["errors"] += 1
                    logger.warning("Auto-import MTGO: error %s: %s", path.name, r["reason"])
            except Exception as e:
                counts["errors"] += 1
                logger.warning("Auto-import MTGO: failed to read %s: %s", path.name, e)

        _set(self._db, _KEY_MTGO_LAST_MTIME, str(new_max_mtime))

    # ─── MTGA（Surveil） ─────────────────────────────────────────────────────

    def _scan_mtga(self, counts: dict) -> None:
        folder_val = _get(self._db, "surveil_folder")
        if not folder_val:
            return
        folder = Path(folder_val)
        if not folder.is_dir():
            logger.warning("Auto-import MTGA: folder not found: %s", folder_val)
            return

        existing_ids: set[str] = {
            row[0] for row in self._db.query(Match.id).filter(Match.source == "mtga").all()
        }

        targets = [
            p for p in folder.glob("*.json")
            if p.stem not in existing_ids
        ]
        if not targets:
            return

        service = SurveilImportService(self._db)
        for path in sorted(targets, key=lambda p: p.stat().st_mtime):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                r = service.import_one(data, path.name, background_tasks=None)
                if r["status"] == "imported":
                    counts["imported"] += 1
                    logger.info("Auto-import MTGA: imported %s", path.name)
                elif r["status"] == "skipped":
                    counts["skipped"] += 1
                else:
                    counts["errors"] += 1
                    logger.warning("Auto-import MTGA: error %s: %s", path.name, r["reason"])
            except Exception as e:
                counts["errors"] += 1
                logger.warning("Auto-import MTGA: failed to process %s: %s", path.name, e)
