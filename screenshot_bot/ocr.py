from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable

import cv2
import numpy as np

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None


def _configure_tesseract() -> None:
    if pytesseract is None:
        return
    candidates = [
        os.environ.get("TESSERACT_CMD"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            return


_configure_tesseract()


@dataclass(frozen=True)
class OCRResult:
    text: str
    confidence: float
    method: str


def _ensure_bgr(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


def _pad(img: np.ndarray, px: int = 8) -> np.ndarray:
    return cv2.copyMakeBorder(img, px, px, px, px, cv2.BORDER_CONSTANT, value=(0, 0, 0))


def preprocess_variants(img: np.ndarray) -> list[tuple[str, np.ndarray]]:
    """Return several OCR-ready variants."""
    bgr0 = _ensure_bgr(img)
    raw_scale = 4 if min(bgr0.shape[:2]) < 100 else 3
    raw_big = cv2.resize(bgr0, None, fx=raw_scale, fy=raw_scale, interpolation=cv2.INTER_CUBIC)
    raw_gray = cv2.cvtColor(raw_big, cv2.COLOR_BGR2GRAY)

    bgr = _pad(bgr0, 8)
    scale = 4 if min(bgr.shape[:2]) < 70 else 3
    big = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)

    variants: list[tuple[str, np.ndarray]] = []
    variants.append(("raw_gray", raw_gray))
    variants.append(("gray", gray))

    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants.append(("otsu", otsu))
    variants.append(("otsu_inv", cv2.bitwise_not(otsu)))

    adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 7)
    variants.append(("adaptive", adaptive))

    hsv = cv2.cvtColor(big, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, (40, 60, 90), (95, 255, 255))
    variants.append(("green_only", green))

    white = cv2.inRange(hsv, (0, 0, 150), (179, 90, 255))
    yellow = cv2.inRange(hsv, (15, 80, 120), (45, 255, 255))
    variants.append(("white_yellow", cv2.bitwise_or(white, yellow)))

    kernel = np.ones((2, 2), np.uint8)
    cleaned: list[tuple[str, np.ndarray]] = []
    for name, v in variants:
        if name == "raw_gray":
            cleaned.append((name, v))
        else:
            cleaned.append((name, cv2.morphologyEx(v, cv2.MORPH_CLOSE, kernel, iterations=1)))
    return cleaned


def _ocr_with_conf(img: np.ndarray, config: str) -> OCRResult:
    if pytesseract is None:
        return OCRResult("", 0.0, "missing_tesseract")
    try:
        data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
    except Exception as exc:
        return OCRResult("", 0.0, f"ocr_error:{type(exc).__name__}")
    words: list[str] = []
    confs: list[float] = []
    for text, conf in zip(data.get("text", []), data.get("conf", [])):
        text = (text or "").strip()
        try:
            c = float(conf)
        except Exception:
            c = -1
        if text:
            words.append(text)
        if c >= 0:
            confs.append(c)
    return OCRResult(" ".join(words).strip(), float(np.mean(confs)) if confs else 0.0, "tesseract")


def read_text(img: np.ndarray, *, psm: int = 7, whitelist: str | None = None) -> str:
    result = read_text_result(img, psm=psm, whitelist=whitelist)
    return result.text


def read_text_result(img: np.ndarray, *, psm: int = 7, whitelist: str | None = None) -> OCRResult:
    if pytesseract is None:
        return OCRResult("", 0.0, "missing_tesseract")
    config = f"--oem 3 --psm {psm}"
    if whitelist:
        config += f" -c tessedit_char_whitelist={whitelist}"

    best = OCRResult("", 0.0, "none")
    for name, variant in preprocess_variants(img):
        res = _ocr_with_conf(variant, config)
        score = res.confidence + min(len(res.text), 20) * 0.5
        if whitelist and "/" in whitelist and "/" in res.text:
            score += 2.0
        best_score = best.confidence + min(len(best.text), 20) * 0.5
        if whitelist and "/" in whitelist and "/" in best.text:
            best_score += 2.0
        if score > best_score:
            best = OCRResult(res.text, res.confidence, name)
    return best


def parse_game_number(text: str, default: int | float | None = 0) -> int | float | None:
    """Parse Survivor.io numbers like 1636K, 40.1M, 293.96%, or 5 / 0."""
    if not text:
        return default
    t = text.upper().replace(",", "").replace(" ", "")
    if "/" in t:
        t = t.split("/", 1)[0]
    m = re.search(r"[-+]?\d+(?:\.\d+)?", t)
    if not m:
        return default
    num = float(m.group(0))
    if "B" in t:
        num *= 1_000_000_000
    elif "M" in t:
        num *= 1_000_000
    elif "K" in t:
        num *= 1_000
    if "%" not in t and num.is_integer():
        return int(num)
    return num


def read_number(img: np.ndarray, default: int | float | None = 0) -> int | float | None:
    result = read_text_result(img, psm=7, whitelist="0123456789.,KkMmBb/%")
    return parse_game_number(result.text, default=default)


def read_int(img: np.ndarray, default: int = 0) -> int:
    val = read_number(img, default=default)
    try:
        return int(round(float(val)))
    except Exception:
        return default


def _parse_quantity_text(text: str, default: int = 1) -> int:
    """Parse small stack labels without letting OCR junk before the number matter."""
    t = (text or "").upper().replace(",", "")
    t = t.replace("O", "0")
    match = re.search(r"(?:X\s*)?(\d+(?:\.\d+)?)([KMB])?", t)
    if not match:
        return default
    num = float(match.group(1))
    suffix = match.group(2) or ""
    if suffix == "B":
        num *= 1_000_000_000
    elif suffix == "M":
        num *= 1_000_000
    elif suffix == "K":
        num *= 1_000
    return int(round(num))


def read_quantity(img: np.ndarray, default: int = 1) -> tuple[int, OCRResult]:
    result = read_text_result(img, psm=7, whitelist="xX0123456789.,KkMmBb")
    return _parse_quantity_text(result.text, default=default), result
