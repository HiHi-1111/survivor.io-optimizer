"""Exact Twinborn mode configuration frontiers.

The supplied sIO runtime exposes six Twinborn techs, each with exactly two modes.
A tech stores one ``mode`` field, which enforces one active mode per pair. Mode
choices are role-labelled by tech and are therefore a small Cartesian product of
complete states, not permutations of inventory items.

Only techs that already have a recognized Twinborn mode are included. This avoids
inventing unlock legality when the profile does not prove Twinborn is active.
Every generated state is subsequently scored by the exact sIO CE runtime.
"""
from __future__ import annotations

from copy import deepcopy
from itertools import product
import re
from typing import Any, Mapping

from optimizer.sio_tech_progression import exact_tech_state

TWINBORN_MODES: dict[str, tuple[str, str]] = {
    "Energy Guidance System": ("Drone Mode", "Forcefield Mode"),
    "Antimatter Maintainer": ("Drill Shot Mode", "Rocket Mode"),
    "Quantum Nanobot": ("Soccer Mode", "Durian Mode"),
    "Phase Driver": ("Lightning Mode", "Boomerang Mode"),
    "Exo-radicator": ("Guardian Mode", "Laser Mode"),
    "Hi-Gravity Pulser": ("Brick Mode", "Molotov Mode"),
}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def recognized_twinborn_state(profile: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Return deployed Twinborn techs whose current mode proves mode access."""
    techs = exact_tech_state(profile)
    result: dict[str, dict[str, Any]] = {}
    for name, modes in TWINBORN_MODES.items():
        state = techs.get(name)
        if not isinstance(state, Mapping) or state.get("deployed") is False:
            continue
        current = str(state.get("mode") or "")
        if current not in modes:
            continue
        result[name] = deepcopy(dict(state))
    return result


def generate_twinborn_mode_actions(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Generate every distinct complete mode assignment exactly once."""
    current = recognized_twinborn_state(profile)
    if not current:
        return []
    names = tuple(name for name in TWINBORN_MODES if name in current)
    current_assignment = tuple(str(current[name]["mode"]) for name in names)
    actions: list[dict[str, Any]] = []
    for assignment in product(*(TWINBORN_MODES[name] for name in names)):
        if assignment == current_assignment:
            continue
        patched = exact_tech_state(profile)
        changed: dict[str, dict[str, str]] = {}
        for name, target_mode in zip(names, assignment):
            before_mode = str(current[name]["mode"])
            patched[name] = {**dict(patched[name]), "mode": target_mode}
            if target_mode != before_mode:
                changed[name] = {"from": before_mode, "to": target_mode}
        if not changed:
            continue
        suffix = "--".join(f"{_slug(name)}-{_slug(mode)}" for name, mode in zip(names, assignment))
        actions.append(
            {
                "action_id": f"tech:twinborn_modes:{suffix}",
                "system": "tech_parts",
                "action_type": "switch_twinborn_modes",
                "state_patch": {"sio_ce": {"techs": patched}},
                "consumed_items": {},
                "required_items": {},
                "refunded_items": {},
                "costs": [],
                "description": "Apply the listed complete Twinborn mode assignment.",
                "confidence": "exact",
                "supported": True,
                "source": "user-supplied sIO runtime",
                "source_modules": [32085, 37013, 13024],
                "metadata": {
                    "exact_after_state": True,
                    "configuration_frontier": True,
                    "one_mode_per_twinborn_pair": True,
                    "combination_search": True,
                    "permutation_search": False,
                    "assignment": dict(zip(names, assignment)),
                    "changed": changed,
                },
            }
        )
    return actions


__all__ = [
    "TWINBORN_MODES",
    "generate_twinborn_mode_actions",
    "recognized_twinborn_state",
]
