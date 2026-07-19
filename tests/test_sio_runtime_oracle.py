from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

import pytest

from optimizer.sio_ce_constants import SIO_BUNDLE_SHA256
from optimizer.sio_runtime_oracle import (
    SioCeRuntimeOracle,
    SioRuntimeInputError,
    build_oracle_request,
    ensure_extracted_bundle,
)


def _tech_profile() -> dict:
    return {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats": {
                "critDamage": 200,
                "shieldDamageUptime": 1,
                "voidNeckBoostUptime": 1,
            },
            "attack": {"atkBase": 1000, "atkFinal": 0},
            "evolvePassives": True,
            "skills": {
                "Drone Mode": True,
                "Exo Bracer": True,
                "Ammo Thruster": True,
                "HE Fuel": True,
                "Energy Cube": True,
            },
            "techs": {
                "Energy Guidance System": {
                    "deployed": True,
                    "rarity": "Eternal",
                    "resonance": 900,
                    "overload": 0,
                    "mode": "Drone Mode",
                }
            },
        },
    }


def test_build_oracle_request_preserves_exact_tech_schema() -> None:
    request = build_oracle_request(_tech_profile())
    tech = request["tech_input"]
    assert tech["evolvePassives"] is True
    assert tech["gameMode"] == "ce"
    assert tech["settings"]["calcMode"] == "damage"
    assert tech["techs"]["Energy Guidance System"]["mode"] == "Drone Mode"
    assert request["attack"] == {"atkBase": 1000, "atkFinal": 0}


def test_missing_evolved_passive_choice_is_unknown_not_guessed() -> None:
    profile = _tech_profile()
    del profile["sio_ce"]["evolvePassives"]
    with pytest.raises(SioRuntimeInputError):
        build_oracle_request(profile)


def test_inexact_flat_tech_snapshot_is_rejected() -> None:
    profile = _tech_profile()
    profile["sio_ce"]["techs"] = {"Drone Mode": 900}
    with pytest.raises(SioRuntimeInputError):
        build_oracle_request(profile)


def test_bundle_hash_is_source_locked(tmp_path: Path) -> None:
    fake = tmp_path / "fake.zip"
    fake.write_bytes(b"not the supplied sIO bundle")
    old = os.environ.pop("SIO_ALLOW_UNVERIFIED_BUNDLE", None)
    try:
        with pytest.raises(Exception) as error:
            ensure_extracted_bundle(fake, cache_root=tmp_path / "cache")
        assert SIO_BUNDLE_SHA256 in str(error.value)
    finally:
        if old is not None:
            os.environ["SIO_ALLOW_UNVERIFIED_BUNDLE"] = old


@pytest.mark.skipif(
    not os.environ.get("SIO_TOOLS_BUNDLE") or shutil.which("node") is None,
    reason="Exact supplied sIO bundle and Node are required for runtime integration.",
)
def test_exact_runtime_matches_known_drone_ce_value(tmp_path: Path) -> None:
    oracle = SioCeRuntimeOracle(
        bundle_path=Path(os.environ["SIO_TOOLS_BUNDLE"]),
        cache_path=tmp_path / "oracle.jsonl",
    )
    result = oracle.score_profile(_tech_profile())
    assert result["supported"] is True
    assert result["total_damage"] == pytest.approx(147297659.83909208, rel=1e-12)
    assert result["formula_provenance"]["modules"] == [13024, 88426, 67727]
    oracle.close()
