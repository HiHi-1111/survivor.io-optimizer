"""Exact Active Pet and Xeno support-role configuration states.

The supplied sIO Pets UI exposes Active Pet as a free selection. For Xeno pets,
module 19425 consumes support row 0 as the active pet's own skills and rows 1+
as named support pets. Each support row's skill list defines its role.

Rows with identical normalized skill lists are interchangeable, so pet names are
chosen as combinations within that role group. Different skill lists are genuine
roles and may receive different pets because their stars scale different effects.
No pet can occupy the active role and a support role at the same time, and support
pet names are unique.
"""
from __future__ import annotations

from copy import deepcopy
from itertools import combinations
import re
from typing import Any, Iterable, Mapping

from optimizer.sio_pets import XENO_NAMES, pet_state

NONE = "None"


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "none"


def _stars(pets: Mapping[str, Any]) -> dict[str, float]:
    raw = pets.get("stars") if isinstance(pets.get("stars"), Mapping) else pets.get("awakened")
    return {str(name): _number(value) for name, value in raw.items()} if isinstance(raw, Mapping) else {}


def owned_pet_candidates(profile: Mapping[str, Any]) -> tuple[str, ...]:
    pets = pet_state(profile)
    stars = _stars(pets)
    current = str(pets.get("active") or pets.get("main_pet") or NONE)
    known = ["Rex", "Croaky", *XENO_NAMES]
    result = [name for name in known if stars.get(name, 0.0) > 0]
    if current != NONE and current not in result:
        result.append(current)
    return tuple(dict.fromkeys(result))


def _skill_signature(row: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(sorted({str(skill) for skill in (row.get("skill") or []) if skill}))


def _support_groups(support: list[Any]) -> tuple[tuple[tuple[str, ...], tuple[int, ...]], ...]:
    by_signature: dict[tuple[str, ...], list[int]] = {}
    for index, row in enumerate(support[1:], start=1):
        if not isinstance(row, Mapping):
            continue
        by_signature.setdefault(_skill_signature(row), []).append(index)
    return tuple(
        (signature, tuple(indices))
        for signature, indices in sorted(by_signature.items(), key=lambda item: (item[0], item[1]))
    )


def _support_assignments(
    groups: tuple[tuple[tuple[str, ...], tuple[int, ...]], ...],
    candidates: tuple[str, ...],
) -> Iterable[dict[int, str]]:
    """Assign unique pets, using combinations for interchangeable role rows."""
    def visit(group_index: int, remaining: tuple[str, ...], assigned: dict[int, str]):
        if group_index >= len(groups):
            yield dict(assigned)
            return
        _signature, indices = groups[group_index]
        size = len(indices)
        if size == 0:
            yield from visit(group_index + 1, remaining, assigned)
            return
        for selected in combinations(remaining, size):
            selected_set = set(selected)
            next_remaining = tuple(name for name in remaining if name not in selected_set)
            # Rows in one signature group are interchangeable; canonical sorted
            # assignment avoids k! permutations of the same exact role group.
            for index, name in zip(sorted(indices), sorted(selected)):
                assigned[index] = name
            yield from visit(group_index + 1, next_remaining, assigned)
            for index in indices:
                assigned.pop(index, None)
    yield from visit(0, tuple(sorted(candidates)), {})


def generate_pet_configuration_actions(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    pets = pet_state(profile)
    if not pets:
        return []
    current_active = str(pets.get("active") or pets.get("main_pet") or NONE)
    candidates = (NONE, *owned_pet_candidates(profile))
    support = deepcopy(pets.get("support")) if isinstance(pets.get("support"), list) else []
    groups = _support_groups(support)
    stars = _stars(pets)
    current_support = tuple(
        str(row.get("name") or NONE)
        for row in support[1:]
        if isinstance(row, Mapping)
    )
    actions: list[dict[str, Any]] = []

    for active in candidates:
        if active in XENO_NAMES:
            support_candidates = tuple(
                name
                for name in XENO_NAMES
                if name != active and stars.get(name, 0.0) > 0
            )
            required = sum(len(indices) for _signature, indices in groups)
            if required > len(support_candidates):
                continue
            assignments = tuple(_support_assignments(groups, support_candidates)) if groups else ({},)
        else:
            assignments = ({},)

        for assignment in assignments:
            patched = deepcopy(pets)
            patched["active"] = None if active == NONE else active
            patched.pop("main_pet", None)
            patched_support = deepcopy(support)
            if active in XENO_NAMES and patched_support:
                if isinstance(patched_support[0], Mapping):
                    patched_support[0] = {**dict(patched_support[0]), "name": active}
                for index, name in assignment.items():
                    patched_support[index] = {**dict(patched_support[index]), "name": name}
                patched["support"] = patched_support
            target_support = tuple(
                str(row.get("name") or NONE)
                for row in patched_support[1:]
                if isinstance(row, Mapping)
            ) if active in XENO_NAMES else current_support
            if active == current_active and target_support == current_support:
                continue
            suffix = f"active-{_slug(active)}"
            if assignment:
                suffix += "--" + "--".join(f"role{index}-{_slug(name)}" for index, name in sorted(assignment.items()))
            actions.append(
                {
                    "action_id": f"pets:configuration:{suffix}",
                    "system": "pets",
                    "action_type": "configure_active_and_support_pets",
                    "state_patch": {"sio_ce": {"pets": patched}},
                    "consumed_items": {},
                    "required_items": {},
                    "refunded_items": {},
                    "costs": [],
                    "description": "Apply the complete Active Pet and Xeno support-role assignment.",
                    "confidence": "exact",
                    "supported": True,
                    "source": "user-supplied sIO runtime",
                    "source_modules": [32085, 37013, 19425, 30396, 88426],
                    "metadata": {
                        "exact_after_state": True,
                        "configuration_frontier": True,
                        "active_pet": active,
                        "support_assignment": {str(index): name for index, name in sorted(assignment.items())},
                        "identical_skill_roles_use_combinations": True,
                        "role_specific_assignment": True,
                        "order_independent_permutation_search": False,
                    },
                }
            )
    return actions


__all__ = [
    "NONE",
    "generate_pet_configuration_actions",
    "owned_pet_candidates",
]
