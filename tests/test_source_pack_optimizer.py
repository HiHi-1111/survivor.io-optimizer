from __future__ import annotations

from optimizer.source_pack_optimizer import (
    clear_source_pack_cache,
    optimize_source_pack_actions,
    optimize_source_pack_batch,
)


def _profile(*, scooter_stats=None, scooter_shards=20):
    return {
        "game_mode": "clan_expedition",
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
                    "stars": 0,
                    "lines": 0,
                    "stats": scooter_stats or {},
                },
            },
        },
        "inventory": {"items": {"electric_scooter_shard": scooter_shards}},
    }


def test_unbridged_resonance_action_is_rejected_not_heuristically_scored() -> None:
    clear_source_pack_cache()
    profile = _profile(scooter_shards=0)
    profile["resources"] = {"resonance_chip": 1}
    result = optimize_source_pack_actions(profile, device="cpu")
    reason = next(
        row["reason"]
        for row in result["rejected_actions"]
        if row["action_id"] == "resonance_multiplier_1_2"
    )
    assert reason.startswith("missing_exact_after_state_bridge:tech_parts")
    assert result["false_prunes"] == []


def test_mount_action_requires_owned_mount_exact_previous_star_and_ce_state() -> None:
    result = optimize_source_pack_actions(_profile(scooter_stats={"skillDamage": 100}), device="cpu")
    assert result["best"]["action_id"] == "upgrade_electric_scooter_y1"
    assert result["best"]["estimated_dps_value"] > 0
    assert result["best"]["after_damage"] > result["best"]["before_damage"]


def test_sync_rate_without_board_stats_is_zero_damage() -> None:
    result = optimize_source_pack_actions(_profile(scooter_stats={}), device="cpu")
    assert result["best"] is None
    assert result["no_action_recommended"] is True
    action = next(row for row in result["ranked_actions"] if row["action_id"] == "upgrade_electric_scooter_y1")
    assert action["expected_dps_gain"] == 0


def test_unaffordable_templates_are_logged_not_pruned() -> None:
    result = optimize_source_pack_actions(_profile(scooter_shards=0), device="cpu")
    assert result["best"] is None
    assert result["rejected_count"] > 0
    assert result["pruning_policy"].startswith("none")


def test_profiles_use_deterministic_exact_cpu_scoring() -> None:
    batch = optimize_source_pack_batch(
        [_profile(scooter_stats={"skillDamage": 100}), _profile(scooter_stats={})],
        device="cpu",
    )
    assert batch["numeric_backend"]["backend"] == "deterministic_cpu_exact_sio_ce"
    assert batch["numeric_backend"]["learned_or_gpu_ranking_used"] is False
    assert batch["profiles"][0]["best"]["action_id"] == "upgrade_electric_scooter_y1"
    assert batch["profiles"][1]["best"] is None
