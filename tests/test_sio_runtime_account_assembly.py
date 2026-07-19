from __future__ import annotations

import os
from pathlib import Path
import shutil

import pytest

from optimizer.sio_ce_account import prepare_sio_ce_profile
from optimizer.sio_runtime_oracle import SioCeRuntimeOracle, build_oracle_request


def _raw_account_profile() -> dict:
    return {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats_stage": "raw_profile",
            "attack": {"atkBase": 1000, "atkFinal": 0},
            "evolvePassives": False,
            "meta": {
                "mainHero": "King",
                "synergy": False,
                "synergyLevel": 0,
                "harmonyL": "None",
                "harmonyR": "None",
                "teamwork": [],
                "clanLevel": 0,
            },
            "heroes": {"King": {"stars": 1, "level": 80}},
            "items": {"Gloves": {"name": "Moonscar Bracer", "e": 1}},
            "collectibles": {"Book of Ancient Wisdom": {"stars": 8}},
            "upgradedCollectibles": [],
            "maxGear": 0,
            "customSets": {},
            "evoTree": {},
            "mounts": {"active": "", "data": {}},
            "skills": {},
            "pets": {},
            "petSkills": {},
            "techs": {},
            "settings": {"revives": [40, 70, 90]},
        },
    }


def test_raw_profile_is_mapped_to_original_sio_account_functions() -> None:
    prepared = prepare_sio_ce_profile(_raw_account_profile(), defer_runtime_conditions=True)
    sio = prepared["sio_ce"]
    account = sio["runtime_account_input"]
    assert sio["runtimeAccountAssembly"] is True
    assert account["mainHero"] == "King"
    assert account["heroes"]["King"] == {"stars": 1, "level": 80}
    assert account["items"]["Gloves"]["name"] == "Moonscar Bracer"
    assert account["collectibles"]["Book of Ancient Wisdom"]["stars"] == 8
    assert account["mounts"] == {"active": "", "data": {}}
    request = build_oracle_request(prepared)
    assert request["account_input"]["mainHero"] == "King"
    assert request["tech_input"] is None
    assert request["items"] == {}
    assert request["collectibles"] == {}


def test_stat_snapshot_does_not_auto_enable_raw_account_assembly() -> None:
    profile = {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats": {"critDamage": 200, "shieldDamageUptime": 1, "voidNeckBoostUptime": 1},
            "attack": {"atkBase": 1000, "atkFinal": 0},
            "evolvePassives": False,
            "techs": {},
        },
    }
    prepared = prepare_sio_ce_profile(profile, defer_runtime_conditions=True)
    assert "runtime_account_input" not in prepared["sio_ce"]
    assert build_oracle_request(prepared)["account_input"] is None


@pytest.mark.skipif(
    not os.environ.get("SIO_TOOLS_BUNDLE") or shutil.which("node") is None,
    reason="Exact supplied sIO bundle and Node are required for runtime integration.",
)
def test_original_sio_account_assembly_matches_bundle_result(tmp_path: Path) -> None:
    prepared = prepare_sio_ce_profile(_raw_account_profile(), defer_runtime_conditions=True)
    oracle = SioCeRuntimeOracle(
        bundle_path=Path(os.environ["SIO_TOOLS_BUNDLE"]),
        cache_path=tmp_path / "account-oracle.jsonl",
    )
    result = oracle.score_profile(prepared)
    assert result["supported"] is True
    assert result["account_assembly_exact"] is True
    assert result["total_damage"] == pytest.approx(130772.97969120006, rel=1e-12)
    assert result["stats"]["critRate"] == 45
    assert result["stats"]["critDamage"] == 200
    assert result["stats"]["atkHeroPercent"] == 5
    assert result["account_context"]["cooldownReduction"] == 1
    required = {37013, 63941, 5005, 42052, 41950, 57223, 89505, 42806, 70324, 51642, 94578, 92316, 30396, 13024, 19425}
    assert required <= set(result["account_assembly_modules"])
    oracle.close()
