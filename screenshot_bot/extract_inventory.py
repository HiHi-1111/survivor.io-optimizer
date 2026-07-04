from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2

from .grid_detector import crop_box, detect_colored_grid, draw_cells, quantity_region
from .ocr import read_quantity
from .template_matcher import draw_matches, load_image, match_best


def extract_inventory(
    screenshot_path: str | Path,
    template_dir: str | Path = "knowledge/icons/items",
    debug_path: str | Path | None = None,
    quantity_debug_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Extract stackable bag/material items from a My Bag screenshot.

    Pipeline:
    1) detect the regular colored item grid
    2) template-match each cell against known item/material icons
    3) crop the bottom-right quantity badge
    4) OCR only that small crop with number-focused OCR
    5) export item + quantity + confidence
    """
    img = load_image(screenshot_path)
    cells = detect_colored_grid(img, expected_cols=5, max_rows=12)

    items: list[dict[str, Any]] = []
    matches = []
    qdebug = Path(quantity_debug_dir) if quantity_debug_dir else None
    if qdebug:
        qdebug.mkdir(parents=True, exist_ok=True)

    for cell in cells:
        cell_img = crop_box(img, cell.box)
        match = match_best(cell_img, template_dir, region=None, threshold=0.45)
        if match:
            # Convert local match box to image coordinates for debug drawing.
            x, y, w, h = match.box
            gx, gy, _, _ = cell.box
            match = type(match)(match.name, match.score, (gx + x, gy + y, w, h), match.template_path)
            matches.append(match)

        qbox = quantity_region(cell.box)
        qcrop = crop_box(img, qbox)
        qty, ocr_result = read_quantity(qcrop, default=1)
        if qdebug:
            cv2.imwrite(str(qdebug / f"cell_{cell.index:03d}_qty.png"), qcrop)

        items.append(
            {
                "index": cell.index,
                "row": cell.row,
                "col": cell.col,
                "box": cell.box,
                "name": match.name if match else None,
                "confidence": round(match.score, 4) if match else 0,
                "quantity": qty,
                "quantity_box": qbox,
                "ocr_text": ocr_result.text,
                "ocr_confidence": round(ocr_result.confidence, 2),
                "ocr_method": ocr_result.method,
            }
        )

    if debug_path:
        debug = draw_cells(img, cells)
        debug = draw_matches(debug, matches)
        debug_path = Path(debug_path)
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_path), debug)

    return {"screen": "inventory", "items": items}
