#!/usr/bin/env python3
"""Run the focused sIO Clan Expedition and lineage validation suite."""

from __future__ import annotations

import subprocess
import sys

TESTS = [
    "tests/test_sio_ce_damage.py",
    "tests/test_sio_items.py",
    "tests/test_sio_account_systems.py",
    "tests/test_sio_runtime_account_assembly.py",
    "tests/test_sio_exact_actions.py",
    "tests/test_sio_tech_progression.py",
    "tests/test_sio_progression_frontiers.py",
    "tests/test_sio_tetris.py",
    "tests/test_sio_runtime_oracle.py",
    "tests/test_sio_bundle_mapping.py",
    "tests/test_sio_calibration.py",
    "tests/test_champion_lineage.py",
    "tests/test_source_policy.py",
    "tests/test_sio_ce_integration.py",
    "tests/test_source_pack_optimizer.py",
]

if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-q", *TESTS]))
