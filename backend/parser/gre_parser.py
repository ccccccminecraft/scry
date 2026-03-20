"""
gre_parser.py - Surveil schema_version=3 JSON (GRE メッセージ形式) のパーサー

schema_version=3 JSON の gre_messages から各ゲームのイベントを抽出する。
カード名解決（grpId → card_name）はこのパーサーでは行わない。
Scry 側の SurveilImportService が Scryfall API を使って解決する。

出力の GREGameAction は grp_id（int）を持ち、呼び出し元が name_map で解決する。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


# ─── 出力型定義 ──────────────────────────────────────────────────────────────

class GREGameAction(TypedDict):
    seq: int
    turn: int
    phase: str
    action_type: str
    player: str
    active_player: str
    grp_id: int | None          # 主カードの grpId（未解決）
    target_player: str | None   # プレイヤー対象（すでに名前）
    target_grp_id: int | None   # カード対象の grpId（未解決）


class GREGame(TypedDict):
    game_number: int
    winner: str
    turns: int
    first_player: str
    mulligans: list[dict]
    actions: list[GREGameAction]


class GREParseResult(TypedDict):
    match_id: str
    source: str
    players: list[str]
    self_seat_id: int
    self_player: str
    match_winner: str
    played_at: datetime
    deck_grp_ids: list[int]
    sideboard_grp_ids: list[int]
    games: list[GREGame]
    all_grp_ids: set[int]   # デッキ + 全イベントで登場した grpId（バッチ解決用）
    obj_name_map: dict[int, str]  # grpId → 合成カード名（トークン・基本土地など Scryfall 未収録分の fallback）
    event_name: Optional[str]     # EventJoin の EventName（例: "Traditional_Ladder"）


class ParseError(Exception):
    pass


# ─── 定数 ────────────────────────────────────────────────────────────────────

# 既知のマナ能力 grpId（Surveil parser.py から移植）
_MANA_ABILITY_GRP_IDS: frozenset[int] = frozenset({
    1001, 1002, 1003, 1004, 1005,
    1152, 1167, 1209, 4247, 9505,
    18504, 174570, 176676, 176678, 176681,
})

_ZONE_TRANSFER_EVENTS = {
    "CastSpell": "cast",
    "PlayLand":  "play_land",
    "Draw":      "draw",
    "Discard":   "discard",
    "Resolve":   "resolve",
    "Mill":      "mill",
}

_PHASE_NAMES = {1: "beginning", 2: "main1", 3: "combat", 4: "main2", 5: "ending"}

_COMBAT_STEP_NAMES = {
    4: "begin_combat", 5: "declare_attackers", 6: "declare_blockers",
    7: "combat_damage", 8: "end_combat",
}

_BEGINNING_STEP_NAMES = {1: "upkeep", 2: "draw_step", 3: "draw_step"}

# SurveilImportService に渡す際にスキップするイベント種別
_SKIP_EVENT_TYPES = frozenset({
    "turn_start", "phase_change",
    "ability_mana", "ability_resolved",
    "resolve", "life_change",
})

# event_type → action_type
_EVENT_TO_ACTION: dict[str, str] = {
    "cast":              "cast",
    "play_land":         "play",
    "draw":              "draw",
    "discard":           "discard",
    "mulligan":          "mulligan",
    "attack":            "attack",
    "block":             "block",
    "ability_activated": "activate",
    "ability_triggered": "trigger",
    "mill":              "mill",
    "damage":            "damage",
}


def _phase_name(phase: int, step: int) -> str:
    if phase == 1:
        return _BEGINNING_STEP_NAMES.get(step, "beginning")
    if phase == 2:
        return "main1"
    if phase == 3:
        return _COMBAT_STEP_NAMES.get(step, "combat")
    if phase == 4:
        return "main2"
    if phase == 5:
        return "ending"
    return "unknown"


# ─── 内部データ構造 ───────────────────────────────────────────────────────────

@dataclass
class _EventData:
    seq: int
    turn: int
    phase: str
    event_type: str
    detail: dict = field(default_factory=dict)


@dataclass
class _GameContext:
    game_number: int
    turn_number: int = 0
    mtgo_turn_number: int = 0
    active_player_seat: int = 0
    phase: str = "beginning"
    events: list[_EventData] = field(default_factory=list)
    sequence: int = 0

    def next_seq(self) -> int:
        self.sequence += 1
        return self.sequence

    def add_event(self, event_type: str, **detail) -> None:
        self.events.append(_EventData(
            seq=self.next_seq(),
            turn=self.mtgo_turn_number,
            phase=self.phase,
            event_type=event_type,
            detail={k: v for k, v in detail.items() if v is not None},
        ))


@dataclass
class _MatchContext:
    players: list[str]
    current_game: int = 0
    games: list[_GameContext] = field(default_factory=list)
    grp_id_map: dict[int, int] = field(default_factory=dict)    # instanceId → grpId
    zone_owner: dict[int, int] = field(default_factory=dict)    # zoneId → ownerSeatId
    target_map: dict[int, list[int]] = field(default_factory=dict)  # affectorId → affectedIds
    obj_name_map: dict[int, str] = field(default_factory=dict)  # grpId → 合成カード名（fallback用）


# ─── エントリーポイント ────────────────────────────────────────────────────────

def parse_gre_json(data: dict) -> GREParseResult:
    """
    schema_version=3 の Surveil JSON を受け取り GREParseResult を返す。
    grpId は未解決のまま返す（呼び出し元が fetch_by_arena_ids() で解決する）。
    """
    version = data.get("schema_version")
    if version != 3:
        raise ParseError(f"Expected schema_version=3, got {version!r}")

    match_id = data.get("match_id", "")
    if not match_id:
        raise ParseError("match_id is missing")

    players: list[str] = data.get("players", [])
    self_seat_id: int = data.get("self_seat_id", 1)
    match_winner: str = data.get("match_winner", "")
    deck_grp_ids: list[int] = data.get("deck_grp_ids", [])
    sideboard_grp_ids: list[int] = data.get("sideboard_grp_ids", [])
    event_name: Optional[str] = data.get("event_name")

    played_at_str = data.get("played_at", "")
    try:
        played_at = datetime.fromisoformat(played_at_str)
    except (ValueError, TypeError):
        played_at = datetime.now(tz=timezone.utc)

    self_player = (
        players[self_seat_id - 1]
        if 0 < self_seat_id <= len(players)
        else (players[0] if players else "")
    )

    # gre_messages からイベントを抽出
    ctx = _MatchContext(players=players)
    for payload in data.get("gre_messages", []):
        _process_payload(payload, ctx)

    # top-level の games メタデータ（winner / turns / first_player / mulligans）とマージ
    games_meta: dict[int, dict] = {g["game_number"]: g for g in data.get("games", [])}

    games: list[GREGame] = []
    for game_ctx in ctx.games:
        meta = games_meta.get(game_ctx.game_number, {})
        mulligans = [
            {"player_name": m.get("player_name", ""), "count": m.get("count", 0)}
            for m in meta.get("mulligans", [])
        ]
        actions = _events_to_actions(game_ctx, ctx)
        games.append(GREGame(
            game_number=game_ctx.game_number,
            winner=meta.get("winner", ""),
            turns=meta.get("turns", 0),
            first_player=meta.get("first_player", ""),
            mulligans=mulligans,
            actions=actions,
        ))

    # バッチ解決のために全 grpId を収集
    all_grp_ids: set[int] = set(deck_grp_ids) | set(sideboard_grp_ids)
    for game in games:
        for act in game["actions"]:
            if act["grp_id"] is not None:
                all_grp_ids.add(act["grp_id"])
            if act["target_grp_id"] is not None:
                all_grp_ids.add(act["target_grp_id"])

    return GREParseResult(
        match_id=match_id,
        source="mtga",
        players=players,
        self_seat_id=self_seat_id,
        self_player=self_player,
        match_winner=match_winner,
        played_at=played_at,
        deck_grp_ids=deck_grp_ids,
        sideboard_grp_ids=sideboard_grp_ids,
        games=games,
        all_grp_ids=all_grp_ids,
        obj_name_map=ctx.obj_name_map,
        event_name=event_name,
    )


# ─── イベント変換 ─────────────────────────────────────────────────────────────

def _events_to_actions(
    game_ctx: _GameContext,
    ctx: _MatchContext,
) -> list[GREGameAction]:
    """_EventData のリストを GREGameAction のリストに変換する。"""
    active_player = ""
    actions: list[GREGameAction] = []

    for event in game_ctx.events:
        et = event.event_type
        detail = event.detail

        if et == "turn_start":
            active_player = detail.get("active_player", active_player)
            continue

        if et in _SKIP_EVENT_TYPES:
            continue

        action_type = _EVENT_TO_ACTION.get(et)
        if action_type is None:
            continue

        player: str = detail.get("player", "")
        grp_id: int | None = detail.get("grp_id")
        target_player: str | None = None
        target_grp_id: int | None = None

        if et == "cast":
            targets = detail.get("targets", [])
            if targets:
                t = targets[0]
                target_player = t.get("player")
                target_grp_id = t.get("grp_id")

        elif et == "attack":
            target_player = detail.get("target_player")

        elif et == "block":
            blocking = detail.get("blocking_grp_ids", [])
            if blocking:
                target_grp_id = blocking[0]

        elif et == "damage":
            grp_id = detail.get("source_grp_id")
            target_player = detail.get("target_player")
            target_grp_id = detail.get("target_grp_id")

        elif et in ("ability_activated", "ability_triggered"):
            grp_id = detail.get("source_grp_id")

        # draw: カード不明（相手の非公開ドロー）はスキップ
        if et == "draw" and grp_id is None:
            continue

        actions.append(GREGameAction(
            seq=event.seq,
            turn=event.turn,
            phase=event.phase,
            action_type=action_type,
            player=player,
            active_player=active_player,
            grp_id=grp_id,
            target_player=target_player,
            target_grp_id=target_grp_id,
        ))

    return actions


# ─── GRE ペイロード処理 ───────────────────────────────────────────────────────

def _process_payload(data: dict, ctx: _MatchContext) -> None:
    """gre_messages の1要素を処理してコンテキストを更新する。"""
    mgr = data.get("matchGameRoomStateChangedEvent")
    if mgr:
        # Playing イベント: players はすでに top-level から取得済みのため何もしない
        return

    gre = data.get("greToClientEvent")
    if not gre:
        return

    for msg in gre.get("greToClientMessages", []):
        msg_type = msg.get("type", "")
        if msg_type == "GREMessageType_GameStateMessage":
            _handle_game_state(msg, ctx)
        elif msg_type == "GREMessageType_MulliganReq":
            _handle_mulligan_req(msg, ctx)
        elif msg_type == "GREMessageType_DeclareAttackersReq":
            _handle_declare_attackers(msg, ctx)
        elif msg_type == "GREMessageType_DeclareBlockersReq":
            _handle_declare_blockers(msg, ctx)


# ─── ヘルパー ─────────────────────────────────────────────────────────────────

_BASIC_LAND_SUBTYPES: frozenset[str] = frozenset({
    "Plains", "Island", "Swamp", "Mountain", "Forest",
})


def _synthesize_obj_name(obj: dict) -> Optional[str]:
    """
    gameObject の type / cardTypes / subtypes から合成カード名を作る。

    Scryfall の /cards/arena/{id} が 404 を返す場合のフォールバック用。
    合成対象を以下の2種に限定する（それ以外はサブタイプ≠カード名のため None）:

    1. GameObjectType_Token: "Warrior Token", "Treasure Token" など
       - トークンはサブタイプがそのまま型名になる慣習がある
    2. GameObjectType_Card + Land + 基本土地サブタイプ1種:
       "Forest", "Island" など（alt-art の arena_id が Scryfall 未収録）

    除外:
    - GameObjectType_Card + Creature/Planeswalker 等:
      サブタイプ（Dragon, Oko 等）はカード名と一致しないため合成しない
    - GameObjectType_Ability / TriggerHolder: カードオブジェクトではない
    """
    obj_type = obj.get("type", "")
    if obj_type in ("GameObjectType_TriggerHolder", "GameObjectType_Ability"):
        return None

    card_types = obj.get("cardTypes", [])
    subtypes = [s.replace("SubType_", "") for s in obj.get("subtypes", [])]

    # 1. トークン: サブタイプから "Warrior Token" 等を合成
    if obj_type == "GameObjectType_Token":
        if subtypes:
            return " ".join(subtypes) + " Token"
        if card_types:
            return " ".join(ct.replace("CardType_", "") for ct in card_types) + " Token"
        return None

    # 2. 基本土地の alt-art: 単一の基本土地サブタイプのみ許可
    if (card_types == ["CardType_Land"]
            and len(subtypes) == 1
            and subtypes[0] in _BASIC_LAND_SUBTYPES):
        return subtypes[0]

    # それ以外の GameObjectType_Card は Scryfall に収録されていないカード or 特殊オブジェクト。
    # サブタイプからカード名を正確に特定できないため None を返す。
    return None


def _to_mtgo_turn(mtga_turn: int) -> int:
    return (mtga_turn + 1) // 2


def _current_game(ctx: _MatchContext) -> Optional[_GameContext]:
    return ctx.games[-1] if ctx.games else None


def _seat_to_name(seat: int, ctx: _MatchContext) -> str:
    idx = seat - 1
    if 0 <= idx < len(ctx.players):
        return ctx.players[idx]
    return f"seat{seat}"


def _get_detail_value(details: list[dict], key: str) -> Optional[list]:
    for d in details:
        if d.get("key") == key:
            return d.get("valueInt32") or d.get("valueString") or d.get("valueFloat")
    return None


# ─── 個別ハンドラ ─────────────────────────────────────────────────────────────

def _handle_game_state(msg: dict, ctx: _MatchContext) -> None:
    gsm = msg.get("gameStateMessage", {})
    gsm_type = gsm.get("type", "")

    # ゲーム番号の更新
    gi = gsm.get("gameInfo", {})
    game_number = gi.get("gameNumber", 0)
    stage = gi.get("stage", "")

    if game_number and game_number != ctx.current_game:
        if stage == "GameStage_Start":
            ctx.current_game = game_number
            ctx.games.append(_GameContext(game_number))

    game_ctx = _current_game(ctx)

    # GameStateType_Full: ゾーンマップを再構築; Diff: 新規ゾーンを追記
    if gsm_type == "GameStateType_Full":
        ctx.zone_owner = {}
    for zone in gsm.get("zones", []):
        zone_id = zone.get("zoneId")
        owner = zone.get("ownerSeatId")
        if zone_id is not None and owner is not None:
            ctx.zone_owner[zone_id] = owner

    # gameObjects: instanceId → grpId を累積 / grpId の合成名を登録
    for obj in gsm.get("gameObjects", []):
        inst_id = obj.get("instanceId")
        grp_id = obj.get("grpId")
        if inst_id is not None and grp_id:
            ctx.grp_id_map[inst_id] = grp_id
            if grp_id not in ctx.obj_name_map:
                synth = _synthesize_obj_name(obj)
                if synth:
                    ctx.obj_name_map[grp_id] = synth

    # turnInfo: ターン番号とアクティブプレイヤーを更新
    turn_info = gsm.get("turnInfo", {})
    turn_number = turn_info.get("turnNumber")
    active_player = turn_info.get("activePlayer")

    if game_ctx is None:
        return

    if turn_number is not None:
        game_ctx.turn_number = turn_number
        game_ctx.mtgo_turn_number = _to_mtgo_turn(turn_number)
    if active_player is not None:
        game_ctx.active_player_seat = active_player

    # persistentAnnotations: TargetSpec を累積
    for ann in gsm.get("persistentAnnotations", []):
        if "AnnotationType_TargetSpec" in ann.get("type", []):
            affector = ann.get("affectorId")
            affected = ann.get("affectedIds", [])
            if affector is not None and affected:
                ctx.target_map[affector] = affected

    # annotations の事前スキャン（UserActionTaken を収集）
    user_actions: dict[int, dict] = {}
    for ann in gsm.get("annotations", []):
        if "AnnotationType_UserActionTaken" in ann.get("type", []):
            details = ann.get("details", [])
            action_type = _get_detail_value(details, "actionType")
            if action_type and action_type[0] == 4:
                affected = ann.get("affectedIds", [])
                if affected:
                    user_actions[affected[0]] = ann

    # annotations からイベントを抽出
    for ann in gsm.get("annotations", []):
        ann_types = ann.get("type", [])

        if "AnnotationType_ObjectIdChanged" in ann_types:
            _handle_id_changed(ann, ctx)

        elif "AnnotationType_NewTurnStarted" in ann_types:
            player_name = _seat_to_name(game_ctx.active_player_seat, ctx)
            game_ctx.add_event("turn_start", active_player=player_name)

        elif "AnnotationType_PhaseOrStepModified" in ann_types:
            _handle_phase_change(ann, game_ctx)

        elif "AnnotationType_ZoneTransfer" in ann_types:
            _handle_zone_transfer(ann, game_ctx, ctx)

        elif "AnnotationType_DamageDealt" in ann_types:
            _handle_damage(ann, game_ctx, ctx)

        elif "AnnotationType_ModifiedLife" in ann_types:
            _handle_life_change(ann, game_ctx, ctx)

        elif "AnnotationType_AbilityInstanceCreated" in ann_types:
            _handle_ability_created(ann, user_actions, game_ctx, ctx)

        elif "AnnotationType_AbilityInstanceDeleted" in ann_types:
            _handle_ability_deleted(ann, game_ctx, ctx)


def _handle_id_changed(ann: dict, ctx: _MatchContext) -> None:
    details = ann.get("details", [])
    orig = _get_detail_value(details, "orig_id")
    new = _get_detail_value(details, "new_id")
    if not (orig and new):
        return
    old_grp = ctx.grp_id_map.get(orig[0])
    if old_grp:
        ctx.grp_id_map[new[0]] = old_grp
    if orig[0] in ctx.target_map:
        ctx.target_map[new[0]] = ctx.target_map.pop(orig[0])


def _handle_phase_change(ann: dict, game_ctx: _GameContext) -> None:
    details = ann.get("details", [])
    phase_val = _get_detail_value(details, "phase")
    step_val  = _get_detail_value(details, "step")
    if not phase_val:
        return
    new_phase = _phase_name(phase_val[0], step_val[0] if step_val else 0)
    if new_phase != game_ctx.phase:
        game_ctx.phase = new_phase
        game_ctx.add_event("phase_change", phase=new_phase)


def _handle_zone_transfer(ann: dict, game_ctx: _GameContext, ctx: _MatchContext) -> None:
    details = ann.get("details", [])
    category_list = _get_detail_value(details, "category")
    if not category_list:
        return

    category = category_list[0]
    event_type = _ZONE_TRANSFER_EVENTS.get(category)
    if event_type is None:
        return

    affected_ids = ann.get("affectedIds", [])
    if not affected_ids:
        return

    instance_id = affected_ids[0]
    grp_id = ctx.grp_id_map.get(instance_id)

    zone_src_list  = _get_detail_value(details, "zone_src")
    zone_dest_list = _get_detail_value(details, "zone_dest")

    if event_type in ("cast", "play_land", "discard", "mill"):
        zone_id = zone_src_list[0] if zone_src_list else None
    else:
        zone_id = zone_dest_list[0] if zone_dest_list else None

    player_seat = ctx.zone_owner.get(zone_id) if zone_id is not None else None
    player_name = _seat_to_name(player_seat, ctx) if player_seat else None

    detail: dict = {}
    if player_name:
        detail["player"] = player_name
    if grp_id:
        detail["grp_id"] = grp_id
    else:
        detail["instance_id"] = instance_id

    if event_type == "cast":
        raw_targets = ctx.target_map.get(instance_id, [])
        if raw_targets:
            targets = []
            for t in raw_targets:
                if t in (1, 2):
                    targets.append({"player": _seat_to_name(t, ctx)})
                else:
                    tgrp = ctx.grp_id_map.get(t)
                    if tgrp:
                        targets.append({"grp_id": tgrp})
                    else:
                        targets.append({"instance_id": t})
            detail["targets"] = targets

    game_ctx.events.append(_EventData(
        seq=game_ctx.next_seq(),
        turn=game_ctx.mtgo_turn_number,
        phase=game_ctx.phase,
        event_type=event_type,
        detail=detail,
    ))


def _handle_damage(ann: dict, game_ctx: _GameContext, ctx: _MatchContext) -> None:
    details = ann.get("details", [])
    damage_list = _get_detail_value(details, "damage")
    type_list   = _get_detail_value(details, "type")
    if not damage_list:
        return

    amount = damage_list[0]
    damage_type_val = type_list[0] if type_list else 0
    damage_type_str = "combat" if damage_type_val == 1 else "noncombat"

    affector_id = ann.get("affectorId")
    affected_ids = ann.get("affectedIds", [])
    target_id = affected_ids[0] if affected_ids else None

    source_grp = ctx.grp_id_map.get(affector_id) if affector_id else None

    detail: dict = {"amount": amount, "damage_type": damage_type_str}
    if source_grp:
        detail["source_grp_id"] = source_grp
    elif affector_id:
        detail["source_instance_id"] = affector_id

    if target_id in (1, 2):
        detail["target_player"] = _seat_to_name(target_id, ctx)
    elif target_id is not None:
        target_grp = ctx.grp_id_map.get(target_id)
        if target_grp:
            detail["target_grp_id"] = target_grp
        else:
            detail["target_instance_id"] = target_id

    game_ctx.events.append(_EventData(
        seq=game_ctx.next_seq(),
        turn=game_ctx.mtgo_turn_number,
        phase=game_ctx.phase,
        event_type="damage",
        detail=detail,
    ))


def _handle_life_change(ann: dict, game_ctx: _GameContext, ctx: _MatchContext) -> None:
    details = ann.get("details", [])
    life_list = _get_detail_value(details, "life")
    if not life_list:
        return
    delta = life_list[0]
    affected_ids = ann.get("affectedIds", [])
    seat = affected_ids[0] if affected_ids else None
    if seat not in (1, 2):
        return
    game_ctx.add_event(
        "life_change",
        player=_seat_to_name(seat, ctx),
        delta=delta,
    )


def _handle_mulligan_req(msg: dict, ctx: _MatchContext) -> None:
    # マリガン情報は schema_version=3 の top-level games.mulligans から取得するため、ここでは何もしない
    pass


def _handle_declare_attackers(msg: dict, ctx: _MatchContext) -> None:
    game_ctx = _current_game(ctx)
    if game_ctx is None:
        return

    req = msg.get("declareAttackersReq", {})
    for attacker in req.get("attackers", []):
        inst_id = attacker.get("attackerInstanceId")
        if inst_id is None:
            continue

        grp_id = ctx.grp_id_map.get(inst_id)
        attacker_name = _seat_to_name(game_ctx.active_player_seat, ctx)

        recipient = attacker.get("selectedDamageRecipient", {})
        target_player = None
        if recipient.get("type") == "DamageRecType_Player":
            target_seat = recipient.get("playerSystemSeatId")
            if target_seat:
                target_player = _seat_to_name(target_seat, ctx)

        detail: dict = {"player": attacker_name}
        if grp_id:
            detail["grp_id"] = grp_id
        else:
            detail["instance_id"] = inst_id
        if target_player:
            detail["target_player"] = target_player

        game_ctx.events.append(_EventData(
            seq=game_ctx.next_seq(),
            turn=game_ctx.mtgo_turn_number,
            phase=game_ctx.phase,
            event_type="attack",
            detail=detail,
        ))


def _handle_declare_blockers(msg: dict, ctx: _MatchContext) -> None:
    game_ctx = _current_game(ctx)
    if game_ctx is None:
        return

    req = msg.get("declareBlockersReq", {})
    blocker_seat = next(
        (s for s in (1, 2) if s != game_ctx.active_player_seat), None
    )
    blocker_name = _seat_to_name(blocker_seat, ctx) if blocker_seat else ""

    for blocker in req.get("blockers", []):
        blocker_inst = blocker.get("blockerInstanceId")
        if blocker_inst is None:
            continue

        blocker_grp = ctx.grp_id_map.get(blocker_inst)
        attacker_insts = blocker.get("attackerInstanceIds", [])
        attacker_grp_ids = [
            ctx.grp_id_map.get(a) for a in attacker_insts
            if ctx.grp_id_map.get(a)
        ]

        detail: dict = {"player": blocker_name}
        if blocker_grp:
            detail["grp_id"] = blocker_grp
        else:
            detail["instance_id"] = blocker_inst
        if attacker_grp_ids:
            detail["blocking_grp_ids"] = attacker_grp_ids

        game_ctx.events.append(_EventData(
            seq=game_ctx.next_seq(),
            turn=game_ctx.mtgo_turn_number,
            phase=game_ctx.phase,
            event_type="block",
            detail=detail,
        ))


def _handle_ability_created(
    ann: dict,
    user_actions: dict[int, dict],
    game_ctx: _GameContext,
    ctx: _MatchContext,
) -> None:
    affected = ann.get("affectedIds", [])
    if not affected:
        return

    ability_inst_id = affected[0]
    source_inst_id = ann.get("affectorId")
    source_grp = ctx.grp_id_map.get(source_inst_id) if source_inst_id else None

    details = ann.get("details", [])
    source_zone_list = _get_detail_value(details, "source_zone")
    source_zone = source_zone_list[0] if source_zone_list else None

    action_ann = user_actions.get(ability_inst_id)
    if action_ann:
        action_details = action_ann.get("details", [])
        ability_grp_id_list = _get_detail_value(action_details, "abilityGrpId")
        ability_grp_id = ability_grp_id_list[0] if ability_grp_id_list else None

        player_seat = action_ann.get("affectorId")
        player_name = _seat_to_name(player_seat, ctx) if player_seat in (1, 2) else None

        is_mana = ability_grp_id in _MANA_ABILITY_GRP_IDS
        event_type = "ability_mana" if is_mana else "ability_activated"

        detail: dict = {}
        if player_name:
            detail["player"] = player_name
        if source_grp:
            detail["source_grp_id"] = source_grp
        elif source_inst_id:
            detail["source_instance_id"] = source_inst_id
        if ability_grp_id is not None:
            detail["ability_grp_id"] = ability_grp_id
        if not is_mana and source_zone is not None:
            detail["source_zone"] = source_zone
    else:
        event_type = "ability_triggered"
        detail = {}
        if source_grp:
            detail["source_grp_id"] = source_grp
        elif source_inst_id:
            detail["source_instance_id"] = source_inst_id
        if source_zone is not None:
            detail["source_zone"] = source_zone

    game_ctx.events.append(_EventData(
        seq=game_ctx.next_seq(),
        turn=game_ctx.mtgo_turn_number,
        phase=game_ctx.phase,
        event_type=event_type,
        detail=detail,
    ))


def _handle_ability_deleted(ann: dict, game_ctx: _GameContext, ctx: _MatchContext) -> None:
    source_inst_id = ann.get("affectorId")
    source_grp = ctx.grp_id_map.get(source_inst_id) if source_inst_id else None

    detail: dict = {}
    if source_grp:
        detail["source_grp_id"] = source_grp
    elif source_inst_id:
        detail["source_instance_id"] = source_inst_id

    game_ctx.events.append(_EventData(
        seq=game_ctx.next_seq(),
        turn=game_ctx.mtgo_turn_number,
        phase=game_ctx.phase,
        event_type="ability_resolved",
        detail=detail,
    ))
