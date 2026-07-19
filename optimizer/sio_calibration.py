"""Immutable sIO-ID / observed Clan Expedition calibration records.

Observed runs are evidence for reviewing formula assembly. They never silently
rescale optimizer damage. A calibration may be exported for analysis only after
repeated same-formula observations pass minimum-sample and dispersion gates.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping

from optimizer.training_memory import utc_now


def _stable(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_stable(value).encode("utf-8")).hexdigest()


def _finite(value: Any) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Calibration damage must be finite.")
    return number


def profile_fingerprint(profile: Mapping[str, Any]) -> str:
    sanitized = dict(profile)
    sanitized.pop("observed_damage", None)
    sanitized.pop("calibration", None)
    sio = sanitized.get("sio_ce")
    if isinstance(sio, Mapping):
        sio = dict(sio)
        for key in ("observed_damage", "observed_ce_damage", "sio_id"):
            sio.pop(key, None)
        sanitized["sio_ce"] = sio
    return _hash(sanitized)


class SioCalibrationStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def record(
        self,
        *,
        sio_id: str,
        profile: Mapping[str, Any],
        predicted_damage: float,
        observed_damage: float,
        formula_provenance: Mapping[str, Any],
        run_context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        predicted = _finite(predicted_damage)
        observed = _finite(observed_damage)
        if predicted <= 0 or observed <= 0:
            raise ValueError("Calibration damage values must be positive.")
        mode = str(profile.get("game_mode") or profile.get("goal_scenario") or "clan_expedition")
        if mode not in {"clan_expedition", "ce"}:
            raise ValueError("Only Clan Expedition calibration records are accepted.")
        record = {
            "schema": "sio_ce_calibration_observation_v1",
            "recorded_at": utc_now(),
            "sio_id_hash": hashlib.sha256(str(sio_id).encode("utf-8")).hexdigest(),
            "profile_fingerprint": profile_fingerprint(profile),
            "predicted_damage": predicted,
            "observed_damage": observed,
            "ratio_observed_to_predicted": observed / predicted,
            "residual": observed - predicted,
            "absolute_percent_error": abs(observed - predicted) / observed * 100.0,
            "formula_provenance": dict(formula_provenance),
            "formula_key": _hash(formula_provenance),
            "run_context": dict(run_context or {}),
            "game_mode": "clan_expedition",
            "automatic_formula_mutation": False,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record

    def rows(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        rows = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if isinstance(value, Mapping):
                    rows.append(dict(value))
        return rows

    def review_candidates(
        self,
        *,
        minimum_samples: int = 5,
        maximum_relative_mad: float = 0.05,
    ) -> list[dict[str, Any]]:
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in self.rows():
            key = (str(row.get("sio_id_hash")), str(row.get("formula_key")))
            groups.setdefault(key, []).append(row)
        candidates = []
        for (sio_id_hash, formula_key), rows in groups.items():
            ratios = [float(row["ratio_observed_to_predicted"]) for row in rows]
            center = median(ratios)
            mad = median(abs(value - center) for value in ratios)
            relative_mad = mad / abs(center) if center else math.inf
            eligible = len(rows) >= minimum_samples and relative_mad <= maximum_relative_mad
            candidates.append({
                "sio_id_hash": sio_id_hash,
                "formula_key": formula_key,
                "samples": len(rows),
                "median_ratio": center,
                "relative_mad": relative_mad,
                "eligible_for_human_review": eligible,
                "automatic_promotion": False,
                "reason": (
                    "enough consistent observations; review formula assembly and uptime inputs"
                    if eligible else "insufficient or inconsistent observations"
                ),
            })
        return sorted(candidates, key=lambda row: (-row["samples"], row["formula_key"]))

    def export_training_rows(self) -> list[dict[str, Any]]:
        """Export observations without converting them into optimizer winners."""
        return [
            {
                "profile_fingerprint": row["profile_fingerprint"],
                "formula_key": row["formula_key"],
                "predicted_damage": row["predicted_damage"],
                "observed_damage": row["observed_damage"],
                "residual": row["residual"],
                "ratio": row["ratio_observed_to_predicted"],
                "target": "formula_assembly_review_only",
            }
            for row in self.rows()
        ]


__all__ = ["SioCalibrationStore", "profile_fingerprint"]
