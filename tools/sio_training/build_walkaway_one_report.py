#!/usr/bin/env python3
"""
Build one single markdown file to send back to ChatGPT.

This intentionally gathers the separate internal artifacts into one report so the user
only has to upload one file.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List


def read_text(path: Path, max_chars: int | None = None) -> str:
    if not path.exists():
        return f"MISSING: {path}"
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except TypeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"ERROR reading {path}: {exc}"
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars] + f"\n\n...TRUNCATED in one-file report after {max_chars} chars. Original chars: {len(text)}"
    return text


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"_error": str(exc), "_path": str(path)}


def tail_lines(path: Path, n: int = 260) -> str:
    text = read_text(path)
    lines = text.splitlines()
    if len(lines) <= n:
        return text
    return "\n".join(lines[-n:])


def md_code(label: str, text: str) -> List[str]:
    return [f"```{label}", text.rstrip(), "```"]


def summarize_fullpower(data: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    alloc = data.get("allocation_counts", {}) if isinstance(data.get("allocation_counts"), dict) else {}
    rv = data.get("resource_view", {}) if isinstance(data.get("resource_view"), dict) else {}
    bag = rv.get("bag_free", {}) if isinstance(rv.get("bag_free"), dict) else {}
    emb = rv.get("embedded_committed", {}) if isinstance(rv.get("embedded_committed"), dict) else {}
    lines.append(f"- schema: {data.get('schema', 'unknown')}")
    lines.append(f"- workers: {data.get('workers', 'unknown')}")
    lines.append(f"- passes: {data.get('passes', 'unknown')}")
    lines.append(f"- combos per pass: {alloc.get('combined_choice_space_count_per_pass', 'unknown')}")
    lines.append(f"- total combos checked: {alloc.get('combined_choice_space_total_checked', 'unknown')}")
    lines.append(f"- deterministic hash match: {data.get('deterministic_hash_match', 'unknown')}")
    lines.append(f"- validation: {data.get('validation', 'unknown')}")
    lines.append(f"- bag_free eternal/void/chaos/relic: {bag.get('eternal_cores')}/{bag.get('void_cores')}/{bag.get('chaos_cores')}/{bag.get('relic_cores')}")
    lines.append(f"- gems: {bag.get('gems')}")
    lines.append(f"- embedded relic cores: {emb.get('relic_cores_in_current_build')}")
    lines.append(f"- embedded/movable awakening cores claimed: {emb.get('movable_awakening_cores_claimed')}")
    blockers = data.get("blocked_from_final_ranking_until", [])
    if blockers:
        lines.append("- blockers:")
        for b in blockers:
            lines.append(f"  - {b}")
    return lines


def summarize_afterstate(data: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append(f"- schema: {data.get('schema', 'unknown')}")
    lines.append(f"- can_start_apply_to_build_state_scaffolding: {data.get('can_start_apply_to_build_state_scaffolding', 'unknown')}")
    blockers = data.get("blocked_from_final_ranking_until", [])
    if blockers:
        lines.append("- blocked bridges:")
        for b in blockers:
            lines.append(f"  - {b}")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--out", default="data/sio_training/SEND_THIS_ONE_REPORT.md")
    ap.add_argument("--log", default="data/sio_training/ONE_SEND/walkaway_run.log")
    args = ap.parse_args()

    root = Path(args.repo_root)
    out = root / args.out
    log = root / args.log

    paths = {
        "fullpower_md": root / "data/sio_training/fullpower/latest/fullpower_candidate_index_report.md",
        "fullpower_json": root / "data/sio_training/fullpower/latest/fullpower_candidate_index.json",
        "afterstate_md": root / "data/sio_training/afterstate/afterstate_bridge_probe_report.md",
        "afterstate_json": root / "data/sio_training/afterstate/afterstate_bridge_probe.json",
        "scoring_md": root / "data/sio_training/scoring/scoring_readiness_report.md",
        "candidate_md": root / "data/sio_training/candidates/candidate_generator_report.md",
        "normalizer_unknowns": root / "data/sio_training/normalized/normalizer_unknowns_report.md",
        "extract_unknowns": root / "data/sio_training/generated/unknowns_report.md",
        "distribution_csv": root / "data/sio_training/fullpower/latest/fullpower_distribution_index.csv",
    }

    fullpower = load_json(paths["fullpower_json"])
    afterstate = load_json(paths["afterstate_json"])

    lines: List[str] = []
    lines.append("# SEND THIS ONE REPORT — Survivor.io optimizer walk-away run")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("## One-file rule")
    lines.append("Upload this file only unless ChatGPT specifically asks for a raw JSON/CSV later.")
    lines.append("")
    lines.append("## Top status")
    lines.extend(summarize_fullpower(fullpower))
    lines.append("")
    lines.append("## After-state status")
    lines.extend(summarize_afterstate(afterstate))
    lines.append("")
    lines.append("## Final ranking rule")
    lines.append("No final best-spend recommendation is allowed until apply_to_build_state and the sIO damage scorer exist and pass validation.")
    lines.append("")

    sections = [
        ("Fullpower candidate index report", paths["fullpower_md"], "markdown", None),
        ("After-state bridge probe report", paths["afterstate_md"], "markdown", None),
        ("Scoring readiness report", paths["scoring_md"], "markdown", None),
        ("Candidate generator report", paths["candidate_md"], "markdown", None),
        ("Normalizer unknowns report", paths["normalizer_unknowns"], "markdown", None),
        ("Extractor unknowns report", paths["extract_unknowns"], "markdown", None),
        ("Distribution CSV preview", paths["distribution_csv"], "csv", 20000),
        ("Walkaway run log tail", log, "text", None),
    ]

    for title, path, lang, max_chars in sections:
        lines.append(f"## {title}")
        lines.append("")
        content = tail_lines(path, 320) if "log" in title.lower() else read_text(path, max_chars=max_chars)
        lines.extend(md_code(lang, content))
        lines.append("")

    lines.append("## Machine-readable fullpower JSON preview")
    lines.append("")
    lines.extend(md_code("json", read_text(paths["fullpower_json"], max_chars=65000)))
    lines.append("")
    lines.append("## Machine-readable afterstate JSON")
    lines.append("")
    lines.extend(md_code("json", read_text(paths["afterstate_json"], max_chars=45000)))
    lines.append("")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"WROTE_ONE_REPORT={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
