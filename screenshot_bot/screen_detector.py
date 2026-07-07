from __future__ import annotations

import re
from pathlib import Path

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
    """OCR several likely title/content crops.

    Survivor.io text is noisy, so one crop is not enough. These crops catch:
    - My Equipment title bar
    - My Bag / My Parts modal title
    - Detailed Stats title + section titles
    """
    h, w = img.shape[:2]
    boxes = [
        (0, 0, w, int(h * 0.45)),
        (int(w * 0.05), int(h * 0.16), int(w * 0.90), int(h * 0.26)),
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


def detect_screen(path: str | Path) -> str:
    """Detect the major Survivor.io screenshot type.

    The detector prefers fuzzy OCR from multiple crops, then falls back to visual
    grid detection. This prevents My Bag/My Parts/Core Stock screens from being
    incorrectly treated as equipment just because they are portrait screenshots.
    """
    img = load_image(path)
    h, w = img.shape[:2]
    text = _read_screen_text(img)

    stats_score = _best_phrase_score(text, STATS_PHRASES)
    equipment_score = _best_phrase_score(text, EQUIPMENT_PHRASES)
    inventory_score = _best_phrase_score(text, INVENTORY_PHRASES)

    if stats_score >= 78:
        return "stats"
    if equipment_score >= 82:
        return "equipment"
    if inventory_score >= 78:
        return "inventory"

    # Visual fallback: bag/parts screens have a regular colored grid. Equipment
    # also has a grid lower down, but most equipment screens are caught by the
    # My Equipment title above. Unknown portrait grids are safer as inventory
    # than as equipment because inventory extraction at least shows cells/qty.
    try:
        cells = detect_colored_grid(img, expected_cols=5, max_rows=12)
        if len(cells) >= 8:
            return "inventory"
    except Exception:
        pass

    if h > w:
        return "unknown"
    return "unknown"
