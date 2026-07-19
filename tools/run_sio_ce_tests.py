#!/usr/bin/env python3
"""Run the focused sIO Clan Expedition validation suite."""

from __future__ import annotations

import subprocess
import sys

TESTS = [
    "tests/test_sio_ce_damage.py",
    "tests/test_source_policy.py",
    "tests/test_sio_ce_integration.py",
]

if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-q", *TESTS]))
