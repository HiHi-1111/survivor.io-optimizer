from __future__ import annotations

from pathlib import Path

from .ocr import read_text
from .template_matcher import load_image


def detect_screen(path: str | Path) -> str:
    """First-pass screenshot detector.

    OCR is only used on broad header areas. For reliable development, pass
    --type inventory, --type stats, or --type equipment when testing a known
    screenshot type.
    """
    img = load_image(path)
    h, w = img.shape[:2]

    header = img[int(h * 0.15) : int(h * 0.35), int(w * 0.05) : int(w * 0.95)]
    text = read_text(header).lower()

    if "my bag" in text or "default" in text:
        return "inventory"
    if "detailed" in text or "stats" in text or "core stock" in text:
        return "stats"
    if "equipment" in text or "my equipment" in text:
        return "equipment"

    # Portrait game screenshots are usually one of our known screens, but the
    # caller should force --type for best results until more examples are added.
    if h > w:
        return "equipment"
    return "unknown"
