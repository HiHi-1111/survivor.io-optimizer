from __future__ import annotations

import json
from pathlib import Path

from optimizer.champion_lineage import (
    ChampionLineage,
    audit_examples,
    evaluate,
    safe_exact_ce_prior,
    train_child,
)
from optimizer.exact_training_labels import append_quarantine_jsonl, prepare_exact_training_rows
from optimizer.learned_ranker import OnlineLinearRanker
from optimizer.numeric_features import FEATURE_COLUMNS


def _row(example_id: str, good_system: str = "good") -> dict:
    return {
        "example_id": example_id,
        "candidates": [
            {
                "action_id": f"{good_system}_action",
                "system": good_system,
                "action_type": "upgrade",
                "exact_damage_delta": 10.0,
                "metadata": {"synergy_score": 1.0},
            },
            {
                "action_id": "bad_action",
                "system": "bad",
                "action_type": "upgrade",
                "exact_damage_delta": -1.0,
                "metadata": {"synergy_score": -1.0},
            },
        ],
    }


def test_genesis_is_nonzero_and_child_inherits_current_champion(tmp_path: Path) -> None:
    lineage = ChampionLineage(tmp_path / "lineage")
    champion = lineage.ensure_genesis()
    child = lineage.spawn_child(seed=7)
    assert champion["champion_id"] == child["primary_parent_id"]
    assert any(abs(value) > 1e-12 for value in champion["weights"])
    assert any(abs(value) > 1e-12 for value in child["inherited_weights"])
    assert child["generation"] == champion["generation"] + 1


def test_rejected_child_never_modifies_parent_checkpoint(tmp_path: Path) -> None:
    lineage = ChampionLineage(tmp_path / "lineage")
    champion = lineage.ensure_genesis()
    parent_path = lineage.champions_dir / f"{champion['champion_id']}.json"
    before = parent_path.read_bytes()
    child = lineage.spawn_child(seed=11)
    child["weights"] = list(child["inherited_weights"])
    lineage.save_child(child, "rejected")
    assert parent_path.read_bytes() == before
    assert lineage.current()["champion_id"] == champion["champion_id"]


def test_legacy_checkpoint_becomes_generation_zero_parent(tmp_path: Path) -> None:
    legacy = tmp_path / "old_champion.json"
    weights = [0.25] * len(FEATURE_COLUMNS)
    legacy.write_text(json.dumps({"weights": weights, "samples": 50, "updates": 12}), encoding="utf-8")
    lineage = ChampionLineage(tmp_path / "lineage")
    champion = lineage.ensure_genesis([legacy])
    assert champion["bootstrap_source"] == "migrated_past_champion"
    assert champion["migrated_from"] == str(legacy)
    assert champion["weights"] == weights


def test_online_ranker_always_inherits_nonzero_champion(tmp_path: Path) -> None:
    checkpoint = tmp_path / "learned_ranker.json"
    ranker = OnlineLinearRanker(checkpoint)
    assert ranker.inherited is True
    assert ranker.parent_champion_id
    assert any(abs(value) > 1e-12 for value in ranker.weights)
    ranker.save()
    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload["can_replace_champion_directly"] is False
    assert payload["role"] == "proposal_ordering_child_only"


def test_zero_legacy_checkpoint_cannot_become_a_child_parent(tmp_path: Path) -> None:
    checkpoint = tmp_path / "learned_ranker.json"
    checkpoint.write_text(json.dumps({"weights": [0.0] * len(FEATURE_COLUMNS)}), encoding="utf-8")
    ranker = OnlineLinearRanker(checkpoint)
    assert any(abs(value) > 1e-12 for value in ranker.weights)
    assert ranker.parent_champion_id


def test_exact_labels_are_removed_from_proposal_features() -> None:
    rows, quarantine = prepare_exact_training_rows([_row("one")])
    assert quarantine == []
    good = next(candidate for candidate in rows[0]["candidates"] if candidate["action_id"] == "good_action")
    assert good["features"]["immediate_damage"] == 0.0
    assert good["features"]["damage_gain_estimate"] == 0.0
    assert good["exact_damage_delta"] == 10.0


def test_same_state_contradictory_exact_labels_are_retained_in_quarantine() -> None:
    first = _row("first")
    second = _row("second")
    second["candidates"][0]["exact_damage_delta"] = -1.0
    second["candidates"][1]["exact_damage_delta"] = 10.0
    original_second = json.loads(json.dumps(second))
    accepted, quarantine = prepare_exact_training_rows([first, second])
    assert len(accepted) == 1
    assert len(quarantine) == 1
    record = quarantine[0]
    assert record["reason"] == "contradictory_exact_label"
    assert record["retained_for_audit"] is True
    assert record["excluded_from_training"] is True
    assert record["raw_row"] == original_second
    assert second == original_second


def test_quarantine_writer_appends_without_replacing_prior_evidence(tmp_path: Path) -> None:
    path = tmp_path / "quarantine.jsonl"
    first = {"reason": "one", "raw_row": {"id": 1}}
    second = {"reason": "two", "raw_row": {"id": 2}}
    assert append_quarantine_jsonl(path, [first]) == 1
    before = path.read_text(encoding="utf-8")
    assert append_quarantine_jsonl(path, [second]) == 1
    after = path.read_text(encoding="utf-8")
    assert after.startswith(before)
    rows = [json.loads(line) for line in after.splitlines()]
    assert rows == [first, second]


def test_child_training_starts_from_parent_and_can_improve_exact_holdout() -> None:
    prepared, quarantine = prepare_exact_training_rows([_row(f"row_{index}") for index in range(8)])
    # Repeated identical evidence is retained in quarantine, not trained twice.
    assert all(record["reason"] == "duplicate_exact_evidence" for record in quarantine)
    examples, schema_quarantine = audit_examples(prepared)
    assert schema_quarantine == []
    parent = safe_exact_ce_prior()
    child = train_child(parent, examples, epochs=10, learning_rate=0.1, seed=5)
    parent_metrics = evaluate(parent, examples)
    child_metrics = evaluate(child, examples)
    assert child != [0.0] * len(child)
    assert child_metrics["top1_accuracy"] >= parent_metrics["top1_accuracy"]
    assert child_metrics["mandatory_failures"] == 0


def test_noop_gate_detects_spend_when_all_exact_deltas_are_nonpositive() -> None:
    rows = [{
        "example_id": "noop",
        "candidates": [
            {
                "action_id": "bad_spend",
                "system": "bad",
                "action_type": "upgrade",
                "exact_damage_delta": -5.0,
                "features": {name: (10.0 if name == "synergy_score" else 0.0) for name in FEATURE_COLUMNS},
            }
        ],
    }]
    prepared, _ = prepare_exact_training_rows(rows)
    examples, _ = audit_examples(prepared)
    weights = [0.0] * len(FEATURE_COLUMNS)
    weights[FEATURE_COLUMNS.index("synergy_score")] = 1.0
    metrics = evaluate(weights, examples)
    assert metrics["no_op_failures"] == 1
    assert metrics["mandatory_failures"] == 1
