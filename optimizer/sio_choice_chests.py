"""Expand exact actions with selector/choice-chest resource combinations.

A choice chest is order-independent: choosing Eternal then Void is the same
inventory transition as choosing Void then Eternal. This module searches
canonical multiset count allocations directly and never creates ordered pick
sequences.

The profile must supply exact chest options and reward units. No conversion is
guessed. Only allocations that exactly cover an action's shortages are emitted,
so no unrepresented leftover reward is silently discarded.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import math
import re
from typing import Any, Iterable, Mapping

from optimizer.sio_combinations import allocation_key, allocation_slug, canonical_json

ROUND_DIGITS = 9
EPSILON = 1e-9


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _rounded(value: Any) -> float:
    return round(_number(value), ROUND_DIGITS)


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
            option_rows = options_raw.items()
        elif isinstance(options_raw, list):
            option_rows = (
                (
                    option.get("resource_id") or option.get("id"),
                    option,
                )
                for option in options_raw
                if isinstance(option, Mapping)
            )
        else:
            option_rows = ()
        for resource_id, units_raw in option_rows:
            if resource_id is None:
                continue
            units = _number(
                units_raw.get("amount", units_raw.get("units", units_raw.get("count", 0)))
                if isinstance(units_raw, Mapping)
                else units_raw
            )
            if units > 0:
                options[str(resource_id)] = _rounded(units)
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
    missing: dict[str, float] = {}
    for resource, raw_required in consumed.items():
        key = str(resource)
        required = _number(raw_required)
        shortage = required - _number(available.get(key)) - _number(refunded.get(resource))
        if shortage > EPSILON:
            missing[key] = _rounded(shortage)
    return missing


def _remaining_key(resources: tuple[str, ...], remaining: Mapping[str, float]) -> tuple[float, ...]:
    return tuple(_rounded(remaining.get(resource, 0.0)) for resource in resources)


def _per_chest_exact_contributions(
    chest: Mapping[str, Any],
    resources: tuple[str, ...],
    remaining: tuple[float, ...],
) -> tuple[dict[str, Any], ...]:
    """Enumerate only count allocations that do not exceed current shortages.

    The recursion chooses a count per canonical reward option. It never builds a
    pick-order sequence, and the maximum count for each option is bounded by both
    available chests and the shortage that option can satisfy.
    """
    resource_index = {resource: index for index, resource in enumerate(resources)}
    options = tuple(
        (resource, _number(units))
        for resource, units in sorted((chest.get("options") or {}).items())
        if resource in resource_index and _number(units) > 0
    )
    chest_limit = int(chest.get("count", 0) or 0)
    rows: list[dict[str, Any]] = []

    def visit(
        option_index: int,
        chests_left: int,
        grants: list[float],
        counts: dict[str, int],
    ) -> None:
        if option_index >= len(options):
            used = chest_limit - chests_left
            rows.append(
                {
                    "used": used,
                    "grants": {
                        resource: _rounded(amount)
                        for resource, amount in zip(resources, grants)
                        if amount > EPSILON
                    },
                    "option_counts": dict(allocation_key(counts)),
                }
            )
            return
        resource, units = options[option_index]
        index = resource_index[resource]
        shortage_left = _rounded(remaining[index] - grants[index])
        maximum = min(chests_left, int(math.floor((shortage_left + EPSILON) / units)))
        for count in range(maximum + 1):
            next_grants = list(grants)
            if count:
                next_grants[index] = _rounded(next_grants[index] + count * units)
                counts[resource] = count
            visit(option_index + 1, chests_left - count, next_grants, counts)
            counts.pop(resource, None)

    visit(0, chest_limit, [0.0] * len(resources), {})
    # Structural dedup protects against duplicate aliases with the same exact
    # grant vector while retaining different chest-use counts when meaningful.
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = canonical_json({"used": row["used"], "grants": row["grants"], "counts": row["option_counts"]})
        unique.setdefault(key, row)
    return tuple(unique.values())


def _pareto_allocations(rows: Iterable[dict[str, Any]], chest_ids: tuple[str, ...]) -> list[dict[str, Any]]:
    """Keep allocations not dominated in every chest type.

    This avoids assuming all chest types have equal opportunity cost. An
    allocation is removed only when another exact allocation uses no more of any
    chest type and strictly less of at least one.
    """
    values = list(rows)
    result: list[dict[str, Any]] = []
    for index, row in enumerate(values):
        vector = tuple(int(row["chests"].get(chest_id, 0)) for chest_id in chest_ids)
        dominated = False
        for other_index, other in enumerate(values):
            if index == other_index:
                continue
            other_vector = tuple(int(other["chests"].get(chest_id, 0)) for chest_id in chest_ids)
            if all(left <= right for left, right in zip(other_vector, vector)) and any(
                left < right for left, right in zip(other_vector, vector)
            ):
                dominated = True
                break
        if not dominated:
            result.append(row)
    return result


def exact_cover_allocations(
    chests: list[dict[str, Any]],
    missing: Mapping[str, float],
) -> list[dict[str, Any]]:
    """Find exact, nondominated chest allocations for one shortage vector.

    Dynamic programming is keyed by chest index and remaining resource amounts.
    Therefore unrelated inventory combinations are never generated.
    """
    resources = tuple(sorted(str(resource) for resource in missing))
    target = _remaining_key(resources, missing)
    relevant_chests = [
        chest
        for chest in chests
        if set((chest.get("options") or {})) & set(resources)
    ]
    chest_ids = tuple(str(chest["resource_id"]) for chest in relevant_chests)

    @lru_cache(maxsize=None)
    def solve(chest_index: int, remaining: tuple[float, ...]) -> tuple[dict[str, Any], ...]:
        if all(amount <= EPSILON for amount in remaining):
            return ({"chests": {}, "grants": {}, "option_counts": {}},)
        if chest_index >= len(relevant_chests):
            return ()
        chest = relevant_chests[chest_index]
        rows: list[dict[str, Any]] = []
        for contribution in _per_chest_exact_contributions(chest, resources, remaining):
            next_remaining = tuple(
                _rounded(amount - _number(contribution["grants"].get(resource)))
                for resource, amount in zip(resources, remaining)
            )
            if any(amount < -EPSILON for amount in next_remaining):
                continue
            for suffix in solve(chest_index + 1, next_remaining):
                chest_id = str(chest["resource_id"])
                used = int(contribution["used"])
                row = {
                    "chests": dict(suffix["chests"]),
                    "grants": dict(suffix["grants"]),
                    "option_counts": dict(suffix["option_counts"]),
                }
                if used:
                    row["chests"][chest_id] = used
                    row["option_counts"][chest_id] = contribution["option_counts"]
                for resource, amount in contribution["grants"].items():
                    row["grants"][resource] = _rounded(row["grants"].get(resource, 0.0) + amount)
                rows.append(row)
        unique: dict[str, dict[str, Any]] = {}
        for row in rows:
            unique.setdefault(canonical_json(row), row)
        return tuple(unique.values())

    exact = [row for row in solve(0, target) if _remaining_key(resources, row["grants"]) == target]
    return sorted(
        _pareto_allocations(exact, chest_ids),
        key=lambda row: (
            tuple(int(row["chests"].get(chest_id, 0)) for chest_id in chest_ids),
            canonical_json(row["option_counts"]),
        ),
    )


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
        for allocation in exact_cover_allocations(chests, missing):
            gross = {
                str(resource): _number(amount)
                for resource, amount in (action.get("consumed_items") or {}).items()
            }
            net = {
                resource: _rounded(max(0.0, amount - _number(allocation["grants"].get(resource))))
                for resource, amount in gross.items()
            }
            net = {resource: amount for resource, amount in net.items() if amount > EPSILON}
            for chest_id, count in allocation["chests"].items():
                if count:
                    net[chest_id] = _rounded(net.get(chest_id, 0.0) + float(count))
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
                    "allocation_policy": "exact_cover_pareto_by_chest_type",
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
    "exact_cover_allocations",
    "expand_actions_with_choice_chests",
    "normalize_choice_chests",
]
