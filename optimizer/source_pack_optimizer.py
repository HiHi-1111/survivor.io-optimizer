"""Exact after-state ranking for source-pack actions.

Only actions with a complete legal state transition and a scoreable sIO Clan
Expedition after-state are ranked. Unsupported systems are returned with an
explicit rejection reason instead of receiving heuristic points.
"""

from __future__ import annotations

from copy import deepcopy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from optimizer.player_state import PlayerState
from optimizer.sio_ce_account import compare_clan_expedition_profiles

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PACK_DIR = ROOT / "knowledge" / "source_pack"
STAR_LABELS = ["Base", "Y1", "Y2", "Y3", "Y4", "R1", "R2", "R3", "R4"]
MOUNT_IDS = {
    "electric_scooter": "Electric Scooter",
    "hoverboard": "Tech Hoverboard",
    "tech_hoverboard": "Tech Hoverboard",
    "doomsteed": "Doomsteed",
}


@lru_cache(maxsize=1)
def load_source_pack_actions() -> list[dict[str, Any]]:
    path = SOURCE_PACK_DIR / "action_templates.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        actions = json.load(handle)
    return [action for action in actions if action.get("enabled")]


def clear_source_pack_cache() -> None:
    load_source_pack_actions.cache_clear()


def _profile_data(profile: PlayerState | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(profile, PlayerState):
        return profile.model_dump()
    return deepcopy(dict(profile))


def _resource_counts(profile: Mapping[str, Any]) -> dict[str, float]:
    counts: dict[str, float] = {}
    sections = [profile.get("resources", {})]
    inventory = profile.get("inventory", {})
    if isinstance(inventory, Mapping):
        sections.append(inventory.get("items", {}))
    for section in sections:
        if not isinstance(section, Mapping):
            continue
        for key, value in section.items():
            amount = value
            if isinstance(value, Mapping):
                amount = value.get("count", value.get("quantity", 0))
            if isinstance(amount, (int, float)):
                counts[str(key)] = counts.get(str(key), 0.0) + float(amount)
    return counts


def _cost_gate(action: Mapping[str, Any], resources: Mapping[str, float]) -> str | None:
    for cost in action.get("costs", []) or []:
        resource_id = str(cost.get("resource_id"))
        required = float(cost.get("amount", 0) or 0)
        available = float(resources.get(resource_id, 0) or 0)
        if required < 0:
            return f"invalid_negative_cost:{resource_id}"
        if available < required:
            return f"insufficient_{resource_id}:requires_{required:g}:has_{available:g}"
    return None


def _mount_container(profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    mounts = profile.setdefault("mounts", {})
    if not isinstance(mounts, dict):
        mounts = {}
        profile["mounts"] = mounts
    data = mounts.get("data")
    if not isinstance(data, dict):
        data = {key: value for key, value in mounts.items() if key != "active"}
        mounts["data"] = data
    return mounts, data


def _mount_state(profile: dict[str, Any], mount_id: str) -> dict[str, Any] | None:
    _mounts, data = _mount_container(profile)
    name = MOUNT_IDS.get(mount_id, mount_id)
    state = data.get(name)
    if isinstance(state, str):
        return {"enabled": True, "rarity": state, "stars": STAR_LABELS.index(state) if state in STAR_LABELS else 0}
    return state if isinstance(state, dict) else None


def _target_star(action: Mapping[str, Any]) -> int | None:
    label = str(action.get("unlock_target", ""))
    return STAR_LABELS.index(label) if label in STAR_LABELS else None


def _simulate_mount_action(action: Mapping[str, Any], profile: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    target_id = str(action.get("target_id", ""))
    name = MOUNT_IDS.get(target_id)
    if not name:
        return None, f"unknown_mount_id:{target_id}"
    mounts, data = _mount_container(profile)
    state = data.get(name)
    if not isinstance(state, dict) or not bool(state.get("enabled", False)):
        return None, f"mount_not_owned:{target_id}"
    target = _target_star(action)
    if target is None:
        return None, f"unknown_mount_target:{action.get('unlock_target')}"
    current = state.get("stars")
    if current is None:
        rarity = str(state.get("rarity", "Base"))
        current = STAR_LABELS.index(rarity) if rarity in STAR_LABELS else 0
    current = int(current)
    if current != target - 1:
        required = STAR_LABELS[target - 1] if target > 0 else "unowned"
        return None, f"star_gate:requires_{required}:has_{STAR_LABELS[current] if 0 <= current < len(STAR_LABELS) else current}"
    state["stars"] = target
    state["rarity"] = STAR_LABELS[target]
    data[name] = state
    mounts["data"] = data
    return profile, None


def _score_action(action: dict[str, Any], profile: dict[str, Any], resources: Mapping[str, float]) -> tuple[dict[str, Any] | None, str | None]:
    cost_reason = _cost_gate(action, resources)
    if cost_reason:
        return None, cost_reason
    if action.get("system") != "mounts" or action.get("action_type") != "upgrade_mount":
        return None, f"missing_exact_after_state_bridge:{action.get('system')}:{action.get('action_type')}"
    after, reason = _simulate_mount_action(action, deepcopy(profile))
    if reason or after is None:
        return None, reason
    comparison = compare_clan_expedition_profiles(profile, after)
    if not comparison.get("supported"):
        return None, "before_or_after_state_not_scoreable"
    delta = float(comparison["delta"])
    percent = comparison.get("percent_gain")
    total_cost = sum(float(cost.get("amount", 0) or 0) for cost in action.get("costs", []) or [])
    return {
        **action,
        "expected_dps_gain": delta,
        "estimated_dps_value": delta,
        "percent_damage_gain": percent,
        "score": delta,
        "total_cost_units": total_cost,
        "resource_cost_penalty": 0.0,
        "before_damage": comparison["before"]["total_damage"],
        "after_damage": comparison["after"]["total_damage"],
        "damage_formula_provenance": comparison["after"]["formula_provenance"],
        "legality": "resource_and_state_gates_passed",
    }, None


def _optimize_one(profile_input: PlayerState | Mapping[str, Any], top_k: int) -> dict[str, Any]:
    profile = _profile_data(profile_input)
    resources = _resource_counts(profile)
    ranked: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for action in load_source_pack_actions():
        candidate, reason = _score_action(action, profile, resources)
        if candidate is None:
            rejected.append({"action_id": str(action.get("action_id")), "reason": str(reason)})
        else:
            ranked.append(candidate)
    ranked.sort(key=lambda row: (-float(row["expected_dps_gain"]), float(row["total_cost_units"]), str(row["action_id"])))
    ranked = ranked[: max(0, top_k)]
    best_spend = ranked[0] if ranked and float(ranked[0]["expected_dps_gain"]) > 0 else None
    baseline = {
        "action_id": "save_hold_no_op",
        "system": "baseline",
        "action_type": "save_hold",
        "expected_dps_gain": 0.0,
        "score": 0.0,
        "costs": [],
    }
    return {
        "best": best_spend,
        "best_including_no_op": best_spend or baseline,
        "no_op_baseline": baseline,
        "no_action_recommended": best_spend is None,
        "ranked_actions": ranked,
        "ranked_alternatives": ranked[1:] if best_spend else ranked,
        "templates_considered": len(load_source_pack_actions()),
        "actionable_count": len(ranked),
        "rejected_count": len(rejected),
        "rejected_actions": rejected,
        "deduplicated_actions": [],
        "false_prunes": [],
        "pruning_policy": "none; exact legal after-states only",
        "warnings": [
            "Only exact mount upgrade after-states are bridged today; all other systems remain unknown rather than heuristically ranked."
        ],
        "explanation": (
            f"{best_spend['action_id']} has the largest exact sIO Clan Expedition damage gain."
            if best_spend else "No legal source-pack action produced positive exact Clan Expedition damage."
        ),
    }


def optimize_source_pack_batch(
    player_states: list[PlayerState | Mapping[str, Any]], *, top_k: int = 10, device: str = "auto"
) -> dict[str, Any]:
    results = [_optimize_one(profile, top_k) for profile in player_states]
    return {
        "profiles": results,
        "numeric_backend": {
            "backend": "deterministic_cpu_exact_sio_ce",
            "requested_device": device,
            "learned_or_gpu_ranking_used": False,
        },
        "profile_feature_matrix_shape": [0, 0],
        "inventory_feature_matrix_shape": [0, 0],
    }


def optimize_source_pack_actions(
    player_state: PlayerState | Mapping[str, Any], *, top_k: int = 10, device: str = "auto"
) -> dict[str, Any]:
    batch = optimize_source_pack_batch([player_state], top_k=top_k, device=device)
    result = batch["profiles"][0]
    result["numeric_backend"] = batch["numeric_backend"]
    return result
