"""Clan Expedition damage entry points backed by the supplied sIO formula.

Whole-profile optimization uses the exact sIO account/runtime pipeline. A small
legacy snapshot reader remains for old imported profiles that already contain
explicit ``damage_multiplier`` values but no reconstructable sIO attack split.
That reader multiplies only the values supplied by the profile, ignores survival
stats, is marked non-runtime-exact, and is excluded from exact training.
"""

from __future__ import annotations

from copy import deepcopy
import math
import re
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
LEGACY_SYSTEMS = ("gear", "survivor", "tech", "pet", "collectibles")
_NUMERIC_TEXT = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)\s*(x|%)?\s*$", re.IGNORECASE)


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, str):
        text = value.replace(",", "").strip()
        match = _NUMERIC_TEXT.match(text)
        if not match:
            return default
        number = float(match.group(1))
        suffix = (match.group(2) or "").lower()
        if suffix == "%":
            number = 1.0 + number / 100.0 if text.startswith("+") else number / 100.0
        value = number
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _plain(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(child) for child in value]
    if hasattr(value, "model_dump"):
        return _plain(value.model_dump())
    if hasattr(value, "dict"):
        return _plain(value.dict())
    if hasattr(value, "__dict__"):
        return _plain(vars(value))
    return str(value)


def _legacy_percent(value: Any) -> float:
    result = _number(value)
    return result * 100.0 if -10.0 <= result <= 10.0 else result


def _legacy_sio_stats(build_stats: Mapping[str, Any]) -> dict[str, Any]:
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


def _flag(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "yes", "1", "active", "equipped", "selected", "slotted", "owned", "unlocked"}:
            return True
        if text in {"false", "no", "0", "inactive", "unequipped", "unselected", "unslotted", "locked", "preview"}:
            return False
    return None


def _inactive_reason(row: Mapping[str, Any], path: tuple[str, ...]) -> str | None:
    text = " ".join(
        str(row.get(key, "")).lower()
        for key in ("record_type", "source", "note_type", "type", "status", "state", "name", "label")
    )
    if any(term in text for term in ("catalog", "source_pack", "reference", "recommendation_candidate", "community_comment", "screenshot_text")):
        return "source/catalog/reference row"
    if any(term in text for term in ("preview", "future", "candidate", "locked")):
        return "future/preview/candidate row"
    for key in ("locked", "preview", "future", "candidate", "missing_resource", "missing_resources"):
        if _flag(row.get(key)) is True:
            return key
    if row.get("missing") or row.get("missing_shards"):
        return "missing-resource"
    for key in ("equipped", "selected", "active", "slotted", "unlocked", "owned", "bought", "purchased"):
        if key in row and _flag(row.get(key)) is False:
            return f"inactive:{key}"
    lowered = ".".join(path).lower()
    if any(term in lowered for term in ("owned_not_equipped", "inactive_mode", "candidate_resonance_assists", "next_breakpoint", "event_shop_options", "source_database_catalog_rows", "discord_notes", "ocr_text")):
        return "inactive path"
    return None


def _contains_explicit_multiplier(value: Any) -> bool:
    value = _plain(value)
    if isinstance(value, Mapping):
        if "damage_multiplier" in value:
            return True
        return any(_contains_explicit_multiplier(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_explicit_multiplier(child) for child in value)
    return False


def _product_explicit_multipliers(
    value: Any,
    path: tuple[str, ...] = (),
    ignored: list[str] | None = None,
) -> float:
    value = _plain(value)
    if isinstance(value, Mapping):
        reason = _inactive_reason(value, path)
        if reason:
            if ignored is not None and "damage_multiplier" in value:
                ignored.append(f"{'.'.join(path) or '<root>'}: {reason}")
            return 1.0
        product = 1.0
        for key, child in value.items():
            if str(key).lower() == "damage_multiplier":
                multiplier = _number(child, 1.0)
                product *= multiplier if multiplier > 0 else 1.0
            else:
                product *= _product_explicit_multipliers(child, path + (str(key),), ignored)
        return product
    if isinstance(value, list):
        product = 1.0
        for index, child in enumerate(value):
            product *= _product_explicit_multipliers(child, path + (str(index),), ignored)
        return product
    return 1.0


def _legacy_base_damage(profile: Mapping[str, Any]) -> float:
    for key in ("base_damage", "base_atk", "atk", "attack"):
        value = profile.get(key)
        if isinstance(value, (int, float, str)) and _number(value) > 0:
            return _number(value)
    for section_name in ("build_stats", "stats"):
        section = profile.get(section_name)
        if isinstance(section, Mapping):
            for key in ("base_damage", "base_atk", "atk", "attack"):
                if _number(section.get(key)) > 0:
                    return _number(section.get(key))
    return 1.0


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _inventory_values(profile: Mapping[str, Any]) -> dict[str, float]:
    values: dict[str, float] = {}
    for section_name in ("inventory", "resources"):
        section = profile.get(section_name)
        if not isinstance(section, Mapping):
            continue
        for key, raw in section.items():
            amount = raw
            if isinstance(raw, Mapping):
                amount = raw.get("count", raw.get("quantity", raw.get("amount", 0)))
            if isinstance(amount, (int, float)):
                values[_normalized_key(str(key))] = float(amount)
    return values


def _lookup_inventory(values: Mapping[str, float], *aliases: str) -> float:
    normalized = [_normalized_key(alias) for alias in aliases]
    for key, value in values.items():
        if key in normalized:
            return float(value)
    for key, value in values.items():
        if any(alias in key or key in alias for alias in normalized if alias):
            return float(value)
    return 0.0


def _near_milestones(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    milestones: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            milestone = value.get("near_milestone")
            if isinstance(milestone, Mapping):
                milestones.append(dict(milestone))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(profile)
    unique: dict[str, dict[str, Any]] = {}
    for row in milestones:
        unique[repr(sorted(row.items(), key=lambda item: str(item[0])))] = row
    return list(unique.values())


def _blocker_report(profile: Mapping[str, Any]) -> dict[str, Any]:
    inventory = _inventory_values(profile)
    real: list[str] = []
    minor: list[str] = []

    relic_have = _lookup_inventory(inventory, "relic core", "relic cores")
    relic_need = _lookup_inventory(inventory, "needed relic cores for next ss af", "relic core needed", "needed relic core")
    if relic_need > relic_have:
        real.append(f"relic core: need {relic_need:g}, have {relic_have:g}")

    awakening_have = _lookup_inventory(inventory, "awakening core", "awakening cores", "s awakening core")
    awakening_need = _lookup_inventory(inventory, "needed awakening cores for next survivor awakening", "awakening core needed", "needed awakening core")
    if awakening_need > awakening_have:
        real.append(f"awakening core: need {awakening_need:g}, have {awakening_have:g}")

    shards_have = _lookup_inventory(inventory, "s survivor shards", "s survivor shard", "yang shard", "survivor shard")
    shards_need = _lookup_inventory(inventory, "needed s survivor shards for next survivor awakening", "needed survivor shard", "survivor shard needed")
    if shards_need > shards_have:
        real.append(f"S survivor shards: need {shards_need:g}, have {shards_have:g}")

    cheap_aliases = {
        "normal salvage cubes": ("normal salvage cubes", "salvage cube normal", "normal cube", "regular salvage"),
        "basic gear fodder": ("basic gear fodder", "fodder basic", "gear food"),
        "purple merge items": ("purple merge items", "purple trash merge"),
        "yellow merge items": ("yellow merge items", "yellow trash merge"),
        "common materials": ("common materials",),
    }
    for label, aliases in cheap_aliases.items():
        if any(_normalized_key(alias) in inventory for alias in aliases) and _lookup_inventory(inventory, *aliases) <= 0:
            minor.append(f"{label}: low-tier material, not a primary CE damage blocker")
    return {
        "real_blockers": real,
        "minor_blockers": minor,
        "near_milestones": _near_milestones(profile),
    }


def _legacy_explicit_multiplier_report(profile: Mapping[str, Any]) -> dict[str, Any] | None:
    if not _contains_explicit_multiplier(profile):
        return None
    base = _legacy_base_damage(profile)
    ignored: list[str] = []
    breakdown: dict[str, float] = {}
    for system in LEGACY_SYSTEMS:
        breakdown[system] = round(
            _product_explicit_multipliers(profile.get(system, {}), (system,), ignored),
            9,
        )
    other_payload = {
        key: value
        for key, value in profile.items()
        if key not in set(LEGACY_SYSTEMS)
        and key not in {"inventory", "resources", "player_stage", "profile_name", "stats", "build_stats", "sio_ce"}
    }
    breakdown["other"] = round(_product_explicit_multipliers(other_payload, ("other",), ignored), 9)
    final_multiplier = math.prod(value if value > 0 else 1.0 for value in breakdown.values())
    total = base * final_multiplier
    blockers = _blocker_report(profile)
    return {
        "supported": True,
        "runtime_exact": False,
        "game_mode": "clan_expedition",
        "calc_mode": "damage",
        "base_damage": base,
        "base_attack": base,
        "total_damage": total,
        "sio_damage_value": total,
        "final_damage_multiplier": final_multiplier,
        "stat_multiplier": final_multiplier,
        "direct_damage_factor": 0.0,
        "direct_damage_multiplier_applied": 1.0,
        "multiplier_breakdown": breakdown,
        "damage_math_type": "legacy_explicit_ce_multiplier_snapshot",
        "blocker_analysis": blockers,
        "true_blockers": blockers["real_blockers"],
        "minor_blockers": blockers["minor_blockers"],
        "next_milestones": blockers["near_milestones"],
        "ignored_inactive_or_future_damage_rows": sorted(set(ignored)),
        "warnings": [
            "Used explicit legacy damage_multiplier values because no exact sIO attack/state split was available.",
            "This compatibility snapshot is excluded from exact oracle training and legal action promotion.",
        ],
        "formula_provenance": {
            "source": "explicit multipliers supplied in imported legacy profile",
            "runtime_exact": False,
            "game_mode": "clan_expedition",
        },
    }


def estimate_damage_score(build_stats: Mapping[str, Any]) -> float:
    profile = {
        "game_mode": "clan_expedition",
        "build_stats": dict(build_stats),
        "sio_ce": {
            "stats_stage": "legacy_stat_snapshot",
            "attack": {"atkBase": _number(build_stats.get("atk")), "atkFinal": 0.0},
            "passive_multiplier": 1.0,
        },
    }
    result = calculate_clan_expedition_damage(_normalize_legacy_profile(profile))
    return round(float(result.get("total_damage") or 0.0), 6)


def estimate_damage_totals(profile_input: Any) -> dict[str, Any]:
    if hasattr(profile_input, "model_dump"):
        profile = profile_input.model_dump()
    elif hasattr(profile_input, "dict"):
        profile = profile_input.dict()
    elif isinstance(profile_input, Mapping):
        profile = deepcopy(dict(profile_input))
    else:
        profile = {}

    explicit_mode = str(profile.get("game_mode") or profile.get("mode") or "").strip().lower().replace("-", "_").replace(" ", "_")
    if explicit_mode and explicit_mode not in {"ce", "clan_expedition", "clan_expedition_damage"}:
        raise UnsupportedGameModeError(f"Only Clan Expedition is supported; received {explicit_mode!r}.")

    legacy_report = _legacy_explicit_multiplier_report(profile)
    sio_attack = (profile.get("sio_ce") or {}).get("attack") if isinstance(profile.get("sio_ce"), Mapping) else None
    if legacy_report is not None and not isinstance(sio_attack, Mapping):
        return legacy_report

    profile = _normalize_legacy_profile(profile)
    result = calculate_clan_expedition_damage(profile)
    blockers = _blocker_report(profile)
    if not result.get("supported"):
        required = list(result.get("required_fields", []))
        return {
            **result,
            "base_damage": None,
            "total_damage": None,
            "final_damage_multiplier": None,
            "multiplier_breakdown": {},
            "damage_math_type": "sio_clan_expedition_unscoreable",
            "blocker_analysis": {
                "real_blockers": [*blockers["real_blockers"], *required],
                "minor_blockers": blockers["minor_blockers"],
                "near_milestones": blockers["near_milestones"],
            },
            "true_blockers": [*blockers["real_blockers"], *required],
            "minor_blockers": blockers["minor_blockers"],
            "next_milestones": blockers["near_milestones"],
        }

    base_attack = float(result["base_attack"])
    total_damage = float(result["total_damage"])
    final_multiplier = total_damage / base_attack if base_attack else None
    return {
        **result,
        "base_damage": base_attack,
        "final_damage_multiplier": final_multiplier,
        "damage_math_type": "sio_clan_expedition_exact_core",
        "blocker_analysis": blockers,
        "true_blockers": blockers["real_blockers"],
        "minor_blockers": blockers["minor_blockers"],
        "next_milestones": blockers["near_milestones"],
        "ignored_inactive_or_future_damage_rows": [],
    }


__all__ = ["UnsupportedGameModeError", "estimate_damage_score", "estimate_damage_totals"]
