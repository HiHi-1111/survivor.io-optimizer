#!/usr/bin/env python3
"""
After-state bridge probe for the Survivor.io optimizer.

This is the next layer after fullpower_candidate_index.py.
It does not rank a final build. It checks whether the current extracted data and
candidate output space are enough to start converting choices into legal
before/after build states.

Output rule:
- If a thing cannot be proven from data, emit needs_* / blocked_* instead of guessing.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def safe_get(d: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def read_distribution(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalized_counts(normalized: Dict[str, Any]) -> Dict[str, Any]:
    counts: Dict[str, Any] = {}
    for key in [
        "items",
        "techs",
        "pets",
        "heroes",
        "collectibles",
        "xenoPetAwakening",
        "mounts",
        "skills",
        "petSkills",
    ]:
        val = normalized.get(key)
        if isinstance(val, dict):
            counts[key] = len(val)
        elif isinstance(val, list):
            counts[key] = len(val)
        else:
            counts[key] = 0
    # Some normalizer versions wrap exact exports under raw_exports / exports / tables.
    for wrapper in ["tables", "raw_exports", "exports", "module_37013_c"]:
        w = normalized.get(wrapper)
        if isinstance(w, dict):
            for key in ["items", "techs", "pets", "heroes", "collectibles", "xenoPetAwakening"]:
                val = w.get(key)
                if counts.get(key, 0) == 0:
                    if isinstance(val, dict):
                        counts[key] = len(val)
                    elif isinstance(val, list):
                        counts[key] = len(val)
    return counts


def make_afterstate_contract(fullpower: Dict[str, Any], normalized: Dict[str, Any], distribution_rows: List[Dict[str, str]]) -> Dict[str, Any]:
    resource_view = fullpower.get("resource_view", {})
    bag = resource_view.get("bag_free", {})
    choice_items = resource_view.get("choice_items", {})
    embedded = resource_view.get("embedded_committed", {})
    counts = fullpower.get("allocation_counts", {})
    norm_counts = normalized_counts(normalized)

    direct_output_caps: Dict[str, int] = {}
    passes = fullpower.get("passes_detail", [])
    if passes:
        max_outputs = passes[0].get("max_direct_outputs", {})
        for k, v in max_outputs.items():
            if isinstance(v, dict):
                direct_output_caps[k] = int(v.get("value", 0) or 0)

    distribution_summary: Dict[str, Any] = {
        "rows_loaded": len(distribution_rows),
        "columns": list(distribution_rows[0].keys()) if distribution_rows else [],
    }

    required_bridges = {
        "choice_outputs_to_resources": {
            "status": "READY",
            "reason": "Fullpower index contains deterministic direct output counts and example outputs.",
        },
        "resources_to_gear_evc_afterstate": {
            "status": "PARTIAL",
            "reason": "Can see current E/V/C and selector families, but cannot legally spend embedded relic cores/S gear until AF refund/rebuild tables are patched or extracted.",
        },
        "resources_to_tech_afterstate": {
            "status": "PARTIAL",
            "reason": "Tech core output families are counted, but exact mapping from Eternal/Void/Chaos Tech Core to resonance/overload gain needs scorer bridge.",
        },
        "resources_to_xeno_afterstate": {
            "status": "PARTIAL",
            "reason": "Core Chest can create Xeno/Awakening outputs, but Xeno awakening reset/refund proof is still needed before using committed awakening cores as flexible.",
        },
        "survivor_switch_afterstate": {
            "status": "BLOCKED",
            "reason": "Survivor shard conversion limits are not patched, so survivor investment cannot be treated as flexible.",
        },
        "sio_damage_score_afterstate": {
            "status": "BLOCKED",
            "reason": "Need sIO damage scorer implementation that consumes normalized formulas and computes before/after damage delta.",
        },
    }

    can_start_apply_to_build_state = all([
        counts.get("combined_choice_space_total_checked", 0) > 0,
        safe_int(bag.get("eternal_cores")) == 240,
        safe_int(bag.get("void_cores")) == 170,
        safe_int(bag.get("chaos_cores")) == 120,
        safe_int(embedded.get("relic_cores_in_current_build")) == 45,
    ])

    blockers = []
    for name, item in required_bridges.items():
        if item["status"] in {"PARTIAL", "BLOCKED"}:
            blockers.append({"bridge": name, **item})

    return {
        "schema": "sio_afterstate_bridge_probe_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rule": "This probe prepares apply_to_build_state. It is not a final build ranker.",
        "can_start_apply_to_build_state_scaffolding": can_start_apply_to_build_state,
        "resource_view_confirmed": {
            "bag_free": bag,
            "choice_items": choice_items,
            "embedded_committed": embedded,
        },
        "choice_space_confirmed": counts,
        "direct_output_caps": direct_output_caps,
        "normalized_table_counts": norm_counts,
        "distribution_summary": distribution_summary,
        "required_bridges": required_bridges,
        "blocked_from_final_ranking_until": [b["bridge"] for b in blockers],
    }


def safe_int(x: Any) -> int:
    try:
        return int(x)
    except Exception:
        return 0


def write_report(path: Path, probe: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# sIO after-state bridge probe")
    lines.append("")
    lines.append(f"Generated: {probe['generated_at']}")
    lines.append("")
    lines.append("## Result")
    lines.append(f"- can_start_apply_to_build_state_scaffolding: {probe['can_start_apply_to_build_state_scaffolding']}")
    lines.append("- final_best_spend_answer: BLOCKED")
    lines.append("- rule: do not rank until after-state simulation + sIO damage scorer exist")
    lines.append("")

    bag = probe["resource_view_confirmed"].get("bag_free", {})
    emb = probe["resource_view_confirmed"].get("embedded_committed", {})
    choices = probe["resource_view_confirmed"].get("choice_items", {})
    lines.append("## Confirmed resource view")
    for k in ["eternal_cores", "void_cores", "chaos_cores", "relic_cores", "gems", "xeno_pet_crystal", "xeno_pet_elixir"]:
        lines.append(f"- bag_free {k}: {bag.get(k, 'unknown')}")
    lines.append(f"- embedded relic_cores_in_current_build: {emb.get('relic_cores_in_current_build', 'unknown')}")
    lines.append(f"- embedded/movable awakening cores claimed: {emb.get('movable_awakening_cores_claimed', 'unknown')}")
    lines.append("")

    lines.append("## Choice inventory")
    for k, v in choices.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## Fullpower choice-space check")
    for k, v in probe.get("choice_space_confirmed", {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## Direct output caps from legal choices")
    for k, v in sorted(probe.get("direct_output_caps", {}).items()):
        lines.append(f"- {k}: max {v}")
    lines.append("")

    lines.append("## Normalized table counts")
    for k, v in probe.get("normalized_table_counts", {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## Bridge status")
    for k, v in probe.get("required_bridges", {}).items():
        lines.append(f"- {k}: {v['status']} — {v['reason']}")
    lines.append("")

    lines.append("## Next real build step")
    lines.append("1. Implement apply_to_build_state for non-embedded bag-free choices first.")
    lines.append("2. Keep embedded relic cores locked until AF refund/rebuild is patched or extracted.")
    lines.append("3. Keep survivor switching blocked until shard conversion rules are patched.")
    lines.append("4. Add sIO scorer only after the after-state object is stable.")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fullpower", default="data/sio_training/fullpower/latest/fullpower_candidate_index.json")
    ap.add_argument("--normalized", default="data/sio_training/normalized/sio_normalized_tables.json")
    ap.add_argument("--distribution", default="data/sio_training/fullpower/latest/fullpower_distribution_index.csv")
    ap.add_argument("--out", default="data/sio_training/afterstate")
    args = ap.parse_args()

    fullpower_path = Path(args.fullpower)
    normalized_path = Path(args.normalized)
    distribution_path = Path(args.distribution)
    out_dir = Path(args.out)

    fullpower = load_json(fullpower_path)
    normalized = load_json(normalized_path)
    distribution = read_distribution(distribution_path)

    if not fullpower:
        raise SystemExit(f"missing or empty fullpower file: {fullpower_path}")

    probe = make_afterstate_contract(fullpower, normalized, distribution)
    write_json(out_dir / "afterstate_bridge_probe.json", probe)
    write_report(out_dir / "afterstate_bridge_probe_report.md", probe)

    print(f"wrote {out_dir / 'afterstate_bridge_probe.json'}")
    print(f"wrote {out_dir / 'afterstate_bridge_probe_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
