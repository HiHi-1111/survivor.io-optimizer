from __future__ import annotations

from optimizer.sio_pet_configurations import (
    generate_pet_configuration_actions,
    owned_pet_candidates,
)
from optimizer.sio_pet_data import SIO_PET_DATA
from optimizer.sio_pets import XENO_NAMES


def _profile(*, active, stars, support=None):
    return {
        "sio_ce": {
            "pets": {
                "active": active,
                "stars": dict(stars),
                "support": list(support or []),
            }
        }
    }


def test_owned_candidates_are_derived_from_complete_source_pet_catalog() -> None:
    normal = next(
        name
        for name, definition in SIO_PET_DATA["pets"].items()
        if definition.get("type") == "Default"
    )
    profile = _profile(active=normal, stars={normal: 1})
    assert normal in owned_pet_candidates(profile)


def test_identical_xeno_skill_rows_use_combinations_not_swapped_permutations() -> None:
    stars = {name: 1 for name in XENO_NAMES}
    support = [
        {"name": "Capy", "skill": ["Sync Rate"]},
        {"name": "Crucker", "skill": ["Dmg to Poisoned"]},
        {"name": "Puffo", "skill": ["Dmg to Poisoned"]},
    ]
    actions = generate_pet_configuration_actions(
        _profile(active="Capy", stars=stars, support=support)
    )
    same_active = [
        action for action in actions
        if action["metadata"]["active_pet"] == "Capy"
    ]
    # Five available support pets choose two identical roles: C(5,2)=10. The
    # current Crucker/Puffo set is skipped, leaving nine exact alternatives.
    assert len(same_active) == 9
    semantic_sets = {
        tuple(sorted(action["metadata"]["support_assignment"].values()))
        for action in same_active
    }
    assert len(semantic_sets) == 9
    assert ("Crucker", "Puffo") not in semantic_sets
    assert all(
        action["metadata"]["identical_skill_roles_use_combinations"] is True
        and action["metadata"]["order_independent_permutation_search"] is False
        for action in same_active
    )


def test_different_skill_rows_remain_distinct_roles() -> None:
    stars = {"Capy": 1, "Crucker": 1, "Puffo": 1}
    support = [
        {"name": "Capy", "skill": ["Sync Rate"]},
        {"name": "Crucker", "skill": ["Dmg to Poisoned"]},
        {"name": "Puffo", "skill": ["Dmg to Chilled"]},
    ]
    actions = generate_pet_configuration_actions(
        _profile(active="Capy", stars=stars, support=support)
    )
    same_active = [
        action for action in actions
        if action["metadata"]["active_pet"] == "Capy"
    ]
    # Two distinct one-pet roles have two valid assignments. The current one is
    # skipped, leaving the role-swapped state because it changes exact effects.
    assert len(same_active) == 1
    assert same_active[0]["metadata"]["support_assignment"] == {
        "1": "Puffo",
        "2": "Crucker",
    }


def test_active_xeno_pet_cannot_also_be_a_named_support_pet() -> None:
    stars = {name: 1 for name in XENO_NAMES}
    support = [
        {"name": "Capy", "skill": ["Sync Rate"]},
        {"name": "Crucker", "skill": ["Dmg to Poisoned"]},
    ]
    actions = generate_pet_configuration_actions(
        _profile(active="Capy", stars=stars, support=support)
    )
    for action in actions:
        active = action["metadata"]["active_pet"]
        assigned = set(action["metadata"]["support_assignment"].values())
        assert active not in assigned
        assert len(assigned) == len(action["metadata"]["support_assignment"])


def test_insufficient_unique_support_pets_skips_that_xeno_active_state() -> None:
    profile = _profile(
        active="Capy",
        stars={"Capy": 1, "Crucker": 1},
        support=[
            {"name": "Capy", "skill": ["Sync Rate"]},
            {"name": "Crucker", "skill": ["Dmg to Poisoned"]},
            {"name": "Crucker", "skill": ["Dmg to Chilled"]},
        ],
    )
    actions = generate_pet_configuration_actions(profile)
    assert not any(action["metadata"]["active_pet"] == "Capy" for action in actions)


def test_current_normal_active_pet_is_not_returned_as_a_noop_action() -> None:
    normal = next(
        name
        for name, definition in SIO_PET_DATA["pets"].items()
        if definition.get("type") == "Default"
    )
    actions = generate_pet_configuration_actions(
        _profile(active=normal, stars={normal: 1})
    )
    assert not any(action["metadata"]["active_pet"] == normal for action in actions)
