from __future__ import annotations

import pytest

from optimizer.damage_engine import estimate_damage_score, estimate_damage_totals
from optimizer.main import optimize
from optimizer.sio_ce_damage import UnsupportedGameModeError
from optimizer.source_pack_optimizer import optimize_source_pack_actions


def ce_profile(*, scooter_stats=None, scooter_stars=0, scooter_shards=20):
    return {
        "game_mode": "clan_expedition",
        "goal_scenario": "clan_expedition",
        "sio_ce": {
            "stats_stage": "post_24804",
            "stats": {},
            "attack": {"atkBase": 1000, "atkFinal": 0},
            "passive_multiplier": 1.0,
        },
        "mounts": {
            "active": "Doomsteed",
            "data": {
                "Doomsteed": {"enabled": True, "stars": 0, "lines": 0, "stats": {}},
                "Electric Scooter": {
                    "enabled": True,
                    "stars": scooter_stars,
                    "lines": 0,
                    "stats": scooter_stats or {},
                },
            },
        },
        "inventory": {"items": {"electric_scooter_shard": scooter_shards}},
    }


def test_damage_engine_delegates_to_sio_ce_formula():
    result = estimate_damage_totals(
        {
            "game_mode": "clan_expedition",
            "sio_ce": {
                "stats_stage": "post_24804",
                "stats": {"skillDamage": 20, "vulnerability": 10},
                "attack": {"atkBase": 1000, "atkFinal": 0},
                "passive_multiplier": 1.0,
            },
        }
    )
    assert result["damage_math_type"] == "sio_clan_expedition_exact_core"
    assert result["total_damage"] == pytest.approx(1320)


def test_legacy_stat_helper_uses_expected_crit_formula():
    assert estimate_damage_score({"atk": 1000, "crit_rate": 0.5, "crit_damage": 3.0}) == 2000


def test_mount_upgrade_is_scored_from_exact_before_after_state():
    result = optimize_source_pack_actions(ce_profile(scooter_stats={"skillDamage": 100}))
    assert result["best"]["action_id"] == "upgrade_electric_scooter_y1"
    assert result["best"]["expected_dps_gain"] > 0
    assert result["best"]["after_damage"] > result["best"]["before_damage"]
    assert result["numeric_backend"]["learned_or_gpu_ranking_used"] is False


def test_sync_rate_upgrade_with_no_board_stats_is_not_fake_damage():
    result = optimize_source_pack_actions(ce_profile(scooter_stats={}))
    assert result["best"] is None
    assert result["no_action_recommended"] is True
    candidate = next(row for row in result["ranked_actions"] if row["action_id"] == "upgrade_electric_scooter_y1")
    assert candidate["expected_dps_gain"] == 0


def test_unbridged_tech_action_is_rejected_not_heuristically_scored():
    profile = ce_profile(scooter_shards=0)
    profile["resources"] = {"resonance_chip": 100}
    result = optimize_source_pack_actions(profile)
    reason = next(row["reason"] for row in result["rejected_actions"] if row["action_id"] == "resonance_multiplier_1_2")
    assert reason.startswith("missing_exact_after_state_bridge:tech_parts")


def test_public_optimizer_does_not_run_generic_global_planner():
    result = optimize(ce_profile(scooter_stats={"skillDamage": 100}), include_global_plan=True)
    assert result["game_mode"] == "clan_expedition"
    assert result["global_plan"]["supported"] is False
    assert result["global_plan"]["learned_or_heuristic_winner_selection"] is False
    assert result["best"]["action_id"] == "upgrade_electric_scooter_y1"


def test_other_modes_are_never_supported():
    profile = ce_profile()
    profile["game_mode"] = "enders_echo"
    with pytest.raises(UnsupportedGameModeError):
        estimate_damage_totals(profile)
