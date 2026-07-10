#!/usr/bin/env python3
"""
Generate legal Survivor.io optimizer candidates from player state + choice items + movement rules.

This is intentionally not a final scorer. It does not invent damage values.
It creates candidate allocations and marks what still requires the sIO damage scorer or mechanics patch.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


CORE_CHEST_OPTIONS = ["Awakening Core", "Xeno Pet Core", "Relic Core", "Resonance Chip"]
RELIC_CORE_CHEST_OPTIONS = ["Relic Core", "S-grade Excellent Choice Pack"]
TECH_CORE_OPTIONS = ["Eternal Tech Core", "Void Tech Core", "Chaos Tech Core"]
S_GRADE_FAMILY_OPTIONS = ["Eternal equipment selector", "Voidwaker equipment selector", "Chaos equipment selector"]


GEAR_SLOTS = ["weapon", "necklace", "gloves", "chest", "belt", "boots"]
SS_SIDES = ["E", "V", "C"]


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_load_error": str(exc), "_path": str(path)}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def distributions(total: int, keys: List[str]) -> Iterable[Dict[str, int]]:
    if not keys:
        return
    if len(keys) == 1:
        yield {keys[0]: total}
        return
    first = keys[0]
    for n in range(total + 1):
        for rest in distributions(total - n, keys[1:]):
            out = {first: n}
            out.update(rest)
            yield out


def compact_counts(d: Dict[str, int]) -> Dict[str, int]:
    return {k: v for k, v in d.items() if v}


def count_distributions(total: int, k: int) -> int:
    # combinations with repetition: C(total+k-1, k-1)
    if total < 0 or k <= 0:
        return 0
    return math.comb(total + k - 1, k - 1)


def build_resource_view(state: Dict[str, Any]) -> Dict[str, Any]:
    resources = state.get("resources", {})
    choice = state.get("choice_consumables", {})
    gear = state.get("gear", {})
    return {
        "bag_free": {
            "eternal_cores": resources.get("eternal_cores", 0),
            "void_cores": resources.get("void_cores", 0),
            "chaos_cores": resources.get("chaos_cores", 0),
            "relic_cores": resources.get("relic_cores_free_to_spend", 0),
            "gems": resources.get("gems", 0),
            "xeno_pet_crystal": state.get("pet", {}).get("xeno_pet_crystal", 0),
            "xeno_pet_elixir": state.get("pet", {}).get("xeno_pet_elixir", 0),
        },
        "choice_items": choice,
        "embedded_committed": {
            "gear_evc_state": gear,
            "relic_cores_in_current_build": resources.get("relic_cores_in_current_build", resources.get("relic_cores_locked_in_current_build", 0)),
            "movable_awakening_cores_claimed": resources.get("movable_awakening_cores", 0),
            "rule": "Committed build resources are not bag inventory. They are usable only through legal modeled reversion/move actions.",
        },
    }


def build_choice_candidates(state: Dict[str, Any], limit_preview: int) -> Dict[str, Any]:
    choice = state.get("choice_consumables", {})
    core_n = int(choice.get("core_chest", 0) or 0)
    relic_n = int(choice.get("relic_core_chest", 0) or 0)
    tech_n = int(choice.get("tech_core_choice_chest", 0) or 0)
    s_pack_n = int(choice.get("s_grade_excellent_choice_pack", 0) or 0)
    void_crate_n = int(choice.get("voidwalker_supply_crate", 0) or 0)

    core_allocs = list(distributions(core_n, CORE_CHEST_OPTIONS))
    relic_allocs = list(distributions(relic_n, RELIC_CORE_CHEST_OPTIONS))
    # Tech core allocations can be huge but current 40 over 3 is only 861.
    tech_allocs = list(distributions(tech_n, TECH_CORE_OPTIONS)) if tech_n <= 60 else []
    s_pack_allocs = list(distributions(s_pack_n, S_GRADE_FAMILY_OPTIONS)) if s_pack_n <= 30 else []

    total_core_relic = len(core_allocs) * len(relic_allocs)
    total_with_tech = total_core_relic * (len(tech_allocs) if tech_allocs else 1)
    total_with_s = total_with_tech * (len(s_pack_allocs) if s_pack_allocs else 1)

    preview = []
    for c in core_allocs:
        for r in relic_allocs:
            gained = {
                "Awakening Core": c.get("Awakening Core", 0),
                "Xeno Pet Core": c.get("Xeno Pet Core", 0),
                "Relic Core": c.get("Relic Core", 0) + r.get("Relic Core", 0),
                "Resonance Chip": c.get("Resonance Chip", 0),
                "S-grade Excellent Choice Pack": r.get("S-grade Excellent Choice Pack", 0),
            }
            preview.append({
                "candidate_type": "core_plus_relic_chest_allocation",
                "source_items": {"Core Chest": core_n, "Relic Core Chest": relic_n},
                "pick_from_core_chest": compact_counts(c),
                "pick_from_relic_core_chest": compact_counts(r),
                "direct_outputs_gained": compact_counts(gained),
                "validity": "valid_choice_allocation_only_not_scored",
                "needs_next": ["apply_to_build_state", "sio_damage_scorer"],
            })
            if len(preview) >= limit_preview:
                break
        if len(preview) >= limit_preview:
            break

    return {
        "counts": {
            "core_chest_allocations": len(core_allocs),
            "relic_core_chest_allocations": len(relic_allocs),
            "core_x_relic_allocations": total_core_relic,
            "tech_core_allocations": len(tech_allocs),
            "s_grade_pack_family_allocations": len(s_pack_allocs),
            "voidwalker_supply_crate_fixed_void_selectors": void_crate_n,
            "combined_choice_space_count_before_slot_level_build_sim": total_with_s,
            "formula_check": {
                "core_chest_expected": count_distributions(core_n, len(CORE_CHEST_OPTIONS)),
                "relic_chest_expected": count_distributions(relic_n, len(RELIC_CORE_CHEST_OPTIONS)),
                "tech_core_expected": count_distributions(tech_n, len(TECH_CORE_OPTIONS)),
                "s_pack_expected": count_distributions(s_pack_n, len(S_GRADE_FAMILY_OPTIONS)),
            },
        },
        "preview_first_candidates": preview,
        "note": "This enumerates legal source-item outputs only. It does not decide what is best until build simulator and damage scorer are implemented.",
    }


def build_respec_action_templates(state: Dict[str, Any], mechanics: Dict[str, Any]) -> List[Dict[str, Any]]:
    gear = state.get("gear", {})
    templates: List[Dict[str, Any]] = []
    for slot in GEAR_SLOTS:
        cur = gear.get(slot, {})
        for side in SS_SIDES:
            level = int(cur.get(side, 0) or 0)
            if level <= 0:
                continue
            templates.append({
                "action_type": "possible_af_downlevel_or_reprioritize",
                "slot": slot,
                "side": side,
                "current_level": level,
                "can_generate_levels_to_move": list(range(level, 0, -1)),
                "classification": "RECOVERABLE_EQUITY_IF_VERIFIED",
                "not_bag_inventory": True,
                "required_before_use": [
                    "exact_refund_items_for_this_slot_side_level",
                    "exact_rebuild_cost_for_new_slot_side_level",
                    "whether refund is 100_percent_for_this_system",
                ],
            })
    templates.append({
        "action_type": "xeno_awakening_core_movement",
        "claimed_movable_awakening_cores": state.get("resources", {}).get("movable_awakening_cores", 0),
        "classification": "UNKNOWN_OR_RECOVERABLE_EQUITY_IF_UI_PROVES_REFUND",
        "required_before_use": ["xeno awakening reset/refund screenshot or verified source"],
    })
    templates.append({
        "action_type": "s_survivor_shard_conversion",
        "classification": "CONVERTIBLE_IF_VERIFIED",
        "required_before_use": ["conversion ratio", "cooldown/limit", "token cost if any"],
    })
    return templates


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="data/sio_training/dtlgrind_state_v2.json")
    ap.add_argument("--mechanics", default="data/sio_training/mechanics_rules_practicality_v1.json")
    ap.add_argument("--normalized", default="data/sio_training/normalized/sio_normalized_tables.json")
    ap.add_argument("--out", default="data/sio_training/candidates")
    ap.add_argument("--preview", type=int, default=80)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state = load_json(Path(args.state), {}) or {}
    mechanics = load_json(Path(args.mechanics), {}) or {}
    normalized = load_json(Path(args.normalized), {}) or {}

    resource_view = build_resource_view(state)
    choice_candidates = build_choice_candidates(state, args.preview)
    respec_templates = build_respec_action_templates(state, mechanics)

    generated = {
        "schema": "sio_candidate_generation_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rule": "Generate candidates from data only. Do not rank until sIO damage scorer is available.",
        "source_files": {
            "state": args.state,
            "mechanics": args.mechanics,
            "normalized": args.normalized,
        },
        "normalizer_status": {
            "schema": normalized.get("schema"),
            "mode": normalized.get("mode"),
        },
        "resource_view": resource_view,
        "choice_candidate_space": choice_candidates,
        "respec_action_templates": respec_templates,
        "blocked_from_final_ranking_until": [
            "sio_damage_scorer_implemented",
            "exact gear AF/refund/rebuild cost tables parsed or patched",
            "xeno awakening reset/refund verified",
            "survivor shard conversion rules verified if survivor switching is considered",
        ],
    }

    write_json(out / "dtlgrind_candidate_space.json", generated)

    unknowns = [
        "Candidate generation succeeded, but it is not final ranking.",
        "Need damage scorer to convert candidate after-state into damage delta.",
        "Need AF cost/refund/rebuild tables before using committed gear equity as movable.",
        "Need Xeno awakening reset/refund proof before using all committed awakening cores as movable.",
        "Need survivor shard conversion rules before treating survivor investment as flexible.",
    ]
    report = [
        "# Candidate generator report",
        "",
        f"Generated: {generated['generated_at']}",
        "",
        "## Choice-space counts",
    ]
    for k, v in choice_candidates["counts"].items():
        report.append(f"- {k}: {v}")
    report += [
        "",
        "## What exists now",
        "- Legal Core Chest + Relic Core Chest output allocations are enumerated.",
        "- Tech Core and S-grade selector family allocation counts are computed.",
        "- Current-build resources are separated from bag-free resources.",
        "- AF downlevel/reprioritize actions are templates only until refund/rebuild costs are verified.",
        "",
        "## Unknowns blocking final best-spend answer",
    ] + [f"- {u}" for u in unknowns]
    report += [
        "",
        "## Files written",
        "- data/sio_training/candidates/dtlgrind_candidate_space.json",
        "- data/sio_training/candidates/candidate_generator_report.md",
    ]
    (out / "candidate_generator_report.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
