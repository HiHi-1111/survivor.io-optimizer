from __future__ import annotations

from optimizer.sio_survivor_configurations import (
    NONE,
    generate_survivor_configuration_actions,
    plan_survivor_configurations,
    teamwork_slot_count,
)


def _hero(stars, *, level=120):
    return {"stars": stars, "level": level}


def test_teamwork_slot_count_matches_sio_module_92316() -> None:
    assert [teamwork_slot_count(stars) for stars in range(6, 15)] == [0, 0, 1, 1, 2, 2, 3, 3, 4]


def test_teamwork_is_enumerated_as_subsets_not_slot_permutations() -> None:
    profile = {
        "sio_ce": {
            "heroes": {
                "Master Yang": _hero(10),
                "Raphael": _hero(7),
                "April": _hero(8),
                "Splinter": _hero(10),
            },
            "meta": {
                "mainHero": "Master Yang",
                "synergy": False,
                "teamwork": [],
            },
            "configuration_constraints": {
                "survivor": {
                    "main_candidates": ["Master Yang"],
                    "teamwork_candidates": ["Raphael", "April", "Splinter"],
                    "max_states": 100,
                }
            },
        }
    }
    plan = plan_survivor_configurations(profile)
    assert plan.complete is True
    # main has two slots: C(3,0) + C(3,1) + C(3,2) = 7 complete states.
    assert plan.total_states == 7
    assignments = {
        tuple(action["metadata"]["teamwork"])
        for action in plan.actions
    }
    assert ("April", "Raphael") in assignments
    assert ("Raphael", "April") not in assignments
    assert all(action["metadata"]["teamwork_permutation_search"] is False for action in plan.actions)


def test_harmony_left_and_right_remain_role_specific_and_distinct() -> None:
    profile = {
        "sio_ce": {
            "heroes": {
                "Master Yang": _hero(8),
                "Common": _hero(7),
                "King": _hero(7),
            },
            "meta": {
                "mainHero": "Master Yang",
                "synergy": True,
                "harmonyL": NONE,
                "harmonyR": NONE,
                "teamwork": [],
            },
            "configuration_constraints": {
                "survivor": {
                    "main_candidates": ["Master Yang"],
                    "harmony_candidates": ["Common", "King"],
                    "teamwork_candidates": [],
                    "max_states": 100,
                }
            },
        }
    }
    plan = plan_survivor_configurations(profile)
    assert plan.complete is True
    # (None, None), four one-sided assignments, and two ordered distinct pairs.
    assert plan.total_states == 7
    roles = {
        (action["metadata"]["harmony_left"], action["metadata"]["harmony_right"])
        for action in plan.actions
    }
    assert ("Common", "King") in roles
    assert ("King", "Common") in roles
    assert ("Common", "Common") not in roles


def test_state_budget_returns_no_partial_actions() -> None:
    profile = {
        "sio_ce": {
            "heroes": {
                "Master Yang": _hero(12),
                "Metalia": _hero(12),
                "Raphael": _hero(8),
                "April": _hero(8),
                "Splinter": _hero(8),
                "Leonardo": _hero(8),
                "Michelangelo": _hero(8),
            },
            "meta": {"mainHero": "Master Yang", "synergy": False, "teamwork": []},
            "configuration_constraints": {"survivor": {"max_states": 2}},
        }
    }
    plan = plan_survivor_configurations(profile)
    assert plan.complete is False
    assert plan.total_states > plan.max_states
    assert plan.actions == ()
    assert generate_survivor_configuration_actions(profile) == []
    assert plan.reason == "exact_survivor_configuration_state_budget_exceeded"


def test_current_state_is_skipped_but_all_other_complete_states_are_actions() -> None:
    profile = {
        "sio_ce": {
            "heroes": {
                "Master Yang": _hero(8),
                "Raphael": _hero(7),
            },
            "meta": {
                "mainHero": "Master Yang",
                "synergy": False,
                "teamwork": ["Raphael"],
            },
            "configuration_constraints": {
                "survivor": {
                    "main_candidates": ["Master Yang"],
                    "teamwork_candidates": ["Raphael"],
                    "max_states": 10,
                }
            },
        }
    }
    plan = plan_survivor_configurations(profile)
    assert plan.total_states == 2
    assert len(plan.actions) == 1
    assert plan.actions[0]["metadata"]["teamwork"] == []
