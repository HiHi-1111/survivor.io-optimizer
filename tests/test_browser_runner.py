from __future__ import annotations

import json
from pathlib import Path

from app.browser_runner import SearchJob
from optimizer.player_state import validate_player_state

ROOT = Path(__file__).resolve().parents[1]


def test_dtlgrind_profile_is_valid_player_state() -> None:
    profile = json.loads((ROOT / "profiles" / "dtlgrind.json").read_text(encoding="utf-8"))
    state = validate_player_state(profile)
    assert state.goal_scenario == "clan_expedition"
    assert state.build_stats.atk == 822300
    assert state.inventory.core_selector_chests == 8
    assert state.resources.gems == 130539


def test_search_job_snapshot_reports_real_rate_and_eta(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text("{}", encoding="utf-8")
    job = SearchJob(profile_path=profile_path)
    job.status = "running"
    job.started_at = 100.0
    job.total_states = 100
    job.checked_states = 40
    job.baseline_damage = 1000
    job.best_damage = 1250
    job.finished_at = 110.0

    snapshot = job.snapshot()

    assert snapshot["states_per_second"] == 4
    assert snapshot["remaining_states"] == 60
    assert snapshot["damage_gain"] == 250
    assert snapshot["damage_gain_percent"] == 25
