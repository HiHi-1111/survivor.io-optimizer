from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class GridCell:
    index: int
    row: int
    col: int
    box: tuple[int, int, int, int]


def _regions_from_projection(values: np.ndarray, threshold_frac: float, min_width: int) -> list[tuple[int, int]]:
    if values.size == 0 or values.max() <= 0:
        return []
    threshold = values.max() * threshold_frac
    regions: list[tuple[int, int]] = []
    start: int | None = None
    for i, v in enumerate(values):
        if v > threshold and start is None:
            start = i
        if (v <= threshold or i == len(values) - 1) and start is not None:
            end = i
            if end - start >= min_width:
                regions.append((start, end))
            start = None
    return regions


def _split_wide_regions(regions: list[tuple[int, int]], expected_count: int) -> list[tuple[int, int]]:
    if not regions:
        return regions
    regions = sorted(regions)
    while len(regions) < expected_count:
        widest_i = max(range(len(regions)), key=lambda i: regions[i][1] - regions[i][0])
        a, b = regions[widest_i]
        if b - a < 20:
            break
        mid = (a + b) // 2
        regions = regions[:widest_i] + [(a, mid), (mid, b)] + regions[widest_i + 1 :]
    return sorted(regions)[:expected_count]


def _keep_regular_grid_rows(regions: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Keep the top consecutive grid rows and drop far-away buttons/text.

    Some screens have saturated buttons near the bottom of the modal. Projection
    sees those as a fake inventory row. Real grid rows have fairly consistent
    spacing; a giant vertical gap means the grid ended.
    """
    regions = sorted(regions)
    if len(regions) <= 2:
        return regions

    heights = [b - a for a, b in regions]
    normal_h = float(np.median(heights[: min(5, len(heights))]))
    kept: list[tuple[int, int]] = []
    prev: tuple[int, int] | None = None

    for row in regions:
        a, b = row
        row_h = b - a
        if normal_h and row_h < normal_h * 0.45:
            break
        if prev is not None:
            gap = a - prev[1]
            if gap > max(normal_h * 1.35, 45):
                break
        kept.append(row)
        prev = row
    return kept


def detect_colored_grid(
    image: np.ndarray,
    *,
    expected_cols: int = 5,
    max_rows: int = 12,
    roi: tuple[float, float, float, float] = (0.03, 0.20, 0.94, 0.65),
) -> list[GridCell]:
    """Find colored square inventory cells by saturation projection."""
    h, w = image.shape[:2]
    rx, ry, rw, rh = roi
    x0, y0 = int(rx * w), int(ry * h)
    x1, y1 = int((rx + rw) * w), int((ry + rh) * h)
    crop = image[y0:y1, x0:x1]

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] > 70) & (hsv[:, :, 2] > 90)).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    col_proj = mask.sum(axis=0)
    row_proj = mask.sum(axis=1)
    col_regions = _regions_from_projection(col_proj, threshold_frac=0.18, min_width=max(12, int(w * 0.025)))
    row_regions = _regions_from_projection(row_proj, threshold_frac=0.18, min_width=max(12, int(h * 0.012)))
    col_regions = _split_wide_regions(col_regions, expected_cols)

    row_regions = [r for r in row_regions if r[0] > int(crop.shape[0] * 0.05)]
    row_regions = _keep_regular_grid_rows(row_regions)
    row_regions = row_regions[:max_rows]

    cells: list[GridCell] = []
    idx = 0
    for row_i, (ya, yb) in enumerate(row_regions):
        for col_i, (xa, xb) in enumerate(col_regions):
            pad_x = max(2, int((xb - xa) * 0.03))
            pad_y = max(2, int((yb - ya) * 0.03))
            x = max(0, x0 + xa - pad_x)
            y = max(0, y0 + ya - pad_y)
            bw = min(w - x, (xb - xa) + pad_x * 2)
            bh = min(h - y, (yb - ya) + pad_y * 2)
            if bw <= 0 or bh <= 0:
                continue
            if 0.45 <= bw / max(1, bh) <= 1.9:
                cells.append(GridCell(index=idx, row=row_i, col=col_i, box=(x, y, bw, bh)))
                idx += 1
    return cells


def crop_box(image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = box
    return image[y : y + h, x : x + w]


def quantity_region(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Bottom-right text badge where x123 quantities appear."""
    x, y, w, h = box
    return (
        int(x + w * 0.35),
        int(y + h * 0.58),
        int(w * 0.62),
        int(h * 0.38),
    )


def draw_cells(image: np.ndarray, cells: list[GridCell], color: tuple[int, int, int] = (0, 255, 255)) -> np.ndarray:
    out = image.copy()
    for cell in cells:
        x, y, w, h = cell.box
        cv2.rectangle(out, (x, y), (x + w, y + h), color, 2)
        cv2.putText(out, str(cell.index), (x + 3, y + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    return out
