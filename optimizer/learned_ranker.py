"""Small persistent online ranker for proposal ordering only.

Exact sIO CE damage always chooses the final optimizer winner. Every enabled
ranker inherits the immutable lineage champion before it can observe a sample;
there is no zero-weight birth path. A saved working child may resume only while
its recorded parent is still the current champion.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

from optimizer.numeric_features import FEATURE_COLUMNS
from optimizer.training_memory import atomic_write_json


class OnlineLinearRanker:
    def __init__(
        self,
        checkpoint_path: Path,
        *,
        learning_rate: float = 0.01,
        enabled: bool = True,
        lineage_root: Path | None = None,
        require_inherited_start: bool = True,
    ) -> None:
        self.checkpoint_path = checkpoint_path
        self.learning_rate = float(learning_rate)
        self.enabled = bool(enabled)
        self.weights = [0.0] * len(FEATURE_COLUMNS)
        self.samples = 0
        self.updates = 0
        self.loaded = False
        self.inherited = False
        self.parent_champion_id: str | None = None
        env_root = os.environ.get("SIO_CHAMPION_LINEAGE_ROOT")
        self.lineage_root = lineage_root or (Path(env_root) if env_root else checkpoint_path.parent / "champion_lineage")
        self.require_inherited_start = bool(require_inherited_start)
        if not self.enabled:
            return

        from optimizer.champion_lineage import ChampionLineage

        working_payload: dict[str, Any] | None = None
        working_weights: list[float] | None = None
        if checkpoint_path.is_file():
            try:
                payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                stored = payload.get("weights", [])
                if len(stored) == len(FEATURE_COLUMNS):
                    values = [float(value) for value in stored]
                    if all(math.isfinite(value) for value in values) and any(abs(value) > 1e-12 for value in values):
                        working_payload = payload
                        working_weights = values
            except (OSError, ValueError, TypeError):
                working_payload = None
                working_weights = None

        # A pre-lineage non-zero checkpoint may seed generation zero once. A
        # zero checkpoint is ignored and replaced with the safe non-zero prior.
        legacy_paths = []
        if working_payload is not None and not working_payload.get("parent_champion_id"):
            legacy_paths.append(checkpoint_path)
        lineage = ChampionLineage(self.lineage_root)
        champion = lineage.ensure_genesis(legacy_paths)
        champion_id = str(champion["champion_id"])
        champion_weights = [float(value) for value in champion["weights"]]
        if not any(abs(value) > 1e-12 for value in champion_weights):
            raise RuntimeError("A proposal ranker cannot inherit a zero checkpoint.")

        can_resume_child = (
            working_payload is not None
            and working_weights is not None
            and str(working_payload.get("parent_champion_id") or "") == champion_id
            and bool(working_payload.get("inherited_from_champion"))
            and working_payload.get("can_replace_champion_directly") is False
        )
        if can_resume_child:
            self.weights = working_weights
            self.samples = int(working_payload.get("samples", 0))
            self.updates = int(working_payload.get("updates", 0))
            self.loaded = True
        else:
            self.weights = champion_weights
            self.loaded = bool(
                champion.get("bootstrap_source") == "migrated_past_champion"
                or champion.get("generation", 0) > 0
            )
            if working_payload is not None and champion.get("migrated_from") == str(checkpoint_path):
                self.samples = int(working_payload.get("samples", 0))
                self.updates = int(working_payload.get("updates", 0))
        self.parent_champion_id = champion_id
        self.inherited = True

    def observe(self, rows: list[dict[str, Any]], winner_ids: set[str]) -> bool:
        if not self.enabled or not rows or not winner_ids:
            return False
        positives = [row for row in rows if str(row.get("action_id", "")) in winner_ids]
        negatives = [row for row in rows if str(row.get("action_id", "")) not in winner_ids]
        if not positives or not negatives:
            return False
        positive = self._mean(positives)
        negative = self._mean(negatives[:256])
        delta = [left - right for left, right in zip(positive, negative)]
        norm = math.sqrt(sum(value * value for value in delta)) or 1.0
        rate = self.learning_rate / math.sqrt(1.0 + self.updates / 1000.0)
        self.weights = [
            max(-10.0, min(10.0, weight + rate * value / norm))
            for weight, value in zip(self.weights, delta)
        ]
        self.samples += 1
        self.updates += 1
        return True

    def _mean(self, rows: list[dict[str, Any]]) -> list[float]:
        values = [
            [float(row.get("features", {}).get(column, 0.0)) for column in FEATURE_COLUMNS]
            for row in rows
        ]
        return [sum(row[index] for row in values) / len(values) for index in range(len(FEATURE_COLUMNS))]

    def snapshot_weights(self) -> list[float]:
        return list(self.weights) if self.enabled else []

    def save(self) -> None:
        if not self.enabled:
            return
        # This is a mutable working-child checkpoint, never the champion file.
        atomic_write_json(self.checkpoint_path, self.report())

    def report(self) -> dict[str, Any]:
        importance = sorted(
            (
                {"feature": name, "weight": round(weight, 8), "importance": round(abs(weight), 8)}
                for name, weight in zip(FEATURE_COLUMNS, self.weights)
            ),
            key=lambda row: row["importance"],
            reverse=True,
        )
        return {
            "version": 3,
            "model": "online_linear_pairwise_ranker",
            "role": "proposal_ordering_child_only",
            "enabled": self.enabled,
            "samples": self.samples,
            "updates": self.updates,
            "loaded_from_checkpoint": self.loaded,
            "inherited_from_champion": self.inherited,
            "parent_champion_id": self.parent_champion_id,
            "lineage_root": str(self.lineage_root),
            "weights": self.weights,
            "feature_importance": importance,
            "checkpoint_path": str(self.checkpoint_path),
            "can_replace_champion_directly": False,
        }


def learned_score(features: list[float], weights: list[float] | None) -> float:
    if not weights:
        return 0.0
    return sum(value * weight for value, weight in zip(features, weights))
