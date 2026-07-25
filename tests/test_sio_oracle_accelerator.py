from __future__ import annotations

from pathlib import Path

import pytest

from optimizer.sio_oracle_accelerator import clear_hot_cache, metrics
from optimizer.sio_runtime_oracle import SioCeRuntimeOracle


def _profile(atk: float = 1000) -> dict:
    return {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats_stage": "post_24804_account_and_items",
            "stats": {"critDamage": 200},
            "attack": {"atkBase": atk, "atkFinal": 0},
        },
    }


def test_duplicate_exact_requests_are_forwarded_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import optimizer.sio_oracle_accelerator as accelerator

    clear_hot_cache()
    forwarded: list[list[dict]] = []

    def fake_original(_self, profiles):
        rows = list(profiles)
        forwarded.append(rows)
        return [{"supported": True, "total_damage": row["sio_ce"]["attack"]["atkBase"]} for row in rows]

    monkeypatch.setattr(accelerator, "_ORIGINAL_SCORE_PROFILES", fake_original)
    oracle = SioCeRuntimeOracle(cache_path=tmp_path / "unused.jsonl")
    rows = oracle.score_profiles([_profile(), _profile(), _profile(2000), _profile()])

    assert len(forwarded) == 1
    assert len(forwarded[0]) == 2
    assert [row["total_damage"] for row in rows] == [1000, 1000, 2000, 1000]
    assert rows[0] is not rows[1]
    assert metrics()["duplicates_collapsed"] >= 2
    oracle.close()


def test_hot_cache_reuses_exact_result_across_calls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import optimizer.sio_oracle_accelerator as accelerator

    clear_hot_cache()
    calls = 0

    def fake_original(_self, profiles):
        nonlocal calls
        calls += 1
        rows = list(profiles)
        return [{"supported": True, "total_damage": 123.0} for _ in rows]

    monkeypatch.setattr(accelerator, "_ORIGINAL_SCORE_PROFILES", fake_original)
    oracle = SioCeRuntimeOracle(cache_path=tmp_path / "unused.jsonl")

    first = oracle.score_profile(_profile())
    second = oracle.score_profile(_profile())

    assert first == second
    assert calls == 1
    assert metrics()["hot_cache_hits"] >= 1
    oracle.close()


def test_distinct_requests_are_never_collapsed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import optimizer.sio_oracle_accelerator as accelerator

    clear_hot_cache()
    seen: list[float] = []

    def fake_original(_self, profiles):
        rows = list(profiles)
        seen.extend(row["sio_ce"]["attack"]["atkBase"] for row in rows)
        return [{"supported": True, "total_damage": value} for value in seen[-len(rows):]]

    monkeypatch.setattr(accelerator, "_ORIGINAL_SCORE_PROFILES", fake_original)
    oracle = SioCeRuntimeOracle(cache_path=tmp_path / "unused.jsonl")
    rows = oracle.score_profiles([_profile(1000), _profile(1001)])

    assert seen == [1000, 1001]
    assert [row["total_damage"] for row in rows] == [1000, 1001]
    oracle.close()
