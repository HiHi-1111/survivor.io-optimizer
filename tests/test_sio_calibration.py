from __future__ import annotations

from pathlib import Path

import pytest

from optimizer.sio_calibration import SioCalibrationStore, profile_fingerprint


def _profile() -> dict:
    return {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "attack": {"atkBase": 1000, "atkFinal": 0},
            "stats": {"critDamage": 200},
        },
    }


def test_profile_fingerprint_ignores_observed_damage_fields() -> None:
    first = _profile()
    second = _profile()
    first["sio_ce"]["observed_ce_damage"] = 100
    second["sio_ce"]["observed_ce_damage"] = 200
    assert profile_fingerprint(first) == profile_fingerprint(second)


def test_calibration_records_are_append_only_and_do_not_mutate_formula(tmp_path: Path) -> None:
    store = SioCalibrationStore(tmp_path / "calibration.jsonl")
    row = store.record(
        sio_id="private-id",
        profile=_profile(),
        predicted_damage=1000,
        observed_damage=1100,
        formula_provenance={"bundle_sha256": "abc", "modules": [67727]},
    )
    assert row["ratio_observed_to_predicted"] == pytest.approx(1.1)
    assert row["automatic_formula_mutation"] is False
    assert "private-id" not in store.path.read_text(encoding="utf-8")
    assert len(store.rows()) == 1


def test_only_consistent_repeated_observations_become_review_candidates(tmp_path: Path) -> None:
    store = SioCalibrationStore(tmp_path / "calibration.jsonl")
    for observed in (1090, 1100, 1110, 1105, 1095):
        store.record(
            sio_id="same-player",
            profile=_profile(),
            predicted_damage=1000,
            observed_damage=observed,
            formula_provenance={"bundle_sha256": "abc", "modules": [67727]},
        )
    candidate = store.review_candidates()[0]
    assert candidate["samples"] == 5
    assert candidate["eligible_for_human_review"] is True
    assert candidate["automatic_promotion"] is False


def test_non_ce_observation_is_rejected(tmp_path: Path) -> None:
    profile = _profile()
    profile["game_mode"] = "enders_echo"
    store = SioCalibrationStore(tmp_path / "calibration.jsonl")
    with pytest.raises(ValueError):
        store.record(
            sio_id="id",
            profile=profile,
            predicted_damage=100,
            observed_damage=100,
            formula_provenance={},
        )
