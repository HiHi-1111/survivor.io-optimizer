from __future__ import annotations

from copy import deepcopy

from optimizer.sio_ce_account import prepare_sio_ce_profile
from optimizer.sio_effect_evaluator import (
    compare_attack_options,
    evaluate_effect_transition,
    evaluate_preflight_transitions,
    load_effect_registry,
)
from optimizer.source_pack_optimizer import optimize_source_pack_actions


def _post_profile(*, atk_base: float = 1000.0, stats: dict | None = None) -> dict:
    return {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats_stage": "post_24804",
            "stats": dict(stats or {}),
            "attack": {"atkBase": atk_base, "atkFinal": 0},
            "passive_multiplier": 1.0,
        },
    }


def _mount_profile(*, uptime: float = 0.0) -> dict:
    return {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats_stage": "raw_profile",
            "stats": {"poisonedUptime": uptime},
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
                    "stats": {"poisoned": 100},
                },
            },
        },
        "inventory": {"items": {"electric_scooter_shard": 20}},
    }


def test_attack_comparison_uses_current_attack_bucket() -> None:
    low = compare_attack_options(prepare_sio_ce_profile(_post_profile(atk_base=1000)))
    high = compare_attack_options(prepare_sio_ce_profile(_post_profile(atk_base=100000)))
    assert low["better_option"] == "atkFinal"
    assert high["better_option"] == "atkPercent"
    assert low["percent_option"]["estimated_percent_gain"] == 10.0
    assert low["flat_option"]["estimated_percent_gain"] == 500.0


def test_poison_bonus_is_skipped_without_a_poison_source_uptime() -> None:
    result = optimize_source_pack_actions(_mount_profile(uptime=0.0), device="cpu")
    skipped = next(
        row for row in result["preflight_neutral_actions"]
        if row["action_id"] == "upgrade_electric_scooter_y1"
    )
    assert "poisoned_requires_poisonedUptime" in skipped["reason"]
    effect = next(
        row for row in skipped["preflight_estimate"]["changed_effects"]
        if row["field"] == "poisoned"
    )
    assert effect["active_for_this_build"] is False
    assert result["effect_preflight"]["estimated_runtime_states_saved"] >= 1


def test_poison_bonus_is_kept_when_poison_uptime_exists() -> None:
    profile = _post_profile(stats={"poisonedUptime": 1.0})
    after = deepcopy(profile)
    after["sio_ce"]["stats"]["poisoned"] = 25.0
    action = {
        "action_id": "items:poisoned-test",
        "system": "items",
        "action_type": "upgrade",
        "state_patch": {"sio_ce": {"stats": {"poisoned": 25.0}}},
        "source_modules": [24804, 67727],
        "metadata": {"exact_after_state": True},
    }
    result = evaluate_preflight_transitions(
        profile,
        [(action, after, {"legal": True, "balanced": True, "consumed": {}, "refunded": {}})],
    )
    assert len(result["transitions"]) == 1
    estimate = result["transitions"][0][0]["preflight_estimate"]
    assert estimate["estimated_damage_gain"] > 0
    assert result["skipped"] == []


def test_unknown_system_is_never_suppressed_even_when_estimate_is_zero() -> None:
    profile = _post_profile()
    action = {
        "action_id": "future:unknown-effect",
        "system": "future_system",
        "action_type": "unknown",
        "state_patch": {"future": {"mystery": 1}},
    }
    after = deepcopy(profile)
    after["future"] = {"mystery": 1}
    result = evaluate_preflight_transitions(
        profile,
        [(action, after, {"legal": True, "balanced": True, "consumed": {}, "refunded": {}})],
    )
    assert len(result["transitions"]) == 1
    assert result["skipped"] == []
    assert result["report"]["unknown_effect_policy"] == "keep_for_exact_runtime"


def test_tech_is_never_suppressed_by_python_preflight() -> None:
    profile = _post_profile()
    action = {
        "action_id": "tech:test",
        "system": "tech_parts",
        "action_type": "future_tech",
        "state_patch": {"sio_ce": {"techs": {"Drone": {"resonance": 1}}}},
    }
    after = deepcopy(profile)
    after["sio_ce"]["techs"] = {"Drone": {"resonance": 1}}
    result = evaluate_preflight_transitions(
        profile,
        [(action, after, {"legal": True, "balanced": True, "consumed": {}, "refunded": {}})],
    )
    assert len(result["transitions"]) == 1
    assert result["skipped"] == []


def test_registry_matches_the_locked_bible_hash_and_dependency_pairs() -> None:
    registry = load_effect_registry()
    assert registry["bundle_sha256"] == "7665a1d4ad479f799b9360347dad98ffdca8125d35c6fb0072c68343708c847d"
    pairs = {(row["effect"], row["uptime"]) for row in registry["conditional_effects"]}
    assert ("poisoned", "poisonedUptime") in pairs
    assert ("weakened", "weakenedUptime") in pairs
    assert ("chilled", "chilledUptime") in pairs
    assert ("laceration", "lacerationUptime") in pairs
    assert ("divineFire", "divineFireUptime") in pairs
