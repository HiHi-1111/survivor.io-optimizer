"""Exact legal after-state ranking for Clan Expedition actions.

The final winner is always the largest before/after sIO CE damage delta. Learned
models may order evaluation elsewhere, but they cannot alter this module's
winner. Every profile baseline and legal after-state is flattened into one sIO
runtime batch so a multi-profile request starts at most one uncached Node process.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Mapping

from optimizer.player_state import PlayerState
from optimizer.sio_ce_account import calculate_clan_expedition_damage_batch
from optimizer.sio_choice_chests import expand_actions_with_choice_chests
from optimizer.sio_effect_evaluator import evaluate_preflight_transitions
from optimizer.sio_exact_actions import (
    affordability_certificate,
    apply_exact_action,
    generate_exact_actions,
    resource_counts,
)
from optimizer.sio_item_reallocations import generate_exhaustive_item_reallocations
from optimizer.sio_mount_puzzle_bridge import apply_verified_mount_puzzle_stats
from optimizer.sio_pet_configurations import generate_pet_configuration_actions
from optimizer.sio_progression_frontiers import generate_progression_frontiers
from optimizer.sio_survivor_configurations import plan_survivor_configurations
from optimizer.sio_tech_configurations import generate_twinborn_mode_actions
from optimizer.sio_tech_progression import generate_tech_progression_actions

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PACK_DIR = ROOT / "knowledge" / "source_pack"
STAR_LABELS = ["Base", "Y1", "Y2", "Y3", "Y4", "R1", "R2", "R3", "R4"]
MOUNT_IDS = {
    "electric_scooter": "Electric Scooter",
    "hoverboard": "Tech Hoverboard",
    "tech_hoverboard": "Tech Hoverboard",
    "doomsteed": "Doomsteed",
}
MOUNT_PUBLIC_IDS = {
    "Electric Scooter": "electric_scooter",
    "Tech Hoverboard": "hoverboard",
    "Doomsteed": "doomsteed",
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


def _plain(value: Any) -> Any:
    """Recursively remove Pydantic/model wrappers without dropping extra fields."""
    if hasattr(value, "model_dump") and callable(value.model_dump):
        value = value.model_dump()
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return deepcopy(value)


def _profile_data(profile: PlayerState | Mapping[str, Any]) -> dict[str, Any]:
    normalized = _plain(profile)
    if not isinstance(normalized, dict):
        raise TypeError("player state must normalize to a mapping")
    normalized, puzzle_report = apply_verified_mount_puzzle_stats(normalized)
    audit = normalized.get("_sio_optimizer_audit")
    if not isinstance(audit, dict):
        audit = {}
    audit["mount_puzzle_bridge"] = puzzle_report
    normalized["_sio_optimizer_audit"] = audit
    return normalized


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


def _simulate_legacy_mount_action(
    action: Mapping[str, Any], profile: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None]:
    target_id = str(action.get("target_id", ""))
    name = MOUNT_IDS.get(target_id)
    if not name:
        return None, f"unknown_mount_id:{target_id}"
    mounts, data = _mount_container(profile)
    state = data.get(name)
    if not isinstance(state, dict) or not bool(state.get("enabled", False)):
        return None, f"mount_not_owned:{target_id}"
    label = str(action.get("unlock_target", ""))
    target = STAR_LABELS.index(label) if label in STAR_LABELS else None
    if target is None:
        return None, f"unknown_mount_target:{label}"
    current = state.get("stars")
    if current is None:
        rarity = str(state.get("rarity", "Base"))
        current = STAR_LABELS.index(rarity) if rarity in STAR_LABELS else 0
    current = int(current)
    if current != target - 1:
        required = STAR_LABELS[target - 1] if target > 0 else "unowned"
        actual = STAR_LABELS[current] if 0 <= current < len(STAR_LABELS) else current
        return None, f"star_gate:requires_{required}:has_{actual}"
    state["stars"] = target
    state["rarity"] = STAR_LABELS[target]
    data[name] = state
    mounts["data"] = data
    return profile, None


def _legacy_cost_certificate(profile: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any]:
    available = resource_counts(profile)
    consumed = {
        str(cost.get("resource_id")): float(cost.get("amount", 0) or 0)
        for cost in action.get("costs", []) or []
    }
    missing = {
        key: amount - available.get(key, 0.0)
        for key, amount in consumed.items()
        if amount < 0 or available.get(key, 0.0) + 1e-9 < amount
    }
    return {
        "legal": not missing,
        "available": available,
        "consumed": consumed,
        "refunded": {},
        "missing": missing,
        "balanced": all(value >= 0 for value in consumed.values()),
    }


def _transition(
    action: Mapping[str, Any], profile: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
    if isinstance(action.get("state_patch"), Mapping):
        certificate = affordability_certificate(profile, action)
        try:
            after = apply_exact_action(profile, action)
        except (TypeError, ValueError) as error:
            return None, None, f"invalid_state_patch:{error}"
    elif action.get("system") == "mounts" and action.get("action_type") == "upgrade_mount":
        certificate = _legacy_cost_certificate(profile, action)
        after, reason = _simulate_legacy_mount_action(action, deepcopy(profile))
        if reason or after is None:
            return None, None, reason
    else:
        return None, None, f"missing_exact_after_state_bridge:{action.get('system')}:{action.get('action_type')}"

    if not certificate.get("balanced"):
        return None, None, "unbalanced_or_negative_resource_ledger"
    if not certificate.get("legal"):
        missing = certificate.get("missing") or {}
        reason = "insufficient_resources:" + ",".join(
            f"{key}={value:g}" for key, value in sorted(missing.items())
        )
        return None, None, reason
    return after, dict(certificate), None


def _public_action_id(action: Mapping[str, Any]) -> str:
    if action.get("system") == "mounts" and str(action.get("action_type", "")).startswith("upgrade_mount"):
        metadata = action.get("metadata") if isinstance(action.get("metadata"), Mapping) else {}
        name = metadata.get("mount")
        target = metadata.get("target_stars")
        if name in MOUNT_PUBLIC_IDS and isinstance(target, (int, float)):
            target_index = int(target)
            if 0 <= target_index < len(STAR_LABELS):
                return f"upgrade_{MOUNT_PUBLIC_IDS[str(name)]}_{STAR_LABELS[target_index].lower()}"
    return str(action.get("action_id"))


def _action_key(action: Mapping[str, Any]) -> str:
    if isinstance(action.get("state_patch"), Mapping):
        return json.dumps(
            {
                "patch": action.get("state_patch"),
                "consumed": action.get("consumed_items"),
                "refunded": action.get("refunded_items"),
                "choice_grants": action.get("choice_chest_grants"),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    return str(action.get("action_id"))


def _all_actions(
    profile: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    survivor_plan = plan_survivor_configurations(profile)
    pet_actions = generate_pet_configuration_actions(profile)
    configuration_searches = {
        "survivor_configurations": {
            "complete": survivor_plan.complete,
            "total_states": survivor_plan.total_states,
            "max_states": survivor_plan.max_states,
            "reason": survivor_plan.reason,
            "main_candidates": list(survivor_plan.main_candidates),
            "actions_generated": len(survivor_plan.actions),
            "teamwork_search": "unordered_combinations",
        },
        "pet_configurations": {
            "complete": True,
            "actions_generated": len(pet_actions),
            "identical_skill_roles": "unordered_combinations",
            "distinct_skill_roles": "role_specific_assignments",
        },
    }
    base_actions = [
        *generate_exact_actions(profile),
        *generate_exhaustive_item_reallocations(profile),
        *generate_twinborn_mode_actions(profile),
        *([deepcopy(action) for action in survivor_plan.actions] if survivor_plan.complete else []),
        *pet_actions,
        *generate_tech_progression_actions(profile),
        *generate_progression_frontiers(profile),
        *load_source_pack_actions(),
    ]
    # Selector chests are expanded only after exact complete after-states exist.
    # The expansion searches canonical count allocations and never ordered pick
    # sequences. Directional equipment source->target reallocations remain ordered
    # because reversing their roles is a genuinely different state transition.
    combined = expand_actions_with_choice_chests(profile, base_actions, resource_counts(profile))
    seen_keys: dict[str, str] = {}
    seen_ids: set[str] = set()
    result: list[dict[str, Any]] = []
    deduplicated: list[dict[str, str]] = []
    for source_action in combined:
        action = dict(source_action)
        action["action_id"] = _public_action_id(action)
        key = _action_key(action)
        action_id = str(action.get("action_id"))
        duplicate_of = seen_keys.get(key)
        if duplicate_of is not None:
            deduplicated.append(
                {
                    "action_id": action_id,
                    "duplicate_of": duplicate_of,
                    "reason": "equivalent_complete_after_state_and_ledger",
                }
            )
            continue
        if action_id in seen_ids:
            deduplicated.append(
                {
                    "action_id": action_id,
                    "duplicate_of": action_id,
                    "reason": "duplicate_action_id",
                }
            )
            continue
        seen_keys[key] = action_id
        seen_ids.add(action_id)
        result.append(action)
    return result, deduplicated, configuration_searches


def _candidate(
    action: Mapping[str, Any],
    certificate: Mapping[str, Any],
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    if not before.get("supported") or not after.get("supported"):
        reason = before.get("reason") or after.get("reason") or "unknown"
        return None, f"before_or_after_state_not_scoreable:{reason}"
    old = float(before["total_damage"])
    new = float(after["total_damage"])
    delta = new - old
    consumed = dict(certificate.get("consumed") or {})
    refunded = dict(certificate.get("refunded") or {})
    return {
        **dict(action),
        "consumed_items": consumed,
        "required_items": consumed,
        "refunded_items": refunded,
        "legality_certificate": dict(certificate),
        "expected_dps_gain": delta,
        "estimated_dps_value": delta,
        "percent_damage_gain": delta / old * 100.0 if old else None,
        "score": delta,
        "total_cost_units": sum(float(value) for value in consumed.values()),
        "resource_cost_penalty": 0.0,
        "before_damage": old,
        "after_damage": new,
        "damage_formula_provenance": after.get("formula_provenance", {}),
        "runtime_exact": bool(after.get("runtime_exact")),
        "legality": "balanced_resource_and_state_gates_passed",
    }, None


def _prepare_profile(profile_input: PlayerState | Mapping[str, Any]) -> dict[str, Any]:
    profile = _profile_data(profile_input)
    actions, deduplicated, configuration_searches = _all_actions(profile)
    transitions: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    rejected: list[dict[str, str]] = []
    for action in actions:
        after, certificate, reason = _transition(action, profile)
        if reason or after is None or certificate is None:
            rejected.append({"action_id": str(action.get("action_id")), "reason": str(reason)})
        else:
            transitions.append((action, after, certificate))
    preflight = evaluate_preflight_transitions(profile, transitions)
    audit = profile.get("_sio_optimizer_audit") if isinstance(profile.get("_sio_optimizer_audit"), Mapping) else {}
    return {
        "profile": profile,
        "actions": actions,
        "transitions": list(preflight["transitions"]),
        "preflight_skipped": list(preflight["skipped"]),
        "effect_preflight": deepcopy(dict(preflight["report"])),
        "rejected": rejected,
        "deduplicated": deduplicated,
        "configuration_searches": configuration_searches,
        "input_audit": deepcopy(dict(audit)),
    }


def _result_from_reports(prepared: Mapping[str, Any], reports: list[Mapping[str, Any]], top_k: int) -> dict[str, Any]:
    actions = list(prepared["actions"])
    transitions = list(prepared["transitions"])
    rejected = [dict(row) for row in prepared["rejected"]]
    deduplicated = [dict(row) for row in prepared.get("deduplicated", [])]
    configuration_searches = deepcopy(dict(prepared.get("configuration_searches") or {}))
    effect_preflight = deepcopy(dict(prepared.get("effect_preflight") or {}))
    preflight_skipped = [dict(row) for row in prepared.get("preflight_skipped", [])]
    configuration_complete = all(
        bool(report.get("complete", False))
        for report in configuration_searches.values()
        if isinstance(report, Mapping)
    )
    if not reports:
        reports = [{"supported": False, "reason": "missing_baseline_formula_report"}]
    before = reports[0]
    after_reports = reports[1:]
    ranked_all: list[dict[str, Any]] = []
    for index, (action, _after_profile, certificate) in enumerate(transitions):
        if index >= len(after_reports):
            rejected.append(
                {
                    "action_id": str(action.get("action_id")),
                    "reason": "missing_after_state_formula_report",
                }
            )
            continue
        candidate, reason = _candidate(action, certificate, before, after_reports[index])
        if candidate is None:
            rejected.append({"action_id": str(action.get("action_id")), "reason": str(reason)})
        else:
            ranked_all.append(candidate)

    ranked_all.sort(
        key=lambda row: (
            -float(row["expected_dps_gain"]),
            float(row["total_cost_units"]),
            str(row["action_id"]),
        )
    )
    ranked = ranked_all[: max(0, top_k)]
    best_evaluated = ranked_all[0] if ranked_all and float(ranked_all[0]["expected_dps_gain"]) > 0 else None
    best_spend = best_evaluated if configuration_complete else None
    baseline = {
        "action_id": "save_hold_no_op",
        "system": "baseline",
        "action_type": "save_hold",
        "expected_dps_gain": 0.0,
        "score": 0.0,
        "costs": [],
        "consumed_items": {},
        "refunded_items": {},
        "legality_certificate": {"legal": True, "balanced": True, "missing": {}},
    }
    warnings = [
        "Actions without an exact cumulative cost or state patch are rejected rather than guessed.",
        "Every exact cumulative progression frontier is evaluated, not only the next level.",
        "Every exact directional two-slot item reallocation frontier is evaluated before structural deduplication.",
        "Twinborn modes are evaluated as complete per-tech assignments, never item permutations.",
        "Teamwork members are evaluated as unordered combinations; Main and Harmony remain role-specific.",
        "Xeno support pets use combinations only inside identical skill-role groups; distinct skill roles remain directional.",
        "Choice chests use canonical multiset allocations, never pick-order permutations.",
        "Tetris layout geometry is excluded; only verified aggregate mount component stats are scored.",
        "every legal exact after-state is batch-scored unless the source-backed effect preflight proves zero CE delta; unknown effects are always exact-scored.",
        "runtime_exact=false means the auditable Python sIO port was used because the supplied runtime was unavailable.",
    ]
    if not configuration_complete:
        warnings.append(
            "A mapped exact configuration search exceeded its declared state budget, so the global recommendation is withheld rather than approximated."
        )
    return {
        "best": best_spend,
        "provisional_best_evaluated": best_evaluated if not configuration_complete else None,
        "best_including_no_op": best_spend or baseline,
        "no_op_baseline": baseline,
        "no_action_recommended": configuration_complete and best_spend is None,
        "recommendation_withheld": not configuration_complete,
        "optimization_complete": configuration_complete,
        "configuration_searches": configuration_searches,
        "input_audit": deepcopy(dict(prepared.get("input_audit") or {})),
        "effect_preflight": effect_preflight,
        "preflight_neutral_count": len(preflight_skipped),
        "preflight_neutral_actions": preflight_skipped,
        "ranked_actions": ranked,
        "ranked_alternatives": ranked[1:] if best_evaluated else ranked,
        "templates_considered": len(actions),
        "actionable_count": len(ranked_all),
        "rejected_count": len(rejected),
        "rejected_actions": rejected,
        "deduplicated_count": len(deduplicated),
        "deduplicated_actions": deduplicated,
        "false_prunes": [],
        "pruning_policy": "only source-proven zero CE states are suppressed; every uncertain or potentially relevant legal state is exact-scored",
        "warnings": warnings,
        "explanation": (
            "No global recommendation was issued because an exact configuration frontier exceeded its state budget."
            if not configuration_complete
            else (
                f"{best_spend['action_id']} has the largest exact sIO Clan Expedition damage gain."
                if best_spend
                else "No legal action beat the mandatory zero-cost no-op baseline."
            )
        ),
    }


def _optimize_one(profile_input: PlayerState | Mapping[str, Any], top_k: int) -> dict[str, Any]:
    prepared = _prepare_profile(profile_input)
    formula_states = [prepared["profile"], *[row[1] for row in prepared["transitions"]]]
    reports = calculate_clan_expedition_damage_batch(formula_states)
    return _result_from_reports(prepared, reports, top_k)


def optimize_source_pack_batch(
    player_states: list[PlayerState | Mapping[str, Any]],
    *,
    top_k: int = 10,
    device: str = "auto",
) -> dict[str, Any]:
    prepared_profiles = [_prepare_profile(profile) for profile in player_states]
    formula_states: list[dict[str, Any]] = []
    slices: list[tuple[int, int]] = []
    for prepared in prepared_profiles:
        start = len(formula_states)
        formula_states.append(prepared["profile"])
        formula_states.extend(row[1] for row in prepared["transitions"])
        slices.append((start, len(formula_states)))

    all_reports = calculate_clan_expedition_damage_batch(formula_states) if formula_states else []
    results = [
        _result_from_reports(prepared, all_reports[start:end], top_k)
        for prepared, (start, end) in zip(prepared_profiles, slices)
    ]
    return {
        "profiles": results,
        "numeric_backend": {
            "backend": "deterministic_cpu_exact_sio_ce",
            "batch_scoring": True,
            "requested_device": device,
            "learned_or_gpu_ranking_used": False,
            "final_winner_source": "exact_before_after_damage_only",
            "profiles_batched": len(prepared_profiles),
            "states_scored_in_one_batch": len(formula_states),
            "runtime_processes_per_uncached_batch": 1 if formula_states else 0,
            "effect_preflight_used": any(bool(row.get("effect_preflight", {}).get("enabled")) for row in prepared_profiles),
            "source_proven_states_skipped": sum(len(row.get("preflight_skipped", [])) for row in prepared_profiles),
        },
        "profile_feature_matrix_shape": [0, 0],
        "inventory_feature_matrix_shape": [0, 0],
    }


def optimize_source_pack_actions(
    player_state: PlayerState | Mapping[str, Any],
    *,
    top_k: int = 10,
    device: str = "auto",
) -> dict[str, Any]:
    batch = optimize_source_pack_batch([player_state], top_k=top_k, device=device)
    result = batch["profiles"][0]
    result["numeric_backend"] = batch["numeric_backend"]
    return result
