#!/usr/bin/env python3
"""Audit the effect preflight against the locked sIO Bible and exact runtime."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from optimizer.sio_ce_constants import SIO_BUNDLE_SHA256
from optimizer.sio_effect_evaluator import compare_attack_options, load_effect_registry
from optimizer.sio_ce_account import prepare_sio_ce_profile
from optimizer.source_pack_optimizer import optimize_source_pack_actions


REQUIRED_MODULES = {
    37013, 24804, 67727, 88426,
    42052, 51642, 19425, 30396, 92316, 57223, 89505,
}
REQUIRED_BUNDLE_TERMS = {
    "poisonedUptime", "weakenedUptime", "chilledUptime",
    "lacerationUptime", "divineFireUptime", "shieldDamageUptime",
    "voidNeckBoostUptime", "atkBase", "atkEquipPercent",
    "atkHeroPercent", "atkPercent", "atkFinal",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bundle_text(path: Path) -> str:
    rows: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for member in archive.infolist():
            if member.filename.endswith((".js", ".html", ".json")):
                rows.append(archive.read(member).decode("utf-8", errors="ignore"))
    return "\n".join(rows)


def _mount_profile(*, stats: dict[str, float] | None = None) -> dict[str, Any]:
    return {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats_stage": "raw_profile",
            "stats": {},
            "evolvePassives": False,
            "attack": {"atkBase": 1000, "atkFinal": 0},
            "passive_multiplier": 1.0,
        },
        "mounts": {
            "active": "Doomsteed",
            "data": {
                "Doomsteed": {"enabled": True, "stars": 0, "lines": 0, "stats": {}},
                "Electric Scooter": {
                    "enabled": True,
                    "stars": 0,
                    "lines": 0,
                    "stats": dict(stats or {}),
                },
            },
        },
        "inventory": {"items": {"electric_scooter_shard": 20}},
    }


@contextmanager
def _temporary_env(**values: str | None) -> Iterator[None]:
    old = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_equivalence(profile: dict[str, Any]) -> dict[str, Any]:
    with _temporary_env(SIO_EFFECT_PREFLIGHT_PRUNE="0"):
        exhaustive = optimize_source_pack_actions(profile, device="cpu")
    with _temporary_env(SIO_EFFECT_PREFLIGHT_PRUNE="1"):
        preflight = optimize_source_pack_actions(profile, device="cpu")
    exhaustive_best = exhaustive.get("best") or exhaustive.get("no_op_baseline")
    preflight_best = preflight.get("best") or preflight.get("no_op_baseline")
    skipped_ids = {row["action_id"] for row in preflight.get("preflight_neutral_actions", [])}
    exact_by_id = {row["action_id"]: row for row in exhaustive.get("ranked_actions", [])}
    false_prunes = [
        {
            "action_id": action_id,
            "exact_damage_gain": exact_by_id[action_id]["expected_dps_gain"],
        }
        for action_id in sorted(skipped_ids & exact_by_id.keys())
        if abs(float(exact_by_id[action_id]["expected_dps_gain"])) > 1e-9
    ]
    return {
        "winner_equal": exhaustive_best.get("action_id") == preflight_best.get("action_id"),
        "exhaustive_winner": exhaustive_best.get("action_id"),
        "preflight_winner": preflight_best.get("action_id"),
        "states_without_suppression": exhaustive.get("numeric_backend", {}).get("states_scored_in_one_batch"),
        "states_with_suppression": preflight.get("numeric_backend", {}).get("states_scored_in_one_batch"),
        "skipped_ids": sorted(skipped_ids),
        "false_prunes": false_prunes,
    }


def audit(bundle: Path | None) -> dict[str, Any]:
    registry = load_effect_registry()
    code = (ROOT / "optimizer" / "sio_ce_damage.py").read_text(encoding="utf-8")
    conditional = registry.get("conditional_effects", [])
    registry_checks = {
        "bundle_hash_matches_constant": registry.get("bundle_sha256") == SIO_BUNDLE_SHA256,
        "all_effect_fields_in_formula_port": all(str(row["effect"]) in code for row in conditional),
        "all_uptime_fields_in_formula_port": all(str(row["uptime"]) in code for row in conditional),
        "safe_systems_declared": set(registry.get("safe_neutral_systems", {})) == {
            "items", "mounts", "pets", "survivor", "collectibles"
        },
    }

    low = compare_attack_options(prepare_sio_ce_profile({
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats_stage": "post_24804", "stats": {},
            "attack": {"atkBase": 1000, "atkFinal": 0}, "passive_multiplier": 1.0,
        },
    }))
    high = compare_attack_options(prepare_sio_ce_profile({
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats_stage": "post_24804", "stats": {},
            "attack": {"atkBase": 100000, "atkFinal": 0}, "passive_multiplier": 1.0,
        },
    }))
    formula_checks = {
        "flat_wins_at_low_attack": low.get("better_option") == "atkFinal",
        "percent_wins_at_high_attack": high.get("better_option") == "atkPercent",
        "low_attack_comparison": low,
        "high_attack_comparison": high,
    }

    bundle_checks: dict[str, Any] = {"provided": bundle is not None}
    equivalence: list[dict[str, Any]] = []
    if bundle is not None:
        actual_hash = _sha256(bundle)
        text = _bundle_text(bundle)
        bundle_checks.update({
            "path": str(bundle),
            "sha256": actual_hash,
            "hash_matches": actual_hash == SIO_BUNDLE_SHA256,
            "missing_modules": sorted(module for module in REQUIRED_MODULES if f"{module}:" not in text),
            "missing_terms": sorted(term for term in REQUIRED_BUNDLE_TERMS if term not in text),
        })
        with _temporary_env(SIO_TOOLS_BUNDLE=str(bundle)):
            equivalence = [
                {"case": "empty_inactive_mount_stats", **_run_equivalence(_mount_profile())},
                {"case": "active_skill_damage_mount_stats", **_run_equivalence(_mount_profile(stats={"skillDamage": 100}))},
                {"case": "inactive_poison_mount_stats", **_run_equivalence(_mount_profile(stats={"poisoned": 100}))},
            ]

    checks = list(registry_checks.values()) + [
        formula_checks["flat_wins_at_low_attack"],
        formula_checks["percent_wins_at_high_attack"],
    ]
    if bundle is not None:
        checks.extend([
            bool(bundle_checks.get("hash_matches")),
            not bundle_checks.get("missing_modules"),
            not bundle_checks.get("missing_terms"),
            all(row["winner_equal"] for row in equivalence),
            all(not row["false_prunes"] for row in equivalence),
        ])
    return {
        "status": "passed" if all(checks) else "failed",
        "registry_checks": registry_checks,
        "formula_checks": formula_checks,
        "bundle_checks": bundle_checks,
        "exact_equivalence_cases": equivalence,
        "false_prunes": [item for row in equivalence for item in row.get("false_prunes", [])],
        "source_policy": "unknown effects remain exact-scored; only source-proven zero CE states may be suppressed",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output", type=Path, default=Path("sio-effect-audit.json"))
    args = parser.parse_args()
    result = audit(args.bundle.resolve() if args.bundle else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
