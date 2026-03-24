"""
インポート処理の進捗状態を保持するモジュールレベルのシングルトン。

フロントエンドが GET /api/import/status をポーリングすることで、
現在どのファイルを処理中か、Scryfall の取得が何件完了したかを確認できる。
"""
from __future__ import annotations

import threading
from typing import List

_lock = threading.Lock()

# 現在の状態
_active: bool = False
_filename: str = ""
_step: str = ""
_scryfall_done: int = 0
_scryfall_total: int = 0
_log: List[str] = []


def get_status() -> dict:
    with _lock:
        return {
            "active": _active,
            "filename": _filename,
            "step": _step,
            "scryfall_done": _scryfall_done,
            "scryfall_total": _scryfall_total,
            "log": list(_log),
        }


def start(filename: str) -> None:
    with _lock:
        global _active, _filename, _step, _scryfall_done, _scryfall_total
        _active = True
        _filename = filename
        _step = "parsing"
        _scryfall_done = 0
        _scryfall_total = 0


def update_step(step: str) -> None:
    with _lock:
        global _step
        _step = step


def update_scryfall(done: int, total: int) -> None:
    with _lock:
        global _scryfall_done, _scryfall_total
        _scryfall_done = done
        _scryfall_total = total


def append_log(msg: str) -> None:
    with _lock:
        _log.append(msg)
        # 直近 200 件のみ保持
        if len(_log) > 200:
            del _log[:-200]


def finish() -> None:
    with _lock:
        global _active
        _active = False


def reset_log() -> None:
    """インポートバッチ開始時にログをクリアする。"""
    with _lock:
        global _active, _filename, _step, _scryfall_done, _scryfall_total
        _log.clear()
        _active = False
        _filename = ""
        _step = ""
        _scryfall_done = 0
        _scryfall_total = 0
