"""Exact sIO mount aggregation for Clan Expedition.

Ports modules 51642, 40514, 37013 and the mount coefficients in 32085.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from optimizer.sio_ce_constants import (
    MOUNT_COMPONENT_STATS,
    MOUNT_DEFINITIONS,
    MOUNT_MAX_COMPLETED_LINES,
    MOUNT_SYNC_RATES,
    SIO_DIRECT_DAMAGE_COEFFICIENTS,
)


def _number(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _add(target: dict[str, float], source: Mapping[str, Any], scale: float = 1.0) -> None:
    for key, value in source.items():
        amount = _number(value) * scale
        if amount:
            target[str(key)] = target.get(str(key), 0.0) + amount


def _line_effects(name: str, completed_lines: int) -> dict[str, float]:
    result: dict[str, float] = {}
    for threshold in sorted(MOUNT_DEFINITIONS[name]["lines"]):
        if threshold > completed_lines:
            break
        _add(result, MOUNT_DEFINITIONS[name]["lines"][threshold])
    return result


def aggregate_mount_stats(mounts: Mapping[str, Any] | None) -> dict[str, Any]:
    """Apply active mount, undeployed sync, line effects and mount damage.

    The supplied sIO module does not treat sync-rate increase itself as damage.
    It scales the undeployed mount's component-board stats. Only the active mount
    gets line effects and direct mount damage.
    """
    if not isinstance(mounts, Mapping):
        return {"stats": {}, "detail": {}, "warnings": []}

    active = mounts.get("active")
    data = mounts.get("data") if isinstance(mounts.get("data"), Mapping) else mounts
    totals: dict[str, float] = {}
    details: dict[str, Any] = {}
    warnings: list[str] = []

    for name, definition in MOUNT_DEFINITIONS.items():
        state = data.get(name, {}) if isinstance(data, Mapping) else {}
        if not isinstance(state, Mapping) or not bool(state.get("enabled", False)):
            continue

        stars = max(0, min(8, int(_number(state.get("stars")))))
        deployed = active == name
        sync = 1.0 if deployed else MOUNT_SYNC_RATES[definition["rarity"]][stars]
        board = state.get("stats") if isinstance(state.get("stats"), Mapping) else {}
        applied: dict[str, float] = {}
        ignored: list[str] = []
        for stat, value in board.items():
            if stat not in MOUNT_COMPONENT_STATS:
                if _number(value):
                    ignored.append(str(stat))
                continue
            amount = _number(value) * sync
            if amount:
                totals[stat] = totals.get(stat, 0.0) + amount
                applied[stat] = amount

        entered_lines = max(0, int(_number(state.get("lines"))))
        applied_lines = 0
        line_stats: dict[str, float] = {}
        mount_damage = 0.0
        if deployed:
            applied_lines = min(entered_lines, MOUNT_MAX_COMPLETED_LINES[stars])
            line_stats = _line_effects(name, applied_lines)
            _add(totals, line_stats)
            mount_damage = definition["damage"][stars] * SIO_DIRECT_DAMAGE_COEFFICIENTS[name]
            totals["mountDamage"] = mount_damage

        if ignored:
            warnings.append(
                f"{name}: fields not consumed by supplied sIO module 51642: "
                + ", ".join(sorted(ignored))
            )
        details[name] = {
            "active": deployed,
            "stars": stars,
            "rarity": definition["rarity"],
            "sync_rate": sync,
            "completed_lines_entered": entered_lines,
            "completed_lines_applied": applied_lines,
            "component_stats_applied": applied,
            "line_effects_applied": line_stats,
            "mount_damage": mount_damage,
        }
    return {"stats": totals, "detail": details, "warnings": warnings}
