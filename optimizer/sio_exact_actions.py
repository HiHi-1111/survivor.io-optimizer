"""Exact legal progression candidates for the sIO Clan Expedition optimizer.

Every generated action contains a complete state patch and a balanced
consumption/refund ledger derived from cumulative sIO tables. Systems whose
cost cannot be proven may still be supplied through ``sio_ce.exact_actions``;
they are never assigned an invented cost.
"""
from __future__ import annotations

from copy import deepcopy
import itertools
import re
from typing import Any, Iterable, Mapping

from optimizer.sio_item_data import SIO_ITEMS
from optimizer.sio_items import SLOTS, item_state_from_profile
from optimizer.sio_mounts import MOUNT_ALIASES
from optimizer.sio_pet_data import SIO_PET_DATA
from optimizer.sio_progression_data import SIO_PROGRESSION_DATA
from optimizer.sio_survivor_data import SIO_SURVIVOR_DATA

DATA = SIO_PROGRESSION_DATA


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _unwrap(value: Any) -> Any:
    if isinstance(value, Mapping) and isinstance(value.get("data"), Mapping):
        return value["data"]
    if isinstance(value, Mapping) and isinstance(value.get("owned"), Mapping):
        return value["owned"]
    return value


def _deep_merge(target: dict[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    for key, value in patch.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = deepcopy(value)
    return target


def apply_exact_action(profile: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any]:
    after = deepcopy(dict(profile))
    patch = action.get("state_patch")
    if not isinstance(patch, Mapping):
        raise ValueError(f"Action {action.get('action_id')} has no state_patch")
    return _deep_merge(after, patch)


def resource_counts(profile: Mapping[str, Any]) -> dict[str, float]:
    counts: dict[str, float] = {}
    sections: list[Any] = [profile.get("resources", {})]
    inventory = profile.get("inventory")
    if isinstance(inventory, Mapping):
        sections.extend([inventory.get("items", {}), inventory.get("resources", {})])
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    sections.append(sio.get("resources", {}))
    for section in sections:
        if not isinstance(section, Mapping):
            continue
        for key, value in section.items():
            amount = value
            if isinstance(value, Mapping):
                amount = value.get("count", value.get("quantity", value.get("amount", 0)))
            if isinstance(amount, (int, float)):
                counts[str(key)] = counts.get(str(key), 0.0) + float(amount)
    aliases = sio.get("resource_aliases") if isinstance(sio.get("resource_aliases"), Mapping) else {}
    for canonical, source in aliases.items():
        names = [source] if isinstance(source, str) else list(source or [])
        counts[str(canonical)] = counts.get(str(canonical), 0.0) + sum(counts.get(str(name), 0.0) for name in names)
    return counts


def _ledger(before: Mapping[str, float], after: Mapping[str, float]) -> tuple[dict[str, float], dict[str, float]]:
    consumed: dict[str, float] = {}
    refunded: dict[str, float] = {}
    for key in sorted(set(before) | set(after)):
        delta = _number(after.get(key)) - _number(before.get(key))
        if delta > 1e-9:
            consumed[key] = round(delta, 9)
        elif delta < -1e-9:
            refunded[key] = round(-delta, 9)
    return consumed, refunded


def affordability_certificate(profile: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any]:
    available = resource_counts(profile)
    consumed = {str(k): _number(v) for k, v in (action.get("consumed_items") or {}).items()}
    refunded = {str(k): _number(v) for k, v in (action.get("refunded_items") or {}).items()}
    missing = {
        key: amount - available.get(key, 0.0) - refunded.get(key, 0.0)
        for key, amount in consumed.items()
        if available.get(key, 0.0) + refunded.get(key, 0.0) + 1e-9 < amount
    }
    return {
        "legal": not missing,
        "available": available,
        "consumed": consumed,
        "refunded": refunded,
        "missing": missing,
        "balanced": all(value >= 0 for value in consumed.values()) and all(value >= 0 for value in refunded.values()),
    }


def _item_resource_totals(items: Mapping[str, Mapping[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {
        "relic_core": 0.0,
        "transmute_core": 0.0,
        "eternal_core": 0.0,
        "void_core": 0.0,
        "chaos_core": 0.0,
    }
    iv, vo, ox, du, copies = DATA["iv"], DATA["vo"], DATA["Ox"], DATA["DU"], DATA["Ai"]
    for state in items.values():
        if not isinstance(state, Mapping):
            continue
        name = str(state.get("name") or "")
        definition = SIO_ITEMS.get(name)
        if not definition:
            continue
        e, v, c, base, x = (int(_number(state.get(key))) for key in ("e", "v", "c", "base", "x"))
        if definition.get("rarity") == "SS":
            e_index, v_index = e, v
        else:
            adjusted = max(c, 3) if c else 0
            half = adjusted // 2
            if adjusted % 2 == 0:
                e_index = v_index = half
            else:
                even_pair = ((adjusted - 3) // 2) % 2 == 0
                e_index, v_index = half + int(not even_pair), half + int(even_pair)
        e_index = max(0, min(e_index, len(iv["e"]) - 1))
        v_index = max(0, min(v_index, len(iv["v"]) - 1))
        c = max(0, min(c, len(iv["c"]) - 1))
        x = max(0, min(x, len(ox) - 1))
        totals["relic_core"] += iv["e"][e_index] + iv["v"][v_index] + iv["c"][c]
        totals["transmute_core"] += ox[x]
        totals["eternal_core"] += vo["e"][e_index] + du["e"][x]
        totals["void_core"] += vo["v"][v_index] + du["v"][x]
        totals["chaos_core"] += vo["c"][c]
        item_type = _slug(str(definition.get("type") or "unknown"))
        for side, index in (("eternal", e_index), ("void", v_index), ("chaos", c)):
            source = {"eternal": "e", "void": "v", "chaos": "c"}[side]
            key = f"item_copy:{item_type}:{side}"
            totals[key] = totals.get(key, 0.0) + copies[source][index]
        core_type = definition.get("coreType")
        if core_type:
            side = {"e": "eternal", "v": "void", "c": "chaos"}[str(core_type)]
            totals[f"{side}_core"] += vo["base"][max(0, min(base, len(vo["base"]) - 1))]
            key = f"item_copy:{item_type}:{side}"
            totals[key] = totals.get(key, 0.0) + copies["base"][max(0, min(base, len(copies["base"]) - 1))]
    return totals


def _item_path_key(name: str) -> str | None:
    if name in DATA["item_paths"]:
        return name
    definition = SIO_ITEMS.get(name, {})
    if definition.get("rarity") == "SS":
        return "SS"
    if definition:
        return "Legend"
    return None


def _item_patch(items: Mapping[str, Any]) -> dict[str, Any]:
    return {"sio_ce": {"items": {slot: deepcopy(state) for slot, state in items.items()}}}


def _make_action(
    *, action_id: str, system: str, action_type: str, patch: Mapping[str, Any],
    consumed: Mapping[str, float], refunded: Mapping[str, float], description: str,
    source_modules: Iterable[int], metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "system": system,
        "action_type": action_type,
        "state_patch": deepcopy(dict(patch)),
        "consumed_items": dict(consumed),
        "required_items": dict(consumed),
        "refunded_items": dict(refunded),
        "costs": [{"resource_id": key, "amount": value} for key, value in consumed.items()],
        "description": description,
        "confidence": "exact",
        "supported": True,
        "source": "user-supplied sIO runtime",
        "source_modules": list(source_modules),
        "metadata": {"exact_after_state": True, **dict(metadata or {})},
    }


def generate_item_actions(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    items = item_state_from_profile(profile)
    if not items:
        return []
    before_totals = _item_resource_totals(items)
    actions: list[dict[str, Any]] = []
    per_slot_up: dict[str, list[tuple[float, dict[str, Any], dict[str, float], dict[str, float]]]] = {}
    per_slot_down: dict[str, list[tuple[float, dict[str, Any], dict[str, float], dict[str, float]]]] = {}

    for slot in SLOTS:
        current = items.get(slot)
        if not isinstance(current, Mapping) or not current.get("name"):
            continue
        name = str(current["name"])
        path_key = _item_path_key(name)
        if path_key:
            candidates = DATA["item_paths"].get(path_key, [])
            for candidate in candidates:
                target = dict(current)
                target.update({key: int(candidate.get(key, 0)) for key in ("e", "v", "c")})
                if int(_number(target.get("x"))) > 0 and (int(_number(target.get("e"))) < 4 or int(_number(target.get("v"))) < 4):
                    continue
                if all(int(_number(target.get(key))) == int(_number(current.get(key))) for key in ("e", "v", "c", "x")):
                    continue
                after_items = deepcopy(items)
                after_items[slot] = target
                after_totals = _item_resource_totals(after_items)
                consumed, refunded = _ledger(before_totals, after_totals)
                distance = sum(consumed.values()) + sum(refunded.values()) * 0.1
                action = _make_action(
                    action_id=f"items:reconfigure:{_slug(slot)}:{_slug(name)}:e{target.get('e',0)}v{target.get('v',0)}c{target.get('c',0)}x{target.get('x',0)}",
                    system="items", action_type="reconfigure_item_path", patch=_item_patch(after_items),
                    consumed=consumed, refunded=refunded,
                    description=f"Set {slot} {name} to E{target.get('e',0)} V{target.get('v',0)} C{target.get('c',0)} X{target.get('x',0)}.",
                    source_modules=[42052, 32085], metadata={"slot": slot, "target": target},
                )
                actions.append(action)
                record = (distance, target, consumed, refunded)
                if sum(consumed.values()) >= sum(refunded.values()):
                    per_slot_up.setdefault(slot, []).append(record)
                else:
                    per_slot_down.setdefault(slot, []).append(record)
        definition = SIO_ITEMS.get(name, {})
        if definition.get("rarity") == "SS" and (definition.get("af") or {}).get("x"):
            current_x = int(_number(current.get("x")))
            if current_x < len(DATA["Ox"]) - 1:
                target = dict(current)
                target["x"] = current_x + 1
                target["e"] = max(4, int(_number(target.get("e"))))
                target["v"] = max(4, int(_number(target.get("v"))))
                after_items = deepcopy(items)
                after_items[slot] = target
                consumed, refunded = _ledger(before_totals, _item_resource_totals(after_items))
                actions.append(_make_action(
                    action_id=f"items:xeno_transmute:{_slug(slot)}:x{target['x']}",
                    system="items", action_type="upgrade_xeno_transmute", patch=_item_patch(after_items),
                    consumed=consumed, refunded=refunded,
                    description=f"Upgrade {slot} {name} Xeno Transmute to X{target['x']}.",
                    source_modules=[42052, 32085], metadata={"slot": slot, "target": target},
                ))

    # Exact two-slot reallocation candidates let committed AF resources move
    # without pretending they are free. Keep only nearest frontiers to avoid a
    # combinatorial explosion.
    for source_slot, target_slot in itertools.permutations(SLOTS, 2):
        downs = sorted(per_slot_down.get(source_slot, []), key=lambda row: row[0])[:4]
        ups = sorted(per_slot_up.get(target_slot, []), key=lambda row: row[0])[:10]
        for _, source_target, _, _ in downs:
            for _, destination_target, _, _ in ups:
                after_items = deepcopy(items)
                after_items[source_slot] = source_target
                after_items[target_slot] = destination_target
                consumed, refunded = _ledger(before_totals, _item_resource_totals(after_items))
                actions.append(_make_action(
                    action_id=(
                        f"items:reallocate:{_slug(source_slot)}_to_{_slug(target_slot)}:"
                        f"{stable_state_id(source_target)}:{stable_state_id(destination_target)}"
                    ),
                    system="items", action_type="reallocate_item_resources", patch=_item_patch(after_items),
                    consumed=consumed, refunded=refunded,
                    description=f"Refund/rebuild {source_slot} and {target_slot} as one balanced transition.",
                    source_modules=[42052, 32085], metadata={"source_slot": source_slot, "target_slot": target_slot},
                ))
    return _deduplicate(actions)


def stable_state_id(state: Mapping[str, Any]) -> str:
    return "".join(f"{key}{int(_number(state.get(key)))}" for key in ("e", "v", "c", "x"))


def _heroes(profile: Mapping[str, Any]) -> dict[str, Any]:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    raw = _unwrap(sio.get("heroes") or profile.get("heroes") or {})
    return deepcopy(dict(raw)) if isinstance(raw, Mapping) else {}


def generate_survivor_actions(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    heroes = _heroes(profile)
    actions: list[dict[str, Any]] = []
    costs, cores = DATA["pA"], DATA["on"]
    for name, state in heroes.items():
        if not isinstance(state, Mapping):
            continue
        current = int(_number(state.get("stars")))
        definition = SIO_SURVIVOR_DATA["heroes"].get(name, {})
        rarity = str(definition.get("rarity") or "")
        if rarity not in costs or current + 1 >= len(costs[rarity]):
            continue
        target = current + 1
        consumed: dict[str, float] = {}
        shard_delta = costs[rarity][target] - costs[rarity][current]
        core_delta = cores[rarity][target] - cores[rarity][current]
        if shard_delta:
            consumed["s_survivor_shard" if rarity == "S" else f"survivor_shard:{_slug(name)}"] = shard_delta
        if core_delta:
            consumed["awakening_core"] = core_delta
        patched = deepcopy(heroes)
        patched[name] = {**dict(state), "stars": target}
        actions.append(_make_action(
            action_id=f"survivor:star:{_slug(name)}:{target}", system="survivor", action_type="upgrade_survivor_star",
            patch={"sio_ce": {"heroes": patched}}, consumed=consumed, refunded={},
            description=f"Upgrade {name} to star {target}.", source_modules=[70941, 32085],
            metadata={"survivor": name, "rarity": rarity, "target_stars": target},
        ))
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    meta = _unwrap(sio.get("meta") or profile.get("meta") or {})
    if isinstance(meta, Mapping) and meta.get("synergy"):
        current = int(_number(meta.get("synergyLevel")))
        if current + 1 < len(costs["synergy"]):
            target = current + 1
            consumed = {}
            shard_delta = costs["synergy"][target] - costs["synergy"][current]
            core_delta = cores["synergy"][target] - cores["synergy"][current]
            if shard_delta: consumed["s_survivor_shard"] = shard_delta
            if core_delta: consumed["awakening_core"] = core_delta
            patched_meta = dict(meta); patched_meta["synergyLevel"] = target
            actions.append(_make_action(
                action_id=f"survivor:synergy:{target}", system="survivor", action_type="upgrade_survivor_synergy",
                patch={"sio_ce": {"meta": patched_meta}}, consumed=consumed, refunded={},
                description=f"Upgrade Survivor Synergy to level {target}.", source_modules=[70941, 32085],
                metadata={"target_level": target},
            ))
    return actions


def generate_pet_actions(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    pets = _unwrap(sio.get("pets") or profile.get("pets") or {})
    if not isinstance(pets, Mapping):
        return []
    stars = pets.get("stars") if isinstance(pets.get("stars"), Mapping) else pets.get("awakened")
    if not isinstance(stars, Mapping):
        return []
    actions: list[dict[str, Any]] = []
    for name, raw_star in stars.items():
        definition = SIO_PET_DATA["pets"].get(name)
        if not definition:
            continue
        pet_type = str(definition.get("type") or "Default")
        current = int(_number(raw_star))
        if current + 1 >= len(DATA["pA"][pet_type]):
            continue
        target = current + 1
        consumed: dict[str, float] = {}
        crystal_delta = DATA["pA"][pet_type][target] - DATA["pA"][pet_type][current]
        core_delta = DATA["on"][pet_type][target] - DATA["on"][pet_type][current]
        if crystal_delta:
            consumed["xeno_pet_crystal" if pet_type == "Xeno" else "pet_awakening_crystal"] = crystal_delta
        if core_delta:
            consumed["xeno_pet_core" if pet_type == "Xeno" else "pet_awakening_core"] = core_delta
        patched = deepcopy(dict(pets)); patched_stars = dict(stars); patched_stars[name] = target; patched["stars"] = patched_stars
        actions.append(_make_action(
            action_id=f"pets:star:{_slug(name)}:{target}", system="pets", action_type="upgrade_pet_star",
            patch={"sio_ce": {"pets": patched}}, consumed=consumed, refunded={},
            description=f"Upgrade {name} to star {target}.", source_modules=[39759, 32085],
            metadata={"pet": name, "pet_type": pet_type, "target_stars": target},
        ))
    return actions


def generate_mount_actions(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    mounts = sio.get("mounts") if isinstance(sio.get("mounts"), Mapping) else profile.get("mounts")
    if not isinstance(mounts, Mapping):
        return []
    data = mounts.get("data") if isinstance(mounts.get("data"), Mapping) else mounts
    actions: list[dict[str, Any]] = []
    rarity_by_name = {"Doomsteed": "Legend", "Tech Hoverboard": "Excellent", "Electric Scooter": "Better"}
    for raw_name, state in data.items():
        if raw_name == "active" or not isinstance(state, Mapping) or not state.get("enabled"):
            continue
        name = MOUNT_ALIASES.get(str(raw_name), str(raw_name))
        rarity = rarity_by_name.get(name)
        if not rarity:
            continue
        current = int(_number(state.get("stars")))
        if current + 1 >= len(DATA["nq"][rarity]):
            continue
        target = current + 1
        consumed = {f"{_slug(name)}_shard": DATA["nq"][rarity][target] - DATA["nq"][rarity][current]}
        core_delta = DATA["SG"][rarity][target] - DATA["SG"][rarity][current]
        if core_delta: consumed["mount_core"] = core_delta
        patched_mounts = deepcopy(dict(mounts))
        patched_data = deepcopy(dict(data)); patched_data[raw_name] = {**dict(state), "stars": target}; patched_mounts["data"] = patched_data
        actions.append(_make_action(
            action_id=f"mounts:star:{_slug(name)}:{target}", system="mounts", action_type="upgrade_mount",
            patch={"mounts": patched_mounts}, consumed=consumed, refunded={},
            description=f"Upgrade {name} to star {target}.", source_modules=[40514, 51642],
            metadata={"mount": name, "target_stars": target},
        ))
    return actions


def generate_collectible_actions(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    raw = _unwrap(sio.get("collectibles") or profile.get("collectibles") or {})
    if not isinstance(raw, Mapping):
        return []
    actions: list[dict[str, Any]] = []
    for name, state in raw.items():
        if not isinstance(state, Mapping):
            continue
        cost = state.get("shards_to_next", state.get("next_star_cost"))
        if not isinstance(cost, (int, float)) or cost < 0:
            continue
        current = int(_number(state.get("stars")))
        target = current + 1
        patched = deepcopy(dict(raw)); patched[name] = {**dict(state), "stars": target}
        resource_id = str(state.get("shard_resource_id") or f"collectible_shard:{_slug(str(name))}")
        actions.append(_make_action(
            action_id=f"collectibles:star:{_slug(str(name))}:{target}", system="collectibles", action_type="upgrade_collectible_star",
            patch={"sio_ce": {"collectibles": patched}}, consumed={resource_id: float(cost)}, refunded={},
            description=f"Upgrade {name} to star {target}.", source_modules=[57223, 89505],
            metadata={"collectible": str(name), "target_stars": target, "cost_supplied_by_profile": True},
        ))
    return actions


def generate_supplied_exact_actions(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    rows = sio.get("exact_actions") or profile.get("exact_actions") or sio.get("tech_upgrade_options") or []
    actions: list[dict[str, Any]] = []
    for index, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, Mapping) or not isinstance(row.get("state_patch"), Mapping):
            continue
        consumed = row.get("consumed_items") or row.get("costs") or {}
        if isinstance(consumed, list):
            consumed = {str(cost["resource_id"]): _number(cost["amount"]) for cost in consumed}
        actions.append(_make_action(
            action_id=str(row.get("action_id") or f"supplied_exact:{index}"),
            system=str(row.get("system") or "supplied_exact"), action_type=str(row.get("action_type") or "state_patch"),
            patch=row["state_patch"], consumed=consumed if isinstance(consumed, Mapping) else {},
            refunded=row.get("refunded_items", {}) if isinstance(row.get("refunded_items"), Mapping) else {},
            description=str(row.get("description") or "Apply supplied exact state patch."),
            source_modules=row.get("source_modules", []), metadata={"supplied_exact_action": True, **dict(row.get("metadata") or {})},
        ))
    return actions


def _deduplicate(actions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set(); result: list[dict[str, Any]] = []
    for action in actions:
        key = repr((action.get("state_patch"), action.get("consumed_items"), action.get("refunded_items")))
        if key in seen: continue
        seen.add(key); result.append(action)
    return result


def generate_exact_actions(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    actions = [
        *generate_item_actions(profile),
        *generate_survivor_actions(profile),
        *generate_pet_actions(profile),
        *generate_mount_actions(profile),
        *generate_collectible_actions(profile),
        *generate_supplied_exact_actions(profile),
    ]
    return sorted(_deduplicate(actions), key=lambda row: str(row.get("action_id")))


__all__ = [
    "affordability_certificate",
    "apply_exact_action",
    "generate_exact_actions",
    "generate_item_actions",
    "generate_mount_actions",
    "generate_pet_actions",
    "generate_survivor_actions",
    "resource_counts",
]
