#!/usr/bin/env python3
"""Train inherited child rankers and promote only exact-CE holdout winners.

The script never cold-starts a child. It migrates a past checkpoint when one
exists, otherwise registers a non-zero deterministic genesis champion once.
Every later child inherits the current champion plus optional hall-of-fame
parents. Exact sIO damage remains the teacher and final optimizer authority.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from optimizer.champion_lineage import (  # noqa: E402
    ChampionLineage,
    audit_examples,
    evaluate,
    train_child,
)
from optimizer.source_pack_optimizer import optimize_source_pack_actions  # noqa: E402
from optimizer.training_memory import atomic_write_json, utc_now  # noqa: E402


def _load_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError(f"{path} must contain a JSON list or JSONL rows.")
        return [dict(row) for row in payload if isinstance(row, Mapping)]
    rows = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, Mapping):
            raise ValueError(f"{path}:{line_number} is not an object")
        rows.append(dict(value))
    return rows


def _examples_from_profiles(profiles: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, profile in enumerate(profiles):
        result = optimize_source_pack_actions(profile, top_k=100000, device="cpu")
        candidates = []
        for action in result.get("ranked_actions", []):
            if not action.get("runtime_exact"):
                continue
            candidates.append({
                **dict(action),
                "exact_damage_delta": float(action.get("expected_dps_gain", 0.0) or 0.0),
            })
        candidates.append({
            "action_id": "save_hold_no_op",
            "action_type": "save_hold",
            "exact_damage_delta": 0.0,
            "confidence": "exact",
            "supported": True,
        })
        if len(candidates) == 1 and result.get("rejected_actions"):
            # A no-op-only row is useful only when all spend actions were exactly
            # evaluated and lost. Unsupported actions are not negative labels.
            continue
        rows.append({
            "example_id": str(profile.get("profile_id") or profile.get("profile_name") or f"profile_{index}"),
            "candidates": candidates,
            "source": "exact_sio_ce_optimizer",
        })
    return rows


def _split(examples, holdout_fraction: float):
    ordered = sorted(examples, key=lambda example: example.fingerprint)
    if len(ordered) < 2:
        return ordered, ordered
    holdout_count = max(1, min(len(ordered) - 1, round(len(ordered) * holdout_fraction)))
    holdout = ordered[:: max(1, len(ordered) // holdout_count)][:holdout_count]
    holdout_ids = {example.fingerprint for example in holdout}
    train = [example for example in ordered if example.fingerprint not in holdout_ids]
    return train or ordered, holdout


def _legacy_paths(values: list[str]) -> list[Path]:
    defaults = [
        ROOT / "training_outputs" / "learned_ranker.json",
        ROOT / "training_outputs" / "champion.json",
        ROOT / "data" / "training" / "learned_ranker.json",
        ROOT / "data" / "optimizer_training" / "learned_ranker.json",
    ]
    return [Path(value) for value in values] + defaults


def _write_markdown(path: Path, report: Mapping[str, Any]) -> None:
    champion = report.get("final_champion", {}) or {}
    lines = [
        "# Champion lineage training report",
        "",
        f"Generated: {report.get('generated_at')}",
        f"Accepted exact examples: {report.get('accepted_examples', 0)}",
        f"Quarantined rows: {report.get('quarantined_rows', 0)}",
        f"Train / holdout: {report.get('train_examples', 0)} / {report.get('holdout_examples', 0)}",
        f"Starting champion: {report.get('starting_champion_id')}",
        f"Final champion: {champion.get('champion_id')}",
        "",
        "## Inheritance rule",
        "",
        "- Every child inherited the current champion checkpoint.",
        "- Available hall-of-fame champions were blended as secondary ancestors.",
        "- A child trained in its own checkpoint; the parent was never modified.",
        "- Promotion required exact holdout improvement, zero no-op failures, zero mandatory failures, and no exact-label regression.",
        "- The learned champion orders proposals only. Exact sIO CE before/after damage still selects the optimizer winner.",
        "",
        "## Generations",
        "",
    ]
    for generation in report.get("generations", []):
        lines.extend([
            f"### Generation {generation.get('generation')}",
            f"- Parent: {generation.get('parent_id')}",
            f"- Children evaluated: {generation.get('children_evaluated')}",
            f"- Promoted: {generation.get('promoted_champion_id') or 'none'}",
            f"- Parent accuracy: {generation.get('champion_metrics', {}).get('top1_accuracy', 0):.6f}",
            f"- Best child accuracy: {generation.get('best_child_metrics', {}).get('top1_accuracy', 0):.6f}",
            "",
        ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dataset", type=Path, help="Exact candidate-label JSON/JSONL")
    source.add_argument("--profiles", type=Path, help="Profiles to label with the exact sIO runtime")
    parser.add_argument("--lineage-root", type=Path, default=ROOT / "training_outputs" / "champion_lineage")
    parser.add_argument("--generations", type=int, default=5)
    parser.add_argument("--children", type=int, default=4)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=0.02)
    parser.add_argument("--holdout-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260719)
    parser.add_argument("--legacy-checkpoint", action="append", default=[])
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    raw_rows = _load_json_or_jsonl(args.dataset) if args.dataset else _examples_from_profiles(_load_json_or_jsonl(args.profiles))
    examples, quarantined = audit_examples(raw_rows)
    if not examples:
        raise SystemExit("No exact, non-contradictory training examples were available. Nothing was invented.")

    lineage = ChampionLineage(args.lineage_root)
    genesis = lineage.ensure_genesis(_legacy_paths(args.legacy_checkpoint))
    train_examples, holdout_examples = _split(examples, max(0.05, min(0.5, args.holdout_fraction)))
    quarantine_path = lineage.quarantine_dir / f"quarantine-{utc_now().replace(':', '')}.json"
    atomic_write_json(quarantine_path, {"rows": quarantined, "count": len(quarantined)})

    report: dict[str, Any] = {
        "version": 1,
        "generated_at": utc_now(),
        "source": str(args.dataset or args.profiles),
        "dataset_hash": __import__("hashlib").sha256(
            json.dumps(raw_rows, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest(),
        "accepted_examples": len(examples),
        "quarantined_rows": len(quarantined),
        "quarantine_path": str(quarantine_path),
        "train_examples": len(train_examples),
        "holdout_examples": len(holdout_examples),
        "starting_champion_id": genesis["champion_id"],
        "generations": [],
    }

    for generation_index in range(max(1, args.generations)):
        parent = lineage.current() or lineage.ensure_genesis()
        champion_metrics = evaluate(parent["weights"], holdout_examples)
        children = []
        for child_index in range(max(1, args.children)):
            child_seed = args.seed + generation_index * 100003 + child_index
            child = lineage.spawn_child(seed=child_seed, child_index=child_index)
            child["weights"] = train_child(
                child["inherited_weights"],
                train_examples,
                epochs=args.epochs,
                learning_rate=args.learning_rate,
                seed=child_seed,
            )
            child["train_metrics"] = evaluate(child["weights"], train_examples)
            child["holdout_metrics"] = evaluate(child["weights"], holdout_examples)
            child["dataset_hash"] = report["dataset_hash"]
            decision = lineage.promotion_decision(child, champion_metrics, child["holdout_metrics"])
            child["promotion_decision"] = decision
            children.append(child)

        children.sort(
            key=lambda child: (
                bool(child["promotion_decision"]["promote"]),
                float(child["holdout_metrics"]["top1_accuracy"]),
                -float(child["holdout_metrics"]["mean_regret"]),
                child["child_id"],
            ),
            reverse=True,
        )
        best = children[0]
        promoted = None
        for child in children:
            status = "promotion_candidate" if child is best and child["promotion_decision"]["promote"] else "rejected"
            lineage.save_child(child, status)
        if best["promotion_decision"]["promote"]:
            promoted = lineage.promote(best, best["promotion_decision"])

        report["generations"].append({
            "generation": generation_index + 1,
            "parent_id": parent["champion_id"],
            "children_evaluated": len(children),
            "champion_metrics": champion_metrics,
            "best_child_id": best["child_id"],
            "best_child_metrics": best["holdout_metrics"],
            "best_child_decision": best["promotion_decision"],
            "promoted_champion_id": promoted.get("champion_id") if promoted else None,
        })

    report["final_champion"] = lineage.current()
    report_path = args.report or args.lineage_root / "latest_training_report.json"
    atomic_write_json(report_path, report)
    _write_markdown(report_path.with_suffix(".md"), report)
    print(json.dumps({
        "status": "ok",
        "starting_champion": report["starting_champion_id"],
        "final_champion": report["final_champion"]["champion_id"],
        "accepted_examples": len(examples),
        "quarantined": len(quarantined),
        "report": str(report_path),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
