"""Immutable parent/child champion lineage for offline proposal-ranker training.

A child always inherits a valid champion. It trains on exact sIO CE labels in a
separate checkpoint and may replace the current champion only after passing
holdout, no-op, conflict and no-regression gates. The deterministic optimizer's
winner remains exact before/after CE damage; these champions only order which
legal candidates should be evaluated first.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any, Iterable, Mapping, Sequence

from optimizer.numeric_features import FEATURE_COLUMNS, action_features
from optimizer.training_memory import atomic_write_json, utc_now

LINEAGE_VERSION = 1


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def safe_exact_ce_prior() -> list[float]:
    """Non-zero deterministic genesis used only when no past checkpoint exists."""
    weights = [0.0] * len(FEATURE_COLUMNS)
    values = {
        "immediate_damage": 1.0,
        "damage_gain_estimate": 1.0,
        "resource_costs": 0.01,
        "missing_data_penalty": 2.0,
        "confidence": 0.01,
        "confidence_score": 0.01,
        "source_confidence": 0.01,
    }
    for name, value in values.items():
        weights[FEATURE_COLUMNS.index(name)] = value
    return weights


def _valid_weights(values: Any) -> list[float] | None:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return None
    if len(values) != len(FEATURE_COLUMNS):
        return None
    converted = [_finite(value, math.nan) for value in values]
    if any(not math.isfinite(value) for value in converted):
        return None
    return converted


def _features(candidate: Mapping[str, Any]) -> list[float]:
    explicit = candidate.get("features")
    if isinstance(explicit, Mapping):
        return [_finite(explicit.get(name)) for name in FEATURE_COLUMNS]
    if isinstance(explicit, Sequence) and not isinstance(explicit, (str, bytes)) and len(explicit) == len(FEATURE_COLUMNS):
        return [_finite(value) for value in explicit]
    action = dict(candidate)
    if "expected_damage_delta" not in action:
        action["expected_damage_delta"] = _finite(
            candidate.get("exact_damage_delta", candidate.get("expected_dps_gain", candidate.get("damage_delta", 0.0)))
        )
    return action_features(action, scenario_id="clan_expedition")


def _candidate_delta(candidate: Mapping[str, Any]) -> float:
    for key in ("exact_damage_delta", "expected_dps_gain", "damage_delta", "label"):
        if key in candidate:
            return _finite(candidate.get(key))
    return 0.0


@dataclass(frozen=True)
class ExactExample:
    example_id: str
    candidates: tuple[dict[str, Any], ...]
    exact_winner_ids: frozenset[str]
    best_delta: float
    fingerprint: str


def normalize_example(row: Mapping[str, Any], index: int = 0) -> ExactExample:
    raw = row.get("candidates", row.get("actions"))
    if not isinstance(raw, list) or not raw:
        raise ValueError("Training row must contain a non-empty candidates/actions list.")
    candidates: list[dict[str, Any]] = []
    ids: set[str] = set()
    for candidate_index, value in enumerate(raw):
        if not isinstance(value, Mapping):
            raise ValueError("Every candidate must be an object.")
        candidate = dict(value)
        action_id = str(candidate.get("action_id") or candidate.get("id") or f"candidate_{candidate_index}")
        if action_id in ids:
            raise ValueError(f"Duplicate action_id {action_id}")
        ids.add(action_id)
        candidate["action_id"] = action_id
        candidate["exact_damage_delta"] = _candidate_delta(candidate)
        candidate["features_vector"] = _features(candidate)
        candidates.append(candidate)

    if not any(str(candidate["action_id"]).startswith("save_hold") or candidate.get("action_type") == "save_hold" for candidate in candidates):
        candidates.append({
            "action_id": "save_hold_no_op",
            "action_type": "save_hold",
            "exact_damage_delta": 0.0,
            "features_vector": action_features(
                {"action_id": "save_hold_no_op", "action_type": "save_hold", "expected_damage_delta": 0.0},
                scenario_id="clan_expedition",
            ),
        })
    best = max(_finite(candidate["exact_damage_delta"]) for candidate in candidates)
    winners = frozenset(
        str(candidate["action_id"])
        for candidate in candidates
        if abs(_finite(candidate["exact_damage_delta"]) - best) <= 1e-9
    )
    explicit_winners = row.get("winner_ids")
    if explicit_winners is not None:
        explicit = {str(value) for value in explicit_winners}
        if explicit != set(winners):
            raise ValueError(f"Explicit winner_ids conflict with exact damage deltas: {explicit} != {set(winners)}")
    canonical = [
        {
            "action_id": candidate["action_id"],
            "exact_damage_delta": candidate["exact_damage_delta"],
            "features": candidate["features_vector"],
        }
        for candidate in sorted(candidates, key=lambda value: str(value["action_id"]))
    ]
    fingerprint = _hash(canonical)
    return ExactExample(
        example_id=str(row.get("example_id") or row.get("profile_id") or f"example_{index}"),
        candidates=tuple(candidates),
        exact_winner_ids=winners,
        best_delta=best,
        fingerprint=fingerprint,
    )


def audit_examples(rows: Iterable[Mapping[str, Any]]) -> tuple[list[ExactExample], list[dict[str, Any]]]:
    accepted: list[ExactExample] = []
    quarantined: list[dict[str, Any]] = []
    by_fingerprint: dict[str, ExactExample] = {}
    for index, row in enumerate(rows):
        try:
            example = normalize_example(row, index)
        except (TypeError, ValueError) as error:
            quarantined.append({"index": index, "reason": str(error), "row_hash": _hash(row)})
            continue
        existing = by_fingerprint.get(example.fingerprint)
        if existing and existing.exact_winner_ids != example.exact_winner_ids:
            quarantined.append({
                "index": index,
                "reason": "contradictory_exact_label",
                "row_hash": _hash(row),
                "existing_example_id": existing.example_id,
            })
            continue
        if existing is None:
            by_fingerprint[example.fingerprint] = example
            accepted.append(example)
    return accepted, quarantined


def predict(weights: Sequence[float], example: ExactExample) -> tuple[str, float]:
    scored = []
    for candidate in example.candidates:
        score = sum(left * right for left, right in zip(weights, candidate["features_vector"]))
        scored.append((score, str(candidate["action_id"])))
    score, action_id = max(scored, key=lambda row: (row[0], row[1]))
    return action_id, score


def evaluate(weights: Sequence[float], examples: Sequence[ExactExample]) -> dict[str, Any]:
    correct = 0
    regret = 0.0
    no_op_failures = 0
    mandatory_failures = 0
    predictions: dict[str, str] = {}
    for example in examples:
        action_id, _ = predict(weights, example)
        predictions[example.example_id] = action_id
        if action_id in example.exact_winner_ids:
            correct += 1
        selected = next(candidate for candidate in example.candidates if candidate["action_id"] == action_id)
        selected_delta = _finite(selected["exact_damage_delta"])
        regret += max(0.0, example.best_delta - selected_delta)
        no_op_is_winner = "save_hold_no_op" in example.exact_winner_ids
        if no_op_is_winner and action_id != "save_hold_no_op":
            no_op_failures += 1
        if selected_delta < -1e-9 or (example.best_delta <= 0 and action_id != "save_hold_no_op"):
            mandatory_failures += 1
    total = len(examples)
    return {
        "examples": total,
        "correct": correct,
        "top1_accuracy": correct / total if total else 0.0,
        "mean_regret": regret / total if total else 0.0,
        "total_regret": regret,
        "no_op_failures": no_op_failures,
        "mandatory_failures": mandatory_failures,
        "predictions": predictions,
    }


def train_child(
    inherited_weights: Sequence[float],
    examples: Sequence[ExactExample],
    *,
    epochs: int = 3,
    learning_rate: float = 0.02,
    seed: int = 0,
) -> list[float]:
    weights = [float(value) for value in inherited_weights]
    rng = random.Random(seed)
    order = list(range(len(examples)))
    updates = 0
    for epoch in range(max(1, int(epochs))):
        rng.shuffle(order)
        rate = float(learning_rate) / math.sqrt(1.0 + epoch)
        for index in order:
            example = examples[index]
            winner_candidates = [candidate for candidate in example.candidates if candidate["action_id"] in example.exact_winner_ids]
            negative_candidates = [candidate for candidate in example.candidates if candidate["action_id"] not in example.exact_winner_ids]
            if not winner_candidates or not negative_candidates:
                continue
            positive = max(
                winner_candidates,
                key=lambda candidate: sum(value * weight for value, weight in zip(candidate["features_vector"], weights)),
            )
            negative = max(
                negative_candidates,
                key=lambda candidate: sum(value * weight for value, weight in zip(candidate["features_vector"], weights)),
            )
            positive_score = sum(value * weight for value, weight in zip(positive["features_vector"], weights))
            negative_score = sum(value * weight for value, weight in zip(negative["features_vector"], weights))
            if positive_score - negative_score >= 1.0:
                continue
            difference = [left - right for left, right in zip(positive["features_vector"], negative["features_vector"])]
            norm = math.sqrt(sum(value * value for value in difference)) or 1.0
            weights = [
                max(-10.0, min(10.0, weight + rate * value / norm))
                for weight, value in zip(weights, difference)
            ]
            updates += 1
    if not any(abs(value) > 1e-12 for value in weights):
        raise RuntimeError("Child training attempted to create a zero checkpoint.")
    return weights


class ChampionLineage:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.registry_path = self.root / "registry.json"
        self.champions_dir = self.root / "champions"
        self.children_dir = self.root / "children"
        self.quarantine_dir = self.root / "quarantine"
        self.root.mkdir(parents=True, exist_ok=True)
        self.champions_dir.mkdir(parents=True, exist_ok=True)
        self.children_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.registry = self._load_registry()

    def _load_registry(self) -> dict[str, Any]:
        if self.registry_path.is_file():
            try:
                payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
                if payload.get("version") == LINEAGE_VERSION:
                    return payload
            except (OSError, ValueError, TypeError):
                pass
        return {
            "version": LINEAGE_VERSION,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "current_champion_id": None,
            "hall_of_fame": [],
            "children": [],
        }

    def _save_registry(self) -> None:
        self.registry["updated_at"] = utc_now()
        atomic_write_json(self.registry_path, self.registry)

    def _checkpoint_path(self, champion_id: str) -> Path:
        return self.champions_dir / f"{champion_id}.json"

    def current(self) -> dict[str, Any] | None:
        champion_id = self.registry.get("current_champion_id")
        if not champion_id:
            return None
        path = self._checkpoint_path(str(champion_id))
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if _valid_weights(payload.get("weights")) is not None else None

    def hall(self) -> list[dict[str, Any]]:
        result = []
        for champion_id in self.registry.get("hall_of_fame", []):
            path = self._checkpoint_path(str(champion_id))
            if path.is_file():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if _valid_weights(payload.get("weights")) is not None:
                    result.append(payload)
        return result

    def ensure_genesis(self, legacy_paths: Iterable[Path] = ()) -> dict[str, Any]:
        current = self.current()
        if current:
            return current
        weights: list[float] | None = None
        source = "deterministic_exact_ce_prior"
        migrated_from = None
        for path in legacy_paths:
            if not Path(path).is_file():
                continue
            try:
                payload = json.loads(Path(path).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            weights = _valid_weights(payload.get("weights"))
            if weights is not None:
                source = "migrated_past_champion"
                migrated_from = str(path)
                break
        if weights is None:
            weights = safe_exact_ce_prior()
        champion_id = "champion-g0000-" + _hash({"weights": weights, "source": source})[:12]
        payload = {
            "version": LINEAGE_VERSION,
            "champion_id": champion_id,
            "generation": 0,
            "parent_ids": [],
            "created_at": utc_now(),
            "weights": weights,
            "feature_columns": list(FEATURE_COLUMNS),
            "metrics": {},
            "bootstrap_source": source,
            "migrated_from": migrated_from,
            "immutable": True,
            "role": "proposal_ordering_only",
        }
        atomic_write_json(self._checkpoint_path(champion_id), payload)
        self.registry["current_champion_id"] = champion_id
        self.registry["hall_of_fame"] = [champion_id]
        self._save_registry()
        return payload

    def spawn_child(self, *, seed: int, child_index: int = 0, historical_parent_count: int = 2) -> dict[str, Any]:
        parent = self.ensure_genesis()
        hall = [entry for entry in self.hall() if entry["champion_id"] != parent["champion_id"]]
        rng = random.Random(seed)
        rng.shuffle(hall)
        historical = hall[: max(0, historical_parent_count)]
        parent_weights = list(parent["weights"])
        weights = [0.85 * value for value in parent_weights]
        remaining = 0.15
        if historical:
            share = remaining / len(historical)
            for old in historical:
                for index, value in enumerate(old["weights"]):
                    weights[index] += share * float(value)
        else:
            for index, value in enumerate(parent_weights):
                weights[index] += remaining * float(value)
        mutation_rng = random.Random(_hash({"parent": parent["champion_id"], "seed": seed, "child": child_index}))
        for index in range(len(weights)):
            weights[index] += mutation_rng.uniform(-0.0025, 0.0025)
        child_id = f"child-g{int(parent.get('generation', 0)) + 1:04d}-{_hash({'parents': [parent['champion_id'], *[x['champion_id'] for x in historical]], 'seed': seed, 'child': child_index})[:12]}"
        return {
            "version": LINEAGE_VERSION,
            "child_id": child_id,
            "generation": int(parent.get("generation", 0)) + 1,
            "parent_ids": [parent["champion_id"], *[entry["champion_id"] for entry in historical]],
            "primary_parent_id": parent["champion_id"],
            "created_at": utc_now(),
            "inherited_weights": list(weights),
            "weights": list(weights),
            "feature_columns": list(FEATURE_COLUMNS),
            "role": "proposal_ordering_only",
        }

    def save_child(self, child: Mapping[str, Any], status: str) -> Path:
        child_id = str(child["child_id"])
        payload = {**deepcopy(dict(child)), "status": status, "saved_at": utc_now()}
        path = self.children_dir / f"{child_id}.json"
        atomic_write_json(path, payload)
        self.registry.setdefault("children", []).append({
            "child_id": child_id,
            "status": status,
            "generation": child.get("generation"),
            "primary_parent_id": child.get("primary_parent_id"),
            "saved_at": payload["saved_at"],
        })
        self._save_registry()
        return path

    def promotion_decision(
        self,
        child: Mapping[str, Any],
        champion_metrics: Mapping[str, Any],
        child_metrics: Mapping[str, Any],
        *,
        minimum_accuracy_gain: float = 0.0,
    ) -> dict[str, Any]:
        champion_predictions = champion_metrics.get("predictions", {}) or {}
        child_predictions = child_metrics.get("predictions", {}) or {}
        regressions = [
            example_id
            for example_id, prediction in champion_predictions.items()
            if prediction != child_predictions.get(example_id)
            and example_id in child_predictions
        ]
        accuracy_gain = _finite(child_metrics.get("top1_accuracy")) - _finite(champion_metrics.get("top1_accuracy"))
        regret_improved = _finite(child_metrics.get("mean_regret")) + 1e-12 < _finite(champion_metrics.get("mean_regret"))
        accuracy_not_worse = accuracy_gain >= -1e-12
        beats = accuracy_gain > minimum_accuracy_gain + 1e-12 or (accuracy_not_worse and regret_improved)
        gates = {
            "beats_champion": beats,
            "no_noop_failures": int(child_metrics.get("no_op_failures", 0)) == 0,
            "no_mandatory_failures": int(child_metrics.get("mandatory_failures", 0)) == 0,
            "accuracy_not_worse": accuracy_not_worse,
            "no_prediction_regression": not regressions,
            "nonzero_inherited_checkpoint": any(abs(float(value)) > 1e-12 for value in child.get("inherited_weights", [])),
            "parent_is_current_champion": child.get("primary_parent_id") == self.registry.get("current_champion_id"),
        }
        return {
            "promote": all(gates.values()),
            "gates": gates,
            "accuracy_gain": accuracy_gain,
            "regressed_example_ids": regressions,
        }

    def promote(self, child: Mapping[str, Any], decision: Mapping[str, Any]) -> dict[str, Any]:
        if not decision.get("promote"):
            raise ValueError("Child cannot be promoted because promotion gates failed.")
        champion_id = str(child["child_id"]).replace("child-", "champion-", 1)
        payload = {
            **deepcopy(dict(child)),
            "champion_id": champion_id,
            "promoted_at": utc_now(),
            "promotion_decision": deepcopy(dict(decision)),
            "immutable": True,
        }
        payload.pop("child_id", None)
        payload.pop("inherited_weights", None)
        atomic_write_json(self._checkpoint_path(champion_id), payload)
        self.registry["current_champion_id"] = champion_id
        hall = self.registry.setdefault("hall_of_fame", [])
        if champion_id not in hall:
            hall.append(champion_id)
        self._save_registry()
        return payload


__all__ = [
    "ChampionLineage",
    "ExactExample",
    "audit_examples",
    "evaluate",
    "normalize_example",
    "predict",
    "safe_exact_ce_prior",
    "train_child",
]
