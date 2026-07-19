"""Public Clan Expedition optimizer entry point."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from optimizer.coverage import coverage_audit_state, coverage_report
from optimizer.damage_engine import UnsupportedGameModeError, estimate_damage_totals
from optimizer.knowledge_loader import load_knowledge
from optimizer.player_state import PlayerState, validate_player_state
from optimizer.search_memory import search_guide_memory
from optimizer.source_pack_optimizer import optimize_source_pack_actions

CE_SCENARIO_ALIASES = {"clan_expedition", "scenario_clan_expedition", "ce"}


def _dump(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return value


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
    for cost in action.get("costs", []) or []:
        item_id = str(cost.get("resource_id"))
        totals[item_id] = totals.get(item_id, 0.0) + float(cost.get("amount", 0) or 0)
    return totals


def _all_resource_counts(state: PlayerState) -> dict[str, float]:
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
    return counts


def optimize(
    player_state_dict: dict[str, Any] | PlayerState,
    *,
    include_global_plan: bool = False,
    planner_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return exact sIO Clan Expedition damage and exact bridged upgrades.

    ``include_global_plan`` remains in the public signature for compatibility,
    but the old generic planner is not executed. It may only return after every
    action family has a legal after-state bridge into the sIO CE formula.
    """
    del planner_options
    knowledge = load_knowledge()
    player_state = validate_player_state(player_state_dict)
    scenario = _select_scenario(knowledge, player_state.goal_scenario)
    damage_report = estimate_damage_totals(player_state)
    source_pack_plan = optimize_source_pack_actions(player_state)

    best = source_pack_plan.get("best")
    ranked = list(source_pack_plan.get("ranked_actions", []))
    rejected = list(source_pack_plan.get("rejected_actions", []))
    resources_used = _costs_to_consumed(best)
    resources = _all_resource_counts(player_state)
    resources_saved = {
        key: amount - resources_used.get(key, 0.0)
        for key, amount in resources.items()
        if amount - resources_used.get(key, 0.0) > 0
    }
    expected_damage_gain = float((best or {}).get("expected_dps_gain", 0.0) or 0.0)

    guide_query = str((best or {}).get("action_id", "")).replace("_", " ")
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
            "The generic multi-system planner was requested but deliberately not run; exact CE after-state bridges are incomplete."
        )
    global_plan = {
        "supported": False,
        "reason": "exact_ce_after_state_bridges_incomplete",
        "learned_or_heuristic_winner_selection": False,
    }
    action_chain = []
    if best:
        action_chain = [{**best, "consumed_items": resources_used}]

    future_goals = [
        "Complete sIO module 24804 condition and uptime assembly.",
        "Add legal CE after-state bridges for SS/Xeno Transmute, Tech, Survivors, Pets and Collectibles.",
        "Keep unsupported mechanics unknown until they match sIO or the user-provided Bible.",
    ]
    explanation = {
        "summary": source_pack_plan.get("explanation"),
        "scenario_tradeoff": scenario.description,
        "resources_used": resources_used,
        "resources_saved": resources_saved,
        "expected_damage_gain": expected_damage_gain,
        "assumptions": list(damage_report.get("warnings", [])),
        "missing_data": coverage.get("systems_missing_data", []),
        "future_goals": future_goals,
        "next_best_action": ranked[1] if len(ranked) > 1 else None,
    }

    return {
        "scenario": _dump(scenario),
        "scenario_used": scenario.id,
        "game_mode": "clan_expedition",
        "recommendation": best,
        "best": best,
        "best_including_no_op": source_pack_plan.get("best_including_no_op"),
        "no_op_baseline": source_pack_plan.get("no_op_baseline"),
        "no_action_recommended": source_pack_plan.get("no_action_recommended", best is None),
        "ranked_alternatives": ranked[1:] if best else ranked,
        "top_options": ranked,
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
        "next_best_action": ranked[1] if len(ranked) > 1 else None,
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
