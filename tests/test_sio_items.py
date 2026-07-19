from __future__ import annotations

import pytest

from optimizer.sio_items import assemble_sio_item_stats


def test_twin_lance_e5_cumulative_stats() -> None:
    profile = {
        "sio_ce": {
            "max_gear": 200,
            "items": {"Weapon": {"name": "Twin Lance", "e": 5, "v": 0, "c": 0, "x": 0}},
        }
    }
    result = assemble_sio_item_stats(
        profile,
        {"critDamage": 200, "shieldDamageUptime": 1, "voidNeckBoostUptime": 1},
    )
    stats = result["stats"]
    assert stats["skillDamage"] == 105
    assert stats["atkPercent"] == 50
    assert stats["atkFinal"] == 4000
    assert stats["atkEquip"] == 952 + 200 * 60
    assert stats["ssMiscPath"] == pytest.approx(133.8)


def test_xeno_transmute_effect_and_damage_duration() -> None:
    profile = {
        "sio_ce": {
            "items": {
                "Weapon": {
                    "name": "Twin Lance",
                    "x": 5,
                    "transmuteEffect": 1,
                    "transmuteCondition": 0,
                }
            }
        }
    }
    stats = assemble_sio_item_stats(profile)["stats"]
    assert stats["poisoned"] > 146
    assert stats["damageTransmute"] == pytest.approx(3 * 4.183333333333334)


def test_moonscar_e1_threshold_full_at_100_crit() -> None:
    profile = {"sio_ce": {"items": {"Gloves": {"name": "Moonscar Bracer", "e": 1}}}}
    stats = assemble_sio_item_stats(profile, {"critRate": 70, "critDamage": 200})["stats"]
    assert stats["critRate"] == 100
    assert stats["critDamage"] == 230
    assert stats["ssGlovesLaser"] == 50


def test_chaos_fusion_power_uses_total_c_stars() -> None:
    profile = {
        "sio_ce": {
            "items": {
                "Weapon": {"name": "Twin Lance", "c": 6},
                "Armor": {"name": "Evervoid Armor", "c": 6},
            }
        }
    }
    stats = assemble_sio_item_stats(profile)["stats"]
    assert stats["vulnerability"] >= 40
    assert stats["ssMiscPath"] > 133.8


def test_missing_gear_level_is_reported_instead_of_invented() -> None:
    profile = {"sio_ce": {"items": {"Weapon": {"name": "Twin Lance", "e": 1}}}}
    result = assemble_sio_item_stats(profile)
    assert "atkEquip" not in result["stats"]
    assert any("max_gear missing" in warning for warning in result["warnings"])
