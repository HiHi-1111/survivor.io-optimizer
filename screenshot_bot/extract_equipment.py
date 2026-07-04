from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2

from .export_profile import empty_profile
from .template_matcher import MatchResult, draw_matches, load_image, match_best

SLOTS = ["Weapon", "Necklace", "Gloves", "Armor", "Belt", "Boots"]

# Relative boxes for the six equipment icon areas.
# These are placeholders until you send real equipment screenshots.
# Format: slot -> (x_pct, y_pct, w_pct, h_pct)
RELATIVE_SLOT_BOXES: dict[str, tuple[float, float, float, float]] = {
    "Weapon": (0.07, 0.22, 0.22, 0.14),
    "Necklace": (0.39, 0.22, 0.22, 0.14),
    "Gloves": (0.71, 0.22, 0.22, 0.14),
    "Armor": (0.07, 0.43, 0.22, 0.14),
    "Belt": (0.39, 0.43, 0.22, 0.14),
    "Boots": (0.71, 0.43, 0.22, 0.14),
}


def rel_to_abs(img_shape: tuple[int, int, int], rel: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    h, w = img_shape[:2]
    x, y, rw, rh = rel
    return int(x * w), int(y * h), int(rw * w), int(rh * h)


def extract_equipment(
    screenshot_path: str | Path,
    template_dir: str | Path = "knowledge/icons/equipment",
    debug_path: str | Path | None = None,
) -> dict[str, Any]:
    img = load_image(screenshot_path)
    profile = empty_profile()
    matches: list[MatchResult] = []

    for slot, rel_box in RELATIVE_SLOT_BOXES.items():
        region = rel_to_abs(img.shape, rel_box)
        match = match_best(img, template_dir, region=region, threshold=0.55)
        if match:
            matches.append(match)
            profile["equipment"][slot] = {
                "name": match.name,
                "confidence": round(match.score, 4),
                "level": None,
                "ss": {"light": None, "void": None, "chaos": None, "xeno": None},
                "af": None,
            }
        else:
            profile["equipment"][slot] = {
                "name": None,
                "confidence": 0,
                "level": None,
                "ss": {"light": None, "void": None, "chaos": None, "xeno": None},
                "af": None,
            }

    if debug_path:
        debug = draw_matches(img, matches)
        debug_path = Path(debug_path)
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_path), debug)

    return profile
