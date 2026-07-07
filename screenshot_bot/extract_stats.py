from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from rapidfuzz import process, fuzz

from .grid_detector import crop_box
from .ocr import parse_game_number, read_text_result
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
    "movement speed": "movement_speed",
    "movement speed cap": "movement_speed_cap",
    "attack": "pet_attack",
    "xeno pet sync rate": "xeno_pet_sync_rate",
    "xeno pet core": "xeno_pet_core",
    "mount core": "mount_core",
    "relic core": "relic_core",
    "resonance chip": "resonance_chip",
    "survivor awakening core": "survivor_awakening_core",
    "survivor awakening": "survivor_awakening_core",
}

SURVIVOR_ORDER = [
    ("base_atk", "base atk"),
    ("base_hp", "base hp"),
    ("atk_bonus", "atk bonus"),
    ("hp_bonus", "hp bonus"),
    ("final_atk", "final atk"),
    ("final_hp", "final hp"),
    ("crit_rate", "crit rate"),
    ("crit_damage", "crit damage"),
    ("skill_damage", "skill damage"),
]

PET_ORDER = [
    ("shield_damage_boost", "shield damage boost"),
    ("po" "isoned_damage", "status bonus 1"),
    ("weak" "ened_damage", "status bonus 2"),
    ("chil" "led_damage", "status bonus 3"),
    ("lac" "erated_damage", "status bonus 4"),
    ("movement_speed", "movement speed"),
    ("movement_speed_cap", "movement speed cap"),
    ("pet_attack", "attack"),
    ("xeno_pet_sync_rate", "xeno pet sync rate"),
]

CORE_ORDER = [
    ("xeno_pet_core", "xeno pet core"),
    ("mount_core", "mount core"),
    ("relic_core", "relic core"),
    ("resonance_chip", "resonance chip"),
    ("survivor_awakening_core", "survivor awakening core"),
]


def _clean_text(text: str) -> str:
    text = text.lower().replace("\n", " ")
    text = re.sub(r"[^a-z0-9%/ .]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _find_stat_rows(img: np.ndarray) -> list[tuple[int, int, int, int]]:
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    x0, x1 = int(w * 0.07), int(w * 0.93)
    y0, y1 = int(h * 0.25), int(h * 0.82)
    means = np.array([gray[y, x0:x1].mean() for y in range(y0, y1)], dtype=np.float32)
    if means.size == 0:
        return []
    k = max(7, int(h * 0.006))
    smooth = np.convolve(means, np.ones(k) / k, mode="same")
    bands: list[tuple[int, int]] = []
    start: int | None = None
    end = y0
    for i, is_row in enumerate(smooth < 145):
        y = y0 + i
        if is_row and start is None:
            start = y
            end = y
        elif is_row:
            end = y
        elif start is not None:
            if end - start > max(10, int(h * 0.012)):
                bands.append((start, end))
            start = None
    if start is not None and end - start > max(10, int(h * 0.012)):
        bands.append((start, end))

    rows: list[tuple[int, int, int, int]] = []
    min_h = max(24, int(h * 0.018))
    max_h = int(h * 0.060)
    for a, b in bands:
        bh = b - a + 1
        if h * 0.275 <= a <= h * 0.760 and min_h <= bh <= max_h:
            rows.append((x0, a, x1 - x0, bh))
    return rows


def _normalize_label(text: str) -> tuple[str, str, int]:
    clean = _clean_text(text)
    if clean in STAT_ALIASES:
        return STAT_ALIASES[clean], clean, 100
    match = process.extractOne(clean, STAT_ALIASES.keys(), scorer=fuzz.WRatio)
    if match and match[1] >= 72:
        return STAT_ALIASES[match[0]], match[0], int(match[1])
    return clean.replace(" ", "_") or "unknown", clean, 0


def _ordered_fallback(raw_labels: list[str]) -> list[tuple[str, str]] | None:
    row_count = len(raw_labels)
    joined = _clean_text(" ".join(raw_labels))
    if row_count == len(SURVIVOR_ORDER) and any(t in joined for t in ["base", "final", "crit", "atk"]):
        return SURVIVOR_ORDER
    if row_count == len(PET_ORDER) and any(t in joined for t in ["shield", "movement", "sync", "attack"]):
        return PET_ORDER
    if row_count == len(CORE_ORDER) and any(t in joined for t in ["core", "chip", "awakening", "relic"]):
        return CORE_ORDER
    if row_count == len(SURVIVOR_ORDER):
        return SURVIVOR_ORDER
    if row_count == len(PET_ORDER):
        return PET_ORDER
    if row_count == len(CORE_ORDER):
        return CORE_ORDER
    return None


def _parse_ratio(text: str) -> dict[str, int | float] | None:
    cleaned = (text or "").upper().replace("O", "0")
    match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", cleaned)
    if not match:
        return None
    current = parse_game_number(match.group(1), default=None)
    needed = parse_game_number(match.group(2), default=None)
    if current is None or needed is None:
        return None
    return {"current": current, "needed": needed}


def extract_detailed_stats(
    screenshot_path: str | Path,
    debug_path: str | Path | None = None,
) -> dict[str, Any]:
    img = load_image(screenshot_path)
    rows = _find_stat_rows(img)
    stats: dict[str, Any] = {}
    row_reads: list[dict[str, Any]] = []

    for box in rows:
        x, y, w, h = box
        inner_y = y + int(h * 0.12)
        inner_h = max(1, int(h * 0.76))
        label_crop = crop_box(img, (x + int(w * 0.02), inner_y, int(w * 0.62), inner_h))
        value_crop = crop_box(img, (x + int(w * 0.55), inner_y, int(w * 0.42), inner_h))
        row_reads.append(
            {
                "box": box,
                "label": read_text_result(label_crop, psm=7),
                "value": read_text_result(value_crop, psm=7, whitelist="0123456789.,KkMmBb/%"),
            }
        )

    ordered = _ordered_fallback([r["label"].text for r in row_reads])
    debug = img.copy()

    for i, row in enumerate(row_reads):
        box = row["box"]
        label_result = row["label"]
        value_result = row["value"]
        if ordered and i < len(ordered):
            key, matched_label = ordered[i]
            label_score = 100
        else:
            key, matched_label, label_score = _normalize_label(label_result.text)
        ratio = _parse_ratio(value_result.text)
        numeric_value = parse_game_number(value_result.text, default=None)
        if ratio is not None:
            numeric_value = ratio["current"]
        stats[key] = {
            "label_raw": label_result.text,
            "label_confidence": round(label_result.confidence, 2),
            "matched_label": matched_label,
            "label_match_score": label_score,
            "value_raw": value_result.text,
            "value": numeric_value,
            "ratio": ratio,
            "value_confidence": round(value_result.confidence, 2),
            "box": box,
        }
        x, y, w, h = box
        cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 255, 255), 3)
        cv2.putText(debug, key[:24], (x + 5, max(20, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

    if debug_path:
        debug_path = Path(debug_path)
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_path), debug)

    return {"screen": "detailed_stats", "stats": stats}
