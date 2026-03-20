"""
ImportService - .dat ファイルのパース・DB 保存・フォーマット推定を行う。
SurveilImportService - Surveil 出力ファイル (MTGA) のパース・DB 保存を行う。
"""
from __future__ import annotations

import json as json_module
import logging
from datetime import datetime, timezone
from typing import Literal, TypedDict

from sqlalchemy.orm import Session

from models.core import Match, MatchPlayer, Game, Mulligan, Action
from models.cache import MtgaCard
from models.deck import DeckDefinition
from parser.log_parser import MTGOLogParser, ParseError, ParseResult
from parser.surveil_parser import (
    SurveilParseResult,
    SurveilGame,
    SurveilGameAction,
    ParseError as SurveilParseError,
    get_non_basic_card_names,
    parse_surveil_json,
)
from parser.gre_parser import (
    GREParseResult,
    ParseError as GREParseError,
    parse_gre_json,
)
from services.scryfall_client import ScryfallClient

logger = logging.getLogger(__name__)

FORMAT_PRIORITY = ["standard", "pioneer", "modern", "pauper", "legacy", "vintage"]

# MTGA は Standard / Pioneer のみ対応（Modern 以下は存在しない）
MTGA_FORMAT_PRIORITY = ["standard", "pioneer"]

# これらのセットコードを持つカードは Pioneer 非合法（Historic / Modern 専用）
_MTGA_NON_PIONEER_SETS = frozenset({
    # Historic Anthologies: Pioneer 以前のカードを MTGA に追加するためのセット
    "HA1", "HA2", "HA3", "HA4", "HA5", "HA6",
    # Modern Horizons: Modern 専用セット（Pioneer 非合法）
    "MH1", "MH2", "MH3",
})

# 現在のスタンダードに含まれるセットコード
# NOTE: スタンダードローテーション（毎年9月頃）に合わせて更新すること。
#       リストにないセットのカードは "pioneer" と判定される（誤判定ではなく保守的な推定）。
_MTGA_STANDARD_SETS = frozenset({
    "WOE",  # Wilds of Eldraine (Sep 2023)
    "LCI",  # The Lost Caverns of Ixalan (Nov 2023)
    "MKM",  # Murders at Karlov Manor (Feb 2024)
    "OTJ",  # Outlaws of Thunder Junction (Apr 2024)
    "BLB",  # Bloomburrow (Aug 2024)
    "DSK",  # Duskmourn: House of Horror (Sep 2024)
    "FDN",  # Foundations (Nov 2024) - 3年間スタンダード残留予定
    # 2025 年以降のセット（knowledge cutoff 以降 - ローテーションに合わせて追加・削除）
    "EOE",  # Aetherdrift (2025)
    "FIN",  # Final Fantasy (2025)
    "ECL",  # Lorwyn Eclipsed (2025)
    "TMT",  # Teenage Mutant Ninja Turtles (2025)
})

# banned カードは試合当時は合法だった可能性が高いため legal 扱いにする
_LEGAL_STATUSES = {"legal", "banned"}


class ImportResult(TypedDict):
    match_id: str
    status: Literal["imported", "skipped", "error"]
    format: str | None
    reason: str | None


class ImportService:
    """インポート処理の中核。パース・保存・フォーマット推定を担う。"""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._parser = MTGOLogParser()
        self._scryfall = ScryfallClient(db)

    def import_one(self, data: bytes, filename: str) -> ImportResult:
        """
        バイト列を受け取りパース・保存する。

        Returns
        -------
        ImportResult
            status が "imported" / "skipped" / "error" のいずれか
        """
        # 1. パース
        try:
            parsed = self._parser.parse_bytes(data)
        except ParseError as e:
            logger.warning("ParseError for %s: %s", filename, e)
            return ImportResult(
                match_id="",
                status="error",
                format=None,
                reason=str(e),
            )

        match_id = parsed["match_id"]

        # 2. 重複チェック
        if self._db.get(Match, match_id) is not None:
            return ImportResult(
                match_id=match_id,
                status="skipped",
                format=None,
                reason="already imported",
            )

        # 3. 保存・フォーマット推定・デッキ名再判定・commit
        try:
            self._save(parsed)
            fmt = self._infer_format(parsed)
            match = self._db.get(Match, match_id)
            match.format = fmt

            # フォーマット確定後にデッキ名を再判定（format条件付き定義に対応）
            player_cards: dict[str, set[str]] = {p: set() for p in parsed["players"]}
            for game_dict in parsed["games"]:
                for act in game_dict["actions"]:
                    if act["action_type"] in ("play", "cast") and act["card_name"]:
                        if act["player"] in player_cards:
                            player_cards[act["player"]].add(act["card_name"])

            for mp in match.players:
                refined = self._detect_deck(mp.player_name, player_cards.get(mp.player_name, set()), fmt)
                if refined is not None:
                    mp.deck_name = refined

            self._db.commit()
        except Exception as e:
            self._db.rollback()
            logger.exception("Import failed for %s: %s", filename, e)
            return ImportResult(
                match_id=match_id,
                status="error",
                format=None,
                reason=str(e),
            )

        return ImportResult(
            match_id=match_id,
            status="imported",
            format=fmt,
            reason=None,
        )

    def _save(self, parsed: ParseResult) -> None:
        """パース結果を DB に flush する（commit はしない）。"""
        now = datetime.now(tz=timezone.utc)

        match = Match(
            id=parsed["match_id"],
            played_at=parsed["played_at"],
            match_winner=parsed["match_winner"],
            game_count=len(parsed["games"]),
            format=None,
            imported_at=now,
        )
        self._db.add(match)
        self._db.flush()

        # プレイヤーごとの使用カードを収集（deck検出用）
        player_cards: dict[str, set[str]] = {p: set() for p in parsed["players"]}
        for game_dict in parsed["games"]:
            for act in game_dict["actions"]:
                if act["action_type"] in ("play", "cast") and act["card_name"]:
                    if act["player"] in player_cards:
                        player_cards[act["player"]].add(act["card_name"])

        for seat, player_name in enumerate(parsed["players"], start=1):
            deck_name = self._detect_deck(player_name, player_cards[player_name], fmt=None)
            self._db.add(MatchPlayer(
                match_id=match.id,
                player_name=player_name,
                seat=seat,
                deck_name=deck_name,
            ))
        self._db.flush()

        for game_dict in parsed["games"]:
            game = Game(
                match_id=match.id,
                game_number=game_dict["game_number"],
                winner=game_dict["winner"],
                turns=game_dict["turns"],
                first_player=game_dict["first_player"],
            )
            self._db.add(game)
            self._db.flush()

            for mul in game_dict["mulligans"]:
                self._db.add(Mulligan(
                    game_id=game.id,
                    player_name=mul["player_name"],
                    count=mul["count"],
                ))

            for act in game_dict["actions"]:
                # card_name が空文字の場合は None に変換して保存
                card_name = act["card_name"] if act["card_name"] else None
                self._db.add(Action(
                    game_id=game.id,
                    turn=act["turn"],
                    active_player=act["active_player"],
                    player_name=act["player"],
                    action_type=act["action_type"],
                    card_name=card_name,
                    target_name=act["target_name"],
                    sequence=act["sequence"],
                ))

            self._db.flush()

    def _detect_deck(self, player_name: str, used_cards: set[str], fmt: str | None) -> str | None:
        return _detect_deck(self._db, player_name, used_cards, fmt)

    def _infer_format(self, parsed: ParseResult) -> str:
        """
        全ゲームの play / cast アクションからカード名を収集し、
        Scryfall の legality 情報をもとにフォーマットを推定する。
        """
        card_names: set[str] = set()
        for game in parsed["games"]:
            for act in game["actions"]:
                if act["action_type"] in ("play", "cast") and act["card_name"]:
                    card_names.add(act["card_name"])

        if not card_names:
            return "unknown"

        legalities = self._scryfall.fetch_legalities(list(card_names))

        if not legalities:
            return "unknown"

        for fmt in FORMAT_PRIORITY:
            if all(
                getattr(card, fmt, "not_legal") in _LEGAL_STATUSES
                for card in legalities.values()
            ):
                return fmt

        return "unknown"


# ─── 共有ヘルパー ──────────────────────────────────────────────────────────────

def _detect_deck(
    db: Session,
    player_name: str,
    used_cards: set[str],
    fmt: str | None,
) -> str | None:
    """
    使用カードとデッキ定義を照合してデッキ名を返す。
    優先順位: プレイヤー固有定義 → 共通定義（player_name IS NULL）
    マッチなしの場合は None を返す。
    """
    definitions = (
        db.query(DeckDefinition)
        .filter(
            (DeckDefinition.player_name == player_name) |
            (DeckDefinition.player_name.is_(None))
        )
        .order_by(
            DeckDefinition.player_name.nullslast(),
            DeckDefinition.id,
        )
        .all()
    )

    if not definitions:
        return None

    best_name: str | None = None
    best_count: int = 0
    best_is_player: bool = False

    for defn in definitions:
        if defn.format and fmt and defn.format != fmt:
            continue
        exclude_cards = {c.card_name for c in defn.cards if c.is_exclude}
        if exclude_cards & used_cards:
            continue
        sig_cards = {c.card_name for c in defn.cards if not c.is_exclude}
        match_count = len(sig_cards & used_cards)
        is_player = defn.player_name is not None

        if match_count >= defn.threshold:
            if (
                best_name is None
                or match_count > best_count
                or (match_count == best_count and is_player and not best_is_player)
            ):
                best_name = defn.deck_name
                best_count = match_count
                best_is_player = is_player

    return best_name


# ─── Surveil インポート ────────────────────────────────────────────────────────

class SurveilImportService:
    """Surveil 出力ファイル (MTGA) のパース・DB 保存・フォーマット推定を担う。"""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._scryfall = ScryfallClient(db)

    def import_one(self, data: dict, filename: str) -> ImportResult:
        """
        Surveil 出力ファイルをデシリアライズした dict を受け取りパース・保存する。
        schema_version=2 と schema_version=3 の両方に対応する。

        Returns
        -------
        ImportResult
            status が "imported" / "skipped" / "error" のいずれか
        """
        if data.get("schema_version") == 3:
            return self._import_v3(data, filename)

        try:
            parsed = parse_surveil_json(data)
        except SurveilParseError as e:
            logger.warning("SurveilParseError for %s: %s", filename, e)
            return ImportResult(match_id="", status="error", format=None, reason=str(e))

        match_id = parsed["match_id"]
        if self._db.get(Match, match_id) is not None:
            return ImportResult(
                match_id=match_id, status="skipped", format=None, reason="already imported"
            )

        try:
            self._save(parsed)
            fmt = self._infer_format_from_deck(parsed["deck_main"])
            match = self._db.get(Match, match_id)
            match.format = fmt

            # self プレイヤーのデッキ名を検出（deck_main の全カードを使用）
            used_cards = set(parsed["deck_main"].keys())
            for mp in match.players:
                if mp.player_name == parsed["self_player"]:
                    refined = _detect_deck(self._db, mp.player_name, used_cards, fmt)
                    if refined is not None:
                        mp.deck_name = refined

            self._db.commit()
        except Exception as e:
            self._db.rollback()
            logger.exception("Surveil import failed for %s: %s", filename, e)
            return ImportResult(match_id=match_id, status="error", format=None, reason=str(e))

        return ImportResult(match_id=match_id, status="imported", format=fmt, reason=None)

    def _save(self, parsed: SurveilParseResult) -> None:
        """パース結果を DB に flush する（commit はしない）。"""
        now = datetime.now(tz=timezone.utc)
        deck_json_str = json_module.dumps(
            {"main": parsed["deck_main"], "sideboard": parsed["deck_sideboard"]},
            ensure_ascii=False,
        )

        match = Match(
            id=parsed["match_id"],
            played_at=parsed["played_at"],
            match_winner=parsed["match_winner"],
            game_count=len(parsed["games"]),
            format=None,
            imported_at=now,
            source="mtga",
        )
        self._db.add(match)
        self._db.flush()

        for seat, player_name in enumerate(parsed["players"], start=1):
            is_self = player_name == parsed["self_player"]
            self._db.add(MatchPlayer(
                match_id=match.id,
                player_name=player_name,
                seat=seat,
                deck_name=None,
                deck_json=deck_json_str if is_self else None,
            ))
        self._db.flush()

        for game_dict in parsed["games"]:
            game = Game(
                match_id=match.id,
                game_number=game_dict["game_number"],
                winner=game_dict["winner"],
                turns=game_dict["turns"],
                first_player=game_dict["first_player"],
            )
            self._db.add(game)
            self._db.flush()

            for mul in game_dict["mulligans"]:
                self._db.add(Mulligan(
                    game_id=game.id,
                    player_name=mul["player_name"],
                    count=mul["count"],
                ))

            for act in game_dict["actions"]:
                self._db.add(Action(
                    game_id=game.id,
                    turn=act["turn"],
                    phase=act["phase"] or None,
                    active_player=act["active_player"],
                    player_name=act["player"],
                    action_type=act["action_type"],
                    card_name=act["card_name"],
                    target_name=act["target_name"],
                    sequence=act["sequence"],
                ))

            self._db.flush()

    def _import_v3(self, data: dict, filename: str) -> ImportResult:
        """schema_version=3（GRE メッセージ形式）のインポート処理。"""
        try:
            gre_result = parse_gre_json(data)
        except GREParseError as e:
            logger.warning("GREParseError for %s: %s", filename, e)
            return ImportResult(match_id="", status="error", format=None, reason=str(e))

        match_id = gre_result["match_id"]
        if self._db.get(Match, match_id) is not None:
            return ImportResult(
                match_id=match_id, status="skipped", format=None, reason="already imported"
            )

        try:
            # grpId を一括解決
            name_map = self._scryfall.fetch_by_arena_ids(list(gre_result["all_grp_ids"]))
            parsed = self._convert_gre_result(gre_result, name_map)

            self._save(parsed)
            # expansion_code ベースのフォーマット判定（mtga_cards 未同期時は Scryfall fallback）
            fmt = self._infer_format_from_grp_ids(gre_result["deck_grp_ids"])
            if fmt is None:
                fmt = self._infer_format_from_deck(parsed["deck_main"])
            match = self._db.get(Match, match_id)
            match.format = fmt

            used_cards = set(parsed["deck_main"].keys())
            for mp in match.players:
                if mp.player_name == parsed["self_player"]:
                    refined = _detect_deck(self._db, mp.player_name, used_cards, fmt)
                    if refined is not None:
                        mp.deck_name = refined

            self._db.commit()
        except Exception as e:
            self._db.rollback()
            logger.exception("GRE import failed for %s: %s", filename, e)
            return ImportResult(match_id=match_id, status="error", format=None, reason=str(e))

        return ImportResult(match_id=match_id, status="imported", format=fmt, reason=None)

    def _convert_gre_result(
        self,
        gre_result: GREParseResult,
        name_map: dict[int, str],
    ) -> SurveilParseResult:
        """GREParseResult + name_map → SurveilParseResult（既存の _save() で使える形式）。"""
        from collections import Counter

        deck_counts: dict[str, int] = dict(Counter(
            name_map[g] for g in gre_result["deck_grp_ids"] if g in name_map
        ))
        sb_counts: dict[str, int] = dict(Counter(
            name_map[g] for g in gre_result["sideboard_grp_ids"] if g in name_map
        ))

        obj_name_map = gre_result["obj_name_map"]

        games: list[SurveilGame] = []
        for game in gre_result["games"]:
            actions: list[SurveilGameAction] = []
            for act in game["actions"]:
                gid = act["grp_id"]
                card_name = (
                    (name_map.get(gid) or obj_name_map.get(gid))
                    if gid is not None else None
                )
                tgid = act["target_grp_id"]
                target_name = (
                    act["target_player"]
                    or ((name_map.get(tgid) or obj_name_map.get(tgid)) if tgid is not None else None)
                )
                actions.append(SurveilGameAction(
                    turn=act["turn"],
                    phase=act["phase"],
                    active_player=act["active_player"],
                    player=act["player"],
                    action_type=act["action_type"],
                    card_name=card_name,
                    target_name=target_name,
                    sequence=act["seq"],
                ))
            games.append(SurveilGame(
                game_number=game["game_number"],
                winner=game["winner"],
                turns=game["turns"],
                first_player=game["first_player"],
                mulligans=game["mulligans"],
                actions=actions,
            ))

        return SurveilParseResult(
            match_id=gre_result["match_id"],
            source="mtga",
            players=gre_result["players"],
            self_seat_id=gre_result["self_seat_id"],
            self_player=gre_result["self_player"],
            match_winner=gre_result["match_winner"],
            played_at=gre_result["played_at"],
            deck_main=deck_counts,
            deck_sideboard=sb_counts,
            games=games,
        )

    def _infer_format_from_grp_ids(self, deck_grp_ids: list[int]) -> str | None:
        """
        MTGA arena_id (grpId) リストから expansion_code ベースでフォーマットを判定する。

        mtga_cards が未同期（データなし）または全カードを解決できない場合は None を返し、
        呼び出し元が Scryfall fallback に切り替える。

        判定ロジック:
          1. 60 枚未満 → Limited とみなして "unknown"
          2. _MTGA_NON_PIONEER_SETS のカードが含まれる → "unknown" (Historic/Alchemy)
          3. 全カードが _MTGA_STANDARD_SETS 由来 → "standard"
          4. それ以外（Pioneer-legal）→ "pioneer"
        """
        if len(deck_grp_ids) < 60:
            return "unknown"

        unique_ids = list(set(deck_grp_ids))
        rows = (
            self._db.query(MtgaCard.arena_id, MtgaCard.expansion_code)
            .filter(MtgaCard.arena_id.in_(unique_ids))
            .all()
        )

        if not rows:
            return None  # mtga_cards 未同期 → Scryfall fallback

        id_to_code: dict[int, str | None] = {r.arena_id: r.expansion_code for r in rows}

        # 全カードが解決できない場合は Scryfall fallback
        if not all(aid in id_to_code for aid in unique_ids):
            return None

        codes = {code for code in id_to_code.values() if code}

        # Non-Pioneer セットのカードが含まれる → Historic / Alchemy
        if codes & _MTGA_NON_PIONEER_SETS:
            return "unknown"

        # 全カードが Standard セット由来 → standard
        if codes and codes <= _MTGA_STANDARD_SETS:
            return "standard"

        # Pioneer-legal → pioneer
        return "pioneer"

    def _infer_format_from_deck(self, deck_main: dict[str, int]) -> str:
        """
        デッキリスト（card_name → count）から Scryfall で legality を確認し
        MTGA_FORMAT_PRIORITY 順にフォーマットを返す。基本土地は除外する。

        TODO: Limited（Draft/Sealed）検知
          GRE メッセージにはイベント名が含まれないため、現状は Limited を正確に検知できない。
          現状は 60 枚未満を Limited とみなして "unknown" を返すが、実際の Limited ログで
          検証後に条件を見直すこと。
        """
        # 60 枚未満は Limited（Draft/Sealed）とみなしてスキップ
        if sum(deck_main.values()) < 60:
            return "unknown"

        card_names = get_non_basic_card_names(deck_main)
        if not card_names:
            return "unknown"

        legalities = self._scryfall.fetch_legalities(card_names)
        if not legalities:
            return "unknown"

        for fmt in MTGA_FORMAT_PRIORITY:
            if all(
                getattr(card, fmt, "not_legal") in _LEGAL_STATUSES
                for card in legalities.values()
            ):
                return fmt

        return "unknown"
