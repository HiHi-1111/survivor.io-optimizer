#!/usr/bin/env python3
"""
Check whether the sIO candidate space is ready for real damage scoring.

This does not rank builds and does not invent values. It verifies that the pipeline has:
- normalized sIO data
- corrected player resource accounting
- generated candidates
- explicit blockers for missing mechanics/formulas
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"_missing": True, "_path": str(path)}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_load_error": str(exc), "_path": str(path)}


def bool_status(ok: bool) -> str:
    return "READY" if ok else "BLOCKED"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default="data/sio_training/candidates/dtlgrind_candidate_space.json")
    ap.add_argument("--normalized", default="data/sio_training/normalized/sio_normalized_tables.json")
    ap.add_argument("--out", default="data/sio_training/scoring")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    cand = load_json(Path(args.candidates))
    norm = load_json(Path(args.normalized))

    rv = cand.get("resource_view", {}) if isinstance(cand, dict) else {}
    bag = rv.get("bag_free", {}) if isinstance(rv, dict) else {}
    embedded = rv.get("embedded_committed", {}) if isinstance(rv, dict) else {}
    counts = cand.get("choice_candidate_space", {}).get("counts", {}) if isinstance(cand, dict) else {}

    candidate_ready = cand.get("schema") == "sio_candidate_generation_v2"
    resource_ready = (
        bag.get("eternal_cores") == 240
        and bag.get("void_cores") == 170
        and bag.get("chaos_cores") == 120
        and embedded.get("relic_cores_in_current_build") == 45
        and embedded.get("movable_awakening_cores_claimed") == 23
    )
    choice_ready = counts.get("combined_choice_space_count_before_slot_level_build_sim", 0) > 0
    normalized_ready = norm.get("schema") is not None and not norm.get("_missing") and not norm.get("_load_error")
    runtime_exact = norm.get("mode") not in ("python_static_fallback", None)

    blockers: List[str] = []
    if not candidate_ready:
        blockers.append("Candidate file is missing or not v2. Rerun generate_sio_candidates.py.")
    if not resource_ready:
        blockers.append("Resource accounting is not mapped correctly. Check v3 resource_accounting -> bag_free/embedded_committed.")
    if not choice_ready:
        blockers.append("Choice-space counts are missing. Candidate enumeration did not produce usable candidates.")
    if not normalized_ready:
        blockers.append("Normalized sIO tables are missing. Rerun normalizer.")
    if not runtime_exact:
        blockers.append("Normalizer is still Python static fallback. Good for indexing, but exact damage scorer needs runtime exports or a deeper parser for module 37013/32085 formulas.")

    blockers += [
        "Implement apply_to_build_state: convert chosen outputs into legal gear/tech/pet/survivor after-states.",
        "Implement sIO damage scorer: calculate before/after damage from normalized sIO formulas, not hardcoded preference.",
        "Patch AF refund/rebuild table before using embedded relic cores/S gear as movable equity.",
        "Patch Xeno awakening reset/refund proof before using all committed awakening cores as movable.",
        "Patch survivor shard conversion rules before treating survivor switching as flexible.",
    ]

    report = [
        "# sIO scoring readiness report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Readiness checks",
        f"- candidate_generator_v2: {bool_status(candidate_ready)}",
        f"- corrected_resource_accounting: {bool_status(resource_ready)}",
        f"- choice_space_enumerated: {bool_status(choice_ready)}",
        f"- normalized_tables_present: {bool_status(normalized_ready)}",
        f"- exact_runtime_exports_available: {bool_status(runtime_exact)}",
        "",
        "## Confirmed resource view",
        f"- bag_free eternal_cores: {bag.get('eternal_cores')}",
        f"- bag_free void_cores: {bag.get('void_cores')}",
        f"- bag_free chaos_cores: {bag.get('chaos_cores')}",
        f"- bag_free relic_cores: {bag.get('relic_cores')}",
        f"- embedded relic_cores_in_current_build: {embedded.get('relic_cores_in_current_build')}",
        f"- embedded/movable awakening cores claimed: {embedded.get('movable_awakening_cores_claimed')}",
        "",
        "## Candidate counts",
    ]
    for k, v in counts.items():
        report.append(f"- {k}: {v}")
    report += [
        "",
        "## Blockers before a real best-spend answer",
        *[f"- {b}" for b in blockers],
        "",
        "## Rule",
        "- Do not rank candidates until apply_to_build_state + sIO damage scorer are implemented.",
        "- Do not treat embedded build materials as free bag inventory.",
        "- Output unknown/needs_data_patch instead of guessing.",
    ]

    (out / "scoring_readiness_report.md").write_text("\n".join(report), encoding="utf-8")
    (out / "scoring_readiness.json").write_text(json.dumps({
        "schema": "sio_scoring_readiness_v1",
        "candidate_ready": candidate_ready,
        "resource_ready": resource_ready,
        "choice_ready": choice_ready,
        "normalized_ready": normalized_ready,
        "runtime_exact": runtime_exact,
        "blockers": blockers,
    }, indent=2), encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
