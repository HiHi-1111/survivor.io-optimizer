from __future__ import annotations

import re
from pathlib import Path

import cv2
import numpy as np
from rapidfuzz import fuzz

from .grid_detector import detect_colored_grid
from .ocr import read_text
from .template_matcher import load_image


STATS_PHRASES = [
    "detailed stats",
    "survivor stats",
    "core stock",
    "pet stats",
    "shield damage boost",
    "xeno pet core",
    "resonance chip",
    "base atk",
    "crit damage",
    "skill damage",
]

INVENTORY_PHRASES = [
    "my bag",
    "my parts",
    "filter",
    "universal shard",
    "items",
    "exchange",
]

EQUIPMENT_PHRASES = ["my equipment"]


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _best_phrase_score(text: str, phrases: list[str]) -> float:
    clean = _norm(text)
    if not clean:
        return 0.0
    return max(fuzz.partial_ratio(clean, _norm(phrase)) for phrase in phrases)


def _read_screen_text(img) -> str:
    """OCR several likely title/content crops."""
    h, w = img.shape[:2]
    boxes = [
        (0, 0, w, int(h * 0.45)),
        (int(w * 0.05), int(h * 0.16), int(w * 0.90), int(h * 0.26)),
        (int(w * 0.05), int(h * 0.30), int(w * 0.90), int(h * 0.45)),
        (int(w * 0.15), int(h * 0.48), int(w * 0.75), int(h * 0.16)),
        (0, int(h * 0.25), w, int(h * 0.55)),
    ]
    chunks: list[str] = []
    for x, y, bw, bh in boxes:
        crop = img[y : y + bh, x : x + bw]
        for psm in (6, 7):
            try:
                text = read_text(crop, psm=psm)
            except Exception:
                text = ""
            if text:
                chunks.append(text)
    return "\n".join(chunks)


def _looks_like_stats_modal(img) -> bool:
    """Visual fallback for Detailed Stats modal.

    The modal has many wide dark horizontal stat rows. Inventory grids have many
    colored squares instead. This catches stats screens even when title OCR is
    weak.
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    x0, x1 = int(w * 0.07), int(w * 0.93)
    y0, y1 = int(h * 0.25), int(h * 0.82)
    means = np.array([gray[y, x0:x1].mean() for y in range(y0, y1)], dtype=np.float32)
    if means.size == 0:
        return False
    k = max(7, int(h * 0.006))
    smooth = np.convolve(means, np.ones(k) / k, mode="same")

    bands = 0
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
            height = end - start
            if max(24, int(h * 0.018)) <= height <= int(h * 0.060):
                bands += 1
            start = None
    if start is not None:
        height = end - start
        if max(24, int(h * 0.018)) <= height <= int(h * 0.060):
            bands += 1

    return bands >= 5


def detect_screen(path: str | Path) -> str:
    """Detect the major Survivor.io screenshot type."""
    img = load_image(path)
    h, w = img.shape[:2]
    text = _read_screen_text(img)

    stats_score = _best_phrase_score(text, STATS_PHRASES)
    equipment_score = _best_phrase_score(text, EQUIPMENT_PHRASES)
    inventory_score = _best_phrase_score(text, INVENTORY_PHRASES)

    if stats_score >= 74 or _looks_like_stats_modal(img):
        return "stats"
    if equipment_score >= 82:
        return "equipment"
    if inventory_score >= 78:
        return "inventory"

    try:
        cells = detect_colored_grid(img, expected_cols=5, max_rows=12)
        if len(cells) >= 8:
            return "inventory"
    except Exception:
        pass

    if h > w:
        return "unknown"
    return "unknown"
