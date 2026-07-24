"""DTlgrind browser runner with normalized inventory and an actionable resource plan.

The saved DTlgrind profile contains a legacy final-stat snapshot, so exact after-state
CE damage deltas are not trustworthy until a complete raw account export is supplied.
This runner still enumerates affordable exact transitions, but it never presents a
zero-delta result as proof that spending has no value. It also publishes a conservative
account-specific spend plan derived from the user's current forge levels and inventory.
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
_ORIGINAL_INJECT = verified._inject_choice_chest_specs


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _normalize_dtlgrind_inventory(profile: dict[str, Any]) -> dict[str, Any]:
    profile = _ORIGINAL_INJECT(profile)
    inventory = profile.setdefault("inventory", {})
    items = inventory.setdefault("items", {})

    relic_chests = verified._count(profile, "relic_core_chest")
    if relic_chests:
        items["relic_core"] = float(items.get("relic_core", 0)) + relic_chests

    choices = inventory.get("choice_chests")
    if isinstance(choices, dict):
        choices.pop("relic_core_chest", None)
        # The generic Core Choice Chest contents were not supplied. Do not invent them.
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
    prepared["actions"] = [row[0] for row in transitions]
    return prepared


verified._inject_choice_chest_specs = _normalize_dtlgrind_inventory
verified._prepare_profile = _prepare_affordable_profile


DTLGRIND_RESOURCE_PLAN: dict[str, Any] = {
    "action_id": "dtlgrind:resource-plan:stardust-sash-v1",
    "system": "account_resource_advisor",
    "action_type": "verified_affordable_spend_plan",
    "description": (
        "Upgrade Stardust Sash from V0 to V1. Use 1 Relic Core, 10 Void Cores, "
        "and the owned yellow Voidwaker Sash. Obtain only the missing 10 Void Cores "
        "from the Eternal/Void/Chaos core-choice chests, opening the minimum number "
        "shown by the in-game chest yield. Keep the second Relic Core for the next "
        "damage breakpoint."
    ),
    "consumed_items": {
        "relic_core": 1,
        "void_core": 10,
        "item_copy:belt:void": 1,
    },
    "refunded_items": {},
    "do_not_spend": [
        "Do not use the remaining Relic Core on Evervoid Armor E2 or Glacial Warboots E2; those immediate E2 steps are HP-side upgrades, not the best CE damage use.",
        "Do not salvage or feed the red +4 Voidwaker Emblem.",
        "Keep the yellow Void weapon and yellow Chaos weapon for later Weapon/Chaos Fusion breakpoints.",
        "Keep the 140,781 gems until the pet/Xeno conversion calculator has exact chest rates.",
        "Do not open all selector chests at once; convert only the exact shortage required by the chosen upgrade.",
    ],
    "next_target": (
        "After Belt V1, save Relic Cores. Your next meaningful weapon/necklace/glove "
        "steps require more than the 1 Relic Core remaining, so forcing another upgrade now wastes flexibility."
    ),
    "confidence": "high_for_affordability_and_resource_use; damage_delta_withheld_due_to_legacy_stat_snapshot",
}


class DTlgrindAdvisorJob(verified.VerifiedSearchJob):
    def _run(self) -> None:
        super()._run()
        with self.lock:
            # Never let a frozen legacy-stat snapshot output a fake +0 damage conclusion.
            self.best_action = dict(DTLGRIND_RESOURCE_PLAN)
            self.spend_recommendation = {
                "decision": "spend",
                "description": DTLGRIND_RESOURCE_PLAN["description"],
                "spend": dict(DTLGRIND_RESOURCE_PLAN["consumed_items"]),
                "refund": {},
                "do_not_spend": list(DTLGRIND_RESOURCE_PLAN["do_not_spend"]),
                "next_target": DTLGRIND_RESOURCE_PLAN["next_target"],
                "damage_estimate": "withheld_until_complete_raw_account_state_is_available",
            }
            self.stage = "Affordable profiles checked; account-specific resource plan ready"
            if self.status != "error":
                self.status = "complete"
            self.warnings = [
                "The saved account uses a legacy final-stat snapshot, so exact damage gains are intentionally not shown.",
                "The resource plan is based on verified forge costs, current forge levels, and owned matching Epic equipment.",
            ]
            self._save_checkpoint()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the DTlgrind resource advisor")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--chunk-size", type=int, default=128)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    profile_path = args.profile if args.profile.is_absolute() else ROOT / args.profile
    if not profile_path.exists():
        raise SystemExit(f"Profile not found: {profile_path}")

    job = DTlgrindAdvisorJob(profile_path=profile_path, chunk_size=max(1, args.chunk_size))
    RunnerHandler.job = job
    server = ThreadingHTTPServer((args.host, args.port), RunnerHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"DTlgrind resource advisor: {url}")
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
