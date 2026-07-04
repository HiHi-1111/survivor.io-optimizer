from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from rapidfuzz import process, fuzz

from .grid_detector import crop_box
from .ocr import parse_game_number, read_number, read_text_result
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
    "xeno pet core": "xeno_pet_core",
    "mount core": "mount_core",
    "relic core": "relic_core",
    "resonance chip": "resonance_chip",
    "survivor awakening core": "survivor_awakening_core",
}


def _find_stat_rows(img: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Find gray rounded stat rows in Detailed Stats modal."""
    h, w = img.shape[:2]
    crop_y0 = int(h * 0.20)
    crop_y1 = int(h * 0.90)
    crop = img[crop_y0:crop_y1]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = ((hsv[:, :, 1] < 110) & (hsv[:, :, 2] > 55) & (hsv[:, :, 2] < 190)).astype(np.uint8) * 255
    kernel = np.ones((7, 45), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rows: list[tuple[int, int, int, int]] = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if bw > w * 0.42 and 30 < bh < 105:
            rows.append((x, y + crop_y0, bw, bh))
    rows = sorted(rows, key=lambda b: b[1])

    # Merge near-duplicate contours from borders/shadows.
    merged: list[tuple[int, int, int, int]] = []
    for row in rows:
        if merged and abs(row[1] - merged[-1][1]) < 12:
            x1 = min(row[0], merged[-1][0])
            y1 = min(row[1], merged[-1][1])
            x2 = max(row[0] + row[2], merged[-1][0] + merged[-1][2])
            y2 = max(row[1] + row[3], merged[-1][1] + merged[-1][3])
            merged[-1] = (x1, y1, x2 - x1, y2 - y1)
        else:
            merged.append(row)
    return merged


def _normalize_label(text: str) -> tuple[str, str, int]:
    clean = " ".join(text.lower().replace("\n", " ").split())
    if clean in STAT_ALIASES:
        return STAT_ALIASES[clean], clean, 100
    match = process.extractOne(clean, STAT_ALIASES.keys(), scorer=fuzz.WRatio)
    if match and match[1] >= 72:
        return STAT_ALIASES[match[0]], match[0], int(match[1])
    return clean.replace(" ", "_") or "unknown", clean, 0


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
        label_crop = crop_box(img, (x + int(w * 0.02), y, int(w * 0.66), h))
        value_crop = crop_box(img, (x + int(w * 0.62), y, int(w * 0.36), h))
        label_result = read_text_result(label_crop, psm=6)
        value_result = read_text_result(value_crop, psm=7, whitelist="0123456789.,KkMmBb/%")
        key, matched_label, label_score = _normalize_label(label_result.text)
        numeric_value = parse_game_number(value_result.text, default=None)
        stats[key] = {
            "label_raw": label_result.text,
            "label_confidence": round(label_result.confidence, 2),
            "matched_label": matched_label,
            "label_match_score": label_score,
            "value_raw": value_result.text,
            "value": numeric_value,
            "value_confidence": round(value_result.confidence, 2),
            "box": box,
        }
        cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 255, 255), 2)
        cv2.putText(debug, key[:22], (x + 5, max(20, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    if debug_path:
        debug_path = Path(debug_path)
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_path), debug)

    return {"screen": "detailed_stats", "stats": stats}
