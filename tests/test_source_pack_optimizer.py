from __future__ import annotations

import optimizer.source_pack_optimizer as source_optimizer
from optimizer.source_pack_optimizer import (
    clear_source_pack_cache,
    optimize_source_pack_actions,
    optimize_source_pack_batch,
)


def _profile(*, scooter_stats=None, scooter_shards=20):
    return {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats_stage": "raw_profile",
            "stats": {},
            "evolvePassives": False,
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


def test_sync_rate_without_board_stats_is_source_proven_neutral() -> None:
    result = optimize_source_pack_actions(_profile(scooter_stats={}), device="cpu")
    assert result["best"] is None
    assert result["no_action_recommended"] is True
    action = next(
        row for row in result["preflight_neutral_actions"]
        if row["action_id"] == "upgrade_electric_scooter_y1"
    )
    assert action["reason"] == "source_proven_zero_ce_delta"
    assert action["preflight_estimate"]["estimated_damage_gain"] == 0


def test_unaffordable_templates_are_logged_not_pruned() -> None:
    result = optimize_source_pack_actions(_profile(scooter_shards=0), device="cpu")
    assert result["best"] is None
    assert result["rejected_count"] > 0
    assert "source-proven zero CE states" in result["pruning_policy"]


def test_profiles_use_deterministic_exact_cpu_scoring() -> None:
    batch = optimize_source_pack_batch(
        [_profile(scooter_stats={"skillDamage": 100}), _profile(scooter_stats={})],
        device="cpu",
    )
    assert batch["numeric_backend"]["backend"] == "deterministic_cpu_exact_sio_ce"
    assert batch["numeric_backend"]["learned_or_gpu_ranking_used"] is False
    assert batch["numeric_backend"]["profiles_batched"] == 2
    assert batch["numeric_backend"]["runtime_processes_per_uncached_batch"] == 1
    assert batch["numeric_backend"]["effect_preflight_used"] is True
    assert batch["profiles"][0]["best"]["action_id"] == "upgrade_electric_scooter_y1"
    assert batch["profiles"][1]["best"] is None


def test_multiple_profiles_are_flattened_into_one_formula_batch(monkeypatch) -> None:
    calls: list[list[dict]] = []

    def fake_formula_batch(states):
        rows = [dict(state) for state in states]
        calls.append(rows)
        reports = []
        for state in rows:
            mounts = state.get("mounts", {})
            data = mounts.get("data", {}) if isinstance(mounts, dict) else {}
            scooter = data.get("Electric Scooter", {}) if isinstance(data, dict) else {}
            stars = int(scooter.get("stars", 0) or 0) if isinstance(scooter, dict) else 0
            reports.append({
                "supported": True,
                "total_damage": 1000.0 + stars * 100.0,
                "formula_provenance": {"test": True},
                "runtime_exact": True,
            })
        return reports

    monkeypatch.setattr(source_optimizer, "calculate_clan_expedition_damage_batch", fake_formula_batch)
    batch = optimize_source_pack_batch(
        [_profile(scooter_stats={"skillDamage": 100}), _profile(scooter_stats={"skillDamage": 100})],
        device="cpu",
    )
    assert len(calls) == 1
    assert len(calls[0]) == batch["numeric_backend"]["states_scored_in_one_batch"]
    assert batch["numeric_backend"]["profiles_batched"] == 2
    assert all(result["best"]["action_id"] == "upgrade_electric_scooter_y1" for result in batch["profiles"])
