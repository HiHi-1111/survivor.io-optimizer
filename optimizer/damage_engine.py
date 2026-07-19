"""Clan Expedition damage entry points backed by the supplied sIO formula.

This module intentionally exposes the legacy public names, but all whole-profile
scoring is delegated to :mod:`optimizer.sio_ce_damage`. Other combat modes are
not supported and no generic breakpoint or rarity score is substituted.
"""

from __future__ import annotations

from typing import Any, Mapping

from optimizer.sio_ce_damage import (
    UnsupportedGameModeError,
    calculate_clan_expedition_damage,
)


def estimate_damage_score(build_stats: Mapping[str, Any]) -> float:
    """Compatibility helper for tests/callers that only have a stat dictionary.

    The values are interpreted as a Clan Expedition stat snapshot. Ratio-style
    legacy fields are normalized by ``sio_ce_damage``. This function is not used
    to rank legal inventory actions; those require complete before/after states.
    """
    profile = {
        "game_mode": "clan_expedition",
        "build_stats": dict(build_stats),
        "sio_ce": {
            "stats_stage": "legacy_stat_snapshot",
            "attack": {
                "atkBase": float(build_stats.get("atk", 0) or 0),
                "atkFinal": 0.0,
            },
            "passive_multiplier": 1.0,
        },
    }
    result = calculate_clan_expedition_damage(profile)
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

    result = calculate_clan_expedition_damage(profile)
    if not result.get("supported"):
        return {
            **result,
            "base_damage": None,
            "total_damage": None,
            "final_damage_multiplier": None,
            "multiplier_breakdown": {},
            "damage_math_type": "sio_clan_expedition_unscoreable",
            "blocker_analysis": {
                "real_blockers": list(result.get("required_fields", [])),
                "minor_blockers": [],
                "near_milestones": [],
            },
            "true_blockers": list(result.get("required_fields", [])),
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
        "blocker_analysis": {
            "real_blockers": [],
            "minor_blockers": [],
            "near_milestones": [],
        },
        "true_blockers": [],
        "minor_blockers": [],
        "next_milestones": [],
        "ignored_inactive_or_future_damage_rows": [],
    }


__all__ = [
    "UnsupportedGameModeError",
    "estimate_damage_score",
    "estimate_damage_totals",
]
