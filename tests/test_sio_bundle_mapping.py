from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_worker_manifest_is_source_locked_and_keeps_all_omitted_workers_explicit() -> None:
    runtime = json.loads((ROOT / "knowledge" / "sio_runtime_manifest.json").read_text(encoding="utf-8"))
    workers = json.loads((ROOT / "knowledge" / "sio_worker_manifest.json").read_text(encoding="utf-8"))
    assert workers["bundle_sha256"] == runtime["bundle_sha256"]
    rows = {row["name"]: row for row in workers["workers"]}
    assert set(rows) == {
        "collectiblesStars",
        "customSets",
        "items",
        "lmeDebuffs",
        "mountPuzzles",
        "petsCores",
        "petsSkills",
        "resonance",
        "skills",
        "tetris",
    }
    for row in rows.values():
        assert row["listed_in_service_worker"] is True
        assert row["present_in_bundle"] is False
        assert row["expected_path"].endswith(f"{row['chunk_id']}.{row['hash']}.js")
        assert row["bot_status"]


def test_feature_registry_discloses_independent_solver_without_worker_parity() -> None:
    registry = {
        row["id"]: row
        for row in json.loads((ROOT / "knowledge" / "sio_feature_registry.json").read_text(encoding="utf-8"))
    }
    mount_puzzle = registry["mount_puzzle_optimizer"]
    assert mount_puzzle["action_status"] == "combination_solver_implemented_profile_bridge_missing"
    assert "worker chunks are absent from the supplied offline bundle" in mount_puzzle["remaining"]
    assert "piece inventory is a multiset combination, not a permutation" in mount_puzzle["known_contract"]
    assert registry["tech_optimizer"]["action_status"] == "partial"
    assert registry["survivor_optimizer"]["action_status"] == "partial"
    assert registry["collectible_optimizer"]["action_status"] == "partial"
    assert registry["xeno_pet_skills"]["action_status"] == "not_generated_without_exact_elixir_costs"


def test_bundle_mapper_script_is_present_and_non_executing() -> None:
    source = (ROOT / "tools" / "sio_training" / "extract_sio_bundle_map.py").read_text(encoding="utf-8")
    assert "webpack_module_count" in source
    assert "missing_worker_chunks" in source
    assert "present_in_bundle" in source
    assert "zipfile.ZipFile" in source
    assert "subprocess" not in source
