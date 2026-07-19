from __future__ import annotations

from optimizer.sio_tech_progression import generate_tech_progression_actions


def _profile(state: dict) -> dict:
    return {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "attack": {"atkBase": 1000, "atkFinal": 0},
            "evolvePassives": False,
            "techs": {"Energy Guidance System": state},
        },
    }


def test_twinborn_multiplier_first_step_costs_one_resonance_chip() -> None:
    actions = generate_tech_progression_actions(
        _profile({
            "deployed": True,
            "rarity": "Eternal",
            "resonance": 0,
            "overload": 0,
            "mode": "Drone Mode",
            "mult": 1.0,
        })
    )
    action = next(row for row in actions if row["action_type"] == "upgrade_resonance_multiplier")
    assert action["metadata"]["target_multiplier"] == 1.2
    assert action["consumed_items"] == {"resonance_chip": 1}
    assert action["state_patch"]["sio_ce"]["techs"]["Energy Guidance System"]["mult"] == 1.2


def test_overload_first_step_requires_900_resonance_and_one_chip() -> None:
    actions = generate_tech_progression_actions(
        _profile({
            "deployed": True,
            "rarity": "Eternal",
            "resonance": 900,
            "overload": 0,
            "mode": "Drone Mode",
            "mult": 1.0,
        })
    )
    action = next(row for row in actions if row["action_type"] == "upgrade_resonance_overload")
    assert action["metadata"]["target_overload"] == 1
    assert action["metadata"]["required_resonance"] == 900
    assert action["consumed_items"] == {"resonance_chip": 1}


def test_multiplier_extra_part_is_skipped_without_exact_part_resource_id() -> None:
    actions = generate_tech_progression_actions(
        _profile({
            "deployed": True,
            "rarity": "Eternal",
            "resonance": 15000,
            "overload": 0,
            "mode": "Drone Mode",
            "mult": 4.0,
        })
    )
    assert not any(
        row["action_type"] == "upgrade_resonance_multiplier"
        and row["metadata"].get("target_multiplier") == 4.2
        for row in actions
    )


def test_multiplier_extra_part_uses_profile_supplied_exact_resource() -> None:
    actions = generate_tech_progression_actions(
        _profile({
            "deployed": True,
            "rarity": "Eternal",
            "resonance": 15000,
            "overload": 0,
            "mode": "Drone Mode",
            "mult": 4.0,
            "part_resource_id": "tech_part:energy_guidance_system:eternal",
        })
    )
    action = next(
        row for row in actions
        if row["action_type"] == "upgrade_resonance_multiplier"
        and row["metadata"].get("target_multiplier") == 4.2
    )
    assert action["consumed_items"] == {
        "resonance_chip": 6,
        "tech_part:energy_guidance_system:eternal": 1,
    }


def test_overload_level_13_uses_exact_matching_part_and_chip_delta() -> None:
    actions = generate_tech_progression_actions(
        _profile({
            "deployed": True,
            "rarity": "Eternal",
            "resonance": 7500,
            "overload": 12,
            "mode": "Drone Mode",
            "mult": 1.0,
            "part_resource_id": "tech_part:energy_guidance_system:eternal",
        })
    )
    action = next(
        row for row in actions
        if row["action_type"] == "upgrade_resonance_overload"
        and row["metadata"].get("target_overload") == 13
    )
    assert action["consumed_items"] == {
        "resonance_chip": 5,
        "tech_part:energy_guidance_system:eternal": 1,
    }
