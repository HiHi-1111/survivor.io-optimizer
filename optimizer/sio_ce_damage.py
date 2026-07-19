"""Exact sIO Clan Expedition core damage formula.

Authority: user-supplied sIO runtime first, then the user's Discord/PDF Bible.
External guides may corroborate mechanics but cannot override those sources.
Only Clan Expedition is supported.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping

from optimizer.sio_ce_constants import (
    SIO_BASE_STATS,
    SIO_BUNDLE_SHA256,
    SIO_DIRECT_DAMAGE_COEFFICIENTS,
    SIO_FORMULA_MODULES,
    SUPPORTED_CALC_MODE,
    SUPPORTED_GAME_MODE,
)
from optimizer.sio_mounts import aggregate_mount_stats


class UnsupportedGameModeError(ValueError):
    pass


@dataclass(frozen=True)
class FormulaProvenance:
    source: str = "user-supplied sIO Tools runtime bundle"
    bundle_sha256: str = SIO_BUNDLE_SHA256
    modules: tuple[int, ...] = SIO_FORMULA_MODULES
    game_mode: str = SUPPORTED_GAME_MODE
    calc_mode: str = SUPPORTED_CALC_MODE


def _num(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return lower if value < lower else upper if value > upper else value


def percent_bonus(value: Any) -> float:
    return (_num(value) + 100.0) * 0.01


def _mode(profile: Mapping[str, Any]) -> str:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    raw = profile.get("game_mode") or profile.get("mode") or profile.get("goal_scenario") or sio.get("game_mode") or SUPPORTED_GAME_MODE
    text = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    return {"ce": SUPPORTED_GAME_MODE, "scenario_clan_expedition": SUPPORTED_GAME_MODE, "clan_expedition_damage": SUPPORTED_GAME_MODE}.get(text, text)


def require_clan_expedition(profile: Mapping[str, Any]) -> None:
    mode = _mode(profile)
    if mode != SUPPORTED_GAME_MODE:
        raise UnsupportedGameModeError(
            f"Only Clan Expedition is supported; received {mode!r}. CE math must not be reused for another mode."
        )


def _add(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        amount = _num(value)
        if amount:
            target[str(key)] = _num(target.get(str(key))) + amount


def calculate_ce_direct_factor(stats: Mapping[str, Any], direct: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Port of sIO module 88426.y."""
    laser_scale = 1.0 / (0.01 * _num(stats.get("ssGlovesLaser")) + 1.0)
    parts = {str(key): _num(value) for key, value in (direct or {}).items()}
    total = sum(parts.values())

    ss_weapon = max(0.0, _num(stats.get("ssMiscPath"))) ** 0.72 * SIO_DIRECT_DAMAGE_COEFFICIENTS["ssWeapon"]
    if _num(stats.get("cooldownReduction")):
        ss_weapon *= _num(stats.get("cooldownReduction"))
    parts["ssWeapon"] = ss_weapon
    parts["taloxaOverload"] = _num(stats.get("taloxaBeam")) * SIO_DIRECT_DAMAGE_COEFFICIENTS["taloxaOverload"]
    parts["crimsonBat"] = _num(stats.get("crimsonBat")) * SIO_DIRECT_DAMAGE_COEFFICIENTS["crimsonBat"]
    total += parts["ssWeapon"] + parts["taloxaOverload"] + parts["crimsonBat"]

    for name, field in {
        "Taloxa": "harmonyTaloxa", "Joey": "harmonyJoey", "Metalia": "harmonyMetalia",
        "Master Yang": "harmonyYang", "King": "harmonyKing", "Common": "harmonyCommon",
    }.items():
        parts[name] = _num(stats.get(field)) * SIO_DIRECT_DAMAGE_COEFFICIENTS[name] * laser_scale
        total += parts[name]
    parts["xeno"] = _num(stats.get("xenoDamage")) * laser_scale
    parts["mount"] = _num(stats.get("mountDamage")) * laser_scale
    total += parts["xeno"] + parts["mount"]
    return {"damage_factor": total, "components": parts, "ss_gloves_laser_scale": laser_scale}


def _payload(profile: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str], dict[str, Any]]:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    stats: dict[str, Any] = deepcopy(SIO_BASE_STATS)
    for row in (profile.get("build_stats"), profile.get("stats"), sio.get("stats")):
        if isinstance(row, Mapping):
            stats.update(row)
    mounts = sio.get("mounts") if isinstance(sio.get("mounts"), Mapping) else profile.get("mounts")
    mount_result = aggregate_mount_stats(mounts if isinstance(mounts, Mapping) else None)
    _add(stats, mount_result["stats"])

    attack: dict[str, Any] = {}
    for row in (profile.get("attack"), sio.get("attack")):
        if isinstance(row, Mapping):
            attack.update(row)
    warnings = list(mount_result["warnings"])
    if "atkBase" not in attack and "atk" in stats:
        attack.update({"atkBase": stats["atk"], "atkFinal": 0.0})
        warnings.append("Used atk as atkBase; exact ATK split was not supplied.")
    stage = str(sio.get("stats_stage", profile.get("stats_stage", "unknown")))
    if stage not in {"post_24804", "sio_post_24804"}:
        warnings.append("Stats are not marked post_24804; item trigger and uptime assembly remains unknown.")
    direct = sio.get("direct_skill_factors") if isinstance(sio.get("direct_skill_factors"), Mapping) else profile.get("direct_skill_factors")
    return stats, attack, dict(direct) if isinstance(direct, Mapping) else {}, warnings, mount_result


def calculate_clan_expedition_damage(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Port the core of sIO modules 67727 and 88426 for one CE profile."""
    require_clan_expedition(profile)
    stats, attack, direct_map, warnings, mount_result = _payload(profile)
    provenance = asdict(FormulaProvenance())
    if "atkBase" not in attack or "atkFinal" not in attack:
        return {"supported": False, "reason": "missing_sio_attack_split", "required_fields": ["sio_ce.attack.atkBase", "sio_ce.attack.atkFinal"], "warnings": warnings, "formula_provenance": provenance}

    crit_rate = clamp(_num(stats.get("critRate")) / 100.0)
    crit_damage = max(_num(stats.get("critDamage")) / 100.0, 2.0)
    base_attack = (
        _num(attack.get("atkBase"))
        + _num(stats.get("atkEquip")) * percent_bonus(stats.get("atkEquipPercent"))
        + _num(stats.get("atkHero")) * percent_bonus(stats.get("atkHeroPercent"))
    ) * percent_bonus(stats.get("atkPercent")) + _num(attack.get("atkFinal")) + _num(stats.get("atkFinal"))

    multipliers = {
        "crit_expected": crit_rate * crit_damage + 1.0 - crit_rate,
        "skill_damage": percent_bonus(max(0.0, _num(stats.get("skillDamage")))),
        "vulnerability": percent_bonus(max(0.0, _num(stats.get("vulnerability")))),
        "shield_damage_uptime": percent_bonus(max(0.0, _num(stats.get("shieldDamage")) * _num(stats.get("shieldDamageUptime")))),
        "poison_weaken_chill_exposed": percent_bonus(
            max(0.0, _num(stats.get("poisoned")) * _num(stats.get("poisonedUptime")))
            + max(0.0, _num(stats.get("weakened")) * _num(stats.get("weakenedUptime")))
            + max(0.0, _num(stats.get("chilled")) * _num(stats.get("chilledUptime")))
            + _num(stats.get("exposedDamage"))
        ),
        "clarity": percent_bonus(stats.get("clarity")),
        "eternal_multiplier": percent_bonus(stats.get("eternalMultiplier")),
        "glacial_bloodline": percent_bonus(stats.get("glacialBloodline")),
        "laceration_divine_fire_uptime": percent_bonus(
            max(0.0, _num(stats.get("laceration")) * _num(stats.get("lacerationUptime")))
            + max(0.0, _num(stats.get("divineFire")) * _num(stats.get("divineFireUptime")))
        ),
        "joey_weak_spot": percent_bonus(stats.get("joeyWeakSpot")),
        "ss_gloves_laser": percent_bonus(stats.get("ssGlovesLaser")),
        "flashrift_rip": percent_bonus(stats.get("flashriftRip")),
        "taloxa_overload": percent_bonus(stats.get("taloxaOverload")),
        "eternal_suit_boost": _num(stats.get("eternalSuitBoost"), 1.0),
        "void_neck_effective": _num(stats.get("voidNeckBoost"), 1.0) * _num(stats.get("voidNeckBoostUptime"), 1.0),
        "void_gloves_instakill": _num(stats.get("voidGlovesInstakill"), 1.0),
        "void_boots_boost": _num(stats.get("voidBootsBoost"), 1.0),
        "chaos_belt_boost": _num(stats.get("chaosBeltBoost"), 1.0),
        "hp_bullet_boost": _num(stats.get("hpBulletBoost"), 1.0),
        "damage_dealt": percent_bonus(stats.get("damageDealt")),
        "adrenaline": percent_bonus(stats.get("adrenaline")),
        "damage_transmute": percent_bonus(stats.get("damageTransmute")),
        "damage_boss": percent_bonus(stats.get("damageBoss")),
        "xeno_res_multiplier": percent_bonus(stats.get("xenoResMultiplier")),
    }
    stat_multiplier = math.prod(multipliers.values())
    direct = calculate_ce_direct_factor(stats, direct_map)
    direct_multiplier = direct["damage_factor"] or 1.0
    passive = _num(sio.get("passive_multiplier", 1.0), 1.0) if (sio := profile.get("sio_ce")) and isinstance(sio, Mapping) else 1.0
    if passive <= 0:
        passive = 1.0
    if not isinstance(sio, Mapping) or "passive_multiplier" not in sio:
        warnings.append("Evolved-passive adjustment from module 67727 is not supplied; using 1.0.")
    total = base_attack * stat_multiplier * direct_multiplier * passive
    return {
        "supported": True,
        "game_mode": SUPPORTED_GAME_MODE,
        "calc_mode": SUPPORTED_CALC_MODE,
        "total_damage": total,
        "sio_damage_value": total,
        "base_attack": base_attack,
        "stat_multiplier": stat_multiplier,
        "direct_damage_factor": direct["damage_factor"],
        "direct_damage_multiplier_applied": direct_multiplier,
        "passive_multiplier": passive,
        "multiplier_breakdown": multipliers,
        "ce_damage_components": direct["components"],
        "mount_detail": mount_result["detail"],
        "normalized_stats": stats,
        "warnings": sorted(set(warnings)),
        "formula_provenance": provenance,
    }


def compare_clan_expedition_profiles(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    before_result = calculate_clan_expedition_damage(before)
    after_result = calculate_clan_expedition_damage(after)
    if not before_result.get("supported") or not after_result.get("supported"):
        return {"supported": False, "before": before_result, "after": after_result, "reason": "before_or_after_state_not_scoreable"}
    old, new = float(before_result["total_damage"]), float(after_result["total_damage"])
    delta = new - old
    return {"supported": True, "before": before_result, "after": after_result, "delta": delta, "percent_gain": delta / old * 100.0 if old else None, "improves_damage": delta > 0}
