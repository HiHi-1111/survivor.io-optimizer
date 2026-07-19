from __future__ import annotations

from optimizer.sio_combinations import (
    allocation_key,
    bounded_multiset_allocations,
    deduplicate_allocations,
    multiset_combination_count,
)


def test_three_selector_chests_over_three_rewards_use_ten_combinations_not_twenty_seven_sequences() -> None:
    rows = list(bounded_multiset_allocations(["eternal", "void", "chaos"], 3))
    assert multiset_combination_count(3, 3) == 10
    assert len(rows) == 10
    assert len({allocation_key(row) for row in rows}) == 10
    actual = {allocation_key(row) for row in rows}
    assert actual >= {
        allocation_key({"eternal": 3}),
        allocation_key({"void": 3}),
        allocation_key({"chaos": 3}),
        allocation_key({"eternal": 1, "void": 1, "chaos": 1}),
    }


def test_capacity_limits_are_applied_to_count_vectors_not_pick_orders() -> None:
    rows = list(
        bounded_multiset_allocations(
            ["a", "b", "c"],
            3,
            capacities={"a": 1, "b": 2, "c": 3},
        )
    )
    assert rows
    assert all(sum(row.values()) == 3 for row in rows)
    assert all(row.get("a", 0) <= 1 for row in rows)
    assert all(row.get("b", 0) <= 2 for row in rows)
    assert len(rows) == len({allocation_key(row) for row in rows})


def test_equivalent_allocations_deduplicate_regardless_of_mapping_order() -> None:
    rows = deduplicate_allocations(
        [
            {"eternal": 2, "void": 1},
            {"void": 1, "eternal": 2},
            {"eternal": 1, "void": 2},
        ]
    )
    assert rows == [
        {"eternal": 2, "void": 1},
        {"eternal": 1, "void": 2},
    ]
