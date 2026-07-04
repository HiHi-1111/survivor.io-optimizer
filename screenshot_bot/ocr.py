from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None


def preprocess_for_ocr(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th


def read_text(img: np.ndarray) -> str:
    if pytesseract is None:
        return ""
    processed = preprocess_for_ocr(img)
    return pytesseract.image_to_string(processed, config="--psm 7").strip()


def read_int(img: np.ndarray, default: int = 0) -> int:
    text = read_text(img)
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else default
