#!/usr/bin/env python3
"""Audit sIO bundle coverage, formula order, uptime fields and evidence retention.

This is intentionally static and deterministic. It does not trust comments or a
single status flag: it checks the source-locked manifest, feature registry, exact
JavaScript oracle, exact action frontiers and Python fallback. When the supplied
bundle is available it also verifies its SHA and required webpack module/token
presence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
import zipfile

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "knowledge" / "sio_runtime_manifest.json"
REGISTRY_PATH = ROOT / "knowledge" / "sio_feature_registry.json"

REQUIRED_REGISTRY_IDS = {
    "clan_expedition_damage_contract",
    "attack_stat_pipeline",
    "crit_expected_damage",
    "boss_debuff_uptime_stack",
    "ss_equipment_evc_paths",
    "chaos_fusion_power",
    "xeno_transmute",
    "normal_tech_resonance",
    "twinborn_tech_modes",
    "resonance_overload",
    "tech_optimizer",
    "survivor_progression",
    "survivor_teamwork",
    "survivor_synergy_harmony",
    "survivor_optimizer",
    "normal_pet_progression",
    "xeno_pets",
    "xeno_pet_skills",
    "collectibles",
    "custom_collection_sets",
    "collectible_optimizer",
    "collectible_deconstructor",
    "mounts",
    "mount_puzzle_optimizer",
    "resource_and_refund_ledger",
    "source_calibration_samples",
    "input_schema_and_aliases",
    "exact_runtime_account_assembly",
    "training_evidence_cleanup",
    "champion_lineage",
    "unsupported_modes",
}
EXACT_RUNTIME_BINDINGS = (
    "runtime.req(13024).T",
    "runtime.req(24804).zP",
    "runtime.req(88426).y",
    "runtime.req(24804).IE",
    "runtime.req(67727).f",
)
EXACT_ACCOUNT_BINDINGS = {
    "37013.c.baseStats": "runtime.req(37013).c.baseStats",
    "63941.x": "runtime.req(63941).x",
    "5005.Q": "runtime.req(5005).Q",
    "42052.vY": "runtime.req(42052).vY",
    "41950.j": "runtime.req(41950).j",
    "57223.m": "runtime.req(57223).m",
    "89505.Y3": "runtime.req(89505).Y3",
    "42806.x": "runtime.req(42806).x",
    "70324.t": "runtime.req(70324).t",
    "30039.s": "runtime.req(30039).s",
    "40498.N": "runtime.req(40498).N",
    "80438.b": "runtime.req(80438).b",
    "51642.F": "runtime.req(51642).F",
    "94578.p": "runtime.req(94578).p",
    "92316.xt": "runtime.req(92316).xt",
    "30396.i": "runtime.req(30396).i",
    "13024.T": "runtime.req(13024).T",
    "19425.a6": "runtime.req(19425).a6",
}
FRONTIER_BINDINGS = {
    "Survivor frontiers": "generate_survivor_frontiers",
    "Pet frontiers": "generate_pet_frontiers",
    "Mount frontiers": "generate_mount_frontiers",
    "Tech frontiers": "generate_tech_frontiers",
    "combined progression frontiers": "generate_progression_frontiers",
}


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _check_contains(errors: list[str], source: str, token: str, label: str) -> None:
    if token not in source:
        errors.append(f"{label}: missing {token!r}")


def _bundle_path() -> Path | None:
    explicit = os.environ.get("SIO_TOOLS_BUNDLE")
    candidates = [Path(explicit).expanduser()] if explicit else []
    archive = ROOT / "data" / "sio_training" / "archive"
    candidates.extend(
        archive / name
        for name in (
            "sio_tools.exp0.dev.zip",
            "sio_tools.exp0.dev(1).zip",
            "sio-tools.exp0.dev.zip",
        )
    )
    for path in candidates:
        if path.is_file():
            return path.resolve()
    return None


def _audit_bundle(bundle: Path, manifest: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    digest = _sha256(bundle)
    if digest != manifest["bundle_sha256"]:
        errors.append(f"bundle SHA mismatch: {digest} != {manifest['bundle_sha256']}")
    with zipfile.ZipFile(bundle) as archive:
        names = [name for name in archive.namelist() if name.endswith(".js")]
        chunks = []
        for name in names:
            data = archive.read(name)
            try:
                chunks.append(data.decode("utf-8"))
            except UnicodeDecodeError:
                errors.append(f"bundle JavaScript is not UTF-8: {name}")
        source = "\n".join(chunks)
    missing_modules = [
        module
        for module in manifest["required_modules"]
        if re.search(rf"(?:^|[,{{])\s*{int(module)}\s*:\s*", source) is None
    ]
    if missing_modules:
        errors.append(f"bundle missing required webpack modules: {missing_modules}")
    for token in manifest["uptime_fields"] + manifest["final_transform_fields"]:
        if token not in source:
            errors.append(f"bundle missing required formula token: {token}")
    return {
        "path": str(bundle),
        "sha256": digest,
        "javascript_files": len(names),
        "missing_modules": missing_modules,
    }


def audit(*, require_bundle: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    manifest = _json(MANIFEST_PATH)
    registry = _json(REGISTRY_PATH)
    registry_ids = {str(row.get("id")) for row in registry if isinstance(row, dict)}
    missing_registry = sorted(REQUIRED_REGISTRY_IDS - registry_ids)
    if missing_registry:
        errors.append(f"feature registry missing systems: {missing_registry}")

    oracle_js = _source("tools/sio_runtime/sio_ce_oracle.js")
    oracle_py = _source("optimizer/sio_runtime_oracle.py")
    account_py = _source("optimizer/sio_ce_account.py")
    item_pipeline_py = _source("optimizer/sio_item_pipeline.py")
    constants_py = _source("optimizer/sio_ce_constants.py")
    tech_py = _source("optimizer/sio_tech_progression.py")
    frontier_py = _source("optimizer/sio_progression_frontiers.py")
    source_optimizer_py = _source("optimizer/source_pack_optimizer.py")
    labels_py = _source("optimizer/exact_training_labels.py")
    state_py = _source("optimizer/player_state.py")

    for token in EXACT_RUNTIME_BINDINGS:
        _check_contains(errors, oracle_js, token, "exact oracle")
    order_positions = [oracle_js.find(token) for token in EXACT_RUNTIME_BINDINGS]
    if any(position < 0 for position in order_positions) or order_positions != sorted(order_positions):
        errors.append(f"exact oracle function binding order is wrong: {order_positions}")
    expected_labels = tuple(manifest["ce_formula_order"])
    if expected_labels != ("13024.T", "24804.zP", "88426.y", "24804.IE", "67727.f"):
        errors.append(f"manifest formula order changed unexpectedly: {expected_labels}")

    manifest_account_functions = set((manifest.get("account_functions") or {}).keys())
    missing_manifest_functions = sorted(set(EXACT_ACCOUNT_BINDINGS) - manifest_account_functions)
    if missing_manifest_functions:
        errors.append(f"manifest missing exact account functions: {missing_manifest_functions}")
    for function_name, token in EXACT_ACCOUNT_BINDINGS.items():
        _check_contains(errors, oracle_js, token, f"exact account function {function_name}")

    for label, token in FRONTIER_BINDINGS.items():
        _check_contains(errors, frontier_py, token, label)
    _check_contains(errors, source_optimizer_py, "generate_progression_frontiers", "frontier optimizer integration")
    _check_contains(errors, source_optimizer_py, "every legal exact after-state is batch-scored", "no-prune exact search")
    _check_contains(errors, frontier_py, '"cumulative_frontier": True', "frontier provenance")
    _check_contains(errors, tech_py, "math.inf, math.inf", "unpublished Overload gates remain unreachable")

    _check_contains(errors, oracle_py, 'ORACLE_SCHEMA = "sio_ce_oracle_v2"', "runtime bridge")
    _check_contains(errors, oracle_py, 'separators=(",", ":")', "runtime bridge compact JSON")
    _check_contains(errors, oracle_py, '"skipRuntime24804": skip_runtime_24804', "post-24804 bridge")
    _check_contains(errors, oracle_py, '"account_input": account_input or None', "raw account bridge")
    _check_contains(errors, oracle_js, "if (skipRuntime24804)", "post-24804 oracle")
    _check_contains(errors, oracle_js, "assembleRuntimeAccount", "raw account oracle")
    _check_contains(errors, account_py, "defer_runtime_conditions=True", "account pipeline")
    _check_contains(errors, account_py, 'sio["runtime_account_input"]', "raw account preservation")
    _check_contains(errors, account_py, "pre_24804_runtime", "account pipeline")
    _check_contains(errors, item_pipeline_py, "finalize_sio_stats_fallback", "Python 24804 fallback")
    _check_contains(errors, item_pipeline_py, "metaliaPoisoned", "Python 24804 fallback")
    _check_contains(errors, item_pipeline_py, "joeyWeakSpot", "Python 24804 fallback")
    _check_contains(errors, labels_py, '"raw_row": evidence', "training cleanup")
    _check_contains(errors, labels_py, 'path.open("a"', "append-only quarantine")
    _check_contains(errors, state_py, "PLAYER_STATE_LIST_ADAPTER", "batch input validation")

    for field, expected in manifest["base_stats"].items():
        pattern = rf'["\']{re.escape(field)}["\']\s*:\s*{re.escape(str(expected))}(?:\.0)?'
        if re.search(pattern, constants_py) is None:
            errors.append(f"base stat default not mapped exactly: {field}={expected}")
    for field in manifest["uptime_fields"]:
        if field not in oracle_js or field not in item_pipeline_py:
            errors.append(f"uptime field not covered in exact and fallback paths: {field}")

    bundle = _bundle_path()
    bundle_report: dict[str, Any] | None = None
    if bundle is not None:
        bundle_report = _audit_bundle(bundle, manifest, errors)
    elif require_bundle:
        errors.append("supplied sIO bundle is required but was not found")
    else:
        warnings.append("sIO bundle not present; static manifest/source audit only")

    unknown_or_partial = []
    for row in registry:
        if not isinstance(row, dict):
            continue
        status = str(row.get("action_status", ""))
        if status in {"partial", "not_yet_automatic", "not_yet_implemented", "unknown_until_exact_return_table_is_supplied"}:
            unknown_or_partial.append(str(row.get("id")))
    if unknown_or_partial:
        warnings.append(f"honest remaining action gaps: {sorted(unknown_or_partial)}")

    return {
        "schema": "sio_runtime_coverage_audit_v2",
        "ok": not errors,
        "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
        "registry_entries": len(registry),
        "missing_registry_ids": missing_registry,
        "account_functions_checked": len(EXACT_ACCOUNT_BINDINGS),
        "progression_frontiers_checked": sorted(FRONTIER_BINDINGS),
        "bundle": bundle_report,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-bundle", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(require_bundle=args.require_bundle)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
