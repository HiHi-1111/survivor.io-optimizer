from __future__ import annotations

import math
from pathlib import Path

from optimizer.sio_tetris import (
    MOUNT_BOARD_SIZES,
    PIECE_ROTATIONS,
    PIECE_TYPES,
    inventory_combination_count,
    inventory_combinations,
    legal_placements,
    solve_mount_puzzle,
    solve_tetris,
)


def test_exact_piece_types_rotations_and_mount_boards() -> None:
    assert PIECE_TYPES == ("I", "O", "T", "J", "L")
    assert {piece: len(PIECE_ROTATIONS[piece]) for piece in PIECE_TYPES} == {
        "I": 2,
        "O": 1,
        "T": 4,
        "J": 4,
        "L": 4,
    }
    assert MOUNT_BOARD_SIZES == {
        "Electric Scooter": (7, 8),
        "Tech Hoverboard": (9, 8),
        "Doomsteed": (12, 8),
    }
    assert "S" not in PIECE_ROTATIONS and "Z" not in PIECE_ROTATIONS


def test_inventory_is_counted_as_multiset_combinations_not_permutations() -> None:
    counts = {piece: 2 for piece in PIECE_TYPES}
    assert inventory_combination_count(counts) == 3**5 == 243
    unique_order_permutations = math.factorial(10) // (math.factorial(2) ** 5)
    assert unique_order_permutations == 113400
    assert inventory_combination_count(counts) < unique_order_permutations
    assert len(list(inventory_combinations(counts))) == 243


def test_solver_source_never_uses_permutation_enumeration() -> None:
    source = Path(__file__).resolve().parents[1] / "optimizer" / "sio_tetris.py"
    text = source.read_text(encoding="utf-8")
    assert "itertools import permutations" not in text
    assert "permutations(" not in text
    assert "fixed_type_multiset_placement_combinations" in text


def test_legal_placements_are_unique_masks() -> None:
    for piece in PIECE_TYPES:
        placements = legal_placements(7, 8, piece)
        assert placements
        assert len({placement.mask for placement in placements}) == len(placements)


def test_small_board_solver_matches_full_rows_then_piece_count() -> None:
    one_row = solve_tetris(4, 1, {"I": 1}, max_states=1000)
    assert one_row["complete"] is True
    assert one_row["full"] == 1
    assert one_row["placed_count"] == 1

    two_rows = solve_tetris(4, 2, {"O": 2}, max_states=10000)
    assert two_rows["complete"] is True
    assert two_rows["full"] == 2
    assert two_rows["placed_count"] == 2
    assert len(two_rows["placements"]) == 2
    assert len({(row["row"], row["col"]) for row in two_rows["placements"]}) == 2


def test_mount_wrapper_uses_combination_search_and_discloses_no_worker_parity() -> None:
    result = solve_mount_puzzle("electric_scooter", {"I": 1}, max_states=100)
    assert result["mount"] == "Electric Scooter"
    assert result["search_model"] == "fixed_type_multiset_placement_combinations"
    assert result["worker_parity"] is False
