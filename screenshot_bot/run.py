from __future__ import annotations

import argparse
from pathlib import Path

from .export_profile import save_profile
from .extract_equipment import extract_equipment
from .extract_inventory import extract_inventory
from .extract_stats import extract_detailed_stats
from .screen_detector import detect_screen


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse Survivor.io screenshots into optimizer JSON")
    parser.add_argument("image", help="Path to screenshot")
    parser.add_argument("--type", choices=["auto", "equipment", "inventory", "stats"], default="auto")
    parser.add_argument("--templates", default="knowledge/icons/equipment", help="Template icon folder")
    parser.add_argument("--out", default="screenshots/output/profile.json")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    screen_type = detect_screen(args.image) if args.type == "auto" else args.type

    if screen_type == "equipment":
        debug_path = "screenshots/debug/equipment_debug.png" if args.debug else None
        profile = extract_equipment(args.image, template_dir=args.templates, debug_path=debug_path)
    elif screen_type == "inventory":
        debug_path = "screenshots/debug/inventory_debug.png" if args.debug else None
        qty_dir = "screenshots/debug/quantity_crops" if args.debug else None
        profile = extract_inventory(args.image, template_dir=args.templates, debug_path=debug_path, quantity_debug_dir=qty_dir)
    elif screen_type == "stats":
        debug_path = "screenshots/debug/stats_debug.png" if args.debug else None
        profile = extract_detailed_stats(args.image, debug_path=debug_path)
    else:
        raise SystemExit(f"Unsupported screen type: {screen_type}")

    save_profile(profile, args.out)
    print(f"Detected screen: {screen_type}")
    print(f"Wrote: {args.out}")
    if args.debug:
        print("Debug output: screenshots/debug/")


if __name__ == "__main__":
    main()
