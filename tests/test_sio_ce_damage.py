from __future__ import annotations

import pytest

from optimizer.sio_ce_damage import (
    SIO_DIRECT_DAMAGE_COEFFICIENTS,
    UnsupportedGameModeError,
    calculate_ce_direct_factor,
    calculate_clan_expedition_damage,
    compare_clan_expedition_profiles,
)
from optimizer.sio_mounts import aggregate_mount_stats


def profile(stats=None, *, atk_base=1000, atk_final=0, **extra):
    return {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats_stage": "post_24804",
            "stats": stats or {},
            "attack": {"atkBase": atk_base, "atkFinal": atk_final},
            "passive_multiplier": 1.0,
        },
        **extra,
    }


def test_base_formula_matches_sio_defaults():
    result = calculate_clan_expedition_damage(profile())
    assert result["supported"] is True
    assert result["base_attack"] == 1000
    assert result["stat_multiplier"] == 1
    assert result["direct_damage_multiplier_applied"] == 1
    assert result["total_damage"] == 1000


def test_crit_expectation_matches_module_67727():
    result = calculate_clan_expedition_damage(profile({"critRate": 50, "critDamage": 300}))
    assert result["multiplier_breakdown"]["crit_expected"] == 2
    assert result["total_damage"] == 2000


def test_damage_buckets_are_multiplicative_not_flat_added():
    result = calculate_clan_expedition_damage(profile({"skillDamage": 20, "vulnerability": 10}))
    assert result["total_damage"] == pytest.approx(1000 * 1.2 * 1.1)


def test_debuff_strength_is_weighted_by_uptime():
    result = calculate_clan_expedition_damage(profile({"poisoned": 50, "poisonedUptime": 0.5}))
    assert result["multiplier_breakdown"]["poison_weaken_chill_exposed"] == 1.25
    assert result["total_damage"] == 1250


def test_direct_ce_components_use_sio_coefficients():
    direct = calculate_ce_direct_factor(
        {
            "ssMiscPath": 100,
            "taloxaBeam": 2,
            "crimsonBat": 3,
            "harmonyYang": 4,
            "xenoDamage": 5,
            "mountDamage": 6,
        }
    )
    expected = (
        100**0.72 * SIO_DIRECT_DAMAGE_COEFFICIENTS["ssWeapon"]
        + 2 * SIO_DIRECT_DAMAGE_COEFFICIENTS["taloxaOverload"]
        + 3 * SIO_DIRECT_DAMAGE_COEFFICIENTS["crimsonBat"]
        + 4 * SIO_DIRECT_DAMAGE_COEFFICIENTS["Master Yang"]
        + 5
        + 6
    )
    assert direct["damage_factor"] == pytest.approx(expected)


def test_mounts_apply_active_lines_and_undeployed_sync_exactly():
    mounts = {
        "active": "Electric Scooter",
        "data": {
            "Electric Scooter": {"enabled": True, "stars": 0, "lines": 3, "stats": {"skillDamage": 10}},
            "Doomsteed": {"enabled": True, "stars": 0, "lines": 8, "stats": {"skillDamage": 100, "poisoned": 50}},
        },
    }
    result = aggregate_mount_stats(mounts)
    stats = result["stats"]
    assert stats["skillDamage"] == 50
    assert stats["poisoned"] == 20
    assert stats["weakened"] == 25
    assert stats["critDamage"] == 20
    assert stats["mountDamage"] == 153 * 77
    assert result["detail"]["Doomsteed"]["sync_rate"] == 0.4
    assert result["detail"]["Doomsteed"]["line_effects_applied"] == {}


def test_mount_sync_rate_is_not_direct_damage_by_itself():
    base_mount = {
        "active": "Electric Scooter",
        "data": {
            "Electric Scooter": {"enabled": True, "stars": 0, "lines": 0, "stats": {}},
            "Doomsteed": {"enabled": True, "stars": 0, "lines": 0, "stats": {}},
        },
    }
    upgraded = {
        "active": "Electric Scooter",
        "data": {
            "Electric Scooter": {"enabled": True, "stars": 0, "lines": 0, "stats": {}},
            "Doomsteed": {"enabled": True, "stars": 1, "lines": 0, "stats": {}},
        },
    }
    assert aggregate_mount_stats(base_mount)["stats"] == aggregate_mount_stats(upgraded)["stats"]


def test_profile_comparison_uses_exact_before_after_damage():
    result = compare_clan_expedition_profiles(profile({"skillDamage": 0}), profile({"skillDamage": 20}))
    assert result["supported"] is True
    assert result["delta"] == 200
    assert result["percent_gain"] == 20


def test_non_ce_modes_are_rejected():
    bad = profile()
    bad["game_mode"] = "enders_echo"
    with pytest.raises(UnsupportedGameModeError):
        calculate_clan_expedition_damage(bad)


def test_missing_sio_attack_split_is_unknown_not_fake_score():
    result = calculate_clan_expedition_damage(
        {"game_mode": "clan_expedition", "sio_ce": {"stats_stage": "post_24804", "stats": {}}}
    )
    assert result["supported"] is False
    assert result["reason"] == "missing_sio_attack_split"
