"""Bridge verified mount-puzzle results into exact mount component stats.

The CE runtime consumes aggregate component stats from ``mounts.data.*.stats``.
It does not need placement coordinates, rotations, board masks, search paths, or
Tetris solver internals. This bridge therefore copies only verified aggregate
stats and leaves the raw puzzle record untouched for audit/review.

A profile must mark a puzzle result ``verified`` or ``source_exact``. Unknown stat
keys, non-finite values, and conflicting pre-existing mount stats are rejected so
puzzle data cannot be guessed or double-counted.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Mapping

from optimizer.sio_ce_constants import MOUNT_COMPONENT_STATS
from optimizer.sio_mounts import MOUNT_ALIASES

PUZZLE_LAYOUT_KEYS = frozenset(
    {
        "placements",
        "board",
        "board_mask",
        "path",
        "states_explored",
        "search_model",
        "worker_parity",
        "rotation",
        "row",
        "col",
    }
)


def _number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"mount puzzle stat is not numeric: {value!r}") from error
    if not math.isfinite(number):
        raise ValueError(f"mount puzzle stat is not finite: {value!r}")
    return number


def _puzzle_section(profile: Mapping[str, Any]) -> Any:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    return (
        sio.get("mount_puzzles")
        or sio.get("mountPuzzles")
        or profile.get("mount_puzzles")
        or profile.get("mountPuzzles")
        or {}
    )


def _mounts(profile: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = profile.get("mounts")
    if not isinstance(raw, dict):
        raw = {}
        profile["mounts"] = raw
    data = raw.get("data")
    if not isinstance(data, dict):
        data = {str(key): deepcopy(value) for key, value in raw.items() if key != "active"}
        raw["data"] = data
    return raw, data


def _canonical_stats(raw: Any) -> dict[str, float]:
    if not isinstance(raw, Mapping):
        raise ValueError("verified mount puzzle result is missing component_stats")
    result: dict[str, float] = {}
    for key, value in raw.items():
        stat = str(key)
        number = _number(value)
        if stat not in MOUNT_COMPONENT_STATS:
            if abs(number) > 1e-12:
                raise ValueError(f"unknown mount component stat: {stat}")
            continue
        if abs(number) > 1e-12:
            result[stat] = number
    return dict(sorted(result.items()))


def apply_verified_mount_puzzle_stats(profile_input: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a normalized copy and an audit report.

    Raw puzzle geometry remains where it was supplied; only aggregate stats are
    copied into the exact mount state.
    """
    profile = deepcopy(dict(profile_input))
    raw = _puzzle_section(profile)
    if not isinstance(raw, Mapping):
        return profile, {"applied": {}, "ignored_unverified": [], "layout_used_for_scoring": False}
    mounts, data = _mounts(profile)
    applied: dict[str, dict[str, float]] = {}
    ignored: list[str] = []
    for raw_name, raw_result in raw.items():
        if not isinstance(raw_result, Mapping):
            continue
        name = MOUNT_ALIASES.get(str(raw_name), str(raw_name))
        if not bool(raw_result.get("verified") or raw_result.get("source_exact")):
            ignored.append(name)
            continue
        stats = _canonical_stats(raw_result.get("component_stats", raw_result.get("stats")))
        state = data.get(name)
        if not isinstance(state, dict):
            raise ValueError(f"verified puzzle result references unknown or unowned mount: {name}")
        existing_raw = state.get("stats")
        existing = _canonical_stats(existing_raw) if isinstance(existing_raw, Mapping) else {}
        if existing and existing != stats:
            raise ValueError(f"conflicting mount component stats for {name}")
        state = deepcopy(state)
        state["stats"] = stats
        data[name] = state
        applied[name] = stats
    mounts["data"] = data
    profile["mounts"] = mounts
    return profile, {
        "applied": applied,
        "ignored_unverified": sorted(ignored),
        "layout_used_for_scoring": False,
        "copied_fields": ["component_stats"],
        "excluded_layout_fields": sorted(PUZZLE_LAYOUT_KEYS),
    }


__all__ = [
    "PUZZLE_LAYOUT_KEYS",
    "apply_verified_mount_puzzle_stats",
]
