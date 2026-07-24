"""DTlgrind runner with account inventory normalized before exact optimization.

This module fixes two browser-runner integration problems without changing the
source-locked optimizer formulas:
1. Epic spare S-grade equipment is exposed as the item_copy resources used by
   Astral Forge affordability checks.
2. Browser progress counts affordable exact transitions, not every theoretical
   progression state that the generator considered and correctly rejected.
"""
from __future__ import annotations

import argparse
import re
import threading
import webbrowser
from pathlib import Path
from typing import Any

from app import verified_browser_runner as verified
from app.browser_runner import ROOT, RunnerHandler, ThreadingHTTPServer
from optimizer.source_pack_optimizer import _prepare_profile as source_prepare_profile

DEFAULT_PROFILE = ROOT / "profiles" / "dtlgrind.json"


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _normalize_dtlgrind_inventory(profile: dict[str, Any]) -> dict[str, Any]:
    """Expose only directly verified inventory conversions to the optimizer.

    Yellow in the supplied inventory is Epic, which is exactly the equipment
    copy unit consumed by SS Astral Forge levels. Purple pieces are deliberately
    not converted because the missing merge-fodder state is not known. The two
    Relic Core chests contain Relic Cores and are therefore counted directly.
    """
    profile = verified._inject_choice_chest_specs(profile)
    inventory = profile.setdefault("inventory", {})
    items = inventory.setdefault("items", {})

    # A Relic Core chest is single-purpose. Count its contents directly and
    # remove the redundant choice-chest representation to prevent double use.
    relic_chests = verified._count(profile, "relic_core_chest")
    if relic_chests:
        items["relic_core"] = float(items.get("relic_core", 0)) + relic_chests
    choices = inventory.get("choice_chests")
    if isinstance(choices, dict):
        choices.pop("relic_core_chest", None)
        # The user's generic Core Choice Chest reward list was not supplied.
        # Do not assign it to unrelated core systems.
        choices.pop("core_selector_chest", None)

    mapped: dict[str, float] = {}
    for row in inventory.get("spare_equipment", []) or []:
        if not isinstance(row, dict) or str(row.get("rarity", "")).lower() != "yellow":
            continue
        slot = _slug(row.get("slot"))
        side = _slug(row.get("side"))
        quantity = float(row.get("quantity", 1) or 0)
        if slot and side and quantity > 0:
            key = f"item_copy:{slot}:{side}"
            items[key] = float(items.get(key, 0)) + quantity
            mapped[key] = mapped.get(key, 0) + quantity

    audit = profile.setdefault("_runner_input_audit", {})
    audit["mapped_epic_spare_equipment"] = mapped
    audit["direct_relic_cores_from_chests"] = relic_chests
    audit["unmapped_generic_core_choice_chests"] = verified._count(
        profile, "core_selector_chest", "core_selector_chests"
    )
    return profile


def _prepare_affordable_profile(profile: dict[str, Any]) -> dict[str, Any]:
    prepared = source_prepare_profile(profile)
    transitions = list(prepared.get("transitions", []))
    # The webpage's discovered/generated count must describe states that can
    # actually be scored for this account. Rejected theoretical targets remain
    # available in rejection diagnostics but are not used as a coverage ratio.
    prepared["actions"] = [row[0] for row in transitions]
    return prepared


# The verified runner resolves these functions from its module globals.
verified._inject_choice_chest_specs = _normalize_dtlgrind_inventory
verified._prepare_profile = _prepare_affordable_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the fixed DTlgrind optimizer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--chunk-size", type=int, default=128)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    profile_path = args.profile if args.profile.is_absolute() else ROOT / args.profile
    if not profile_path.exists():
        raise SystemExit(f"Profile not found: {profile_path}")

    job = verified.VerifiedSearchJob(profile_path=profile_path, chunk_size=max(1, args.chunk_size))
    RunnerHandler.job = job
    server = ThreadingHTTPServer((args.host, args.port), RunnerHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Fixed DTlgrind browser optimizer: {url}")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
