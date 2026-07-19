"""Public Clan Expedition optimizer entry point."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from optimizer.coverage import coverage_audit_state, coverage_report
from optimizer.damage_engine import UnsupportedGameModeError, estimate_damage_totals
from optimizer.knowledge_loader import load_knowledge
from optimizer.player_state import PlayerState, validate_player_state
from optimizer.search_memory import search_guide_memory
from optimizer.source_pack_optimizer import optimize_source_pack_actions

# Old objective labels are migration aliases into the one CE contract. They do
# not enable another combat mode or change the exact before/after winner.
CE_SCENARIO_ALIASES = {
    "clan_expedition",
    "scenario_clan_expedition",
    "clan_expedition_damage",
    "ce",
    "normal",
    "scenario_1",
    "scenario_2",
    "scenario_3",
    "scenario_event_shop",
    "scenario_f2p_gems",
    "scenario_chapter_push",
    "scenario_clan_shop",
    "scenario_pet_xeno",
    "scenario_gear_ss",
    "scenario_collectibles",
}


def _dump(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return value


def _raw_profile(value: dict[str, Any] | PlayerState) -> dict[str, Any]:
    dumped = _dump(value)
    return deepcopy(dict(dumped)) if isinstance(dumped, Mapping) else {}


def _select_scenario(knowledge: dict[str, Any], scenario_id: str):
    requested = str(scenario_id or "clan_expedition").strip().lower()
    if requested not in CE_SCENARIO_ALIASES:
        raise UnsupportedGameModeError(
            f"Only Clan Expedition is supported; requested scenario {scenario_id!r}."
        )
    for scenario in knowledge["scenarios"]:
        if scenario.id == "clan_expedition":
            return scenario
    raise RuntimeError("knowledge/scenarios.json is missing the Clan Expedition scenario")


def _costs_to_consumed(action: Mapping[str, Any] | None) -> dict[str, float]:
    totals: dict[str, float] = {}
    if not action:
        return totals
    consumed = action.get("consumed_items")
    if isinstance(consumed, Mapping):
        return {str(key): float(value or 0) for key, value in consumed.items()}
    for cost in action.get("costs", []) or []:
        item_id = str(cost.get("resource_id"))
        totals[item_id] = totals.get(item_id, 0.0) + float(cost.get("amount", 0) or 0)
    return totals


def _all_resource_counts(state: PlayerState, raw: Mapping[str, Any]) -> dict[str, float]:
    counts = {
        str(key): float(value or 0)
        for key, value in state.resources.model_dump().items()
        if isinstance(value, (int, float))
    }
    for key, value in state.inventory.items.items():
        amount = value
        if isinstance(value, Mapping):
            amount = value.get("count", value.get("quantity", 0))
        if isinstance(amount, (int, float)):
            counts[str(key)] = counts.get(str(key), 0.0) + float(amount)
    for section_name in ("resources", "inventory"):
        section = raw.get(section_name)
        if not isinstance(section, Mapping):
            continue
        for key, value in section.items():
            amount = value
            if isinstance(value, Mapping):
                amount = value.get("count", value.get("quantity", value.get("amount", 0)))
            if isinstance(amount, (int, float)):
                counts[str(key)] = max(counts.get(str(key), 0.0), float(amount))
    return counts


def optimize(
    player_state_dict: dict[str, Any] | PlayerState,
    *,
    include_global_plan: bool = False,
    planner_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return sIO Clan Expedition damage and exact bridged upgrades.

    ``include_global_plan`` remains in the public signature for compatibility,
    but the retired generic planner is never allowed to choose the winner.
    """
    del planner_options
    raw = _raw_profile(player_state_dict)
    knowledge = load_knowledge()
    player_state = validate_player_state(player_state_dict)
    requested_scenario = raw.get("goal_scenario", player_state.goal_scenario)
    scenario = _select_scenario(knowledge, str(requested_scenario))
    raw["game_mode"] = "clan_expedition"
    raw["goal_scenario"] = "clan_expedition"
    damage_report = estimate_damage_totals(raw)
    source_pack_plan = optimize_source_pack_actions(raw)

    best_spend = source_pack_plan.get("best")
    public_best = source_pack_plan.get("best_including_no_op") or best_spend
    ranked_spend = list(source_pack_plan.get("ranked_actions", []))
    public_options = ranked_spend if best_spend else ([public_best] if public_best else [])
    rejected = list(source_pack_plan.get("rejected_actions", []))
    resources_used = _costs_to_consumed(best_spend)
    resources = _all_resource_counts(player_state, raw)
    resources_saved = {
        key: amount - resources_used.get(key, 0.0)
        for key, amount in resources.items()
        if amount - resources_used.get(key, 0.0) > 0
    }
    expected_damage_gain = float((best_spend or {}).get("expected_dps_gain", 0.0) or 0.0)

    guide_query = str((best_spend or {}).get("action_id", "")).replace("_", " ")
    guide_matches = search_guide_memory(guide_query) if guide_query else []
    source_refs = sorted(
        {
            str(match.get("source_ref") or match.get("source"))
            for match in guide_matches
            if match.get("source_ref") or match.get("source")
        }
    )
    coverage = coverage_report(knowledge, coverage_audit_state(knowledge))
    warnings = list(damage_report.get("warnings", [])) + list(source_pack_plan.get("warnings", []))
    if include_global_plan:
        warnings.append(
            "The retired generic planner was requested but did not choose the winner; exact CE before/after damage remained authoritative."
        )
    action_chain = [{**best_spend, "consumed_items": resources_used}] if best_spend else []
    compatibility_steps = action_chain or ([public_best] if public_best else [])
    global_plan = {
        "supported": False,
        "reason": "generic_multimode_planner_retired_exact_ce_only",
        "learned_or_heuristic_winner_selection": False,
        "actions_considered": int(source_pack_plan.get("templates_considered", 0)),
        "best_action_chain": {
            "ordered_steps": compatibility_steps,
            "marginal_value": {
                "delta": expected_damage_gain,
                "before": damage_report.get("total_damage"),
                "after": (
                    float(damage_report.get("total_damage") or 0.0) + expected_damage_gain
                    if damage_report.get("total_damage") is not None else None
                ),
            },
        },
    }

    future_goals = [
        "Supply exact source data for any mechanic still marked unknown.",
        "Record repeated observed CE runs only for formula-review calibration.",
        "Keep learned champions limited to proposal ordering; exact CE damage remains the winner gate.",
    ]
    next_best = ranked_spend[1] if len(ranked_spend) > 1 else None
    explanation = {
        "summary": source_pack_plan.get("explanation"),
        "scenario_tradeoff": scenario.description,
        "resources_used": resources_used,
        "resources_saved": resources_saved,
        "expected_damage_gain": expected_damage_gain,
        "assumptions": list(damage_report.get("warnings", [])),
        "missing_data": coverage.get("systems_missing_data", []),
        "future_goals": future_goals,
        "next_best_action": next_best,
    }

    return {
        "scenario": _dump(scenario),
        "scenario_used": scenario.id,
        "requested_scenario_alias": requested_scenario,
        "game_mode": "clan_expedition",
        "recommendation": public_best,
        "best": public_best,
        "best_spend_action": best_spend,
        "best_including_no_op": public_best,
        "no_op_baseline": source_pack_plan.get("no_op_baseline"),
        "no_action_recommended": source_pack_plan.get("no_action_recommended", best_spend is None),
        "ranked_alternatives": ranked_spend[1:] if best_spend else [],
        "top_options": public_options,
        "rejected_alternatives": rejected,
        "avoid": rejected,
        "action_chain": action_chain,
        "resources_used": resources_used,
        "resources_saved": resources_saved,
        "damage_report": damage_report,
        "total_damage": damage_report.get("total_damage"),
        "final_damage_multiplier": damage_report.get("final_damage_multiplier"),
        "multiplier_breakdown": damage_report.get("multiplier_breakdown"),
        "blocker_analysis": damage_report.get("blocker_analysis"),
        "expected_damage_gain": expected_damage_gain,
        "long_term_value": 0.0,
        "explanation": explanation,
        "warnings": sorted(set(warnings)),
        "assumptions": list(damage_report.get("warnings", [])),
        "future_goals": future_goals,
        "missing_data": coverage.get("systems_missing_data", []),
        "confidence_level": "exact_core_with_explicit_unknowns" if damage_report.get("supported") else "unknown",
        "next_best_action": next_best,
        "global_plan": global_plan,
        "guide_matches": guide_matches,
        "source_refs": source_refs,
        "confidence": "exact_core_with_explicit_unknowns" if damage_report.get("supported") else "unknown",
        "next_goal": future_goals[0],
        "source_pack_plan": source_pack_plan,
    }


if __name__ == "__main__":
    from run_demo import main

    main()
