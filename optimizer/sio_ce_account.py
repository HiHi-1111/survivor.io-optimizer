"""Full account-to-damage Clan Expedition pipeline built around sIO.

Python assembles account systems in the same order as sIO. When the supplied
runtime bundle is available, modules 13024, 88426 and 67727 are the final
teacher/oracle, including Twinborn, Overload and evolved-passive timing.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping

from optimizer.sio_ce_constants import SIO_BASE_STATS
from optimizer.sio_ce_damage import (
    UnsupportedGameModeError,
    calculate_clan_expedition_damage as calculate_ce_core,
    percent_bonus,
)
from optimizer.sio_collectibles import assemble_sio_collectible_stats, collectible_state
from optimizer.sio_item_pipeline import apply_sio_item_conditions, assemble_sio_item_base_stats
from optimizer.sio_items import item_state_from_profile
from optimizer.sio_mounts import aggregate_mount_stats
from optimizer.sio_pets import assemble_sio_pet_stats, pet_state
from optimizer.sio_runtime_oracle import (
    SioRuntimeInputError,
    SioRuntimeUnavailable,
    default_oracle,
)
from optimizer.sio_survivors import (
    assemble_sio_skill_evo_stats,
    assemble_sio_survivor_stats,
    hero_state_from_profile,
)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _add(target: dict[str, Any], source: Mapping[str, Any] | None) -> None:
    for key, value in (source or {}).items():
        amount = _number(value)
        if amount:
            target[str(key)] = _number(target.get(str(key))) + amount


def _sio(profile: Mapping[str, Any]) -> Mapping[str, Any]:
    return profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}


def _has_mount_state(profile: Mapping[str, Any]) -> bool:
    sio = _sio(profile)
    mounts = sio.get("mounts") if isinstance(sio.get("mounts"), Mapping) else profile.get("mounts")
    if not isinstance(mounts, Mapping):
        return False
    if mounts.get("active"):
        return True
    data = mounts.get("data") if isinstance(mounts.get("data"), Mapping) else mounts
    return any(
        isinstance(value, Mapping) and bool(value.get("enabled"))
        for key, value in data.items()
        if key != "active"
    )


def _has_tech_state(profile: Mapping[str, Any]) -> bool:
    sio = _sio(profile)
    return bool(sio.get("tech_input") or sio.get("techs") or profile.get("techs") or profile.get("tech"))


def _explicit_stats(profile: Mapping[str, Any]) -> dict[str, Any]:
    sio = _sio(profile)
    stats: dict[str, Any] = deepcopy(SIO_BASE_STATS)
    for row in (profile.get("build_stats"), profile.get("stats"), sio.get("stats")):
        if isinstance(row, Mapping):
            stats.update(row)
    return stats


def _base_attack(stats: Mapping[str, Any], attack: Mapping[str, Any]) -> float:
    return (
        _number(attack.get("atkBase"))
        + _number(stats.get("atkEquip")) * percent_bonus(stats.get("atkEquipPercent"))
        + _number(stats.get("atkHero")) * percent_bonus(stats.get("atkHeroPercent"))
    ) * percent_bonus(stats.get("atkPercent")) + _number(attack.get("atkFinal")) + _number(stats.get("atkFinal"))


def prepare_sio_ce_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Build a post-24804 account profile without changing the caller's object."""
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
    sio["stats"] = stats
    sio["stats_stage"] = "post_24804"
    # Mount effects are already inside stats. Hide raw mounts from the core
    # calculator so they cannot be applied twice.
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


def _report_from_exact(prepared: Mapping[str, Any], exact: Mapping[str, Any]) -> dict[str, Any]:
    if not exact.get("supported"):
        raise SioRuntimeUnavailable(str(exact.get("error") or "sIO runtime returned unsupported"))
    sio = _sio(prepared)
    attack: dict[str, Any] = {}
    for row in (prepared.get("attack"), sio.get("attack")):
        if isinstance(row, Mapping):
            attack.update(row)
    stats = dict(exact.get("stats") or {})
    # Use the Python port only for human-readable multiplier buckets. The total
    # below always comes from runtime module 67727.
    breakdown_profile = deepcopy(dict(prepared))
    breakdown_sio = dict(_sio(breakdown_profile))
    breakdown_sio["stats"] = stats
    breakdown_sio["stats_stage"] = "post_24804"
    breakdown_sio["direct_skill_factors"] = {}
    breakdown_sio["evolvePassives"] = False
    breakdown_profile["sio_ce"] = breakdown_sio
    breakdown = calculate_ce_core(breakdown_profile)
    base_attack = _base_attack(stats, attack)
    stat_multiplier = _number(breakdown.get("stat_multiplier"), 1.0)
    direct_factor = _number(exact.get("damage_factor"), 0.0)
    denominator = base_attack * stat_multiplier * (direct_factor or 1.0)
    passive_adjustment = _number(exact.get("total_damage")) / denominator if denominator else 1.0
    return {
        "supported": True,
        "game_mode": "clan_expedition",
        "calc_mode": "damage",
        "total_damage": _number(exact.get("total_damage")),
        "sio_damage_value": _number(exact.get("total_damage")),
        "base_attack": base_attack,
        "stat_multiplier": stat_multiplier,
        "direct_damage_factor": direct_factor,
        "direct_damage_multiplier_applied": direct_factor or 1.0,
        "passive_multiplier": passive_adjustment,
        "multiplier_breakdown": breakdown.get("multiplier_breakdown", {}),
        "ce_damage_components": exact.get("ce_damage", {}),
        "normalized_stats": stats,
        "tech_stats": exact.get("tech_stats", {}),
        "passive_pools": exact.get("passive_pools", []),
        "formula_provenance": exact.get("formula_provenance", {}),
        "runtime_exact": True,
    }


def _decorate_report(
    original: Mapping[str, Any], prepared: Mapping[str, Any], result: dict[str, Any],
    *, formula_pipeline: str, runtime_error: str | None = None,
) -> dict[str, Any]:
    warnings = list(prepared.get("_sio_pipeline_warnings", []))
    if runtime_error:
        warnings.append(f"Exact sIO runtime oracle unavailable: {runtime_error}")
    if runtime_error and _has_tech_state(original):
        result = {
            **result,
            "supported": False,
            "reason": "exact_sio_runtime_required_for_tech_twinborn_overload",
            "required_fields": ["valid sIO bundle", "Node.js", "exact sIO tech schema", "evolvePassives"],
        }
    result["warnings"] = sorted(set(list(result.get("warnings", [])) + warnings))
    detail = prepared.get("_sio_account_detail", {})
    result["account_detail"] = detail
    if detail:
        result["item_detail"] = detail.get("items", {})
        result["mount_detail"] = detail.get("mounts", {})
    result["formula_pipeline"] = formula_pipeline
    if runtime_error:
        result["runtime_oracle_error"] = runtime_error
    return result


def calculate_clan_expedition_damage_batch(
    profiles: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    originals = [dict(profile) for profile in profiles]
    prepared = [prepare_sio_ce_profile(profile) for profile in originals]
    try:
        exact_rows = default_oracle().score_profiles(prepared)
    except (SioRuntimeUnavailable, SioRuntimeInputError, OSError, ValueError) as error:
        message = str(error)
        return [
            _decorate_report(
                original,
                ready,
                calculate_ce_core(ready),
                formula_pipeline="partial_python_sio_account_assembly_then_24804_67727_88426",
                runtime_error=message,
            )
            for original, ready in zip(originals, prepared)
        ]

    reports: list[dict[str, Any]] = []
    for original, ready, exact in zip(originals, prepared, exact_rows):
        try:
            report = _report_from_exact(ready, exact)
            reports.append(_decorate_report(
                original,
                ready,
                report,
                formula_pipeline="sio_account_assembly_then_24804_then_runtime_13024_88426_67727",
            ))
        except (SioRuntimeUnavailable, SioRuntimeInputError, OSError, ValueError) as error:
            reports.append(_decorate_report(
                original,
                ready,
                calculate_ce_core(ready),
                formula_pipeline="partial_python_sio_account_assembly_then_24804_67727_88426",
                runtime_error=str(error),
            ))
    return reports


def calculate_clan_expedition_damage(profile: Mapping[str, Any]) -> dict[str, Any]:
    return calculate_clan_expedition_damage_batch([profile])[0]


def compare_clan_expedition_profiles(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    before_result, after_result = calculate_clan_expedition_damage_batch([before, after])
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
    "calculate_clan_expedition_damage_batch",
    "compare_clan_expedition_profiles",
    "prepare_sio_ce_profile",
]
