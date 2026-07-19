#!/usr/bin/env python3
"""Record one observed Clan Expedition result against the exact sIO prediction.

The sIO ID is hashed before storage. This command never alters formulas or
champions; repeated consistent observations are only flagged for review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from optimizer.damage_engine import estimate_damage_totals  # noqa: E402
from optimizer.sio_calibration import SioCalibrationStore  # noqa: E402


def _load_profile(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("Profile JSON must be an object.")
    return dict(value)


def _nested(profile: Mapping[str, Any], key: str) -> Any:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    return sio.get(key, profile.get(key))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--sio-id")
    parser.add_argument("--observed-damage", type=float)
    parser.add_argument(
        "--store",
        type=Path,
        default=ROOT / "training_outputs" / "sio_calibration" / "observations.jsonl",
    )
    parser.add_argument("--context", help="Optional JSON object describing the CE run.")
    args = parser.parse_args()

    profile = _load_profile(args.profile)
    sio_id = args.sio_id or _nested(profile, "sio_id")
    observed = args.observed_damage
    if observed is None:
        observed = _nested(profile, "observed_ce_damage")
    if not sio_id:
        raise SystemExit("Missing sIO ID. Supply --sio-id or sio_ce.sio_id in the profile.")
    if observed is None:
        raise SystemExit(
            "Missing observed damage. Supply --observed-damage or sio_ce.observed_ce_damage in the profile."
        )

    result = estimate_damage_totals(profile)
    if not result.get("supported"):
        raise SystemExit(f"Profile is not exactly scoreable: {result.get('reason')}")
    if not result.get("runtime_exact"):
        raise SystemExit(
            "Calibration requires the supplied sIO runtime oracle. A Python fallback is not accepted as a teacher."
        )
    context = json.loads(args.context) if args.context else {}
    if not isinstance(context, Mapping):
        raise SystemExit("--context must be a JSON object.")

    store = SioCalibrationStore(args.store)
    record = store.record(
        sio_id=str(sio_id),
        profile=profile,
        predicted_damage=float(result["total_damage"]),
        observed_damage=float(observed),
        formula_provenance=result.get("formula_provenance", {}),
        run_context=context,
    )
    review = store.review_candidates()
    print(json.dumps({
        "status": "recorded",
        "store": str(args.store),
        "profile_fingerprint": record["profile_fingerprint"],
        "predicted_damage": record["predicted_damage"],
        "observed_damage": record["observed_damage"],
        "absolute_percent_error": record["absolute_percent_error"],
        "review_candidates": review,
        "automatic_formula_mutation": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
