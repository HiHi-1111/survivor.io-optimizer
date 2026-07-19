"""Order-sensitive sIO item pipeline for Clan Expedition.

Module 42052 assembles item/forge data. Module 24804 then applies item
conditions after account-wide stats have been merged. Keeping those phases
separate prevents Moonscar, Twin Lance and uptime thresholds from reading an
incomplete account state.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from optimizer.sio_item_data import SIO_ITEMS
from optimizer.sio_items import (
    CE_DURATION,
    SLOTS,
    SS_GLOVES_LASER_FACTOR,
    TRANSMUTE_CONDITIONS,
    TRANSMUTE_DURATION_10,
    TRANSMUTE_DURATION_15,
    TRANSMUTE_EFFECT_10,
    TRANSMUTE_EFFECT_15,
    TRANSMUTE_STATS,
    _add,
    _apply_collectibles,
    _apply_sets,
    _apply_special_item_rules,
    _gear_level_cap,
    _num,
    _threshold,
    _unwrap_data,
    collectible_stars_from_profile,
    item_state_from_profile,
)


def _active_survivor(profile: Mapping[str, Any]) -> str:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    survivor = profile.get("survivor") if isinstance(profile.get("survivor"), Mapping) else {}
    meta = sio.get("meta") if isinstance(sio.get("meta"), Mapping) else profile.get("meta")
    meta = _unwrap_data(meta) if isinstance(meta, Mapping) else {}
    return str(
        survivor.get("id")
        or sio.get("active_survivor")
        or profile.get("active_survivor")
        or meta.get("mainHero")
        or meta.get("main_hero")
        or ""
    )


def assemble_sio_item_base_stats(
    profile: Mapping[str, Any],
    base_stats: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply item, AF, Chaos Fusion, Transmute and item-linked collectibles.

    Conditional module-24804 effects are intentionally deferred.
    """
    items = item_state_from_profile(profile)
    collectibles = collectible_stars_from_profile(profile)
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    upgraded = set(sio.get("upgraded_collectibles", profile.get("upgraded_collectibles", [])) or [])
    max_gear = int(_num(sio.get("max_gear", profile.get("max_gear", 0))))
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
                valid = (
                    0 <= effect_index < len(TRANSMUTE_STATS)
                    and 0 <= condition_index < len(TRANSMUTE_CONDITIONS[slot])
                )
                if valid:
                    cooldown = TRANSMUTE_CONDITIONS[slot][condition_index]
                    effect = TRANSMUTE_EFFECT_15 if cooldown == 15 else TRANSMUTE_EFFECT_10
                    duration = TRANSMUTE_DURATION_15 if cooldown == 15 else TRANSMUTE_DURATION_10
                    target = TRANSMUTE_STATS[effect_index]
                    item_stats[target] = item_stats.get(target, 0.0) + effect
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
                item_stats["atkEquip"] = (
                    item_stats.get("atkEquip", 0.0)
                    + _num(definition["baseAtk"])
                    + min(max_gear, cap) * _num(definition["atkGrowth"])
                )
        _add(stats, item_stats)
        _apply_sets(stats, definition.get("sets"), collectibles, detail["sets"])
        _apply_collectibles(stats, definition.get("collectibles"), collectibles, upgraded, detail["collectibles"])
        detail["items"][slot] = {"name": name, "state": deepcopy(state), "effects": item_stats}

    if "ssGlovesLaser" in stats:
        stats["ssGlovesLaser"] *= SS_GLOVES_LASER_FACTOR
    return {
        "stats": stats,
        "detail": detail,
        "warnings": sorted(set(warnings)),
        "items": items,
        "collectibles": collectibles,
        "stats_stage": "pre_24804_item_conditions",
    }


def apply_sio_item_conditions(
    profile: Mapping[str, Any],
    stats: Mapping[str, Any],
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply module-24804 conditions after all account and mount stats exist."""
    items = item_state_from_profile(profile)
    collectibles = collectible_stars_from_profile(profile)
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    settings = sio.get("settings") if isinstance(sio.get("settings"), Mapping) else profile.get("settings", {})
    settings = _unwrap_data(settings) if isinstance(settings, Mapping) else {}
    revives = [_num(value) for value in (settings.get("revives", [40, 70, 90]) or [])]
    result = {str(key): _num(value) for key, value in stats.items() if _num(value)}
    target_detail = detail if detail is not None else {}
    _apply_special_item_rules(
        result,
        items,
        collectibles,
        revives,
        _active_survivor(profile) == "Venato",
        target_detail,
    )
    return {
        "stats": result,
        "detail": target_detail,
        "duration": CE_DURATION,
        "stats_stage": "post_24804_account_and_items",
    }
