#!/usr/bin/env python3
"""
Full-power candidate-space indexer for the Survivor.io optimizer.

This intentionally still does NOT rank best spend. It burns CPU to enumerate the full
legal choice-output space, validates counts/resources, writes stable hashes, and produces
index tables that the later build-state simulator/scorer can consume.

v2 nested-choice fix:
- Relic Core Chest can output S-grade Excellent Choice Pack.
- Those newly-created S packs must be included in the Eternal/Void/Chaos selector-family
  allocation space.
- Therefore the S-pack allocation count depends on each relic chest allocation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

CORE_KEYS = ("Awakening Core", "Xeno Pet Core", "Relic Core", "Resonance Chip")
RELIC_KEYS = ("Relic Core", "S-grade Excellent Choice Pack")
TECH_KEYS = ("Eternal Tech Core", "Void Tech Core", "Chaos Tech Core")
S_KEYS = ("Eternal equipment selector", "Voidwaker equipment selector", "Chaos equipment selector")


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"_load_error": str(exc), "_path": str(path)}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def distributions(total: int, k: int) -> Iterable[Tuple[int, ...]]:
    if k == 1:
        yield (total,)
        return
    for n in range(total + 1):
        for rest in distributions(total - n, k - 1):
            yield (n,) + rest


def count_distributions(total: int, k: int) -> int:
    if total < 0 or k <= 0:
        return 0
    return math.comb(total + k - 1, k - 1)


def first_number(*values: Any, default: int = 0) -> int:
    for value in values:
        if value is None:
            continue
        try:
            if isinstance(value, str) and not value.strip():
                continue
            return int(value)
        except Exception:
            continue
    return default


def read_resource_view(state: Dict[str, Any], candidate: Dict[str, Any] | None) -> Dict[str, Any]:
    if candidate and isinstance(candidate.get("resource_view"), dict):
        return candidate["resource_view"]

    resources = state.get("resources", {}) if isinstance(state.get("resources"), dict) else {}
    accounting = state.get("resource_accounting", {}) if isinstance(state.get("resource_accounting"), dict) else {}
    pet = state.get("pet", {}) if isinstance(state.get("pet"), dict) else {}
    return {
        "bag_free": {
            "eternal_cores": first_number(resources.get("eternal_cores"), accounting.get("eternal_cores_current_count")),
            "void_cores": first_number(resources.get("void_cores"), accounting.get("void_cores_current_count")),
            "chaos_cores": first_number(resources.get("chaos_cores"), accounting.get("chaos_cores_current_count")),
            "relic_cores": first_number(resources.get("relic_cores_free_to_spend"), accounting.get("relic_cores_free_to_spend")),
            "gems": first_number(resources.get("gems"), accounting.get("gems")),
            "xeno_pet_crystal": first_number(pet.get("xeno_pet_crystal")),
            "xeno_pet_elixir": first_number(pet.get("xeno_pet_elixir")),
        },
        "embedded_committed": {
            "relic_cores_in_current_build": first_number(
                resources.get("relic_cores_in_current_build"),
                resources.get("relic_cores_locked_in_current_build"),
                accounting.get("relic_cores_inside_current_build"),
            ),
            "movable_awakening_cores_claimed": first_number(resources.get("movable_awakening_cores"), accounting.get("movable_awakening_cores")),
            "rule": "Committed build resources are not bag inventory. They require modeled reversion/move actions.",
        },
    }


def derive_counts(state: Dict[str, Any]) -> Dict[str, int]:
    choice = state.get("choice_consumables", {}) if isinstance(state.get("choice_consumables"), dict) else {}
    return {
        "core_chest": int(choice.get("core_chest", 0) or 0),
        "relic_core_chest": int(choice.get("relic_core_chest", 0) or 0),
        "tech_core_choice_chest": int(choice.get("tech_core_choice_chest", 0) or 0),
        "s_grade_excellent_choice_pack": int(choice.get("s_grade_excellent_choice_pack", 0) or 0),
        "voidwalker_supply_crate": int(choice.get("voidwalker_supply_crate", 0) or 0),
    }


def direct_outputs(core: Tuple[int, ...], relic: Tuple[int, ...], tech: Tuple[int, ...], s_pack: Tuple[int, ...], void_crates: int) -> Dict[str, int]:
    """
    Convert one fully-opened choice tuple into final direct outputs.

    Important:
    - Relic Core Chest -> S-grade Excellent Choice Pack is NOT left as a final direct output here.
    - It is opened in the same candidate into Eternal/Void/Chaos equipment selector family outputs.
    """
    out: Dict[str, int] = {}
    for k, v in zip(CORE_KEYS, core):
        if v:
            out[k] = out.get(k, 0) + int(v)

    relic_core_count = int(relic[0])
    if relic_core_count:
        out["Relic Core"] = out.get("Relic Core", 0) + relic_core_count

    for k, v in zip(TECH_KEYS, tech):
        if v:
            out[k] = out.get(k, 0) + int(v)

    for k, v in zip(S_KEYS, s_pack):
        if v:
            out[k] = out.get(k, 0) + int(v)

    if void_crates:
        out["Voidwaker equipment selector"] = out.get("Voidwaker equipment selector", 0) + int(void_crates)
    return out


def worker(args: Tuple[int, Tuple[int, ...], List[Tuple[int, ...]], List[Tuple[int, ...]], int, int]) -> Dict[str, Any]:
    core_idx, core, relics, techs, base_s_pack_n, void_crates = args
    h = hashlib.sha256()
    count = 0
    by_relic = Counter()
    by_xeno = Counter()
    by_awake = Counter()
    by_res_chip = Counter()
    by_total_s_packs = Counter()
    maxima: Dict[str, Tuple[int, Dict[str, int]]] = {}

    for relic in relics:
        s_from_relic = int(relic[1])
        total_s_pack_n = base_s_pack_n + s_from_relic
        s_packs = list(distributions(total_s_pack_n, len(S_KEYS)))
        by_total_s_packs[total_s_pack_n] += len(techs) * len(s_packs)
        for tech in techs:
            for s_pack in s_packs:
                out = direct_outputs(core, relic, tech, s_pack, void_crates)
                count += 1
                relic_total = out.get("Relic Core", 0)
                xeno_total = out.get("Xeno Pet Core", 0)
                awake_total = out.get("Awakening Core", 0)
                res_total = out.get("Resonance Chip", 0)
                by_relic[relic_total] += 1
                by_xeno[xeno_total] += 1
                by_awake[awake_total] += 1
                by_res_chip[res_total] += 1
                for key, val in out.items():
                    prev = maxima.get(key)
                    if prev is None or val > prev[0]:
                        maxima[key] = (val, out)
                # Compact stable hash. Enough to prove every tuple was visited without writing every row.
                h.update((str(core_idx) + "|" + ",".join(map(str, core + relic + tech + s_pack)) + "\n").encode("utf-8"))

    return {
        "core_idx": core_idx,
        "count": count,
        "sha256": h.hexdigest(),
        "by_relic": dict(by_relic),
        "by_xeno": dict(by_xeno),
        "by_awake": dict(by_awake),
        "by_resonance_chip": dict(by_res_chip),
        "by_total_s_packs_to_allocate": dict(by_total_s_packs),
        "maxima": {k: {"value": v[0], "example_outputs": v[1]} for k, v in maxima.items()},
    }


def merge_counters(target: Counter, data: Dict[str, int]) -> None:
    for k, v in data.items():
        target[int(k)] += int(v)


def update_maxima(target: Dict[str, Dict[str, Any]], source: Dict[str, Dict[str, Any]]) -> None:
    for key, entry in source.items():
        if key not in target or int(entry["value"]) > int(target[key]["value"]):
            target[key] = entry


def run_full_index(state: Dict[str, Any], candidate: Dict[str, Any] | None, out: Path, passes: int, workers: int, verbose_every: int) -> Dict[str, Any]:
    counts = derive_counts(state)
    core_allocs = list(distributions(counts["core_chest"], len(CORE_KEYS)))
    relic_allocs = list(distributions(counts["relic_core_chest"], len(RELIC_KEYS)))
    tech_allocs = list(distributions(counts["tech_core_choice_chest"], len(TECH_KEYS)))
    base_s_pack_n = counts["s_grade_excellent_choice_pack"]
    base_s_pack_allocs = list(distributions(base_s_pack_n, len(S_KEYS)))
    void_crates = counts["voidwalker_supply_crate"]

    nested_s_pack_alloc_sum = 0
    nested_s_pack_rows = []
    for relic in relic_allocs:
        s_from_relic = int(relic[1])
        total_s_pack_n = base_s_pack_n + s_from_relic
        allocs = count_distributions(total_s_pack_n, len(S_KEYS))
        nested_s_pack_alloc_sum += allocs
        nested_s_pack_rows.append({
            "relic_core_chest_relic_cores": int(relic[0]),
            "relic_core_chest_s_grade_packs": s_from_relic,
            "total_s_grade_packs_to_allocate": total_s_pack_n,
            "s_grade_family_allocations": allocs,
        })

    expected_per_pass = len(core_allocs) * len(tech_allocs) * nested_s_pack_alloc_sum
    previous_undercount = len(core_allocs) * len(relic_allocs) * len(tech_allocs) * len(base_s_pack_allocs)

    print(f"Core allocations: {len(core_allocs)}")
    print(f"Relic allocations: {len(relic_allocs)}")
    print(f"Tech allocations: {len(tech_allocs)}")
    print(f"Base S-pack allocations: {len(base_s_pack_allocs)}")
    print(f"Nested S-pack allocation sum across relic choices: {nested_s_pack_alloc_sum}")
    print(f"Previous undercount if relic-created S packs are not opened: {previous_undercount:,}")
    print(f"Expected per pass with nested S-pack expansion: {expected_per_pass:,}")
    print(f"Workers: {workers}")
    print(f"Passes: {passes}")

    all_passes = []
    for p in range(1, passes + 1):
        start = time.time()
        tasks = [(i, core, relic_allocs, tech_allocs, base_s_pack_n, void_crates) for i, core in enumerate(core_allocs)]
        completed = 0
        total_count = 0
        digest_parts = []
        by_relic = Counter()
        by_xeno = Counter()
        by_awake = Counter()
        by_res_chip = Counter()
        by_total_s_packs = Counter()
        maxima: Dict[str, Dict[str, Any]] = {}

        print(f"\n=== FULL ENUMERATION PASS {p}/{passes} ===")
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(worker, task) for task in tasks]
            for fut in as_completed(futures):
                result = fut.result()
                completed += 1
                total_count += int(result["count"])
                digest_parts.append((int(result["core_idx"]), result["sha256"]))
                merge_counters(by_relic, result["by_relic"])
                merge_counters(by_xeno, result["by_xeno"])
                merge_counters(by_awake, result["by_awake"])
                merge_counters(by_res_chip, result["by_resonance_chip"])
                merge_counters(by_total_s_packs, result["by_total_s_packs_to_allocate"])
                update_maxima(maxima, result["maxima"])
                if completed % max(1, verbose_every) == 0 or completed == len(tasks):
                    elapsed = time.time() - start
                    rate = total_count / elapsed if elapsed else 0
                    print(f"pass {p}: tasks {completed}/{len(tasks)} combos {total_count:,}/{expected_per_pass:,} rate {rate:,.0f}/s")

        digest_parts.sort()
        pass_hash = hashlib.sha256("|".join(h for _, h in digest_parts).encode("utf-8")).hexdigest()
        duration = time.time() - start
        ok = total_count == expected_per_pass
        print(f"PASS {p} complete: {total_count:,} combos in {duration:.1f}s hash={pass_hash} ok={ok}")
        all_passes.append({
            "pass": p,
            "combo_count": total_count,
            "expected_count": expected_per_pass,
            "ok": ok,
            "duration_seconds": round(duration, 3),
            "combo_rate_per_second": round(total_count / duration, 2) if duration else None,
            "sha256": pass_hash,
            "by_relic_core_total": dict(sorted(by_relic.items())),
            "by_xeno_pet_core_total": dict(sorted(by_xeno.items())),
            "by_awakening_core_total": dict(sorted(by_awake.items())),
            "by_resonance_chip_total": dict(sorted(by_res_chip.items())),
            "by_total_s_grade_packs_to_allocate": dict(sorted(by_total_s_packs.items())),
            "max_direct_outputs": maxima,
        })

    hashes = [p["sha256"] for p in all_passes]
    deterministic = len(set(hashes)) == 1
    resource_view = read_resource_view(state, candidate)

    validation = []
    if expected_per_pass <= previous_undercount:
        validation.append("WARNING: nested S-pack expansion did not increase candidate space; check Relic Core Chest modeling")
    if resource_view.get("bag_free", {}).get("eternal_cores") != 240:
        validation.append("WARNING: eternal cores not mapped to 240")
    if resource_view.get("embedded_committed", {}).get("relic_cores_in_current_build") != 45:
        validation.append("WARNING: embedded relic cores not mapped to 45")
    if not deterministic:
        validation.append("WARNING: pass hashes differ; enumeration is not deterministic")
    if not validation:
        validation.append("OK: full nested choice-space enumeration validated and deterministic")

    summary = {
        "schema": "sio_fullpower_candidate_index_v2_nested_choices",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rule": "This is a full index/check of legal choice outputs, not a best-spend ranker.",
        "nested_choice_rule": "S-grade Excellent Choice Packs created by Relic Core Chest are opened into Eternal/Void/Chaos selector-family allocations in the same candidate space.",
        "workers": workers,
        "passes": passes,
        "resource_view": resource_view,
        "choice_counts": counts,
        "allocation_counts": {
            "core_chest_allocations": len(core_allocs),
            "relic_core_chest_allocations": len(relic_allocs),
            "tech_core_allocations": len(tech_allocs),
            "base_s_grade_pack_allocations": len(base_s_pack_allocs),
            "nested_s_grade_pack_allocation_sum_across_relic_choices": nested_s_pack_alloc_sum,
            "previous_undercounted_choice_space_count_per_pass": previous_undercount,
            "combined_choice_space_count_per_pass": expected_per_pass,
            "combined_choice_space_total_checked": expected_per_pass * passes,
        },
        "nested_s_grade_pack_by_relic_choice": nested_s_pack_rows,
        "passes_detail": all_passes,
        "deterministic_hash_match": deterministic,
        "validation": validation,
        "blocked_from_final_ranking_until": [
            "apply_to_build_state implemented",
            "sIO damage scorer implemented",
            "AF refund/rebuild material tables patched or extracted",
            "Xeno awakening reset/refund proof patched if using committed awakening cores",
            "survivor shard conversion rules patched if survivor switching is considered",
        ],
    }
    write_json(out / "fullpower_candidate_index.json", summary)

    # Small CSV for quick spreadsheet-style inspection.
    csv_path = out / "fullpower_distribution_index.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["pass", "metric", "value", "candidate_count"])
        for p in all_passes:
            for metric_name in [
                "by_relic_core_total",
                "by_xeno_pet_core_total",
                "by_awakening_core_total",
                "by_resonance_chip_total",
                "by_total_s_grade_packs_to_allocate",
            ]:
                for value, count in p[metric_name].items():
                    writer.writerow([p["pass"], metric_name, value, count])

    md = [
        "# Full-power candidate index report",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Result",
    ]
    md += [f"- {x}" for x in validation]
    md += [
        "",
        "## Nested S-grade choice fix",
        "- Relic Core Chest can output S-grade Excellent Choice Pack.",
        "- Those new S-grade packs are now opened into Eternal/Void/Chaos selector family allocations.",
        f"- previous undercount per pass: {previous_undercount:,}",
        f"- corrected nested count per pass: {expected_per_pass:,}",
        f"- added candidates per pass: {expected_per_pass - previous_undercount:,}",
        "",
        "## Machine usage",
        f"- workers: {workers}",
        f"- passes: {passes}",
        f"- combos per pass: {expected_per_pass:,}",
        f"- total combos checked: {expected_per_pass * passes:,}",
        f"- deterministic hash match: {deterministic}",
        "",
        "## Resource view",
        f"- bag_free eternal_cores: {resource_view.get('bag_free', {}).get('eternal_cores')}",
        f"- bag_free void_cores: {resource_view.get('bag_free', {}).get('void_cores')}",
        f"- bag_free chaos_cores: {resource_view.get('bag_free', {}).get('chaos_cores')}",
        f"- bag_free relic_cores: {resource_view.get('bag_free', {}).get('relic_cores')}",
        f"- embedded relic_cores_in_current_build: {resource_view.get('embedded_committed', {}).get('relic_cores_in_current_build')}",
        f"- embedded/movable awakening cores claimed: {resource_view.get('embedded_committed', {}).get('movable_awakening_cores_claimed')}",
        "",
        "## Pass hashes",
    ]
    for p in all_passes:
        md.append(f"- pass {p['pass']}: {p['sha256']} ({p['combo_count']:,} combos, {p['duration_seconds']}s)")
    md += [
        "",
        "## Still blocked before real ranking",
        "- Need apply_to_build_state to turn selected outputs into legal final gear/tech/pet/survivor states.",
        "- Need sIO damage scorer to compute before/after damage delta.",
        "- Need AF refund/rebuild table before using embedded relic cores/S gear as movable equity.",
        "- Need Xeno awakening reset/refund proof before using all committed awakening cores as movable.",
        "",
        "## Files written",
        "- data/sio_training/fullpower/latest/fullpower_candidate_index.json",
        "- data/sio_training/fullpower/latest/fullpower_distribution_index.csv",
        "- data/sio_training/fullpower/latest/fullpower_candidate_index_report.md",
    ]
    (out / "fullpower_candidate_index_report.md").write_text("\n".join(md), encoding="utf-8")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="data/sio_training/dtlgrind_state_v2.json")
    ap.add_argument("--candidate", default="data/sio_training/candidates/dtlgrind_candidate_space.json")
    ap.add_argument("--out", default="data/sio_training/fullpower/latest")
    ap.add_argument("--passes", type=int, default=int(os.environ.get("SIO_FULLPOWER_PASSES", "3")))
    ap.add_argument("--workers", type=int, default=int(os.environ.get("SIO_FULLPOWER_WORKERS", "0")))
    ap.add_argument("--verbose-every", type=int, default=int(os.environ.get("SIO_FULLPOWER_VERBOSE_EVERY", "8")))
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state = load_json(Path(args.state), {}) or {}
    candidate = load_json(Path(args.candidate), {}) or {}
    cpu = os.cpu_count() or 2
    workers = args.workers if args.workers > 0 else max(1, cpu - 1)
    workers = max(1, min(workers, cpu))

    try:
        summary = run_full_index(state, candidate, out, max(1, args.passes), workers, max(1, args.verbose_every))
        print("\nDONE full-power candidate index")
        print("Report:", out / "fullpower_candidate_index_report.md")
        if not all("OK:" in x for x in summary.get("validation", [])):
            sys.exit(2)
    except KeyboardInterrupt:
        print("Interrupted by user.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
