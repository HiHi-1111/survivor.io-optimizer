"""Expand exact actions with selector/choice-chest resource combinations.

A choice chest is order-independent: choosing Eternal then Void is the same
inventory transition as choosing Void then Eternal. This module enumerates
multiset count allocations directly and never creates ordered pick sequences.

The profile must supply the exact chest options and units. No reward conversion
is guessed. Supported input shape, at the profile root or under ``sio_ce``::

    "choice_chests": {
        "core_selector_chest": {
            "count": 3,
            "options": {
                "eternal_core": 1,
                "void_core": 1,
                "chaos_core": 1
            }
        }
    }

``count`` may be omitted when the chest is already present in normal resources.
Only allocations that exactly cover shortages are emitted, so no unrepresented
leftover reward is silently discarded.
"""
from __future__ import annotations

from copy import deepcopy
import math
import re
from typing import Any, Iterable, Mapping

from optimizer.sio_combinations import (
    allocation_key,
    allocation_slug,
    bounded_multiset_allocations,
    canonical_json,
)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _choice_chest_section(profile: Mapping[str, Any]) -> Any:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    inventory = profile.get("inventory") if isinstance(profile.get("inventory"), Mapping) else {}
    return (
        sio.get("choice_chests")
        or sio.get("selector_chests")
        or profile.get("choice_chests")
        or profile.get("selector_chests")
        or inventory.get("choice_chests")
        or inventory.get("selector_chests")
        or {}
    )


def normalize_choice_chests(
    profile: Mapping[str, Any],
    available_resources: Mapping[str, float],
) -> list[dict[str, Any]]:
    """Return source-supplied exact chest specifications in stable order."""
    raw = _choice_chest_section(profile)
    rows: list[tuple[str, Any]] = []
    if isinstance(raw, Mapping):
        rows = [(str(key), value) for key, value in raw.items()]
    elif isinstance(raw, list):
        rows = [
            (str(value.get("resource_id") or value.get("chest_id") or f"choice_chest_{index}"), value)
            for index, value in enumerate(raw)
            if isinstance(value, Mapping)
        ]

    result: list[dict[str, Any]] = []
    for default_id, raw_row in rows:
        if not isinstance(raw_row, Mapping):
            continue
        chest_id = str(raw_row.get("resource_id") or raw_row.get("chest_id") or default_id)
        options_raw = raw_row.get("options") or raw_row.get("rewards") or {}
        options: dict[str, float] = {}
        if isinstance(options_raw, Mapping):
            for resource_id, units_raw in options_raw.items():
                units = _number(
                    units_raw.get("amount", units_raw.get("units", units_raw.get("count", 0)))
                    if isinstance(units_raw, Mapping)
                    else units_raw
                )
                if units > 0:
                    options[str(resource_id)] = units
        elif isinstance(options_raw, list):
            for option in options_raw:
                if not isinstance(option, Mapping):
                    continue
                resource_id = option.get("resource_id") or option.get("id")
                units = _number(option.get("amount", option.get("units", option.get("count", 0))))
                if resource_id is not None and units > 0:
                    options[str(resource_id)] = units
        if not options:
            continue
        supplied_count = _number(raw_row.get("count", raw_row.get("quantity", 0)))
        available_count = _number(available_resources.get(chest_id, 0.0))
        count = int(max(0.0, available_count if available_count > 0 else supplied_count))
        if count <= 0:
            continue
        result.append(
            {
                "resource_id": chest_id,
                "count": count,
                "options": dict(sorted(options.items())),
                "source_exact": True,
            }
        )
    return sorted(result, key=lambda row: row["resource_id"])


def _missing_resources(
    action: Mapping[str, Any],
    available: Mapping[str, float],
) -> dict[str, float]:
    consumed = action.get("consumed_items") if isinstance(action.get("consumed_items"), Mapping) else {}
    refunded = action.get("refunded_items") if isinstance(action.get("refunded_items"), Mapping) else {}
    return {
        str(resource): round(required - available.get(str(resource), 0.0) - _number(refunded.get(resource)), 9)
        for resource, raw_required in consumed.items()
        if (required := _number(raw_required))
        > available.get(str(resource), 0.0) + _number(refunded.get(resource)) + 1e-9
    }


def _allocations_for_chest(chest: Mapping[str, Any]) -> list[dict[str, Any]]:
    options = chest["options"]
    rows: list[dict[str, Any]] = [
        {"chests": {}, "grants": {}, "option_counts": {}}
    ]
    for used in range(1, int(chest["count"]) + 1):
        for allocation in bounded_multiset_allocations(options, used):
            grants = {
                resource: round(count * _number(options[resource]), 9)
                for resource, count in allocation.items()
                if count
            }
            rows.append(
                {
                    "chests": {str(chest["resource_id"]): used},
                    "grants": grants,
                    "option_counts": {str(chest["resource_id"]): dict(allocation_key(allocation))},
                }
            )
    return rows


def _combine_chest_allocations(chests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    combined = [{"chests": {}, "grants": {}, "option_counts": {}}]
    for chest in chests:
        next_rows: list[dict[str, Any]] = []
        for left in combined:
            for right in _allocations_for_chest(chest):
                row = {
                    "chests": {**left["chests"], **right["chests"]},
                    "grants": dict(left["grants"]),
                    "option_counts": {**left["option_counts"], **right["option_counts"]},
                }
                for resource, amount in right["grants"].items():
                    row["grants"][resource] = round(row["grants"].get(resource, 0.0) + amount, 9)
                next_rows.append(row)
        combined = next_rows
    return combined


def _exactly_covers(grants: Mapping[str, float], missing: Mapping[str, float]) -> bool:
    relevant = set(grants) | set(missing)
    return all(abs(_number(grants.get(key)) - _number(missing.get(key))) <= 1e-9 for key in relevant)


def expand_actions_with_choice_chests(
    profile: Mapping[str, Any],
    actions: Iterable[Mapping[str, Any]],
    available_resources: Mapping[str, float],
) -> list[dict[str, Any]]:
    """Append legal chest-assisted variants for otherwise unaffordable actions."""
    originals = [deepcopy(dict(action)) for action in actions]
    chests = normalize_choice_chests(profile, available_resources)
    if not chests:
        return originals
    all_allocations = _combine_chest_allocations(chests)
    result = list(originals)
    seen = {
        canonical_json(
            {
                "patch": action.get("state_patch"),
                "consumed": action.get("consumed_items"),
                "refunded": action.get("refunded_items"),
            }
        )
        for action in originals
    }

    for action in originals:
        missing = _missing_resources(action, available_resources)
        if not missing:
            continue
        coverable = {resource for chest in chests for resource in chest["options"]}
        if set(missing) - coverable:
            continue
        feasible = [row for row in all_allocations if _exactly_covers(row["grants"], missing)]
        if not feasible:
            continue
        minimum_used = min(sum(row["chests"].values()) for row in feasible)
        feasible = [row for row in feasible if sum(row["chests"].values()) == minimum_used]
        for allocation in feasible:
            gross = {
                str(resource): _number(amount)
                for resource, amount in (action.get("consumed_items") or {}).items()
            }
            net = {
                resource: round(max(0.0, amount - _number(allocation["grants"].get(resource))), 9)
                for resource, amount in gross.items()
            }
            net = {resource: amount for resource, amount in net.items() if amount > 1e-9}
            for chest_id, count in allocation["chests"].items():
                if count:
                    net[chest_id] = net.get(chest_id, 0.0) + float(count)
            variant = deepcopy(action)
            suffix = "--".join(
                f"{_slug(chest_id)}-{allocation_slug(option_counts)}"
                for chest_id, option_counts in sorted(allocation["option_counts"].items())
                if option_counts
            )
            variant["action_id"] = f"{action.get('action_id')}:choice:{suffix}"
            variant["gross_required_items"] = gross
            variant["consumed_items"] = net
            variant["required_items"] = dict(net)
            variant["choice_chest_grants"] = dict(allocation["grants"])
            variant["costs"] = [
                {"resource_id": resource, "amount": amount}
                for resource, amount in sorted(net.items())
            ]
            metadata = dict(variant.get("metadata") or {})
            metadata.update(
                {
                    "choice_chest_allocation": allocation["option_counts"],
                    "choice_chests_used": allocation["chests"],
                    "choice_chest_grants": allocation["grants"],
                    "combination_search": True,
                    "permutation_search": False,
                    "exact_shortage_coverage": True,
                }
            )
            variant["metadata"] = metadata
            variant["description"] = (
                f"{action.get('description', 'Apply exact action')} Use selector chests as the canonical "
                "unordered allocation shown in metadata."
            )
            key = canonical_json(
                {
                    "patch": variant.get("state_patch"),
                    "consumed": variant.get("consumed_items"),
                    "refunded": variant.get("refunded_items"),
                }
            )
            if key in seen:
                continue
            seen.add(key)
            result.append(variant)
    return result


__all__ = [
    "expand_actions_with_choice_chests",
    "normalize_choice_chests",
]
