from __future__ import annotations

from pathlib import Path

from .template_matcher import load_image


def detect_screen(path: str | Path) -> str:
    """Very small first-pass detector.

    This will improve once we have real screenshots. For now, callers can pass
    --type equipment to force equipment parsing.
    """
    img = load_image(path)
    h, w = img.shape[:2]

    # Most Survivor.io inventory/equipment screenshots are portrait mobile.
    if h > w:
        return "equipment"
    return "unknown"
