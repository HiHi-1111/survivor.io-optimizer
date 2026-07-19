"""Canonical multiset search helpers for order-independent Survivor.io choices.

These helpers intentionally enumerate count vectors, not ordered pick sequences.
They are used for selector/choice chests, identical inventory items, and any other
choice where selecting A then B is the same state as selecting B then A.

Do not use them when roles are genuinely directional, such as moving resources
from one equipment slot to a different target slot.
"""
from __future__ import annotations

import json
import math
from typing import Any, Iterable, Iterator, Mapping, Sequence


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def canonical_option_ids(options: Iterable[Any]) -> tuple[str, ...]:
    """Return deterministic unique option identifiers.

    Duplicate labels are collapsed because they describe the same selectable
    outcome. Callers that have distinct outcomes must give them distinct IDs.
    """
    return tuple(sorted({str(option) for option in options}))


def multiset_combination_count(option_count: int, picks: int) -> int:
    """Count unordered selections with replacement.

    For three options and three selector chests this is C(5, 3) = 10, not
    3**3 = 27 ordered pick sequences.
    """
    option_count = _nonnegative_int(option_count)
    picks = _nonnegative_int(picks)
    if option_count == 0:
        return int(picks == 0)
    return math.comb(option_count + picks - 1, picks)


def bounded_multiset_allocations(
    options: Iterable[Any],
    picks: int,
    *,
    capacities: Mapping[str, Any] | None = None,
) -> Iterator[dict[str, int]]:
    """Yield each unique count allocation exactly once.

    The search walks a fixed canonical option order and chooses a count for each
    option. It never constructs ordered sequences and then deduplicates them.
    """
    option_ids = canonical_option_ids(options)
    picks = _nonnegative_int(picks)
    limits = {
        option: _nonnegative_int((capacities or {}).get(option, picks))
        for option in option_ids
    }

    def visit(index: int, remaining: int, counts: list[int]) -> Iterator[dict[str, int]]:
        if index == len(option_ids):
            if remaining == 0:
                yield {
                    option: count
                    for option, count in zip(option_ids, counts)
                    if count
                }
            return
        option = option_ids[index]
        maximum = min(remaining, limits[option])
        if index == len(option_ids) - 1:
            if remaining <= maximum:
                yield from visit(index + 1, 0, [*counts, remaining])
            return
        for count in range(maximum + 1):
            yield from visit(index + 1, remaining - count, [*counts, count])

    if not option_ids:
        if picks == 0:
            yield {}
        return
    yield from visit(0, picks, [])


def allocation_key(allocation: Mapping[str, Any]) -> tuple[tuple[str, int], ...]:
    """Canonical hashable identity for an unordered allocation."""
    return tuple(
        sorted(
            (str(option), _nonnegative_int(count))
            for option, count in allocation.items()
            if _nonnegative_int(count)
        )
    )


def allocation_slug(allocation: Mapping[str, Any]) -> str:
    key = allocation_key(allocation)
    return "__".join(f"{option}x{count}" for option, count in key) or "empty"


def canonical_json(value: Any) -> str:
    """Stable structural identity used to remove equivalent generated actions."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def deduplicate_allocations(
    allocations: Iterable[Mapping[str, Any]],
) -> list[dict[str, int]]:
    seen: set[tuple[tuple[str, int], ...]] = set()
    result: list[dict[str, int]] = []
    for allocation in allocations:
        key = allocation_key(allocation)
        if key in seen:
            continue
        seen.add(key)
        result.append(dict(key))
    return result


__all__ = [
    "allocation_key",
    "allocation_slug",
    "bounded_multiset_allocations",
    "canonical_json",
    "canonical_option_ids",
    "deduplicate_allocations",
    "multiset_combination_count",
]
