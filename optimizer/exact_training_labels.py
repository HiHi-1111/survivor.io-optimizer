"""Prepare exact sIO labels without leaking the answer into model features."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Iterable, Mapping

from optimizer.numeric_features import FEATURE_COLUMNS, action_features


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_stable(value).encode("utf-8")).hexdigest()


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
        return {name: float(explicit.get(name, 0.0) or 0.0) for name in FEATURE_COLUMNS}
    sanitized = deepcopy(dict(candidate))
    # Exact before/after damage is the teacher label, not an input available to
    # a proposal-ordering child before the oracle evaluates the action.
    for key in ("exact_damage_delta", "expected_dps_gain", "estimated_dps_value", "damage_delta", "score"):
        sanitized.pop(key, None)
    sanitized["expected_damage_delta"] = 0.0
    vector = action_features(sanitized, scenario_id="clan_expedition")
    return dict(zip(FEATURE_COLUMNS, vector))


def prepare_exact_training_rows(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Add label-free features and quarantine same-state conflicting winners."""
    accepted: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    seen: dict[str, frozenset[str]] = {}
    for index, raw_row in enumerate(rows):
        row = deepcopy(dict(raw_row))
        candidates = row.get("candidates", row.get("actions"))
        if not isinstance(candidates, list) or not candidates:
            quarantined.append({"index": index, "reason": "missing_candidates", "row_hash": _hash(row)})
            continue
        prepared = []
        for candidate_index, raw_candidate in enumerate(candidates):
            if not isinstance(raw_candidate, Mapping):
                continue
            candidate = deepcopy(dict(raw_candidate))
            candidate["action_id"] = str(candidate.get("action_id") or candidate.get("id") or f"candidate_{candidate_index}")
            candidate["exact_damage_delta"] = _delta(candidate)
            candidate["features"] = _proposal_features(candidate)
            prepared.append(candidate)
        if not any(candidate.get("action_type") == "save_hold" or str(candidate["action_id"]).startswith("save_hold") for candidate in prepared):
            no_op = {"action_id": "save_hold_no_op", "action_type": "save_hold", "exact_damage_delta": 0.0}
            no_op["features"] = _proposal_features(no_op)
            prepared.append(no_op)
        best = max(_delta(candidate) for candidate in prepared)
        winners = frozenset(candidate["action_id"] for candidate in prepared if abs(_delta(candidate) - best) <= 1e-9)
        state_key = _hash([
            {"action_id": candidate["action_id"], "features": candidate["features"]}
            for candidate in sorted(prepared, key=lambda value: value["action_id"])
        ])
        previous = seen.get(state_key)
        if previous is not None and previous != winners:
            quarantined.append({
                "index": index,
                "reason": "contradictory_exact_label",
                "row_hash": _hash(row),
                "state_key": state_key,
                "previous_winners": sorted(previous),
                "new_winners": sorted(winners),
            })
            continue
        if previous is not None:
            continue
        seen[state_key] = winners
        row["candidates"] = prepared
        row.pop("actions", None)
        row["winner_ids"] = sorted(winners)
        row["exact_state_key"] = state_key
        accepted.append(row)
    return accepted, quarantined


__all__ = ["prepare_exact_training_rows"]
