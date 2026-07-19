"""Combination-based mount-puzzle solver mapped from the supplied sIO UI.

The supplied bundle exposes the five tetromino definitions, mount board sizes,
and the worker request/result contract, but omits the actual ``tetris`` and
``mountPuzzles`` worker chunks. This module therefore implements an independent,
deterministic solver and never claims worker parity.

Piece inventory is a multiset. Search processes piece types in a fixed order and
chooses increasing placement indices for repeated copies. It never enumerates
permutations of identical pieces or piece-order sequences.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import product
import math
from typing import Any, Iterable, Mapping, Sequence

PIECE_TYPES = ("I", "O", "T", "J", "L")

# Exact rotations exposed by the supplied sIO UI chunk. Coordinates are row/col.
PIECE_ROTATIONS: dict[str, tuple[tuple[tuple[int, int], ...], ...]] = {
    "I": (
        ((0, 0), (0, 1), (0, 2), (0, 3)),
        ((0, 0), (1, 0), (2, 0), (3, 0)),
    ),
    "O": (
        ((0, 0), (0, 1), (1, 0), (1, 1)),
    ),
    "T": (
        ((0, 1), (1, 0), (1, 1), (1, 2)),
        ((0, 0), (1, 0), (1, 1), (2, 0)),
        ((0, 0), (0, 1), (0, 2), (1, 1)),
        ((0, 1), (1, 0), (1, 1), (2, 1)),
    ),
    "J": (
        ((0, 0), (1, 0), (1, 1), (1, 2)),
        ((0, 0), (0, 1), (1, 0), (2, 0)),
        ((0, 0), (0, 1), (0, 2), (1, 2)),
        ((0, 1), (1, 1), (2, 0), (2, 1)),
    ),
    "L": (
        ((0, 2), (1, 0), (1, 1), (1, 2)),
        ((0, 0), (1, 0), (2, 0), (2, 1)),
        ((0, 0), (0, 1), (0, 2), (1, 0)),
        ((0, 0), (0, 1), (1, 1), (2, 1)),
    ),
}

# sIO stores width/height in this orientation. User-facing boards are 8x7, 8x9,
# and 8x12 respectively.
MOUNT_BOARD_SIZES: dict[str, tuple[int, int]] = {
    "Electric Scooter": (7, 8),
    "Tech Hoverboard": (9, 8),
    "Doomsteed": (12, 8),
}
MOUNT_BOARD_ALIASES = {
    "electric_scooter": "Electric Scooter",
    "scooter": "Electric Scooter",
    "hoverboard": "Tech Hoverboard",
    "tech_hoverboard": "Tech Hoverboard",
    "doomsteed": "Doomsteed",
}


@dataclass(frozen=True)
class Placement:
    type: str
    rotation: int
    row: int
    col: int
    mask: int

    def public(self) -> dict[str, int | str]:
        return {
            "type": self.type,
            "rotation": self.rotation,
            "row": self.row,
            "col": self.col,
        }


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def canonical_counts(counts: Mapping[str, Any] | Sequence[int] | None) -> tuple[int, ...]:
    """Return one canonical multiset count vector in ``PIECE_TYPES`` order."""
    if counts is None:
        return (0,) * len(PIECE_TYPES)
    if isinstance(counts, Mapping):
        return tuple(_nonnegative_int(counts.get(piece, 0)) for piece in PIECE_TYPES)
    values = list(counts)
    return tuple(_nonnegative_int(values[index]) if index < len(values) else 0 for index in range(len(PIECE_TYPES)))


def counts_mapping(counts: Mapping[str, Any] | Sequence[int] | None) -> dict[str, int]:
    vector = canonical_counts(counts)
    return dict(zip(PIECE_TYPES, vector))


def inventory_combination_count(counts: Mapping[str, Any] | Sequence[int] | None, *, include_empty: bool = True) -> int:
    """Count unique inventory sub-multisets without ordering pieces.

    For two copies of each of five types this is ``3**5 == 243`` combinations,
    not ``10! / (2!**5) == 113400`` unique order permutations.
    """
    total = math.prod(value + 1 for value in canonical_counts(counts))
    return total if include_empty else max(0, total - 1)


def inventory_combinations(
    counts: Mapping[str, Any] | Sequence[int] | None,
    *,
    include_empty: bool = True,
    max_total_pieces: int | None = None,
) -> Iterable[dict[str, int]]:
    """Yield unique sub-multisets as count maps, never item permutations."""
    vector = canonical_counts(counts)
    for candidate in product(*(range(value + 1) for value in vector)):
        if not include_empty and not any(candidate):
            continue
        if max_total_pieces is not None and sum(candidate) > max(0, int(max_total_pieces)):
            continue
        yield dict(zip(PIECE_TYPES, candidate))


def board_size(mount: str) -> tuple[int, int]:
    name = MOUNT_BOARD_ALIASES.get(str(mount), str(mount))
    if name not in MOUNT_BOARD_SIZES:
        raise ValueError(f"unknown mount puzzle board: {mount}")
    return MOUNT_BOARD_SIZES[name]


def _rotation_size(cells: Sequence[tuple[int, int]]) -> tuple[int, int]:
    return max(row for row, _ in cells) + 1, max(col for _, col in cells) + 1


@lru_cache(maxsize=64)
def legal_placements(width: int, height: int, piece: str) -> tuple[Placement, ...]:
    """Return every unique in-bounds placement for one piece type."""
    width, height = int(width), int(height)
    if width <= 0 or height <= 0:
        raise ValueError("board width and height must be positive")
    if piece not in PIECE_ROTATIONS:
        raise ValueError(f"unknown tetromino type: {piece}")
    result: list[Placement] = []
    seen_masks: set[int] = set()
    for rotation, cells in enumerate(PIECE_ROTATIONS[piece]):
        shape_height, shape_width = _rotation_size(cells)
        for row in range(height - shape_height + 1):
            for col in range(width - shape_width + 1):
                mask = 0
                for cell_row, cell_col in cells:
                    index = (row + cell_row) * width + col + cell_col
                    mask |= 1 << index
                if mask in seen_masks:
                    continue
                seen_masks.add(mask)
                result.append(Placement(piece, rotation, row, col, mask))
    return tuple(result)


def _row_masks(width: int, height: int) -> tuple[int, ...]:
    full = (1 << width) - 1
    return tuple(full << (row * width) for row in range(height))


def completed_rows(board: int, width: int, height: int) -> int:
    return sum(1 for mask in _row_masks(width, height) if board & mask == mask)


def render_board(width: int, height: int, placements: Iterable[Mapping[str, Any]]) -> list[list[str | None]]:
    """Rebuild the UI-style board from ``type/rotation/row/col`` placements."""
    board: list[list[str | None]] = [[None for _ in range(width)] for _ in range(height)]
    for placement in placements:
        piece = str(placement["type"])
        rotation = int(placement["rotation"])
        row = int(placement["row"])
        col = int(placement["col"])
        cells = PIECE_ROTATIONS[piece][rotation]
        for cell_row, cell_col in cells:
            target_row, target_col = row + cell_row, col + cell_col
            if not (0 <= target_row < height and 0 <= target_col < width):
                raise ValueError("placement is outside the board")
            if board[target_row][target_col] is not None:
                raise ValueError("placements overlap")
            board[target_row][target_col] = piece
    return board


def _upper_row_bound(board: int, row_masks: tuple[int, ...], remaining_pieces: int) -> int:
    budget = max(0, remaining_pieces) * 4
    full = 0
    missing: list[int] = []
    for mask in row_masks:
        occupied = (board & mask).bit_count()
        if occupied == mask.bit_count():
            full += 1
        else:
            missing.append(mask.bit_count() - occupied)
    for need in sorted(missing):
        if need > budget:
            break
        budget -= need
        full += 1
    return full


def solve_tetris(
    width: int,
    height: int,
    counts: Mapping[str, Any] | Sequence[int],
    *,
    max_states: int = 250_000,
) -> dict[str, Any]:
    """Solve a mount board using combinations of placements, not permutations.

    Objective matches the supplied sIO UI contract: maximize completed rows, then
    maximize the number of placed pieces. ``complete`` is false when ``max_states``
    stops the independent search; the returned placement is still the best found.
    """
    width, height = int(width), int(height)
    if width <= 0 or height <= 0:
        raise ValueError("board width and height must be positive")
    count_vector = canonical_counts(counts)
    max_states = max(1, int(max_states))
    placements_by_type = tuple(legal_placements(width, height, piece) for piece in PIECE_TYPES)
    row_masks = _row_masks(width, height)

    best_score = (0, 0)
    best_board = 0
    best_path: tuple[Placement, ...] = ()
    explored = 0
    truncated = False
    # For the same board/type/count, a smaller next-placement index dominates a
    # larger one because it leaves a superset of combination choices available.
    smallest_start: dict[tuple[int, int, int], int] = {}

    def visit(
        type_index: int,
        remaining_current: int,
        start_index: int,
        board: int,
        path: tuple[Placement, ...],
    ) -> None:
        nonlocal best_score, best_board, best_path, explored, truncated
        if explored >= max_states:
            truncated = True
            return
        explored += 1

        score = (completed_rows(board, width, height), len(path))
        if score > best_score:
            best_score, best_board, best_path = score, board, path

        if type_index >= len(PIECE_TYPES):
            return
        remaining_total = remaining_current + sum(count_vector[type_index + 1 :])
        upper_rows = _upper_row_bound(board, row_masks, remaining_total)
        if upper_rows < best_score[0]:
            return
        if upper_rows == best_score[0] and len(path) + remaining_total <= best_score[1]:
            return

        state_key = (type_index, remaining_current, board)
        previous_start = smallest_start.get(state_key)
        if previous_start is not None and previous_start <= start_index:
            return
        smallest_start[state_key] = start_index

        # Choose another copy of this type using an increasing placement index.
        # This enumerates combinations of placements and eliminates copy-order
        # permutations such as A/B and B/A.
        if remaining_current > 0:
            legal = placements_by_type[type_index]
            candidates = [
                placement
                for placement in legal[start_index:]
                if board & placement.mask == 0
            ]
            # Find good rows early so branch-and-bound becomes useful sooner.
            candidates.sort(
                key=lambda placement: (
                    completed_rows(board | placement.mask, width, height),
                    -placement.row,
                    -placement.col,
                ),
                reverse=True,
            )
            index_by_mask = {placement.mask: index for index, placement in enumerate(legal)}
            for placement in candidates:
                visit(
                    type_index,
                    remaining_current - 1,
                    index_by_mask[placement.mask] + 1,
                    board | placement.mask,
                    path + (placement,),
                )
                if truncated:
                    return

        # Use zero more copies of this type, then move to the next type. Fixed
        # type order removes cross-type piece-order permutations.
        next_index = type_index + 1
        next_remaining = count_vector[next_index] if next_index < len(PIECE_TYPES) else 0
        visit(next_index, next_remaining, 0, board, path)

    visit(0, count_vector[0], 0, 0, ())
    public_path = [placement.public() for placement in best_path]
    return {
        "full": best_score[0],
        "placements": public_path,
        "placed_count": best_score[1],
        "board": render_board(width, height, public_path),
        "board_mask": best_board,
        "counts": counts_mapping(count_vector),
        "combination_count": inventory_combination_count(count_vector),
        "states_explored": explored,
        "complete": not truncated,
        "search_model": "fixed_type_multiset_placement_combinations",
        "worker_parity": False,
        "source_status": "sIO UI contract mapped; omitted worker independently reimplemented",
    }


def solve_mount_puzzle(
    mount: str,
    counts: Mapping[str, Any] | Sequence[int],
    *,
    max_states: int = 250_000,
) -> dict[str, Any]:
    width, height = board_size(mount)
    result = solve_tetris(width, height, counts, max_states=max_states)
    result["mount"] = MOUNT_BOARD_ALIASES.get(str(mount), str(mount))
    return result


__all__ = [
    "MOUNT_BOARD_SIZES",
    "PIECE_ROTATIONS",
    "PIECE_TYPES",
    "Placement",
    "board_size",
    "canonical_counts",
    "completed_rows",
    "counts_mapping",
    "inventory_combination_count",
    "inventory_combinations",
    "legal_placements",
    "render_board",
    "solve_mount_puzzle",
    "solve_tetris",
]
