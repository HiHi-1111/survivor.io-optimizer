from __future__ import annotations

from optimizer.exact_training_labels import LAYOUT_ONLY_KEYS, prepare_exact_training_rows
from optimizer.numeric_features import FEATURE_COLUMNS


def _row(placement):
    return {
        "candidates": [
            {
                "action_id": "mount_stats_from_puzzle",
                "system": "mounts",
                "action_type": "apply_mount_component_stats",
                "metadata": {
                    "attack_gain_estimate": 12,
                    "placements": placement,
                    "board": [["I", None]],
                    "states_explored": 999,
                },
                "exact_damage_delta": 50,
            },
            {
                "action_id": "save_hold_no_op",
                "action_type": "save_hold",
                "exact_damage_delta": 0,
            },
        ]
    }


def test_different_tetris_geometry_with_same_result_has_identical_training_features() -> None:
    first, first_quarantine = prepare_exact_training_rows([_row([{"type": "I", "row": 0, "col": 0, "rotation": 0}])])
    second, second_quarantine = prepare_exact_training_rows([_row([{"type": "I", "row": 4, "col": 3, "rotation": 1}])])
    assert not first_quarantine
    assert not second_quarantine
    left = first[0]["candidates"][0]
    right = second[0]["candidates"][0]
    assert left["features"] == right["features"]
    assert left["exact_damage_delta"] == right["exact_damage_delta"] == 50
    assert left["training_exclusions"] == ["mount_puzzle_layout_geometry"]


def test_explicit_feature_input_is_strictly_allowlisted() -> None:
    accepted, quarantined = prepare_exact_training_rows(
        [
            {
                "candidates": [
                    {
                        "action_id": "mount_result",
                        "features": {
                            "attack_gain_estimate": 4,
                            "row": 88,
                            "rotation": 3,
                            "board_mask": 123456,
                        },
                        "exact_damage_delta": 1,
                    }
                ]
            }
        ]
    )
    assert not quarantined
    features = accepted[0]["candidates"][0]["features"]
    assert set(features) == set(FEATURE_COLUMNS)
    assert not (set(features) & LAYOUT_ONLY_KEYS)


def test_raw_layout_evidence_is_retained_even_though_it_is_not_a_feature() -> None:
    original = _row([{"type": "T", "row": 2, "col": 1, "rotation": 3}])
    accepted, quarantined = prepare_exact_training_rows([original])
    assert not quarantined
    candidate = accepted[0]["candidates"][0]
    assert candidate["metadata"]["placements"] == original["candidates"][0]["metadata"]["placements"]
    assert all(key not in candidate["features"] for key in LAYOUT_ONLY_KEYS)


def test_layout_marker_uses_exact_keys_not_substrings() -> None:
    accepted, quarantined = prepare_exact_training_rows(
        [
            {
                "candidates": [
                    {
                        "action_id": "ordinary_action",
                        "metadata": {
                            "growth_value": 3,
                            "brown_resource": 4,
                            "pathway_bonus": 5,
                        },
                        "exact_damage_delta": 1,
                    }
                ]
            }
        ]
    )
    assert not quarantined
    candidate = accepted[0]["candidates"][0]
    assert "training_exclusions" not in candidate
