from __future__ import annotations

from optimizer.player_state import validate_player_state, validate_player_states


def test_sio_aliases_normalize_without_removing_original_evidence() -> None:
    source = {
        "gameMode": "clan_expedition",
        "goalScenario": "clan_expedition",
        "sioCE": {
            "statsStage": "raw_profile",
            "evolve_passives": True,
            "active_survivor": "Venato",
            "evo_tree": {"Expose Weakness": True},
            "pet_skills": {"Sync Rate": {"value": 20}},
            "upgraded_collectibles": ["Lucky Charm"],
            "choiceChests": {"core_selector": {"count": 2}},
            "configurationConstraints": {"survivor": {"max_states": 100}},
            "mountPuzzles": {"Doomsteed": {"verified": False}},
            "new_sio_field_from_future_update": {"kept": True},
        },
    }
    state = validate_player_state(source)
    assert state.game_mode == "clan_expedition"
    assert state.goal_scenario == "clan_expedition"
    assert state.sio_ce.stats_stage == "raw_profile"
    assert state.sio_ce.evolvePassives is True
    assert state.sio_ce.activeSurvivor == "Venato"
    assert state.sio_ce.evoTree == {"Expose Weakness": True}
    assert state.sio_ce.petSkills == {"Sync Rate": {"value": 20}}
    assert state.sio_ce.upgradedCollectibles == ["Lucky Charm"]
    assert state.sio_ce.choice_chests == {"core_selector": {"count": 2}}
    assert state.sio_ce.configuration_constraints == {"survivor": {"max_states": 100}}
    assert state.sio_ce.mount_puzzles == {"Doomsteed": {"verified": False}}
    dumped = state.model_dump()
    assert dumped["sio_ce"]["new_sio_field_from_future_update"] == {"kept": True}
    assert dumped["sio_ce"]["evolve_passives"] is True
    assert dumped["sio_ce"]["choiceChests"] == {"core_selector": {"count": 2}}
    assert dumped["sio_ce"]["configurationConstraints"] == {"survivor": {"max_states": 100}}
    assert dumped["sio_ce"]["mountPuzzles"] == {"Doomsteed": {"verified": False}}


def test_inventory_choice_chests_are_typed_but_unknown_fields_stay_lossless() -> None:
    state = validate_player_state(
        {
            "inventory": {
                "choice_chests": {"selector": {"count": 3}},
                "future_inventory_field": {"x": 1},
            }
        }
    )
    assert state.inventory.choice_chests == {"selector": {"count": 3}}
    assert state.model_dump()["inventory"]["future_inventory_field"] == {"x": 1}


def test_reused_batch_adapter_reads_multiple_complete_profiles() -> None:
    rows = [
        {"sio_ce": {"attack": {"atkBase": 1, "atkFinal": 0}, "evolvePassives": False}},
        {"sio_ce": {"attack": {"atkBase": 2, "atkFinal": 0}, "evolvePassives": True}},
    ]
    states = validate_player_states(rows)
    assert [state.sio_ce.attack["atkBase"] for state in states] == [1, 2]
    assert [state.sio_ce.evolvePassives for state in states] == [False, True]
