"""Full account-to-damage Clan Expedition pipeline built around sIO.

Raw account profiles are assembled by the original sIO runtime functions. Python
also assembles the same source-backed systems so the optimizer retains an
auditable fallback when Node or the source-locked bundle is unavailable. The
exact runtime then executes Tech, uptime conditions, direct damage, final stat
transforms and CE damage in the original order.
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
from optimizer.sio_collectibles import assemble_sio_collectible_stats
from optimizer.sio_item_pipeline import apply_sio_item_conditions, assemble_sio_item_base_stats
from optimizer.sio_items import item_state_from_profile
from optimizer.sio_mounts import aggregate_mount_stats
from optimizer.sio_pets import assemble_sio_pet_stats
from optimizer.sio_runtime_oracle import (
    SioRuntimeInputError,
    SioRuntimeUnavailable,
    default_oracle,
)
from optimizer.sio_survivors import assemble_sio_skill_evo_stats, assemble_sio_survivor_stats

POST_24804_STAGES = {
    "post_24804",
    "sio_post_24804",
    "post_24804_items",
    "post_24804_account_and_items",
}
RAW_ACCOUNT_STAGES = {
    "raw_profile",
    "sio_raw_profile",
    "raw_account",
    "account_profile",
}
RAW_ACCOUNT_SECTION_KEYS = {
    "heroes",
    "items",
    "collectibles",
    "customSets",
    "evoTree",
    "mounts",
    "skills",
    "pets",
    "petSkills",
    "techs",
}


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


def _plain_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping) and isinstance(value.get("data"), Mapping):
        value = value["data"]
    if isinstance(value, Mapping) and isinstance(value.get("owned"), Mapping):
        value = value["owned"]
    return deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def _first_mapping(*values: Any) -> dict[str, Any]:
    for value in values:
        result = _plain_mapping(value)
        if result:
            return result
    return {}


def _normalize_explicit_tech_input(sio: dict[str, Any]) -> None:
    """Flatten an oracle-native Tech payload without discarding extra fields."""
    explicit = sio.get("tech_input")
    if not isinstance(explicit, Mapping):
        return
    if isinstance(explicit.get("techs"), Mapping):
        sio["techs"] = deepcopy(dict(explicit["techs"]))
    for key in (
        "evolvePassives",
        "skills",
        "collectibles",
        "upgradedCollectibles",
        "eeSkills",
        "eeOmnipower",
    ):
        if key in explicit:
            sio[key] = deepcopy(explicit[key])
    explicit_settings = explicit.get("settings")
    if isinstance(explicit_settings, Mapping):
        existing = sio.get("settings") if isinstance(sio.get("settings"), Mapping) else {}
        sio["settings"] = {**dict(existing), **deepcopy(dict(explicit_settings))}
    sio.pop("tech_input", None)


def _runtime_account_input(
    profile: Mapping[str, Any],
    sio: Mapping[str, Any],
    *,
    stage: str,
    mounts: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Map the raw profile to the pure account functions used by sIO's UI.

    Automatic runtime assembly is limited to explicitly raw account stages. A
    pre-computed stat snapshot is never reinterpreted as raw ownership data.
    Callers may opt in or out with ``runtimeAccountAssembly`` and may provide a
    fully mapped ``runtime_account_input`` when importing sIO state directly.
    """
    explicit = sio.get("runtime_account_input")
    if isinstance(explicit, Mapping):
        return deepcopy(dict(explicit))
    enabled = sio.get("runtimeAccountAssembly", profile.get("runtimeAccountAssembly"))
    if enabled is False:
        return None
    has_raw_sections = any(key in sio or key in profile for key in RAW_ACCOUNT_SECTION_KEYS)
    if enabled is not True and not (stage in RAW_ACCOUNT_STAGES and has_raw_sections):
        return None

    meta = _first_mapping(sio.get("meta"), profile.get("meta"))
    heroes = _first_mapping(sio.get("heroes"), profile.get("heroes"))
    collectibles = _first_mapping(sio.get("collectibles"), profile.get("collectibles"))
    custom_sets = _first_mapping(
        sio.get("customSets"),
        sio.get("custom_sets"),
        profile.get("customSets"),
        profile.get("custom_sets"),
    )
    evo_tree = _first_mapping(
        sio.get("evoTree"),
        sio.get("evo_tree"),
        profile.get("evoTree"),
        profile.get("evo_tree"),
    )
    skills = _first_mapping(sio.get("skills"), profile.get("skills"))
    pets = _first_mapping(sio.get("pets"), profile.get("pets"))
    pet_skills = _first_mapping(
        sio.get("petSkills"),
        sio.get("pet_skills"),
        profile.get("petSkills"),
        profile.get("pet_skills"),
    )
    techs = _first_mapping(sio.get("techs"), profile.get("techs"))
    settings = _first_mapping(sio.get("settings"), profile.get("settings"))
    settings.setdefault("revives", [40, 70, 90])
    settings["calcMode"] = "damage"
    items = item_state_from_profile(profile)
    upgraded = (
        sio.get("upgradedCollectibles")
        or sio.get("upgraded_collectibles")
        or profile.get("upgradedCollectibles")
        or profile.get("upgraded_collectibles")
        or []
    )
    if not isinstance(upgraded, (list, tuple, set)):
        upgraded = []
    teamwork = sio.get("teamwork", meta.get("teamwork", profile.get("teamwork", [])))
    if not isinstance(teamwork, (list, tuple, set, Mapping)):
        teamwork = []
    stats_overrides = _first_mapping(
        sio.get("statsOverrides"),
        sio.get("stats_overrides"),
        profile.get("statsOverrides"),
        profile.get("stats_overrides"),
    )
    main_hero = str(
        sio.get("activeSurvivor")
        or sio.get("active_survivor")
        or meta.get("mainHero")
        or meta.get("main_hero")
        or "None"
    )
    return {
        "beta": bool(sio.get("beta", profile.get("beta", False))),
        "mainHero": main_hero,
        "synergy": bool(sio.get("synergy", meta.get("synergy", False))),
        "synergyLevel": int(_number(sio.get("synergyLevel", meta.get("synergyLevel", 0)))),
        "harmonyL": str(sio.get("harmonyL", meta.get("harmonyL", "None")) or "None"),
        "harmonyR": str(sio.get("harmonyR", meta.get("harmonyR", "None")) or "None"),
        "teamwork": deepcopy(teamwork),
        "clanLevel": int(_number(sio.get("clanLevel", meta.get("clanLevel", 0)))),
        "heroes": heroes,
        "items": items,
        "collectibles": collectibles,
        "upgradedCollectibles": list(upgraded),
        "maxGear": int(_number(sio.get("maxGear", meta.get("maxGear", profile.get("maxGear", 0))))),
        "customSets": custom_sets,
        "evoTree": evo_tree,
        "mounts": deepcopy(dict(mounts or {})),
        "skills": skills,
        "pets": pets,
        "petSkills": pet_skills,
        "techs": techs,
        "settings": settings,
        "evolvePassives": bool(sio.get("evolvePassives", profile.get("evolvePassives", False))),
        "turf": _first_mapping(sio.get("turf"), profile.get("turf")),
        "lmeTestaments": _first_mapping(sio.get("lmeTestaments"), profile.get("lmeTestaments")),
        "lmeStatsOverrides": _first_mapping(sio.get("lmeStatsOverrides"), profile.get("lmeStatsOverrides")),
        "eeSkills": deepcopy(sio.get("eeSkills", profile.get("eeSkills"))),
        "eeOmnipower": deepcopy(sio.get("eeOmnipower", profile.get("eeOmnipower"))),
        "statsOverrides": stats_overrides,
        "gameMode": "ce",
    }


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


def prepare_sio_ce_profile(
    profile: Mapping[str, Any],
    *,
    defer_runtime_conditions: bool = False,
) -> dict[str, Any]:
    """Assemble account stats without mutating the caller.

    Raw profile ownership is preserved under ``runtime_account_input`` before the
    Python fallback modifies or hides any section. The JavaScript runtime may use
    that input to execute the original sIO account functions directly.
    """
    prepared = deepcopy(dict(profile))
    sio = prepared.get("sio_ce")
    if not isinstance(sio, dict):
        sio = {}
        prepared["sio_ce"] = sio
    _normalize_explicit_tech_input(sio)
    stage = str(sio.get("stats_stage", prepared.get("stats_stage", "unknown")))
    if stage in POST_24804_STAGES:
        prepared["_sio_account_detail"] = {}
        prepared["_sio_pipeline_warnings"] = []
        sio["skipRuntime24804"] = True
        return prepared

    mounts = sio.get("mounts") if isinstance(sio.get("mounts"), Mapping) else prepared.get("mounts")
    exact_account_input = _runtime_account_input(
        prepared,
        sio,
        stage=stage,
        mounts=mounts if isinstance(mounts, Mapping) else None,
    )
    if exact_account_input is not None:
        sio["runtime_account_input"] = exact_account_input
        sio["runtimeAccountAssembly"] = True

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

    mount_result = aggregate_mount_stats(mounts if isinstance(mounts, Mapping) else None)
    _add(stats, mount_result.get("stats"))

    if defer_runtime_conditions:
        final_item_detail = item_result.get("detail", {})
        stats_stage = "pre_24804_runtime"
        sio["skipRuntime24804"] = False
    else:
        conditioned = apply_sio_item_conditions(prepared, stats, item_result.get("detail", {}))
        stats = dict(conditioned["stats"])
        final_item_detail = conditioned["detail"]
        stats_stage = "post_24804"
        sio["skipRuntime24804"] = True

    warnings = list(item_result.get("warnings", []))
    warnings.extend(pet_result.get("warnings", []))
    warnings.extend(mount_result.get("warnings", []))
    sio["stats"] = stats
    sio["stats_stage"] = stats_stage
    # Mount effects are already inside the Python fallback stat map. The exact
    # runtime retains the untouched raw mount state inside runtime_account_input.
    sio.pop("mounts", None)
    prepared["mounts"] = {}
    prepared["sio_ce"] = sio
    prepared["_sio_account_detail"] = {
        "survivors": survivor_result.get("detail", {}),
        "collectibles": collectible_result.get("detail", {}),
        "skills_and_evo": skill_result.get("detail", {}),
        "pets": pet_result.get("detail", {}),
        "mounts": mount_result.get("detail", {}),
        "items": final_item_detail,
        "runtime_account_assembly_requested": exact_account_input is not None,
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
        "pre_finalize_stats": exact.get("pre_finalize_stats", {}),
        "uptime_values": exact.get("uptime_values", {}),
        "tech_stats": exact.get("tech_stats", {}),
        "passive_pools": exact.get("passive_pools", []),
        "formula_provenance": exact.get("formula_provenance", {}),
        "formula_order": exact.get("formula_order", []),
        "account_assembly_exact": bool(exact.get("account_assembly_exact")),
        "account_assembly_modules": exact.get("account_assembly_modules", []),
        "account_context": exact.get("account_context", {}),
        "runtime_exact": True,
    }


def _decorate_report(
    original: Mapping[str, Any],
    prepared: Mapping[str, Any],
    result: dict[str, Any],
    *,
    formula_pipeline: str,
    runtime_error: str | None = None,
) -> dict[str, Any]:
    warnings = list(prepared.get("_sio_pipeline_warnings", []))
    if runtime_error:
        warnings.append(f"Exact sIO runtime oracle unavailable: {runtime_error}")
        result["runtime_exact"] = False
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


def _fallback_reports(
    originals: list[dict[str, Any]],
    message: str,
) -> list[dict[str, Any]]:
    fallback_profiles = [prepare_sio_ce_profile(profile, defer_runtime_conditions=False) for profile in originals]
    return [
        _decorate_report(
            original,
            ready,
            calculate_ce_core(ready),
            formula_pipeline="python_fallback_24804_67727_88426",
            runtime_error=message,
        )
        for original, ready in zip(originals, fallback_profiles)
    ]


def calculate_clan_expedition_damage_batch(
    profiles: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    originals = [deepcopy(dict(profile)) for profile in profiles]
    prepared = [prepare_sio_ce_profile(profile, defer_runtime_conditions=True) for profile in originals]
    try:
        exact_rows = default_oracle().score_profiles(prepared)
    except (SioRuntimeUnavailable, SioRuntimeInputError, OSError, ValueError) as error:
        return _fallback_reports(originals, str(error))

    reports: list[dict[str, Any]] = []
    for original, ready, exact in zip(originals, prepared, exact_rows):
        try:
            report = _report_from_exact(ready, exact)
            formula_pipeline = (
                "sio_runtime_account_then_13024_24804_88426_67727"
                if report.get("account_assembly_exact")
                else "sio_account_then_runtime_13024_24804_88426_67727"
            )
            reports.append(
                _decorate_report(
                    original,
                    ready,
                    report,
                    formula_pipeline=formula_pipeline,
                )
            )
        except (SioRuntimeUnavailable, SioRuntimeInputError, OSError, ValueError) as error:
            reports.extend(_fallback_reports([original], str(error)))
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
