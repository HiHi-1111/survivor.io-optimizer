"""Exact cumulative progression frontiers from the source-locked sIO tables.

The optimizer cannot see a distant damage breakpoint if it only evaluates the
next star or Overload level. These generators expose every legal higher target
as one cumulative before/after action. They do not create free intermediate
steps: each action consumes the exact cumulative delta from the current state.
"""
from __future__ import annotations

from copy import deepcopy
import math
import re
from typing import Any, Iterable, Mapping

from optimizer.sio_mounts import MOUNT_ALIASES
from optimizer.sio_pet_data import SIO_PET_DATA
from optimizer.sio_progression_data import SIO_PROGRESSION_DATA
from optimizer.sio_survivor_data import SIO_SURVIVOR_DATA
from optimizer.sio_tech_progression import (
    MULTIPLIER_CHIPS,
    MULTIPLIER_EXTRA_PARTS,
    OVERLOAD_CHIPS,
    OVERLOAD_EXTRA_PARTS,
    OVERLOAD_RESONANCE_THRESHOLDS,
    TECH_TYPES,
    exact_tech_state,
)

DATA = SIO_PROGRESSION_DATA


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _unwrap(value: Any) -> Any:
    if isinstance(value, Mapping) and isinstance(value.get("data"), Mapping):
        return value["data"]
    if isinstance(value, Mapping) and isinstance(value.get("owned"), Mapping):
        return value["owned"]
    return value


def _action(
    *,
    action_id: str,
    system: str,
    action_type: str,
    patch: Mapping[str, Any],
    consumed: Mapping[str, float],
    description: str,
    source_modules: Iterable[int],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "system": system,
        "action_type": action_type,
        "state_patch": deepcopy(dict(patch)),
        "consumed_items": {str(key): float(value) for key, value in consumed.items() if _number(value) > 0},
        "required_items": {str(key): float(value) for key, value in consumed.items() if _number(value) > 0},
        "refunded_items": {},
        "costs": [
            {"resource_id": str(key), "amount": float(value)}
            for key, value in consumed.items()
            if _number(value) > 0
        ],
        "description": description,
        "confidence": "exact",
        "supported": True,
        "source": "user-supplied sIO runtime",
        "source_modules": list(source_modules),
        "metadata": {
            "exact_after_state": True,
            "cumulative_frontier": True,
            **dict(metadata),
        },
    }


def _heroes(profile: Mapping[str, Any]) -> dict[str, Any]:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    raw = _unwrap(sio.get("heroes") or profile.get("heroes") or {})
    return deepcopy(dict(raw)) if isinstance(raw, Mapping) else {}


def generate_survivor_frontiers(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    heroes = _heroes(profile)
    actions: list[dict[str, Any]] = []
    costs, cores = DATA["pA"], DATA["on"]
    for name, state in heroes.items():
        if not isinstance(state, Mapping):
            continue
        current = int(_number(state.get("stars")))
        definition = SIO_SURVIVOR_DATA["heroes"].get(name, {})
        rarity = str(definition.get("rarity") or "")
        if rarity not in costs or current < 0 or current >= len(costs[rarity]):
            continue
        for target in range(current + 1, len(costs[rarity])):
            consumed: dict[str, float] = {}
            shard_delta = _number(costs[rarity][target]) - _number(costs[rarity][current])
            core_delta = _number(cores[rarity][target]) - _number(cores[rarity][current])
            if shard_delta > 0:
                consumed[
                    "s_survivor_shard" if rarity == "S" else f"survivor_shard:{_slug(str(name))}"
                ] = shard_delta
            if core_delta > 0:
                consumed["awakening_core"] = core_delta
            patched = deepcopy(heroes)
            patched[name] = {**dict(state), "stars": target}
            actions.append(
                _action(
                    action_id=f"survivor:frontier:{_slug(str(name))}:{target}",
                    system="survivor",
                    action_type="upgrade_survivor_star_frontier",
                    patch={"sio_ce": {"heroes": patched}},
                    consumed=consumed,
                    description=f"Upgrade {name} from star {current} directly to star {target}.",
                    source_modules=[70941, 32085],
                    metadata={
                        "survivor": str(name),
                        "rarity": rarity,
                        "current_stars": current,
                        "target_stars": target,
                    },
                )
            )

    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    meta = _unwrap(sio.get("meta") or profile.get("meta") or {})
    if isinstance(meta, Mapping) and meta.get("synergy"):
        current = int(_number(meta.get("synergyLevel")))
        if 0 <= current < len(costs["synergy"]):
            for target in range(current + 1, len(costs["synergy"])):
                consumed: dict[str, float] = {}
                shard_delta = _number(costs["synergy"][target]) - _number(costs["synergy"][current])
                core_delta = _number(cores["synergy"][target]) - _number(cores["synergy"][current])
                if shard_delta > 0:
                    consumed["s_survivor_shard"] = shard_delta
                if core_delta > 0:
                    consumed["awakening_core"] = core_delta
                patched_meta = deepcopy(dict(meta))
                patched_meta["synergyLevel"] = target
                actions.append(
                    _action(
                        action_id=f"survivor:synergy_frontier:{target}",
                        system="survivor",
                        action_type="upgrade_survivor_synergy_frontier",
                        patch={"sio_ce": {"meta": patched_meta}},
                        consumed=consumed,
                        description=f"Upgrade Survivor Synergy from {current} directly to {target}.",
                        source_modules=[70941, 32085],
                        metadata={"current_level": current, "target_level": target},
                    )
                )
    return actions


def generate_pet_frontiers(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
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
        cost_table = DATA["pA"].get(pet_type)
        core_table = DATA["on"].get(pet_type)
        if not cost_table or not core_table or current < 0 or current >= len(cost_table):
            continue
        for target in range(current + 1, len(cost_table)):
            consumed: dict[str, float] = {}
            crystal_delta = _number(cost_table[target]) - _number(cost_table[current])
            core_delta = _number(core_table[target]) - _number(core_table[current])
            if crystal_delta > 0:
                consumed[
                    "xeno_pet_crystal" if pet_type == "Xeno" else "pet_awakening_crystal"
                ] = crystal_delta
            if core_delta > 0:
                consumed[
                    "xeno_pet_core" if pet_type == "Xeno" else "pet_awakening_core"
                ] = core_delta
            patched_pets = deepcopy(dict(pets))
            patched_stars = deepcopy(dict(stars))
            patched_stars[name] = target
            patched_pets["stars"] = patched_stars
            actions.append(
                _action(
                    action_id=f"pets:frontier:{_slug(str(name))}:{target}",
                    system="pets",
                    action_type="upgrade_pet_star_frontier",
                    patch={"sio_ce": {"pets": patched_pets}},
                    consumed=consumed,
                    description=f"Upgrade {name} from star {current} directly to star {target}.",
                    source_modules=[39759, 32085],
                    metadata={
                        "pet": str(name),
                        "pet_type": pet_type,
                        "current_stars": current,
                        "target_stars": target,
                    },
                )
            )
    return actions


def generate_mount_frontiers(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    mounts = sio.get("mounts") if isinstance(sio.get("mounts"), Mapping) else profile.get("mounts")
    if not isinstance(mounts, Mapping):
        return []
    data = mounts.get("data") if isinstance(mounts.get("data"), Mapping) else mounts
    rarity_by_name = {
        "Doomsteed": "Legend",
        "Tech Hoverboard": "Excellent",
        "Electric Scooter": "Better",
    }
    actions: list[dict[str, Any]] = []
    for raw_name, state in data.items():
        if raw_name == "active" or not isinstance(state, Mapping) or not state.get("enabled"):
            continue
        name = MOUNT_ALIASES.get(str(raw_name), str(raw_name))
        rarity = rarity_by_name.get(name)
        if not rarity:
            continue
        current = int(_number(state.get("stars")))
        shard_table = DATA["nq"].get(rarity)
        core_table = DATA["SG"].get(rarity)
        if not shard_table or not core_table or current < 0 or current >= len(shard_table):
            continue
        for target in range(current + 1, len(shard_table)):
            consumed = {
                f"{_slug(name)}_shard": _number(shard_table[target]) - _number(shard_table[current])
            }
            core_delta = _number(core_table[target]) - _number(core_table[current])
            if core_delta > 0:
                consumed["mount_core"] = core_delta
            patched_mounts = deepcopy(dict(mounts))
            patched_data = deepcopy(dict(data))
            patched_data[raw_name] = {**dict(state), "stars": target}
            patched_mounts["data"] = patched_data
            actions.append(
                _action(
                    action_id=f"mounts:frontier:{_slug(name)}:{target}",
                    system="mounts",
                    action_type="upgrade_mount_frontier",
                    patch={"mounts": patched_mounts},
                    consumed=consumed,
                    description=f"Upgrade {name} from star {current} directly to star {target}.",
                    source_modules=[40514, 51642, 32085],
                    metadata={
                        "mount": name,
                        "rarity": rarity,
                        "current_stars": current,
                        "target_stars": target,
                    },
                )
            )
    return actions


def _part_resource(state: Mapping[str, Any]) -> str | None:
    value = state.get("part_resource_id") or state.get("tech_part_resource_id")
    return str(value) if value else None


def generate_tech_frontiers(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    techs = exact_tech_state(profile)
    actions: list[dict[str, Any]] = []
    for name, state in techs.items():
        if state.get("deployed") is False:
            continue
        tech_type = str(state.get("tech_type") or TECH_TYPES.get(name) or "")
        if tech_type not in MULTIPLIER_CHIPS:
            continue
        multiplier = round(_number(state.get("mult", state.get("multiplier", 1.0)), 1.0), 1)
        multiplier_table = MULTIPLIER_CHIPS[tech_type]
        if multiplier in multiplier_table:
            current_chips = _number(multiplier_table[multiplier])
            part_resource = _part_resource(state)
            for target in sorted(value for value in multiplier_table if value > multiplier):
                target_chips = _number(multiplier_table[target])
                part_delta = _number(MULTIPLIER_EXTRA_PARTS.get(int(target_chips), 0)) - _number(
                    MULTIPLIER_EXTRA_PARTS.get(int(current_chips), 0)
                )
                if part_delta > 0 and not part_resource:
                    continue
                consumed: dict[str, float] = {}
                if target_chips > current_chips:
                    consumed["resonance_chip"] = target_chips - current_chips
                if part_delta > 0 and part_resource:
                    consumed[part_resource] = part_delta
                patched = deepcopy(techs)
                patched[name] = {**dict(state), "mult": target, "multiplier": target}
                actions.append(
                    _action(
                        action_id=f"tech:multiplier_frontier:{_slug(name)}:{target:g}",
                        system="tech_parts",
                        action_type="upgrade_resonance_multiplier_frontier",
                        patch={"sio_ce": {"techs": patched}},
                        consumed=consumed,
                        description=f"Increase {name} multiplier from {multiplier:g} directly to {target:g}.",
                        source_modules=[19426, 13024, 32085],
                        metadata={
                            "tech": name,
                            "tech_type": tech_type,
                            "current_multiplier": multiplier,
                            "target_multiplier": target,
                            "cumulative_chip_before": current_chips,
                            "cumulative_chip_after": target_chips,
                        },
                    )
                )

        current_overload = int(_number(state.get("overload", 0)))
        resonance = _number(state.get("resonance", 0))
        part_resource = _part_resource(state)
        if 0 <= current_overload < len(OVERLOAD_CHIPS):
            for target in range(current_overload + 1, len(OVERLOAD_CHIPS)):
                if resonance < _number(OVERLOAD_RESONANCE_THRESHOLDS[target]):
                    continue
                part_delta = _number(OVERLOAD_EXTRA_PARTS[target]) - _number(
                    OVERLOAD_EXTRA_PARTS[current_overload]
                )
                if part_delta > 0 and not part_resource:
                    continue
                consumed: dict[str, float] = {}
                chip_delta = _number(OVERLOAD_CHIPS[target]) - _number(OVERLOAD_CHIPS[current_overload])
                if chip_delta > 0:
                    consumed["resonance_chip"] = chip_delta
                if part_delta > 0 and part_resource:
                    consumed[part_resource] = part_delta
                patched = deepcopy(techs)
                patched[name] = {**dict(state), "overload": target}
                actions.append(
                    _action(
                        action_id=f"tech:overload_frontier:{_slug(name)}:{target}",
                        system="tech_parts",
                        action_type="upgrade_resonance_overload_frontier",
                        patch={"sio_ce": {"techs": patched}},
                        consumed=consumed,
                        description=f"Increase {name} Overload from {current_overload} directly to {target}.",
                        source_modules=[19426, 13024, 32085],
                        metadata={
                            "tech": name,
                            "tech_type": tech_type,
                            "current_overload": current_overload,
                            "target_overload": target,
                            "required_resonance": OVERLOAD_RESONANCE_THRESHOLDS[target],
                            "current_resonance": resonance,
                        },
                    )
                )
    return actions


def generate_progression_frontiers(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = [
        *generate_survivor_frontiers(profile),
        *generate_pet_frontiers(profile),
        *generate_mount_frontiers(profile),
        *generate_tech_frontiers(profile),
    ]
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for action in result:
        key = repr((action.get("state_patch"), action.get("consumed_items")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(action)
    return sorted(unique, key=lambda row: str(row.get("action_id")))


__all__ = [
    "generate_mount_frontiers",
    "generate_pet_frontiers",
    "generate_progression_frontiers",
    "generate_survivor_frontiers",
    "generate_tech_frontiers",
]
