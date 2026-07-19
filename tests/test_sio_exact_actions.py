from __future__ import annotations

from optimizer.sio_exact_actions import (
    affordability_certificate,
    generate_exact_actions,
    generate_item_actions,
    generate_mount_actions,
    generate_pet_actions,
    generate_survivor_actions,
)


def _base_profile() -> dict:
    return {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "attack": {"atkBase": 1000, "atkFinal": 0},
            "evolvePassives": False,
        },
    }


def test_twin_lance_e1_uses_exact_cumulative_relic_and_eternal_cost() -> None:
    profile = _base_profile()
    profile["sio_ce"]["items"] = {
        "Weapon": {"name": "Twin Lance", "e": 0, "v": 0, "c": 0, "x": 0}
    }
    actions = generate_item_actions(profile)
    action = next(
        row for row in actions
        if row["metadata"].get("slot") == "Weapon"
        and row["metadata"].get("target", {}).get("e") == 1
        and row["metadata"].get("target", {}).get("v") == 0
        and row["metadata"].get("target", {}).get("c") == 0
    )
    assert action["consumed_items"]["relic_core"] == 1
    assert action["consumed_items"]["eternal_core"] == 10
    assert action["refunded_items"] == {}


def test_two_slot_item_reallocation_has_real_refund_ledger() -> None:
    profile = _base_profile()
    profile["sio_ce"]["items"] = {
        "Weapon": {"name": "Twin Lance", "e": 3, "v": 2, "c": 2, "x": 0},
        "Necklace": {"name": "Judgment Necklace", "e": 0, "v": 0, "c": 0, "x": 0},
    }
    actions = generate_item_actions(profile)
    reallocation = next(
        row for row in actions
        if row["action_type"] == "reallocate_item_resources"
        and row["refunded_items"]
        and row["consumed_items"]
    )
    assert reallocation["metadata"]["source_slot"] != reallocation["metadata"]["target_slot"]
    assert all(value >= 0 for value in reallocation["refunded_items"].values())
    assert all(value >= 0 for value in reallocation["consumed_items"].values())


def test_master_yang_first_star_costs_exact_s_shards() -> None:
    profile = _base_profile()
    profile["sio_ce"]["heroes"] = {"Master Yang": {"stars": 0, "level": 120}}
    action = next(row for row in generate_survivor_actions(profile) if row["action_id"] == "survivor:star:master_yang:1")
    assert action["consumed_items"] == {"s_survivor_shard": 120}


def test_xeno_pet_second_star_uses_incremental_crystal_and_core_cost() -> None:
    profile = _base_profile()
    profile["sio_ce"]["pets"] = {
        "active": "Crucker",
        "stars": {"Crucker": 1},
    }
    action = next(row for row in generate_pet_actions(profile) if row["action_id"] == "pets:star:crucker:2")
    assert action["consumed_items"] == {"xeno_pet_crystal": 20, "xeno_pet_core": 1}


def test_mount_first_star_uses_incremental_shards_and_legend_core() -> None:
    profile = _base_profile()
    profile["mounts"] = {
        "active": "Electric Scooter",
        "data": {
            "Electric Scooter": {"enabled": True, "stars": 0, "lines": 0, "stats": {}},
            "Doomsteed": {"enabled": True, "stars": 0, "lines": 0, "stats": {}},
        },
    }
    actions = generate_mount_actions(profile)
    scooter = next(row for row in actions if row["metadata"].get("mount") == "Electric Scooter")
    doomsteed = next(row for row in actions if row["metadata"].get("mount") == "Doomsteed")
    assert scooter["consumed_items"] == {"electric_scooter_shard": 20}
    assert doomsteed["consumed_items"] == {"doomsteed_shard": 20, "mount_core": 1}


def test_refunds_count_toward_same_transition_affordability() -> None:
    profile = _base_profile()
    profile["resources"] = {"relic_core": 0}
    action = {
        "action_id": "balanced_move",
        "state_patch": {"sio_ce": {"marker": True}},
        "consumed_items": {"relic_core": 5},
        "refunded_items": {"relic_core": 5},
    }
    certificate = affordability_certificate(profile, action)
    assert certificate["legal"] is True
    assert certificate["balanced"] is True
    assert certificate["missing"] == {}


def test_supplied_exact_tech_patch_is_never_given_an_invented_cost() -> None:
    profile = _base_profile()
    profile["resources"] = {"resonance_chip": 1}
    profile["sio_ce"]["exact_actions"] = [
        {
            "action_id": "tech:drone:resonance_chip_1",
            "system": "tech_parts",
            "action_type": "upgrade_resonance_multiplier",
            "state_patch": {
                "sio_ce": {
                    "techs": {
                        "Energy Guidance System": {
                            "deployed": True,
                            "rarity": "Eternal",
                            "resonance": 900,
                            "overload": 0,
                            "mode": "Drone Mode",
                        }
                    }
                }
            },
            "consumed_items": {"resonance_chip": 1},
            "source_modules": [13024],
        }
    ]
    action = next(row for row in generate_exact_actions(profile) if row["action_id"] == "tech:drone:resonance_chip_1")
    assert action["consumed_items"] == {"resonance_chip": 1}
    assert action["metadata"]["supplied_exact_action"] is True
