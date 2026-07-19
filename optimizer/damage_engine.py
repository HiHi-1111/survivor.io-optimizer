"""Clan Expedition damage entry points backed by the supplied sIO formula.

This module intentionally exposes the legacy public names, but all whole-profile
scoring is delegated to :mod:`optimizer.sio_ce_account`. Other combat modes are
not supported and no generic breakpoint or rarity score is substituted.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from optimizer.sio_ce_account import (
    UnsupportedGameModeError,
    calculate_clan_expedition_damage,
)

LEGACY_ALIASES = {
    "crit_rate": "critRate",
    "crit_damage": "critDamage",
    "skill_damage": "skillDamage",
    "vulnerability": "vulnerability",
    "shield_damage": "shieldDamage",
    "damage_to_chilled": "chilled",
    "damage_to_poisoned": "poisoned",
    "boss_damage": "damageBoss",
}


def _number(value: Any) -> float:
    try:
        result = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) else 0.0


def _legacy_percent(value: Any) -> float:
    result = _number(value)
    return result * 100.0 if -10.0 <= result <= 10.0 else result


def _legacy_sio_stats(build_stats: Mapping[str, Any]) -> dict[str, Any]:
    """Translate the old snake-case stat snapshot into sIO field names."""
    converted: dict[str, Any] = {}
    for source, target in LEGACY_ALIASES.items():
        if source not in build_stats:
            continue
        value = _legacy_percent(build_stats[source])
        if source == "crit_damage" and value == 0:
            continue
        converted[target] = value
    dealt = _legacy_percent(build_stats.get("all_damage")) + _legacy_percent(build_stats.get("final_damage"))
    if dealt:
        converted["damageDealt"] = dealt
    return converted


def _normalize_legacy_profile(profile: dict[str, Any]) -> dict[str, Any]:
    build_stats = profile.get("build_stats")
    if not isinstance(build_stats, Mapping):
        return profile
    sio = profile.get("sio_ce")
    if not isinstance(sio, dict):
        sio = {}
        profile["sio_ce"] = sio
    explicit = sio.get("stats") if isinstance(sio.get("stats"), Mapping) else {}
    sio["stats"] = {**_legacy_sio_stats(build_stats), **dict(explicit)}
    if not isinstance(sio.get("attack"), Mapping) or not sio.get("attack"):
        if _number(build_stats.get("atk")):
            sio["attack"] = {"atkBase": _number(build_stats.get("atk")), "atkFinal": 0.0}
    return profile


def estimate_damage_score(build_stats: Mapping[str, Any]) -> float:
    """Compatibility helper for callers that only have a stat dictionary.

    The values are interpreted as a Clan Expedition stat snapshot. This helper
    is not used to rank inventory actions; those require complete legal
    before/after states.
    """
    profile = {
        "game_mode": "clan_expedition",
        "build_stats": dict(build_stats),
        "sio_ce": {
            "stats_stage": "legacy_stat_snapshot",
            "attack": {
                "atkBase": _number(build_stats.get("atk")),
                "atkFinal": 0.0,
            },
            "passive_multiplier": 1.0,
        },
    }
    result = calculate_clan_expedition_damage(_normalize_legacy_profile(profile))
    return round(float(result.get("total_damage") or 0.0), 6)


def estimate_damage_totals(profile_input: Any) -> dict[str, Any]:
    """Calculate one exact-mode Clan Expedition damage report.

    A missing formula input returns ``supported=False`` and ``total_damage=None``.
    A non-CE mode raises :class:`UnsupportedGameModeError` so mode-specific data
    can never silently contaminate CE recommendations.
    """
    if hasattr(profile_input, "model_dump"):
        profile = profile_input.model_dump()
    elif hasattr(profile_input, "dict"):
        profile = profile_input.dict()
    elif isinstance(profile_input, Mapping):
        profile = dict(profile_input)
    else:
        profile = {}
    profile = _normalize_legacy_profile(profile)

    result = calculate_clan_expedition_damage(profile)
    if not result.get("supported"):
        blockers = list(result.get("required_fields", []))
        return {
            **result,
            "base_damage": None,
            "total_damage": None,
            "final_damage_multiplier": None,
            "multiplier_breakdown": {},
            "damage_math_type": "sio_clan_expedition_unscoreable",
            "blocker_analysis": {"real_blockers": blockers, "minor_blockers": [], "near_milestones": []},
            "true_blockers": blockers,
            "minor_blockers": [],
            "next_milestones": [],
        }

    base_attack = float(result["base_attack"])
    total_damage = float(result["total_damage"])
    final_multiplier = total_damage / base_attack if base_attack else None
    return {
        **result,
        "base_damage": base_attack,
        "final_damage_multiplier": final_multiplier,
        "damage_math_type": "sio_clan_expedition_exact_core",
        "blocker_analysis": {"real_blockers": [], "minor_blockers": [], "near_milestones": []},
        "true_blockers": [],
        "minor_blockers": [],
        "next_milestones": [],
        "ignored_inactive_or_future_damage_rows": [],
    }


__all__ = ["UnsupportedGameModeError", "estimate_damage_score", "estimate_damage_totals"]
