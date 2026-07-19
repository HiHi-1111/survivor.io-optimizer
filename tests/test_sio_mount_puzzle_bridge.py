from __future__ import annotations

import pytest

from optimizer.sio_mount_puzzle_bridge import apply_verified_mount_puzzle_stats


def _profile():
    return {
        "mounts": {
            "active": "Electric Scooter",
            "data": {
                "Electric Scooter": {
                    "enabled": True,
                    "stars": 0,
                    "stats": {},
                }
            },
        }
    }


def test_only_verified_aggregate_component_stats_are_copied() -> None:
    profile = _profile()
    profile["sio_ce"] = {
        "mount_puzzles": {
            "electric_scooter": {
                "verified": True,
                "component_stats": {"skillDamage": 12, "critRate": 3},
                "placements": [{"type": "I", "row": 0, "col": 0, "rotation": 0}],
                "board_mask": 123,
                "states_explored": 456,
            }
        }
    }
    normalized, report = apply_verified_mount_puzzle_stats(profile)
    assert normalized["mounts"]["data"]["Electric Scooter"]["stats"] == {
        "critRate": 3.0,
        "skillDamage": 12.0,
    }
    assert normalized["sio_ce"]["mount_puzzles"] == profile["sio_ce"]["mount_puzzles"]
    assert report["layout_used_for_scoring"] is False
    assert report["applied"]["Electric Scooter"]["skillDamage"] == 12.0


def test_unverified_puzzle_result_is_retained_but_not_scored() -> None:
    profile = _profile()
    profile["mount_puzzles"] = {
        "Electric Scooter": {
            "component_stats": {"skillDamage": 99},
            "placements": [{"type": "O"}],
        }
    }
    normalized, report = apply_verified_mount_puzzle_stats(profile)
    assert normalized["mounts"]["data"]["Electric Scooter"]["stats"] == {}
    assert normalized["mount_puzzles"] == profile["mount_puzzles"]
    assert report["ignored_unverified"] == ["Electric Scooter"]


def test_conflicting_existing_stats_are_rejected_instead_of_double_counted() -> None:
    profile = _profile()
    profile["mounts"]["data"]["Electric Scooter"]["stats"] = {"skillDamage": 10}
    profile["mount_puzzles"] = {
        "Electric Scooter": {
            "verified": True,
            "component_stats": {"skillDamage": 12},
        }
    }
    with pytest.raises(ValueError, match="conflicting mount component stats"):
        apply_verified_mount_puzzle_stats(profile)


def test_unknown_nonzero_component_stat_is_rejected() -> None:
    profile = _profile()
    profile["mount_puzzles"] = {
        "Electric Scooter": {
            "verified": True,
            "component_stats": {"madeUpDamage": 100},
        }
    }
    with pytest.raises(ValueError, match="unknown mount component stat"):
        apply_verified_mount_puzzle_stats(profile)


def test_verified_result_requires_an_owned_mount_state() -> None:
    profile = {"mounts": {"active": "Doomsteed", "data": {}}}
    profile["mount_puzzles"] = {
        "Doomsteed": {
            "source_exact": True,
            "component_stats": {"skillDamage": 1},
        }
    }
    with pytest.raises(ValueError, match="unknown or unowned mount"):
        apply_verified_mount_puzzle_stats(profile)
