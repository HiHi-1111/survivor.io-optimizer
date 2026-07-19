"""sIO equipment, Astral Forge, Chaos Fusion and Xeno Transmute assembly.

This ports the data-driven part of sIO module 42052 and the Clan Expedition
item-condition pass in module 24804. Values come from module 37013.c.
"""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Mapping

from optimizer.sio_item_data import SIO_ITEMS

SLOTS = ("Weapon", "Armor", "Necklace", "Belt", "Gloves", "Boots")
SS_NAMES = {
    "Weapon": "Twin Lance",
    "Armor": "Evervoid Armor",
    "Necklace": "Judgment Necklace",
    "Belt": "Stardust Sash",
    "Gloves": "Moonscar Bracer",
    "Boots": "Glacial Warboots",
}
TRANSMUTE_STATS = ("chilled", "poisoned", "weakened")
TRANSMUTE_CONDITIONS = {
    "Weapon": (15, 10, 10),
    "Armor": (15, 10, 10),
    "Necklace": (15, 10, 10),
    "Belt": (15, 10, 10),
}
TRANSMUTE_EFFECT_15 = 146.41666666666669
TRANSMUTE_EFFECT_10 = 166.83333333333334
TRANSMUTE_DURATION_15 = 4.183333333333334
TRANSMUTE_DURATION_10 = 4.766666666666667
SS_GLOVES_LASER_FACTOR = 0.5
CE_DURATION = 180.0


def _num(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _add(out: dict[str, float], values: Mapping[str, Any] | None, scale: float = 1.0) -> None:
    if not values:
        return
    for key, value in values.items():
        number = _num(value) * scale
        if number:
            out[str(key)] = out.get(str(key), 0.0) + number


def _threshold(table: Mapping[str, Any] | None, level: float) -> dict[str, float]:
    if not table:
        return {}
    nums = list(table.get("nums", []) or [])
    vals = list(table.get("vals", []) or [])
    selected: Mapping[str, Any] | None = None
    for threshold, value in zip(nums, vals):
        if level < _num(threshold):
            break
        selected = value
    return {str(key): _num(value) for key, value in (selected or {}).items() if _num(value)}


def _unwrap_data(value: Any) -> Any:
    if isinstance(value, Mapping) and isinstance(value.get("data"), Mapping):
        return value["data"]
    return value


def item_state_from_profile(profile: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    raw = sio.get("items") or profile.get("items")
    raw = _unwrap_data(raw)
    if isinstance(raw, Mapping) and any(slot in raw for slot in SLOTS):
        return {slot: dict(raw.get(slot, {}) or {}) for slot in SLOTS}

    gear = profile.get("gear")
    result: dict[str, dict[str, Any]] = {}
    if isinstance(gear, Mapping):
        for slot in SLOTS:
            state = gear.get(slot.lower()) or gear.get(slot)
            if isinstance(state, Mapping):
                state = dict(state)
                state.setdefault("name", state.get("id"))
                result[slot] = state
    return result


def collectible_stars_from_profile(profile: Mapping[str, Any]) -> dict[str, dict[str, float]]:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    raw = sio.get("collectibles") or profile.get("collectibles") or {}
    raw = _unwrap_data(raw)
    if isinstance(raw, Mapping) and isinstance(raw.get("owned"), Mapping):
        raw = raw["owned"]
    result: dict[str, dict[str, float]] = {}
    if not isinstance(raw, Mapping):
        return result
    for name, value in raw.items():
        if isinstance(value, Mapping):
            result[str(name)] = {"stars": _num(value.get("stars"))}
        elif isinstance(value, (int, float)):
            result[str(name)] = {"stars": _num(value)}
    return result


def _set_progress(names: list[str], collectibles: Mapping[str, Mapping[str, Any]]) -> dict[str, float]:
    gold = red = 0.0
    gold_each = red_each = math.inf
    for name in names:
        stars = _num((collectibles.get(name) or {}).get("stars"))
        gold += min(5.0, stars)
        red += max(0.0, stars - 5.0)
        gold_each = min(gold_each, stars)
        red_each = min(red_each, stars - 5.0)
    if math.isinf(gold_each):
        gold_each = 0.0
    if math.isinf(red_each):
        red_each = 0.0
    return {
        "gold": gold,
        "red": red,
        "total": gold + red,
        "goldEach": gold_each,
        "redEach": red_each,
    }


def _apply_sets(
    out: dict[str, float],
    sets: Mapping[str, Any] | None,
    collectibles: Mapping[str, Mapping[str, Any]],
    detail: dict[str, Any],
) -> None:
    for set_name, definition in (sets or {}).items():
        progress = _set_progress(list(definition.get("collectibles", []) or []), collectibles)
        applied: dict[str, float] = {}
        for progress_type, thresholds in (definition.get("stars", {}) or {}).items():
            current = progress.get(str(progress_type), 0.0)
            for threshold, effects in sorted(
                ((float(key), value) for key, value in (thresholds or {}).items()),
                key=lambda row: row[0],
            ):
                if current >= threshold:
                    _add(out, effects)
                    _add(applied, effects)
        detail[set_name] = {"progress": progress, "effects": applied}


def _apply_collectibles(
    out: dict[str, float],
    definitions: Mapping[str, Any] | None,
    collectibles: Mapping[str, Mapping[str, Any]],
    upgraded: set[str],
    detail: dict[str, Any],
) -> None:
    for name, definition in (definitions or {}).items():
        stars = _num((collectibles.get(name) or {}).get("stars"))
        effects = _threshold(definition.get("stars"), stars)
        scale = 1.33 if name in upgraded else 1.0
        _add(out, effects, scale)
        if effects:
            detail[name] = {"stars": stars, "scale": scale, "effects": effects}


def _gear_level_cap(chaos_level: int) -> int:
    if chaos_level >= 9:
        return 230
    if chaos_level >= 7:
        return 220
    if chaos_level >= 5:
        return 215
    if chaos_level >= 3:
        return 210
    if chaos_level >= 1:
        return 205
    return 200


def _revive_average(duration: float, revives: list[float], percent: float) -> float:
    if duration <= 0:
        return 1.0
    growth = 1.0 + percent / 100.0
    previous = 0.0
    multiplier = 1.0
    weighted = 0.0
    for revive in revives:
        weighted += (revive - previous) * multiplier
        multiplier *= growth
        previous = revive
    weighted += (duration - previous) * multiplier
    return weighted / duration


def _activation_fraction(required: float, has_void_flux: bool, has_chaos_flux: bool) -> float:
    chaos = 40.0 if has_chaos_flux else 0.0
    void = 20.0 if has_void_flux else 0.0
    if not has_chaos_flux:
        return (float(chaos >= required) + float(chaos + void >= required)) * 0.5
    first = max(0.0, min(1.0, (chaos - required) / chaos))
    second = max(0.0, min(1.0, (chaos + void - required) / chaos))
    return (first + second) * 0.5


def _all_at_least(collectibles: Mapping[str, Mapping[str, Any]], names: list[str], stars: float) -> bool:
    return bool(names) and all(_num((collectibles.get(name) or {}).get("stars")) >= stars for name in names)


def _apply_special_item_rules(
    stats: dict[str, float],
    items: Mapping[str, Mapping[str, Any]],
    collectibles: Mapping[str, Mapping[str, Any]],
    revives: list[float],
    venato: bool,
    detail: dict[str, Any],
) -> None:
    is_ss = {
        slot: (items.get(slot) or {}).get("name") == name
        for slot, name in SS_NAMES.items()
    }
    final_revive = revives[-1] if revives else 0.0
    ss_belt = is_ss["Belt"]
    shield_delta = -(
        final_revive - 3 * 2 - (2 + (5 * (1 + final_revive / 60.0) if ss_belt else 0.0)) / 2.0
    ) / CE_DURATION
    if (items.get("Armor") or {}).get("name") == "Eternal Suit":
        stats["shieldDamageUptime"] = stats.get("shieldDamageUptime", 0.0) + shield_delta

    if (items.get("Necklace") or {}).get("name") == "Voidwaker Emblem" and not venato:
        divisor = (revives.index(180) + 1) if 180 in revives else 3
        time_fraction = final_revive / divisor / CE_DURATION
        charm = _num((collectibles.get("Lucky Charm") or {}).get("stars"))
        low_hp = 0.5 + 0.25 * float(charm >= 3)
        lost = time_fraction * (1 - low_hp) + 0.4 * time_fraction / 2
        armor_e = int(_num((items.get("Armor") or {}).get("e")))
        if not is_ss["Armor"] or armor_e < 3:
            stats["shieldDamageUptime"] = stats.get("shieldDamageUptime", 0.0) + shield_delta / 3 * (1 - (low_hp - 0.4))
            stats["voidNeckBoostUptime"] = stats.get("voidNeckBoostUptime", 0.0) - lost
        else:
            stats["voidNeckBoostUptime"] = stats.get("voidNeckBoostUptime", 0.0) - 0.5 * lost

    gloves = items.get("Gloves") or {}
    if is_ss["Gloves"]:
        e = int(_num(gloves.get("e")))
        v = int(_num(gloves.get("v")))
        c = int(_num(gloves.get("c")))
        initial_crit = stats.get("critRate", 0.0)
        if v >= 4:
            stats["critRate"] = stats.get("critRate", 0.0) + 10
            stats["critRateFlux"] = stats.get("critRateFlux", 0.0) + 10
        if 6 <= c < 10:
            stats["critRate"] = stats.get("critRate", 0.0) + 20
            stats["critRateFlux"] = stats.get("critRateFlux", 0.0) + 20
        divine = SIO_ITEMS["Moonscar Bracer"]["sets"]["Summon the Divine Dragon"]["collectibles"]
        divine_all_red = _all_at_least(collectibles, divine, 8)
        divine_total = sum(_num((collectibles.get(name) or {}).get("stars")) for name in divine)
        for level, threshold, stat, base, boosted in (
            (1, 100.0, "critDamage", 30.0, 60.0 if divine_all_red else 30.0),
            (3, 130.0, "skillDamage", 30.0, 60.0 if divine_total >= 25 else 30.0),
            (5, 150.0, "critDamage", 100.0, 100.0),
        ):
            if e < level:
                continue
            value = boosted if level in {1, 3} else base
            fraction = 1.0 if initial_crit >= threshold else _activation_fraction(
                threshold - initial_crit, v >= 4, 6 <= c < 10
            )
            if fraction > 0:
                stats[stat] = stats.get(stat, 0.0) + value * fraction
                detail.setdefault("moonscar_thresholds", []).append(
                    {"level": level, "stat": stat, "value": value, "uptime": fraction}
                )

    boots = items.get("Boots") or {}
    if is_ss["Boots"]:
        e = int(_num(boots.get("e")))
        c = int(_num(boots.get("c")))
        conduct = SIO_ITEMS["Glacial Warboots"]["sets"]["Conduct Experiments"]["collectibles"]
        if e >= 1 and _all_at_least(collectibles, conduct, 3):
            stats["shieldDamage"] = stats.get("shieldDamage", 0.0) + (60 if e >= 5 else 50)
        if c >= 6:
            stats["glacialBloodline"] = stats.get("glacialBloodline", 0.0) + (6 if e >= 5 else 5)
        if c >= 10:
            stats["glacialBloodline"] = stats.get("glacialBloodline", 0.0) + (6.6 if e >= 5 else 5.5)

    if is_ss["Necklace"] and is_ss["Armor"] and _num((items.get("Necklace") or {}).get("e")) >= 5 and _num((items.get("Armor") or {}).get("e")) >= 5:
        stats["shieldDamage"] = stats.get("shieldDamage", 0.0) + 10

    weapon = items.get("Weapon") or {}
    if is_ss["Weapon"]:
        e = int(_num(weapon.get("e")))
        v = int(_num(weapon.get("v")))
        c = int(_num(weapon.get("c")))
        x = int(_num(weapon.get("x")))
        initial_crit = stats.get("critRate", 0.0)
        local_skill = stats.get("skillDamage", 0.0)
        local_shield = stats.get("shieldDamage", 0.0)
        total_chaos = int(sum(_num((items.get(slot) or {}).get("c")) for slot in SLOTS))
        if c >= 2:
            standin = SIO_ITEMS["Twin Lance"]["sets"]["Summon the Stand-in!"]
            progress = _set_progress(standin["collectibles"], collectibles)
            if progress["goldEach"] >= 3:
                stats["vulnerability"] = stats.get("vulnerability", 0.0) + 30
            if progress["total"] >= 25:
                stats["ssMiscPath"] = stats.get("ssMiscPath", 0.0) + 40
                if c >= 6:
                    stats["ssMiscPath"] += 55
        if x >= 8:
            stats["skillDamage"] = stats.get("skillDamage", 0.0) + (45 if e >= 5 else 30)
        if total_chaos >= 9:
            stats["skillDamage"] = stats.get("skillDamage", 0.0) + (75 if e >= 5 else 50)
            stats["ssMiscPath"] = stats.get("ssMiscPath", 0.0) + (25 + 15 * int(x >= 8)) * (3 if e >= 5 else 2 * int(e >= 1))
        repeated = 60 + 2 * (80 if v >= 4 else 55)
        for threshold in (18, 27, 36, 45):
            if total_chaos >= threshold:
                stats["ssMiscPath"] = stats.get("ssMiscPath", 0.0) + repeated
        if total_chaos >= 24 and is_ss["Necklace"]:
            stats["skillDamage"] = stats.get("skillDamage", 0.0) + 30
            stats["ssMiscPath"] = stats.get("ssMiscPath", 0.0) + 36
        if total_chaos >= 39:
            if initial_crit > 50:
                local_skill += 30
                stats["skillDamage"] = stats.get("skillDamage", 0.0) + 30
            if local_skill > 50:
                local_shield += 30
                stats["shieldDamage"] = stats.get("shieldDamage", 0.0) + 30
            if local_shield > 50:
                stats["critDamage"] = stats.get("critDamage", 0.0) + 30
        if total_chaos >= 42:
            if initial_crit > 50:
                stats["ssMiscPath"] = stats.get("ssMiscPath", 0.0) + 10
            if initial_crit > 100:
                stats["ssMiscPath"] = stats.get("ssMiscPath", 0.0) + 20
        c10_slots = [slot for slot in SLOTS if is_ss[slot] and _num((items.get(slot) or {}).get("c")) >= 10]
        if total_chaos >= 48 and c10_slots:
            _add(stats, {"shieldDamage": 30, "skillDamage": 30, "poisoned": 30})
        if total_chaos >= 51 and c >= 10:
            _add(stats, {"damageBoss": 12, "ssMiscPath": 5})
        if total_chaos >= 54:
            _add(stats, {"damageBoss": 4 * len(c10_slots), "ssMiscPath": 2 * len(c10_slots)})
        erudite = SIO_ITEMS["Twin Lance"]["sets"]["Erudite Heirloom"]["collectibles"]
        if _all_at_least(collectibles, erudite, 8):
            stats["skillDamage"] = stats.get("skillDamage", 0.0) + (30 if e >= 5 else 20)
        stats["ssMiscPath"] = ((stats.get("ssMiscPath", 0.0) + 100.0) / 100.0) * 133.8
        detail["twin_lance_special"] = {"total_chaos": total_chaos, "c10_slots": c10_slots}

    if "eternalSuitBoost" in stats:
        stats["eternalSuitBoost"] = _revive_average(CE_DURATION, revives, stats["eternalSuitBoost"])
    if "voidNeckBoost" in stats:
        stats["voidNeckBoost"] = (stats["voidNeckBoost"] + 100.0) / 100.0
    if "voidBootsBoost" in stats:
        stats["voidBootsBoost"] = (stats["voidBootsBoost"] + 100.0) / 100.0
    if "minEnergyFlux" in stats and "maxEnergyFlux" in stats:
        stats["chaosBeltBoost"] = ((stats["maxEnergyFlux"] - stats["minEnergyFlux"]) / 2 + stats["minEnergyFlux"]) / 100.0
    for uptime in (
        "lacerationUptime", "divineFireUptime", "poisonedUptime", "weakenedUptime",
        "chilledUptime", "shieldDamageUptime", "voidNeckBoostUptime",
    ):
        if uptime in stats:
            stats[uptime] = max(0.0, min(1.0, stats[uptime]))


def assemble_sio_item_stats(profile: Mapping[str, Any], base_stats: Mapping[str, Any] | None = None) -> dict[str, Any]:
    items = item_state_from_profile(profile)
    collectibles = collectible_stars_from_profile(profile)
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    upgraded = set(sio.get("upgraded_collectibles", profile.get("upgraded_collectibles", [])) or [])
    max_gear = int(_num(sio.get("max_gear", profile.get("max_gear", 0))))
    settings = sio.get("settings") if isinstance(sio.get("settings"), Mapping) else profile.get("settings", {})
    settings = _unwrap_data(settings) if isinstance(settings, Mapping) else {}
    revives = [_num(value) for value in (settings.get("revives", [40, 70, 90]) or [])]
    survivor = profile.get("survivor") if isinstance(profile.get("survivor"), Mapping) else {}
    active_survivor = str(survivor.get("id") or profile.get("active_survivor") or "")

    stats = {str(key): _num(value) for key, value in (base_stats or {}).items() if _num(value)}
    detail: dict[str, Any] = {"items": {}, "sets": {}, "collectibles": {}}
    warnings: list[str] = []
    total_chaos = int(sum(_num((items.get(slot) or {}).get("c")) for slot in SLOTS))

    for slot in SLOTS:
        state = items.get(slot) or {}
        name = str(state.get("name") or "")
        if not name or name == "None":
            continue
        definition = SIO_ITEMS.get(name)
        if not definition:
            warnings.append(f"Unknown sIO item definition: {slot}={name}")
            continue
        item_stats: dict[str, float] = {}
        _add(item_stats, definition.get("stats"))
        for path in ("base", "e", "v", "c", "x"):
            _add(item_stats, _threshold((definition.get("af") or {}).get(path), _num(state.get(path))))
        if definition.get("rarity") == "SS":
            _add(item_stats, _threshold((definition.get("af") or {}).get("cfp"), total_chaos))
            x_level = int(_num(state.get("x")))
            if x_level > 0 and slot in TRANSMUTE_CONDITIONS:
                effect_index = int(_num(state.get("transmuteEffect")))
                condition_index = int(_num(state.get("transmuteCondition")))
                if 0 <= effect_index < len(TRANSMUTE_STATS) and 0 <= condition_index < len(TRANSMUTE_CONDITIONS[slot]):
                    cooldown = TRANSMUTE_CONDITIONS[slot][condition_index]
                    effect = TRANSMUTE_EFFECT_15 if cooldown == 15 else TRANSMUTE_EFFECT_10
                    duration = TRANSMUTE_DURATION_15 if cooldown == 15 else TRANSMUTE_DURATION_10
                    item_stats[TRANSMUTE_STATS[effect_index]] = item_stats.get(TRANSMUTE_STATS[effect_index], 0.0) + effect
                    if x_level >= 5:
                        item_stats["damageTransmute"] = item_stats.get("damageTransmute", 0.0) + 3 * duration
                    if x_level >= 13:
                        item_stats["damageTransmute"] = item_stats.get("damageTransmute", 0.0) + duration
                else:
                    warnings.append(f"{name}: invalid Xeno Transmute effect/condition selection")
        if definition.get("baseAtk") and definition.get("atkGrowth"):
            if max_gear <= 0:
                warnings.append(f"{name}: max_gear missing; atkEquip contribution omitted")
            else:
                cap = _gear_level_cap(int(_num(state.get("c")))) if definition.get("rarity") == "SS" else 160
                item_stats["atkEquip"] = item_stats.get("atkEquip", 0.0) + _num(definition["baseAtk"]) + min(max_gear, cap) * _num(definition["atkGrowth"])
        _add(stats, item_stats)
        _apply_sets(stats, definition.get("sets"), collectibles, detail["sets"])
        _apply_collectibles(stats, definition.get("collectibles"), collectibles, upgraded, detail["collectibles"])
        detail["items"][slot] = {"name": name, "state": deepcopy(state), "effects": item_stats}

    if "ssGlovesLaser" in stats:
        stats["ssGlovesLaser"] *= SS_GLOVES_LASER_FACTOR
    _apply_special_item_rules(stats, items, collectibles, revives, active_survivor == "Venato", detail)
    return {
        "stats": stats,
        "detail": detail,
        "warnings": sorted(set(warnings)),
        "items": items,
        "collectibles": collectibles,
        "stats_stage": "post_24804_items",
    }
