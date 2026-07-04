from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


@dataclass(frozen=True)
class MatchResult:
    name: str
    score: float
    box: tuple[int, int, int, int]
    template_path: str


def load_image(path: str | Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    return img


def iter_templates(folder: str | Path) -> Iterable[tuple[str, Path, np.ndarray]]:
    folder = Path(folder)
    if not folder.exists():
        return
    for path in sorted(folder.rglob("*")):
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            continue
        yield path.stem.replace("_", " "), path, img


def match_best(
    screenshot: np.ndarray,
    template_folder: str | Path,
    region: tuple[int, int, int, int] | None = None,
    threshold: float = 0.72,
) -> MatchResult | None:
    """Return the best icon template match inside an optional x,y,w,h region."""
    x0, y0 = 0, 0
    search = screenshot
    if region:
        x0, y0, w, h = region
        search = screenshot[y0 : y0 + h, x0 : x0 + w]

    best: MatchResult | None = None
    for name, path, tmpl in iter_templates(template_folder) or []:
        if tmpl.shape[0] > search.shape[0] or tmpl.shape[1] > search.shape[1]:
            continue
        res = cv2.matchTemplate(search, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if best is None or max_val > best.score:
            tx, ty = max_loc
            h, w = tmpl.shape[:2]
            best = MatchResult(
                name=name,
                score=float(max_val),
                box=(x0 + tx, y0 + ty, w, h),
                template_path=str(path),
            )

    if best and best.score >= threshold:
        return best
    return best


def draw_matches(image: np.ndarray, matches: list[MatchResult]) -> np.ndarray:
    out = image.copy()
    for m in matches:
        x, y, w, h = m.box
        cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(out, f"{m.name} {m.score:.2f}", (x, max(20, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    return out
