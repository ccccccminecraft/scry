"""
ScryfallClient - Scryfall API からカード適性情報を取得してキャッシュする。

レート制限: 100ms/リクエスト（Scryfall 公式推奨）
"""
from __future__ import annotations

import time
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from models.cache import CardLegality, MtgaCard, Setting

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

        キャッシュ済み分は DB から取得し、未キャッシュ分のみ
        Scryfall POST /cards/collection（最大 75 件/バッチ）で取得する。

        Returns
        -------
        dict[int, str]
            arena_id → card_name のマップ。取得できなかった ID は含まれない。
        """
        if not arena_ids:
            return {}

        unique_ids = list(set(arena_ids))

        # キャッシュ済みを一括取得
        cached = (
            self._db.query(MtgaCard)
            .filter(MtgaCard.arena_id.in_(unique_ids))
            .all()
        )
        result: dict[int, str] = {c.arena_id: c.card_name for c in cached}

        # 未キャッシュ分を個別取得（GET /cards/arena/{id}）
        uncached = [aid for aid in unique_ids if aid not in result]
        for arena_id in uncached:
            name = self._fetch_one_by_arena_id(arena_id)
            if name:
                self._db.add(MtgaCard(
                    arena_id=arena_id,
                    card_name=name,
                    fetched_at=datetime.now(timezone.utc),
                ))
                result[arena_id] = name

        if uncached:
            self._db.flush()

        return result

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

    def sync_bulk_data(self) -> int:
        """
        Scryfall Bulk Data（default_cards）を同期して mtga_cards テーブルを更新する。
        arena_id を持つカードのみを対象とし、既存レコードは上書きする。

        Returns
        -------
        int
            upsert したカード件数
        """
        # Step 1: bulk-data メタ情報取得
        self._rate_limit()
        meta_resp = httpx.get(f"{SCRYFALL_BASE}/bulk-data", timeout=REQUEST_TIMEOUT)
        meta_resp.raise_for_status()

        download_uri: str | None = None
        for entry in meta_resp.json().get("data", []):
            if entry.get("type") == "default_cards":
                download_uri = entry["download_uri"]
                break

        if not download_uri:
            raise RuntimeError("default_cards not found in Scryfall bulk-data response")

        # Step 2: バルクデータダウンロード（~100MB、タイムアウトを長めに設定）
        logger.info("Scryfall bulk download start: %s", download_uri)
        bulk_resp = httpx.get(download_uri, timeout=300.0)
        bulk_resp.raise_for_status()
        cards: list[dict] = bulk_resp.json()
        logger.info("Scryfall bulk download complete: %d total cards", len(cards))

        # Step 3: arena_id でデデュープ（同一 arena_id を持つ複数印刷物が存在するため）
        arena_map: dict[int, str] = {}
        for card in cards:
            arena_id = card.get("arena_id")
            if arena_id is None:
                continue
            name = card.get("name")
            if name:
                arena_map[arena_id] = name

        # INSERT OR REPLACE でバッチ upsert
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        rows = [
            {"arena_id": aid, "card_name": name, "fetched_at": now_str}
            for aid, name in arena_map.items()
        ]
        self._db.execute(
            text(
                "INSERT OR REPLACE INTO mtga_cards (arena_id, card_name, fetched_at)"
                " VALUES (:arena_id, :card_name, :fetched_at)"
            ),
            rows,
        )
        count = len(arena_map)

        # Step 4: 同期日時を settings に保存
        setting = self._db.get(Setting, "scryfall_bulk_updated_at")
        if setting:
            setting.value = now.isoformat()
        else:
            self._db.add(Setting(key="scryfall_bulk_updated_at", value=now.isoformat()))
        self._db.flush()

        logger.info("Scryfall bulk sync completed: %d arena_id cards upserted", count)
        return count

    def _rate_limit(self) -> None:
        """前回リクエストから 100ms 未満なら sleep して待機する。"""
        elapsed = time.monotonic() - self._last_request
        if elapsed < RATE_LIMIT_SEC:
            time.sleep(RATE_LIMIT_SEC - elapsed)
        self._last_request = time.monotonic()
