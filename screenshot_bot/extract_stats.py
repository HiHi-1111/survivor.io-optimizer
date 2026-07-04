from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .grid_detector import crop_box
from .ocr import read_text
from .template_matcher import load_image

STAT_ALIASES = {
    "base atk": "base_atk",
    "base hp": "base_hp",
    "atk bonus": "atk_bonus",
    "hp bonus": "hp_bonus",
    "final atk": "final_atk",
    "final hp": "final_hp",
    "crit rate": "crit_rate",
    "crit damage": "crit_damage",
    "skill damage": "skill_damage",
    "shield damage boost": "shield_damage_boost",
    "increased damage to poisoned targets": "poisoned_damage",
    "increased damage to weakened targets": "weakened_damage",
    "increased damage to chilled targets": "chilled_damage",
    "increased damage to lacerated targets": "lacerated_damage",
    "movement speed": "movement_speed",
    "movement speed cap": "movement_speed_cap",
    "attack": "pet_attack",
    "xeno pet sync rate": "xeno_pet_sync_rate",
}


def _find_stat_rows(img: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Find gray rounded stat rows in Detailed Stats modal."""
    h, w = img.shape[:2]
    # Rows sit inside the centered modal; ignore top resource bar and bottom nav.
    crop_y0 = int(h * 0.22)
    crop_y1 = int(h * 0.90)
    crop = img[crop_y0:crop_y1]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    # gray-blue row panels have low saturation and mid value, black borders.
    mask = ((hsv[:, :, 1] < 90) & (hsv[:, :, 2] > 65) & (hsv[:, :, 2] < 180)).astype(np.uint8) * 255
    kernel = np.ones((9, 35), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rows: list[tuple[int, int, int, int]] = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if bw > w * 0.45 and 35 < bh < 95:
            rows.append((x, y + crop_y0, bw, bh))
    rows = sorted(rows, key=lambda b: b[1])
    return rows


def _normalize_label(text: str) -> str:
    clean = " ".join(text.lower().replace("\n", " ").split())
    return STAT_ALIASES.get(clean, clean.replace(" ", "_"))


def extract_detailed_stats(
    screenshot_path: str | Path,
    debug_path: str | Path | None = None,
) -> dict[str, Any]:
    img = load_image(screenshot_path)
    rows = _find_stat_rows(img)
    stats: dict[str, Any] = {}

    debug = img.copy()
    for i, box in enumerate(rows):
        x, y, w, h = box
        label_crop = crop_box(img, (x + int(w * 0.02), y, int(w * 0.62), h))
        value_crop = crop_box(img, (x + int(w * 0.62), y, int(w * 0.36), h))
        label_raw = read_text(label_crop)
        value_raw = read_text(value_crop)
        key = _normalize_label(label_raw) if label_raw else f"unknown_{i}"
        stats[key] = {
            "label_raw": label_raw,
            "value_raw": value_raw,
            "box": box,
        }
        cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 255, 255), 2)
        cv2.putText(debug, key[:20], (x + 5, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    if debug_path:
        debug_path = Path(debug_path)
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_path), debug)

    return {"screen": "detailed_stats", "stats": stats}
