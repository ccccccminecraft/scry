"""
ScryfallClient - Scryfall API からカード適性情報を取得してキャッシュする。

レート制限: 100ms/リクエスト（Scryfall 公式推奨）
"""
from __future__ import annotations

import time
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from models.cache import CardLegality, MtgaCard

logger = logging.getLogger(__name__)

SCRYFALL_BASE = "https://api.scryfall.com"
RATE_LIMIT_SEC = 0.1  # 100ms
REQUEST_TIMEOUT = 10.0


class ScryfallClient:
    """Scryfall API クライアント。キャッシュ済みの legality は DB から取得する。"""

    _last_request: float = 0.0  # クラス変数: インスタンス間でレート制限を共有

    def __init__(self, db: Session) -> None:
        self._db = db

    def fetch_legalities(self, card_names: list[str]) -> dict[str, CardLegality]:
        """
        カード名のリストに対するカード適性情報を返す。

        キャッシュ済みの分は DB から取得し、未キャッシュ分のみ Scryfall API に問い合わせる。
        取得失敗したカードは結果から除外される（フォーマット推定から除外される）。
        """
        if not card_names:
            return {}

        # キャッシュ済み分を一括取得
        cached = (
            self._db.query(CardLegality)
            .filter(CardLegality.card_name.in_(card_names))
            .all()
        )
        result: dict[str, CardLegality] = {c.card_name: c for c in cached}

        # 未キャッシュ分を取得
        uncached = [name for name in card_names if name not in result]
        for name in uncached:
            card = self._fetch_one_by_name(name)
            if card is not None:
                self._db.add(card)
                self._db.flush()
                result[name] = card

        return result

    def _fetch_one_by_name(self, card_name: str) -> CardLegality | None:
        """
        カード名で1件取得する。失敗時（404・タイムアウト等）は None を返す。
        """
        self._rate_limit()
        url = f"{SCRYFALL_BASE}/cards/named"
        try:
            response = httpx.get(url, params={"exact": card_name}, timeout=REQUEST_TIMEOUT)
            if response.status_code == 404:
                logger.debug("Scryfall: card_name=%r not found", card_name)
                return None
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "2"))
                logger.warning("Scryfall rate limited, waiting %ds", retry_after)
                time.sleep(retry_after)
                response = httpx.get(url, params={"exact": card_name}, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.warning("Scryfall fetch failed for card_name=%r: %s", card_name, e)
            return None

        legalities = data.get("legalities", {})
        return CardLegality(
            card_name=card_name,
            standard=legalities.get("standard", "not_legal"),
            pioneer=legalities.get("pioneer", "not_legal"),
            modern=legalities.get("modern", "not_legal"),
            pauper=legalities.get("pauper", "not_legal"),
            legacy=legalities.get("legacy", "not_legal"),
            vintage=legalities.get("vintage", "not_legal"),
            fetched_at=datetime.now(tz=timezone.utc),
        )

    def fetch_by_arena_ids(self, arena_ids: list[int]) -> dict[int, str]:
        """
        MTGA arena_id（grpId）のリストからカード名を返す。

        mtga_cards テーブル（Raw_CardDatabase から同期済み）のみを参照する。
        同期されていない ID は結果から除外される。

        Returns
        -------
        dict[int, str]
            arena_id → card_name のマップ。取得できなかった ID は含まれない。
        """
        if not arena_ids:
            return {}

        unique_ids = list(set(arena_ids))

        rows = (
            self._db.query(MtgaCard)
            .filter(MtgaCard.arena_id.in_(unique_ids))
            .all()
        )
        return {c.arena_id: c.card_name for c in rows}

    def _fetch_one_by_arena_id(self, arena_id: int) -> str | None:
        """
        GET /cards/arena/{id} で MTGA arena_id（grpId）からカード名を1件取得する。
        失敗時（404・タイムアウト等）は None を返す。
        """
        self._rate_limit()
        url = f"{SCRYFALL_BASE}/cards/arena/{arena_id}"
        try:
            response = httpx.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code == 404:
                logger.debug("Scryfall: arena_id=%d not found", arena_id)
                return None
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "2"))
                logger.warning("Scryfall rate limited, waiting %ds", retry_after)
                time.sleep(retry_after)
                response = httpx.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.json().get("name")
        except Exception as e:
            logger.warning("Scryfall arena lookup failed for %d: %s", arena_id, e)
            return None

    def _rate_limit(self) -> None:
        """前回リクエストから 100ms 未満なら sleep して待機する。"""
        elapsed = time.monotonic() - self._last_request
        if elapsed < RATE_LIMIT_SEC:
            time.sleep(RATE_LIMIT_SEC - elapsed)
        self._last_request = time.monotonic()
