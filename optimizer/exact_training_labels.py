"""Prepare exact sIO labels without leaking answers or deleting evidence.

Mount-puzzle placement is deterministic search output, not a learned target. Raw
placements remain in retained evidence for audits, but only their resulting exact
mount stats and CE damage can influence proposal-training labels.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from optimizer.numeric_features import FEATURE_COLUMNS, action_features


# These fields describe how a deterministic Tetris/mount-puzzle solver reached a
# layout. They must not become model features. The exact aggregate mount stats
# produced by the layout may still be represented through normal action metadata
# such as attack/crit estimates or, preferably, exact before/after CE labels.
LAYOUT_ONLY_KEYS = frozenset(
    {
        "placements",
        "placement",
        "board",
        "board_mask",
        "rotation",
        "row",
        "col",
        "cell",
        "cells",
        "path",
        "states_explored",
        "search_model",
        "worker_parity",
        "tetris",
        "mount_puzzle",
        "mountPuzzle",
        "puzzle_layout",
        "layout",
    }
)


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_stable(value).encode("utf-8")).hexdigest()


def _contains_layout_only_data(value: Any) -> bool:
    """Detect exact layout keys without substring false positives."""
    if isinstance(value, Mapping):
        return any(
            str(key) in LAYOUT_ONLY_KEYS or _contains_layout_only_data(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_layout_only_data(item) for item in value)
    return False


def _strip_layout_only_data(value: Any) -> Any:
    """Recursively remove placement geometry from a feature-extraction copy.

    This never mutates or replaces the retained raw evidence.
    """
    if isinstance(value, Mapping):
        return {
            str(key): _strip_layout_only_data(item)
            for key, item in value.items()
            if str(key) not in LAYOUT_ONLY_KEYS
        }
    if isinstance(value, list):
        return [_strip_layout_only_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_strip_layout_only_data(item) for item in value)
    return value


def _delta(candidate: Mapping[str, Any]) -> float:
    for key in ("exact_damage_delta", "expected_dps_gain", "damage_delta", "label"):
        if key in candidate:
            try:
                return float(candidate[key])
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def _proposal_features(candidate: Mapping[str, Any]) -> dict[str, float]:
    explicit = candidate.get("features")
    if isinstance(explicit, Mapping):
        # FEATURE_COLUMNS is a strict allow-list. Geometry or arbitrary fields in
        # an imported feature dictionary cannot enter the champion.
        return {name: float(explicit.get(name, 0.0) or 0.0) for name in FEATURE_COLUMNS}
    sanitized = _strip_layout_only_data(deepcopy(dict(candidate)))
    # Exact before/after damage is the teacher label, never an input available to
    # a proposal-ordering child before the oracle evaluates the action.
    for key in (
        "exact_damage_delta",
        "expected_dps_gain",
        "estimated_dps_value",
        "damage_delta",
        "score",
    ):
        sanitized.pop(key, None)
    sanitized["expected_damage_delta"] = 0.0
    vector = action_features(sanitized, scenario_id="clan_expedition")
    return dict(zip(FEATURE_COLUMNS, vector))


def _quarantine(index: int, reason: str, raw_row: Mapping[str, Any], **detail: Any) -> dict[str, Any]:
    evidence = deepcopy(dict(raw_row))
    return {
        "index": index,
        "reason": reason,
        "row_hash": _hash(evidence),
        "retained_for_audit": True,
        "excluded_from_training": True,
        "raw_row": evidence,
        **detail,
    }


def prepare_exact_training_rows(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Add label-free features and quarantine conflicting or malformed evidence.

    Cleanup means classification, not deletion. Every rejected row is returned in
    full under ``raw_row`` with a stable SHA-256 fingerprint so it can be fixed,
    compared or restored later without contaminating champion training.
    """
    accepted: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    seen: dict[str, frozenset[str]] = {}
    for index, raw_input in enumerate(rows):
        original = deepcopy(dict(raw_input))
        row = deepcopy(original)
        candidates = row.get("candidates", row.get("actions"))
        if not isinstance(candidates, list) or not candidates:
            quarantined.append(_quarantine(index, "missing_candidates", original))
            continue
        prepared = []
        for candidate_index, raw_candidate in enumerate(candidates):
            if not isinstance(raw_candidate, Mapping):
                continue
            candidate = deepcopy(dict(raw_candidate))
            candidate["action_id"] = str(
                candidate.get("action_id")
                or candidate.get("id")
                or f"candidate_{candidate_index}"
            )
            candidate["exact_damage_delta"] = _delta(candidate)
            candidate["features"] = _proposal_features(candidate)
            if _contains_layout_only_data(raw_candidate):
                candidate["training_exclusions"] = ["mount_puzzle_layout_geometry"]
            prepared.append(candidate)
        if not prepared:
            quarantined.append(_quarantine(index, "no_valid_candidate_objects", original))
            continue
        if not any(
            candidate.get("action_type") == "save_hold"
            or str(candidate["action_id"]).startswith("save_hold")
            for candidate in prepared
        ):
            no_op = {
                "action_id": "save_hold_no_op",
                "action_type": "save_hold",
                "exact_damage_delta": 0.0,
            }
            no_op["features"] = _proposal_features(no_op)
            prepared.append(no_op)
        best = max(_delta(candidate) for candidate in prepared)
        winners = frozenset(
            candidate["action_id"]
            for candidate in prepared
            if abs(_delta(candidate) - best) <= 1e-9
        )
        state_key = _hash(
            [
                {"action_id": candidate["action_id"], "features": candidate["features"]}
                for candidate in sorted(prepared, key=lambda value: value["action_id"])
            ]
        )
        previous = seen.get(state_key)
        if previous is not None and previous != winners:
            quarantined.append(
                _quarantine(
                    index,
                    "contradictory_exact_label",
                    original,
                    state_key=state_key,
                    previous_winners=sorted(previous),
                    new_winners=sorted(winners),
                )
            )
            continue
        if previous is not None:
            quarantined.append(
                _quarantine(
                    index,
                    "duplicate_exact_evidence",
                    original,
                    state_key=state_key,
                    winners=sorted(winners),
                )
            )
            continue
        seen[state_key] = winners
        row["candidates"] = prepared
        row.pop("actions", None)
        row["winner_ids"] = sorted(winners)
        row["exact_state_key"] = state_key
        row["source_row_hash"] = _hash(original)
        accepted.append(row)
    return accepted, quarantined


def append_quarantine_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> int:
    """Append retained evidence; never truncate or rewrite the quarantine file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(_stable(dict(record)) + "\n")
            count += 1
    return count


__all__ = [
    "LAYOUT_ONLY_KEYS",
    "append_quarantine_jsonl",
    "prepare_exact_training_rows",
]
