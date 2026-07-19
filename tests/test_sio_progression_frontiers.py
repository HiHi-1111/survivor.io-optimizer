from __future__ import annotations

from optimizer.sio_progression_data import SIO_PROGRESSION_DATA
from optimizer.sio_progression_frontiers import (
    generate_mount_frontiers,
    generate_pet_frontiers,
    generate_survivor_frontiers,
    generate_tech_frontiers,
)
from optimizer.sio_tech_progression import (
    MULTIPLIER_CHIPS,
    MULTIPLIER_EXTRA_PARTS,
    OVERLOAD_CHIPS,
    OVERLOAD_EXTRA_PARTS,
)


def test_survivor_frontiers_include_distant_exact_cumulative_target() -> None:
    profile = {"sio_ce": {"heroes": {"King": {"stars": 0, "level": 80}}}}
    actions = generate_survivor_frontiers(profile)
    target = max(row["metadata"]["target_stars"] for row in actions)
    action = next(row for row in actions if row["metadata"]["target_stars"] == target)
    assert target == len(SIO_PROGRESSION_DATA["pA"]["Common"]) - 1
    assert action["state_patch"]["sio_ce"]["heroes"]["King"]["stars"] == target
    assert action["consumed_items"]["survivor_shard:king"] == (
        SIO_PROGRESSION_DATA["pA"]["Common"][target]
        - SIO_PROGRESSION_DATA["pA"]["Common"][0]
    )
    assert action["consumed_items"]["awakening_core"] == (
        SIO_PROGRESSION_DATA["on"]["Common"][target]
        - SIO_PROGRESSION_DATA["on"]["Common"][0]
    )


def test_synergy_frontiers_use_cumulative_s_shards_and_cores() -> None:
    profile = {"sio_ce": {"heroes": {}, "meta": {"synergy": True, "synergyLevel": 1}}}
    actions = [row for row in generate_survivor_frontiers(profile) if "synergy_frontier" in row["action_id"]]
    target = max(row["metadata"]["target_level"] for row in actions)
    action = next(row for row in actions if row["metadata"]["target_level"] == target)
    assert action["consumed_items"]["s_survivor_shard"] == (
        SIO_PROGRESSION_DATA["pA"]["synergy"][target]
        - SIO_PROGRESSION_DATA["pA"]["synergy"][1]
    )
    assert action["consumed_items"]["awakening_core"] == (
        SIO_PROGRESSION_DATA["on"]["synergy"][target]
        - SIO_PROGRESSION_DATA["on"]["synergy"][1]
    )


def test_xeno_pet_frontiers_include_all_higher_stars() -> None:
    profile = {"sio_ce": {"pets": {"active": "Capy", "stars": {"Capy": 1}, "support": []}}}
    actions = generate_pet_frontiers(profile)
    target = max(row["metadata"]["target_stars"] for row in actions)
    action = next(row for row in actions if row["metadata"]["target_stars"] == target)
    assert target == len(SIO_PROGRESSION_DATA["pA"]["Xeno"]) - 1
    assert action["consumed_items"]["xeno_pet_crystal"] == (
        SIO_PROGRESSION_DATA["pA"]["Xeno"][target]
        - SIO_PROGRESSION_DATA["pA"]["Xeno"][1]
    )
    assert action["consumed_items"]["xeno_pet_core"] == (
        SIO_PROGRESSION_DATA["on"]["Xeno"][target]
        - SIO_PROGRESSION_DATA["on"]["Xeno"][1]
    )


def test_mount_frontiers_use_exact_shard_and_core_deltas() -> None:
    profile = {
        "mounts": {
            "active": "Electric Scooter",
            "data": {"Electric Scooter": {"enabled": True, "stars": 1, "stats": {}}},
        }
    }
    actions = generate_mount_frontiers(profile)
    target = max(row["metadata"]["target_stars"] for row in actions)
    action = next(row for row in actions if row["metadata"]["target_stars"] == target)
    assert action["consumed_items"]["electric_scooter_shard"] == (
        SIO_PROGRESSION_DATA["nq"]["Better"][target]
        - SIO_PROGRESSION_DATA["nq"]["Better"][1]
    )
    expected_core = (
        SIO_PROGRESSION_DATA["SG"]["Better"][target]
        - SIO_PROGRESSION_DATA["SG"]["Better"][1]
    )
    if expected_core:
        assert action["consumed_items"]["mount_core"] == expected_core


def test_twinborn_multiplier_frontier_accounts_for_all_matching_parts() -> None:
    resource = "tech_part:energy_guidance_system:eternal"
    profile = {
        "sio_ce": {
            "techs": {
                "Energy Guidance System": {
                    "deployed": True,
                    "rarity": "Eternal",
                    "resonance": 15000,
                    "overload": 0,
                    "mode": "Drone Mode",
                    "mult": 1.0,
                    "part_resource_id": resource,
                }
            }
        }
    }
    actions = generate_tech_frontiers(profile)
    action = next(
        row
        for row in actions
        if row["action_type"] == "upgrade_resonance_multiplier_frontier"
        and row["metadata"]["target_multiplier"] == 5.0
    )
    target_chips = MULTIPLIER_CHIPS["twin"][5.0]
    assert action["consumed_items"]["resonance_chip"] == target_chips
    assert action["consumed_items"][resource] == MULTIPLIER_EXTRA_PARTS[target_chips]


def test_overload_frontier_sees_level_13_gate_and_cumulative_cost() -> None:
    resource = "tech_part:energy_guidance_system:eternal"
    profile = {
        "sio_ce": {
            "techs": {
                "Energy Guidance System": {
                    "deployed": True,
                    "rarity": "Eternal",
                    "resonance": 10500,
                    "overload": 0,
                    "mode": "Drone Mode",
                    "mult": 1.0,
                    "part_resource_id": resource,
                }
            }
        }
    }
    action = next(
        row
        for row in generate_tech_frontiers(profile)
        if row["action_type"] == "upgrade_resonance_overload_frontier"
        and row["metadata"]["target_overload"] == 13
    )
    assert action["metadata"]["required_resonance"] == 10500
    assert action["consumed_items"]["resonance_chip"] == OVERLOAD_CHIPS[13]
    assert action["consumed_items"][resource] == OVERLOAD_EXTRA_PARTS[13]
