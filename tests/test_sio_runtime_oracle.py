from __future__ import annotations

import os
from pathlib import Path
import shutil

import pytest

from optimizer.sio_ce_constants import SIO_BUNDLE_SHA256
from optimizer.sio_runtime_oracle import (
    ORACLE_SCHEMA,
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
            "settings": {"revives": [40, 70, 90]},
        },
    }


def test_build_oracle_request_preserves_exact_tech_and_uptime_context() -> None:
    profile = _tech_profile()
    profile["sio_ce"]["items"] = {
        "Armor": {"name": "Eternal Suit", "e": 1},
        "Necklace": {"name": "Voidwaker Emblem", "e": 0},
    }
    profile["sio_ce"]["collectibles"] = {"Lucky Charm": {"stars": 3}}
    profile["sio_ce"]["meta"] = {"mainHero": "Venato"}
    request = build_oracle_request(profile)
    tech = request["tech_input"]
    assert tech["evolvePassives"] is True
    assert tech["gameMode"] == "ce"
    assert tech["settings"]["calcMode"] == "damage"
    assert tech["techs"]["Energy Guidance System"]["mode"] == "Drone Mode"
    assert request["attack"] == {"atkBase": 1000, "atkFinal": 0}
    assert request["items"]["Armor"]["name"] == "Eternal Suit"
    assert request["collectibles"]["Lucky Charm"]["stars"] == 3
    assert request["activeSurvivor"] == "Venato"
    assert request["venato"] is True
    assert request["settings"]["revives"] == [40, 70, 90]
    assert request["skipRuntime24804"] is False


def test_known_snake_case_aliases_are_preserved() -> None:
    profile = _tech_profile()
    profile["sio_ce"]["upgraded_collectibles"] = ["Lucky Charm"]
    profile["sio_ce"]["active_survivor"] = "King"
    request = build_oracle_request(profile)
    assert request["upgradedCollectibles"] == ["Lucky Charm"]
    assert request["activeSurvivor"] == "King"


def test_post_24804_request_drops_raw_upgrade_context_and_needs_no_evolve_choice() -> None:
    profile = {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats_stage": "post_24804_account_and_items",
            "stats": {
                "critDamage": 200,
                "hpBulletBoost": 1.6,
                "adrenaline": 12,
                "poisonedUptime": 1,
                "weakenedUptime": 0,
                "shieldDamageUptime": 1,
                "voidNeckBoostUptime": 1,
            },
            "attack": {"atkBase": 1000, "atkFinal": 0},
            "techs": {"Energy Guidance System": {"deployed": True}},
            "items": {"Armor": {"name": "Eternal Suit", "e": 1}},
            "collectibles": {"Lucky Charm": {"stars": 8}},
        },
    }
    request = build_oracle_request(profile)
    assert request["skipRuntime24804"] is True
    assert request["statsStage"] == "post_24804_account_and_items"
    assert request["tech_input"] is None
    assert request["items"] == {}
    assert request["collectibles"] == {}
    assert request["stats"]["hpBulletBoost"] == 1.6


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
def test_exact_runtime_runs_24804_before_final_ce_damage(tmp_path: Path) -> None:
    oracle = SioCeRuntimeOracle(
        bundle_path=Path(os.environ["SIO_TOOLS_BUNDLE"]),
        cache_path=tmp_path / "oracle.jsonl",
    )
    result = oracle.score_profile(_tech_profile())
    assert result["supported"] is True
    assert result["total_damage"] == pytest.approx(147297659.83909208, rel=1e-12)
    assert result["formula_provenance"]["schema"] == ORACLE_SCHEMA
    assert result["formula_provenance"]["modules"] == [13024, 24804, 88426, 67727]
    assert result["formula_order"] == ["13024.T", "24804.zP", "88426.y", "24804.IE", "67727.f"]
    assert result["skipped_24804"] is False
    assert all(0 <= value <= 1 for value in result["uptime_values"].values())
    oracle.close()


@pytest.mark.skipif(
    not os.environ.get("SIO_TOOLS_BUNDLE") or shutil.which("node") is None,
    reason="Exact supplied sIO bundle and Node are required for runtime integration.",
)
def test_exact_runtime_applies_evolved_passive_final_transforms(tmp_path: Path) -> None:
    profile = {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats": {
                "critDamage": 200,
                "hpBulletBoost": 50,
                "adrenaline": 10,
                "metaliaPoisoned": 60,
                "metaliaChilled": 30,
                "joeyWeakSpot": 10,
                "poisonedUptime": 2,
                "weakenedUptime": -1,
                "chilledUptime": 0.5,
                "shieldDamageUptime": 1,
                "voidNeckBoostUptime": 1,
            },
            "attack": {"atkBase": 1000, "atkFinal": 0},
            "evolvePassives": True,
            "techs": {},
            "skills": {},
            "settings": {"revives": [40, 70, 90]},
        },
    }
    oracle = SioCeRuntimeOracle(
        bundle_path=Path(os.environ["SIO_TOOLS_BUNDLE"]),
        cache_path=tmp_path / "oracle.jsonl",
    )
    result = oracle.score_profile(profile)
    stats = result["stats"]
    assert stats["hpBulletBoost"] == pytest.approx(1.6)
    assert stats["adrenaline"] == pytest.approx(12)
    assert stats["poisoned"] == pytest.approx(75)
    assert stats["chilled"] == pytest.approx(45)
    assert stats["metaliaPoisoned"] == 0
    assert stats["metaliaChilled"] == 0
    assert stats["joeyWeakSpot"] == pytest.approx(13.5)
    assert result["uptime_values"]["poisonedUptime"] == 1
    assert result["uptime_values"]["weakenedUptime"] == 0
    assert result["uptime_values"]["chilledUptime"] == pytest.approx(0.5)
    oracle.close()


@pytest.mark.skipif(
    not os.environ.get("SIO_TOOLS_BUNDLE") or shutil.which("node") is None,
    reason="Exact supplied sIO bundle and Node are required for runtime integration.",
)
def test_post_24804_snapshot_is_not_transformed_a_second_time(tmp_path: Path) -> None:
    profile = {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats_stage": "post_24804_account_and_items",
            "stats": {
                "critDamage": 200,
                "hpBulletBoost": 1.6,
                "adrenaline": 12,
                "poisoned": 75,
                "chilled": 45,
                "poisonedUptime": 1,
                "weakenedUptime": 0,
                "chilledUptime": 0.5,
                "shieldDamageUptime": 1,
                "voidNeckBoostUptime": 1,
            },
            "attack": {"atkBase": 1000, "atkFinal": 0},
            "techs": {"Energy Guidance System": {"deployed": True}},
        },
    }
    oracle = SioCeRuntimeOracle(
        bundle_path=Path(os.environ["SIO_TOOLS_BUNDLE"]),
        cache_path=tmp_path / "oracle.jsonl",
    )
    result = oracle.score_profile(profile)
    assert result["supported"] is True
    assert result["skipped_24804"] is True
    assert result["stats"]["hpBulletBoost"] == pytest.approx(1.6)
    assert result["stats"]["adrenaline"] == pytest.approx(12)
    assert result["stats"]["poisoned"] == pytest.approx(75)
    assert result["stats"]["chilled"] == pytest.approx(45)
    assert result["formula_modules"] == [88426, 67727]
    assert result["formula_order"] == ["post_24804_snapshot", "88426.y", "67727.f"]
    oracle.close()
