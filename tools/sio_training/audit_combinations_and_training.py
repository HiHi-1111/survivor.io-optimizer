#!/usr/bin/env python3
"""Fail CI on permutation search, hidden caps, or layout-training leakage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

# This legacy occurrence is directional: source is downgraded/refunded and target
# is upgraded. Reversing the pair changes the after-state, so it is not an
# order-equivalent inventory permutation. The complete frontier uses nested role
# loops in sio_item_reallocations.py and is checked separately below.
ALLOWED_DIRECTIONAL_PERMUTATION = {
    "optimizer/sio_exact_actions.py": "for source_slot, target_slot in itertools.permutations(SLOTS, 2):",
}
TRAINING_FILES = (
    "optimizer/exact_training_labels.py",
    "optimizer/learned_ranker.py",
    "optimizer/champion_lineage.py",
    "tools/sio_training/train_champion_lineage.py",
)


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def audit() -> dict:
    errors: list[str] = []
    permutation_hits: list[dict[str, object]] = []
    for path in sorted((ROOT / "optimizer").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(source.splitlines(), 1):
            if re.search(r"\b(?:itertools\.)?permutations\s*\(", line):
                relative = str(path.relative_to(ROOT)).replace("\\", "/")
                permutation_hits.append({"path": relative, "line": line_number, "text": line.strip()})
                expected = ALLOWED_DIRECTIONAL_PERMUTATION.get(relative)
                if expected is None or line.strip() != expected:
                    errors.append(f"order-independent permutation search found: {relative}:{line_number}: {line.strip()}")

    combinations = _source("optimizer/sio_combinations.py")
    choice_chests = _source("optimizer/sio_choice_chests.py")
    item_reallocations = _source("optimizer/sio_item_reallocations.py")
    survivor_configurations = _source("optimizer/sio_survivor_configurations.py")
    tech_configurations = _source("optimizer/sio_tech_configurations.py")
    mount_bridge = _source("optimizer/sio_mount_puzzle_bridge.py")
    optimizer = _source("optimizer/source_pack_optimizer.py")
    labels = _source("optimizer/exact_training_labels.py")
    tetris = _source("optimizer/sio_tetris.py")

    required = {
        "multiset count-vector generator": (combinations, "bounded_multiset_allocations"),
        "selector chest exact-cover integration": (optimizer, "expand_actions_with_choice_chests"),
        "selector chest shortage-pruned DP": (choice_chests, "exact_cover_allocations"),
        "selector chest Pareto preservation": (choice_chests, "_pareto_allocations"),
        "selector chest no-permutation marker": (choice_chests, '"permutation_search": False'),
        "complete directional item frontier": (item_reallocations, "directional_reallocation_pairs"),
        "complete item frontier integration": (optimizer, "generate_exhaustive_item_reallocations"),
        "structural state deduplication report": (optimizer, '"deduplicated_count"'),
        "Twinborn role assignment product": (tech_configurations, "generate_twinborn_mode_actions"),
        "Twinborn one-mode certificate": (tech_configurations, '"one_mode_per_twinborn_pair": True'),
        "Survivor complete-state planner": (survivor_configurations, "plan_survivor_configurations"),
        "Teamwork subset combinations": (survivor_configurations, "for subset in combinations"),
        "Survivor incomplete-search withholding": (optimizer, '"recommendation_withheld"'),
        "Tetris fixed multiset search": (tetris, "fixed_type_multiset_placement_combinations"),
        "verified mount stat bridge": (mount_bridge, "apply_verified_mount_puzzle_stats"),
        "mount layout excluded from scoring": (mount_bridge, '"layout_used_for_scoring": False'),
        "layout training exclusion": (labels, "LAYOUT_ONLY_KEYS"),
        "layout structural detector": (labels, "_contains_layout_only_data"),
        "layout recursive sanitizer": (labels, "_strip_layout_only_data"),
    }
    for label, (source, token) in required.items():
        if token not in source:
            errors.append(f"{label}: missing {token!r}")

    if "[:4]" in item_reallocations or "[:10]" in item_reallocations:
        errors.append("complete item reallocation frontier contains a nearest-frontier slice")
    if "permutations(" in survivor_configurations:
        errors.append("Survivor Teamwork configuration must not use permutations")
    if "sio_tetris" in mount_bridge:
        errors.append("mount stat bridge must not execute or import the Tetris solver")

    training_layout_imports: list[str] = []
    for relative in TRAINING_FILES:
        source = _source(relative)
        if "sio_tetris" in source:
            training_layout_imports.append(relative)
            errors.append(f"training code must not import the Tetris placement solver: {relative}")
        if re.search(r"features\s*\[.*(?:placements|board_mask|rotation|states_explored)", source):
            errors.append(f"training code reads layout geometry as a feature: {relative}")

    return {
        "schema": "sio_combination_training_audit_v3",
        "ok": not errors,
        "permutation_hits": permutation_hits,
        "allowed_directional_permutations": sorted(ALLOWED_DIRECTIONAL_PERMUTATION),
        "training_layout_imports": training_layout_imports,
        "rules": [
            "choice chests and identical inventory choices use multiset count combinations",
            "choice allocations are generated only for the exact action shortage vector",
            "directional source-to-target transitions may remain ordered when reversal changes the state",
            "every exact directional item frontier is generated before structural state deduplication",
            "Teamwork is an unordered subset while Main and Harmony positions remain role-specific",
            "Twinborn mode assignments are per-tech complete states, not inventory permutations",
            "Tetris placement geometry is deterministic runtime output and is excluded from learned features",
            "only verified resulting mount stats and exact CE damage may affect scoring or training",
            "incomplete exact configuration frontiers withhold the global recommendation",
        ],
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
