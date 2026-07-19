from __future__ import annotations

from optimizer.sio_tech_configurations import (
    TWINBORN_MODES,
    generate_twinborn_mode_actions,
    recognized_twinborn_state,
)


def _profile(techs):
    return {"sio_ce": {"techs": techs}}


def test_all_six_twinborn_pairs_are_mapped_to_exact_modes() -> None:
    assert TWINBORN_MODES == {
        "Energy Guidance System": ("Drone Mode", "Forcefield Mode"),
        "Antimatter Maintainer": ("Drill Shot Mode", "Rocket Mode"),
        "Quantum Nanobot": ("Soccer Mode", "Durian Mode"),
        "Phase Driver": ("Lightning Mode", "Boomerang Mode"),
        "Exo-radicator": ("Guardian Mode", "Laser Mode"),
        "Hi-Gravity Pulser": ("Brick Mode", "Molotov Mode"),
    }


def test_unproven_twinborn_unlock_does_not_generate_free_mode_switch() -> None:
    profile = _profile(
        {
            "Energy Guidance System": {
                "deployed": True,
                "rarity": "Eternal",
            }
        }
    )
    assert recognized_twinborn_state(profile) == {}
    assert generate_twinborn_mode_actions(profile) == []


def test_one_twinborn_part_generates_only_the_alternate_mode() -> None:
    profile = _profile(
        {
            "Energy Guidance System": {
                "deployed": True,
                "mode": "Drone Mode",
                "rarity": "Eternal",
            }
        }
    )
    actions = generate_twinborn_mode_actions(profile)
    assert len(actions) == 1
    action = actions[0]
    assert action["state_patch"]["sio_ce"]["techs"]["Energy Guidance System"]["mode"] == "Forcefield Mode"
    assert action["consumed_items"] == {}
    assert action["metadata"]["one_mode_per_twinborn_pair"] is True
    assert action["metadata"]["permutation_search"] is False


def test_two_twinborn_parts_generate_cartesian_complete_assignments_not_sequences() -> None:
    profile = _profile(
        {
            "Energy Guidance System": {"deployed": True, "mode": "Drone Mode"},
            "Quantum Nanobot": {"deployed": True, "mode": "Durian Mode"},
        }
    )
    actions = generate_twinborn_mode_actions(profile)
    assert len(actions) == 3  # 2**2 complete assignments minus current state
    assignments = {
        tuple(sorted(action["metadata"]["assignment"].items()))
        for action in actions
    }
    assert assignments == {
        (
            ("Energy Guidance System", "Drone Mode"),
            ("Quantum Nanobot", "Soccer Mode"),
        ),
        (
            ("Energy Guidance System", "Forcefield Mode"),
            ("Quantum Nanobot", "Durian Mode"),
        ),
        (
            ("Energy Guidance System", "Forcefield Mode"),
            ("Quantum Nanobot", "Soccer Mode"),
        ),
    }
    assert len({action["action_id"] for action in actions}) == 3


def test_deployed_false_or_unknown_mode_is_excluded() -> None:
    profile = _profile(
        {
            "Energy Guidance System": {"deployed": False, "mode": "Drone Mode"},
            "Quantum Nanobot": {"deployed": True, "mode": "Not a real mode"},
        }
    )
    assert generate_twinborn_mode_actions(profile) == []
