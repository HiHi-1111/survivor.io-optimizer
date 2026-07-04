from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def empty_profile() -> dict[str, Any]:
    return {
        "equipment": {},
        "pets": {},
        "tech": {},
        "collectibles": {},
        "mounts": {},
        "meta": {"source": "screenshot_bot"},
    }


def save_profile(profile: dict[str, Any], out_path: str | Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
