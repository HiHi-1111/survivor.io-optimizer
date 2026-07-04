from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .extract_equipment import extract_equipment
from .extract_inventory import extract_inventory
from .extract_stats import extract_detailed_stats
from .screen_detector import detect_screen

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def process_one(path: Path, args: argparse.Namespace) -> dict[str, Any]:
    kind = detect_screen(path) if args.type == "auto" else args.type
    debug_base = Path(args.debug_dir)
    out: dict[str, Any]
    if kind == "equipment":
        out = extract_equipment(path, template_dir=args.equipment_templates, debug_path=debug_base / f"{path.stem}_equipment_debug.png")
    elif kind == "inventory":
        out = extract_inventory(
            path,
            template_dir=args.item_templates,
            debug_path=debug_base / f"{path.stem}_inventory_debug.png",
            quantity_debug_dir=debug_base / f"{path.stem}_quantity_crops",
        )
    elif kind == "stats":
        out = extract_detailed_stats(path, debug_path=debug_base / f"{path.stem}_stats_debug.png")
    else:
        out = {"screen": "unknown", "path": str(path), "error": f"Unsupported type {kind}"}
    out["source_image"] = str(path)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch parse Survivor.io screenshots")
    parser.add_argument("input_dir", nargs="?", default="screenshots/input")
    parser.add_argument("--type", choices=["auto", "equipment", "inventory", "stats"], default="auto")
    parser.add_argument("--out", default="screenshots/output/batch_results.json")
    parser.add_argument("--debug-dir", default="screenshots/debug")
    parser.add_argument("--equipment-templates", default="knowledge/icons/equipment")
    parser.add_argument("--item-templates", default="knowledge/icons/items")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    images = sorted(p for p in input_dir.rglob("*") if p.suffix.lower() in IMAGE_EXTS)
    Path(args.debug_dir).mkdir(parents=True, exist_ok=True)
    results = [process_one(p, args) for p in images]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"screenshots": results}, indent=2), encoding="utf-8")
    print(f"Processed {len(results)} screenshots")
    print(f"Wrote: {out_path}")
    print(f"Debug: {args.debug_dir}")


if __name__ == "__main__":
    main()
