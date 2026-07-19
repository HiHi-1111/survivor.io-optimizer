#!/usr/bin/env python3
"""Fail CI on accidental permutation search or mount-layout training leakage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

# This is directional: source is downgraded/refunded and target is upgraded.
# Reversing the pair changes the after-state, so it is not an order-equivalent
# inventory permutation.
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
    optimizer = _source("optimizer/source_pack_optimizer.py")
    labels = _source("optimizer/exact_training_labels.py")
    tetris = _source("optimizer/sio_tetris.py")

    required = {
        "multiset count-vector generator": (combinations, "bounded_multiset_allocations"),
        "selector chest combination integration": (optimizer, "expand_actions_with_choice_chests"),
        "selector chest no-permutation marker": (choice_chests, '"permutation_search": False'),
        "Tetris fixed multiset search": (tetris, "fixed_type_multiset_placement_combinations"),
        "layout training exclusion": (labels, "LAYOUT_ONLY_KEYS"),
        "layout recursive sanitizer": (labels, "_strip_layout_only_data"),
    }
    for label, (source, token) in required.items():
        if token not in source:
            errors.append(f"{label}: missing {token!r}")

    training_layout_imports: list[str] = []
    for relative in TRAINING_FILES:
        source = _source(relative)
        if "sio_tetris" in source:
            training_layout_imports.append(relative)
            errors.append(f"training code must not import the Tetris placement solver: {relative}")
        if re.search(r"features\s*\[.*(?:placements|board_mask|rotation|states_explored)", source):
            errors.append(f"training code reads layout geometry as a feature: {relative}")

    return {
        "schema": "sio_combination_training_audit_v1",
        "ok": not errors,
        "permutation_hits": permutation_hits,
        "allowed_directional_permutations": sorted(ALLOWED_DIRECTIONAL_PERMUTATION),
        "training_layout_imports": training_layout_imports,
        "rules": [
            "choice chests and identical inventory choices use multiset count combinations",
            "directional source-to-target transitions may remain ordered when reversal changes the state",
            "Tetris placement geometry is deterministic runtime output and is excluded from learned features",
            "only resulting exact mount stats and exact CE damage may affect training",
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
