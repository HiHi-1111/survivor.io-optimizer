#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_load_error": str(exc), "_path": str(path)}


def read_text(path: Path, limit_chars: int | None = None) -> str:
    if not path.exists():
        return f"MISSING: {path}"
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except TypeError:
        text = path.read_text(encoding="utf-8-sig")
    if limit_chars and len(text) > limit_chars:
        return text[:limit_chars] + f"\n\n...TRUNCATED IN ONE-REPORT VIEW; original file has {len(text):,} chars...\n"
    return text


def find_count(obj: Any, key: str) -> int:
    best = 0
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k == key and isinstance(v, (dict, list)):
                    best = max(best, len(v))
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            for v in cur:
                if isinstance(v, (dict, list)):
                    stack.append(v)
    return best


def one_line_summary(fullpower: Dict[str, Any], candidate: Dict[str, Any], scoring: Dict[str, Any], normalized: Dict[str, Any]) -> List[str]:
    fp_counts = fullpower.get("allocation_counts", {}) if isinstance(fullpower, dict) else {}
    rv = fullpower.get("resource_view") or candidate.get("resource_view", {})
    bag = rv.get("bag_free", {}) if isinstance(rv, dict) else {}
    emb = rv.get("embedded_committed", {}) if isinstance(rv, dict) else {}
    passes = fullpower.get("passes", "unknown")
    workers = fullpower.get("workers", "unknown")
    schema = candidate.get("schema", "unknown")
    norm_mode = normalized.get("mode", "unknown")
    return [
        "# Survivor.io Optimizer SEND THIS ONE REPORT",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Bottom line",
        "- Final best-spend answer: BLOCKED until apply_to_build_state + sIO damage scorer exist.",
        "- Candidate/resource/fullpower validation: GOOD if the checks below say READY/OK.",
        "- Do not treat embedded relic cores or committed awakening cores as free inventory.",
        "",
        "## Key validated numbers",
        f"- candidate schema: {schema}",
        f"- normalizer mode: {norm_mode}",
        f"- workers: {workers}",
        f"- passes: {passes}",
        f"- combos per pass: {fp_counts.get('combined_choice_space_count_per_pass')}",
        f"- total combos checked: {fp_counts.get('combined_choice_space_total_checked')}",
        f"- deterministic hash match: {fullpower.get('deterministic_hash_match')}",
        f"- bag_free eternal_cores: {bag.get('eternal_cores')}",
        f"- bag_free void_cores: {bag.get('void_cores')}",
        f"- bag_free chaos_cores: {bag.get('chaos_cores')}",
        f"- bag_free relic_cores: {bag.get('relic_cores')}",
        f"- gems: {bag.get('gems')}",
        f"- embedded relic cores in current build: {emb.get('relic_cores_in_current_build')}",
        f"- movable awakening cores claimed: {emb.get('movable_awakening_cores_claimed')}",
        "",
        "## Normalized data quick counts, deep scan",
        f"- items: {find_count(normalized, 'items')}",
        f"- techs: {find_count(normalized, 'techs')}",
        f"- pets: {find_count(normalized, 'pets')}",
        f"- heroes: {find_count(normalized, 'heroes')}",
        f"- collectibles: {find_count(normalized, 'collectibles')}",
        f"- xenoPetAwakening: {find_count(normalized, 'xenoPetAwakening')}",
        "",
        "## Remaining blockers",
        "- apply_to_build_state: not done yet.",
        "- sIO damage scorer: not done yet.",
        "- AF refund/rebuild table: still needs patch/extraction before embedded relic cores can move.",
        "- Xeno awakening reset/refund proof: still needed before committed awakening cores are treated as flexible.",
        "- survivor shard conversion rules: still blocked unless patched.",
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/sio_training/SEND_THIS_ONE_REPORT.md")
    ap.add_argument("--also-root", default="SEND_THIS_ONE_REPORT.md")
    args = ap.parse_args()

    fullpower_json = load_json(Path("data/sio_training/fullpower/latest/fullpower_candidate_index.json"))
    candidate_json = load_json(Path("data/sio_training/candidates/dtlgrind_candidate_space.json"))
    scoring_json = load_json(Path("data/sio_training/scoring/scoring_readiness.json"))
    normalized_json = load_json(Path("data/sio_training/normalized/sio_normalized_tables.json"))

    sections: List[Tuple[str, str, int | None]] = [
        ("Fullpower candidate index report", "data/sio_training/fullpower/latest/fullpower_candidate_index_report.md", None),
        ("After-state bridge probe report", "data/sio_training/afterstate/afterstate_bridge_probe_report.md", None),
        ("Candidate generator report", "data/sio_training/candidates/candidate_generator_report.md", None),
        ("Scoring readiness report", "data/sio_training/scoring/scoring_readiness_report.md", None),
        ("Normalizer unknowns report", "data/sio_training/normalized/normalizer_unknowns_report.md", None),
        ("Extractor unknowns report", "data/sio_training/generated/unknowns_report.md", None),
        ("Walkaway log", "data/sio_training/walkaway/walkaway_one_report.log", 120000),
    ]

    lines = one_line_summary(fullpower_json, candidate_json, scoring_json, normalized_json)
    for title, raw_path, limit in sections:
        path = Path(raw_path)
        lines += ["", "---", "", f"## FILE: {raw_path}", "", read_text(path, limit)]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines).replace("\r\n", "\n")
    out_path.write_text(text, encoding="utf-8")

    root_path = Path(args.also_root)
    if root_path:
        root_path.write_text(text, encoding="utf-8")

    print("WROTE ONE REPORT:")
    print(out_path.resolve())
    if root_path:
        print(root_path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
