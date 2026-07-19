"""Full account-to-damage Clan Expedition pipeline built around sIO.

This orchestrates the exact source modules in their sIO order, then delegates
only the final CE arithmetic to :mod:`optimizer.sio_ce_damage`.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from optimizer.sio_ce_constants import SIO_BASE_STATS
from optimizer.sio_ce_damage import (
    UnsupportedGameModeError,
    calculate_clan_expedition_damage as calculate_ce_core,
)
from optimizer.sio_collectibles import assemble_sio_collectible_stats, collectible_state
from optimizer.sio_item_pipeline import apply_sio_item_conditions, assemble_sio_item_base_stats
from optimizer.sio_items import item_state_from_profile
from optimizer.sio_mounts import aggregate_mount_stats
from optimizer.sio_pets import assemble_sio_pet_stats, pet_state
from optimizer.sio_survivors import (
    assemble_sio_skill_evo_stats,
    assemble_sio_survivor_stats,
    hero_state_from_profile,
)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result


def _add(target: dict[str, Any], source: Mapping[str, Any] | None) -> None:
    for key, value in (source or {}).items():
        amount = _number(value)
        if amount:
            target[str(key)] = _number(target.get(str(key))) + amount


def _sio(profile: Mapping[str, Any]) -> Mapping[str, Any]:
    return profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}


def _raw_systems_present(profile: Mapping[str, Any]) -> bool:
    sio = _sio(profile)
    return bool(
        item_state_from_profile(profile)
        or hero_state_from_profile(profile)
        or collectible_state(profile)
        or (pet_state(profile).get("active") or pet_state(profile).get("main_pet"))
        or profile.get("skills")
        or profile.get("evoTree")
        or sio.get("skills")
        or sio.get("evoTree")
        or profile.get("mounts")
        or sio.get("mounts")
    )


def _explicit_stats(profile: Mapping[str, Any]) -> dict[str, Any]:
    sio = _sio(profile)
    stats: dict[str, Any] = deepcopy(SIO_BASE_STATS)
    for row in (profile.get("build_stats"), profile.get("stats"), sio.get("stats")):
        if isinstance(row, Mapping):
            stats.update(row)
    return stats


def prepare_sio_ce_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Build a post-24804 profile without changing the caller's object."""
    prepared = deepcopy(dict(profile))
    sio = prepared.get("sio_ce")
    if not isinstance(sio, dict):
        sio = {}
        prepared["sio_ce"] = sio
    stage = str(sio.get("stats_stage", prepared.get("stats_stage", "unknown")))
    if stage in {"post_24804", "sio_post_24804", "post_24804_account_and_items"}:
        prepared["_sio_account_detail"] = {}
        prepared["_sio_pipeline_warnings"] = []
        return prepared

    stats = _explicit_stats(prepared)
    survivor_result = assemble_sio_survivor_stats(prepared)
    collectible_result = assemble_sio_collectible_stats(prepared)
    skill_result = assemble_sio_skill_evo_stats(prepared)
    pet_result = assemble_sio_pet_stats(prepared)
    _add(stats, survivor_result.get("stats"))
    _add(stats, collectible_result.get("stats"))

    item_result: dict[str, Any] = {"detail": {}, "warnings": []}
    if item_state_from_profile(prepared):
        item_result = assemble_sio_item_base_stats(prepared, stats)
        stats = dict(item_result["stats"])

    _add(stats, skill_result.get("stats"))
    _add(stats, pet_result.get("stats"))

    mounts = sio.get("mounts") if isinstance(sio.get("mounts"), Mapping) else prepared.get("mounts")
    mount_result = aggregate_mount_stats(mounts if isinstance(mounts, Mapping) else None)
    _add(stats, mount_result.get("stats"))

    if item_state_from_profile(prepared):
        conditioned = apply_sio_item_conditions(prepared, stats, item_result.get("detail", {}))
        stats = dict(conditioned["stats"])
        item_result["detail"] = conditioned["detail"]

    warnings = list(item_result.get("warnings", []))
    warnings.extend(pet_result.get("warnings", []))
    warnings.extend(mount_result.get("warnings", []))
    if _raw_systems_present(prepared):
        warnings.append(
            "Tech/Twinborn/Overload and the evolved-passive timing loop are not yet assembled; those fields remain unknown."
        )

    sio["stats"] = stats
    sio["stats_stage"] = "post_24804_account_and_items"
    # Mount stats and direct mount damage are already in ``stats``. Remove raw
    # mounts from the core payload to prevent a second aggregation.
    sio.pop("mounts", None)
    prepared["mounts"] = {}
    prepared["sio_ce"] = sio
    prepared["_sio_account_detail"] = {
        "survivors": survivor_result.get("detail", {}),
        "collectibles": collectible_result.get("detail", {}),
        "skills_and_evo": skill_result.get("detail", {}),
        "pets": pet_result.get("detail", {}),
        "mounts": mount_result.get("detail", {}),
        "items": item_result.get("detail", {}),
    }
    prepared["_sio_pipeline_warnings"] = sorted(set(warnings))
    return prepared


def calculate_clan_expedition_damage(profile: Mapping[str, Any]) -> dict[str, Any]:
    prepared = prepare_sio_ce_profile(profile)
    result = calculate_ce_core(prepared)
    pipeline_warnings = list(prepared.get("_sio_pipeline_warnings", []))
    result["warnings"] = sorted(set(list(result.get("warnings", [])) + pipeline_warnings))
    detail = prepared.get("_sio_account_detail", {})
    result["account_detail"] = detail
    if detail:
        result["item_detail"] = detail.get("items", {})
        result["mount_detail"] = detail.get("mounts", {})
    result["formula_pipeline"] = "sio_account_assembly_then_24804_then_67727_88426"
    return result


def compare_clan_expedition_profiles(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    before_result = calculate_clan_expedition_damage(before)
    after_result = calculate_clan_expedition_damage(after)
    if not before_result.get("supported") or not after_result.get("supported"):
        return {
            "supported": False,
            "before": before_result,
            "after": after_result,
            "reason": "before_or_after_state_not_scoreable",
        }
    old = float(before_result["total_damage"])
    new = float(after_result["total_damage"])
    delta = new - old
    return {
        "supported": True,
        "before": before_result,
        "after": after_result,
        "delta": delta,
        "percent_gain": delta / old * 100.0 if old else None,
        "improves_damage": delta > 0,
    }


__all__ = [
    "UnsupportedGameModeError",
    "calculate_clan_expedition_damage",
    "compare_clan_expedition_profiles",
    "prepare_sio_ce_profile",
]
