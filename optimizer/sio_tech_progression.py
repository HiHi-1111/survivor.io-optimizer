"""Exact sIO Tech multiplier and Resonance Overload progression actions.

The cumulative chip/part tables are exported from sIO module 32085 and the
resource accounting rule is the one used by module 19426. A Tech-part cost is
emitted only when the profile supplies the exact ``part_resource_id`` for that
Tech; the optimizer never assumes that a generic or wrong-type Tech part may be
consumed.
"""
from __future__ import annotations

from copy import deepcopy
import math
import re
from typing import Any, Mapping

TECH_TYPES = {
    "Energy Guidance System": "twin",
    "Antimatter Maintainer": "twin",
    "Quantum Nanobot": "twin",
    "Phase Driver": "twin",
    "Exo-radicator": "twin",
    "Energy Diffuser": "atk",
    "Hi-Maintainer": "def",
    "Precision Device": "atk",
    "Antimatter Generator": "atk",
    "Hi-Gravity Pulser": "twin",
}

# Exact module 32085.nk export: cumulative multiplier-chip spend.
MULTIPLIER_CHIPS = {
    "atk": {
        1.0: 0, 1.2: 1, 1.4: 2, 1.6: 4, 1.8: 7, 2.0: 12,
        2.2: 17, 2.4: 24, 2.6: 33, 2.8: 45, 3.0: 60,
    },
    "def": {
        1.0: 0, 1.2: 1, 1.4: 2, 1.6: 4, 1.8: 7, 2.0: 12,
        2.2: 17, 2.4: 24, 2.6: 33, 2.8: 45, 3.0: 60,
    },
    "twin": {
        1.0: 0, 1.2: 1, 1.4: 2, 1.6: 4, 1.8: 6, 2.0: 9,
        2.2: 12, 2.4: 16, 2.6: 20, 2.8: 25, 3.0: 30,
        3.2: 36, 3.4: 42, 3.6: 48, 3.8: 54, 4.0: 60,
        4.2: 66, 4.4: 72, 4.6: 78, 4.8: 84, 5.0: 90,
    },
}

# Exact module 32085.jc export: cumulative overload-chip spend at levels 0..18.
OVERLOAD_CHIPS = (0, 1, 2, 3, 5, 7, 9, 12, 15, 18, 22, 26, 30, 35, 40, 45, 50, 55, 60)

# Exact module 32085.Fd export: cumulative extra matching Tech parts.
OVERLOAD_EXTRA_PARTS = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6)

# Exact module 32085.gs export: extra matching parts from multiplier chips.
MULTIPLIER_EXTRA_PARTS = {
    0: 0, 1: 0, 2: 0, 4: 0, 6: 0, 9: 0, 12: 0, 16: 0,
    20: 0, 25: 0, 30: 0, 36: 1, 42: 2, 48: 3, 54: 4,
    60: 5, 66: 6, 72: 7, 78: 8, 84: 9, 90: 10,
}

# Exact module 32085.sm export. The supplied bundle publishes legal resonance
# gates through Overload 16. Levels 17 and 18 have chip/part rows but no gate in
# this bundle, so they are represented as unreachable rather than guessed.
OVERLOAD_RESONANCE_THRESHOLDS = (
    0, 900, 1200, 1650, 2100, 2550, 3000, 3500, 4500,
    5000, 6000, 7500, 9000, 10500, 12000, 13500, 15000,
    math.inf, math.inf,
)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _unwrap(value: Any) -> Any:
    if isinstance(value, Mapping) and isinstance(value.get("data"), Mapping):
        return value["data"]
    return value


def exact_tech_state(profile: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    explicit = sio.get("tech_input")
    if isinstance(explicit, Mapping) and isinstance(explicit.get("techs"), Mapping):
        raw = explicit["techs"]
    else:
        raw = _unwrap(sio.get("techs") or profile.get("techs") or {})
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(name): deepcopy(dict(state))
        for name, state in raw.items()
        if isinstance(state, Mapping)
    }


def _current_multiplier(state: Mapping[str, Any]) -> float:
    return round(_num(state.get("mult", state.get("multiplier", state.get("supportParts", 1.0))), 1.0), 1)


def _part_resource(state: Mapping[str, Any]) -> str | None:
    value = state.get("part_resource_id") or state.get("tech_part_resource_id")
    return str(value) if value else None


def _make_action(
    *, action_id: str, action_type: str, techs: Mapping[str, Any],
    consumed: Mapping[str, float], description: str, metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "system": "tech_parts",
        "action_type": action_type,
        "state_patch": {"sio_ce": {"techs": deepcopy(dict(techs))}},
        "consumed_items": dict(consumed),
        "required_items": dict(consumed),
        "refunded_items": {},
        "costs": [{"resource_id": key, "amount": value} for key, value in consumed.items()],
        "description": description,
        "confidence": "exact",
        "supported": True,
        "source": "user-supplied sIO runtime",
        "source_modules": [19426, 13024, 32085],
        "metadata": {"exact_after_state": True, **dict(metadata)},
    }


def generate_tech_progression_actions(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    techs = exact_tech_state(profile)
    actions: list[dict[str, Any]] = []
    for name, state in techs.items():
        tech_type = str(state.get("tech_type") or TECH_TYPES.get(name) or "")
        if tech_type not in MULTIPLIER_CHIPS or state.get("deployed") is False:
            continue
        current_multiplier = _current_multiplier(state)
        multipliers = sorted(MULTIPLIER_CHIPS[tech_type])
        try:
            index = multipliers.index(current_multiplier)
        except ValueError:
            index = -1
        if 0 <= index < len(multipliers) - 1:
            target_multiplier = multipliers[index + 1]
            current_chips = MULTIPLIER_CHIPS[tech_type][current_multiplier]
            target_chips = MULTIPLIER_CHIPS[tech_type][target_multiplier]
            chip_delta = target_chips - current_chips
            part_delta = MULTIPLIER_EXTRA_PARTS.get(target_chips, 0) - MULTIPLIER_EXTRA_PARTS.get(current_chips, 0)
            consumed: dict[str, float] = {}
            if chip_delta:
                consumed["resonance_chip"] = chip_delta
            part_resource = _part_resource(state)
            if not part_delta or part_resource:
                if part_delta:
                    consumed[str(part_resource)] = part_delta
                patched = deepcopy(techs)
                patched[name] = {**state, "mult": target_multiplier, "multiplier": target_multiplier}
                actions.append(_make_action(
                    action_id=f"tech:multiplier:{_slug(name)}:{target_multiplier:g}",
                    action_type="upgrade_resonance_multiplier",
                    techs=patched,
                    consumed=consumed,
                    description=f"Increase {name} resonance multiplier from {current_multiplier:g} to {target_multiplier:g}.",
                    metadata={
                        "tech": name,
                        "tech_type": tech_type,
                        "current_multiplier": current_multiplier,
                        "target_multiplier": target_multiplier,
                        "cumulative_chip_before": current_chips,
                        "cumulative_chip_after": target_chips,
                    },
                ))

        current_overload = int(_num(state.get("overload", 0)))
        target_overload = current_overload + 1
        resonance = _num(state.get("resonance", 0))
        if (
            target_overload < len(OVERLOAD_CHIPS)
            and target_overload < len(OVERLOAD_RESONANCE_THRESHOLDS)
            and resonance >= OVERLOAD_RESONANCE_THRESHOLDS[target_overload]
        ):
            chip_delta = OVERLOAD_CHIPS[target_overload] - OVERLOAD_CHIPS[current_overload]
            part_delta = OVERLOAD_EXTRA_PARTS[target_overload] - OVERLOAD_EXTRA_PARTS[current_overload]
            consumed: dict[str, float] = {}
            if chip_delta:
                consumed["resonance_chip"] = chip_delta
            part_resource = _part_resource(state)
            if part_delta and not part_resource:
                continue
            if part_delta:
                consumed[str(part_resource)] = part_delta
            patched = deepcopy(techs)
            patched[name] = {**state, "overload": target_overload}
            actions.append(_make_action(
                action_id=f"tech:overload:{_slug(name)}:{target_overload}",
                action_type="upgrade_resonance_overload",
                techs=patched,
                consumed=consumed,
                description=f"Increase {name} Resonance Overload to level {target_overload}.",
                metadata={
                    "tech": name,
                    "tech_type": tech_type,
                    "current_overload": current_overload,
                    "target_overload": target_overload,
                    "required_resonance": OVERLOAD_RESONANCE_THRESHOLDS[target_overload],
                    "current_resonance": resonance,
                },
            ))
    return actions


__all__ = [
    "MULTIPLIER_CHIPS",
    "MULTIPLIER_EXTRA_PARTS",
    "OVERLOAD_CHIPS",
    "OVERLOAD_EXTRA_PARTS",
    "OVERLOAD_RESONANCE_THRESHOLDS",
    "TECH_TYPES",
    "exact_tech_state",
    "generate_tech_progression_actions",
]
