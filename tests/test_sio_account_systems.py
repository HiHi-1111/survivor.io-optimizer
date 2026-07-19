from __future__ import annotations

from optimizer.damage_engine import estimate_damage_totals
from optimizer.sio_collectibles import assemble_sio_collectible_stats
from optimizer.sio_pets import assemble_sio_pet_stats
from optimizer.sio_survivors import (
    assemble_sio_skill_evo_stats,
    assemble_sio_survivor_stats,
)


def test_survivor_level_and_main_star_scope():
    result = assemble_sio_survivor_stats(
        {"sio_ce": {"heroes": {"King": {"stars": 1, "level": 80}}, "meta": {"mainHero": "King"}}}
    )
    assert result["stats"]["critRate"] == 5
    assert result["stats"]["atkHeroPercent"] == 5


def test_synergy_adds_exact_threshold_and_hero_atk():
    result = assemble_sio_survivor_stats(
        {"sio_ce": {"heroes": {}, "meta": {"synergy": True, "synergyLevel": 10}}}
    )
    assert result["stats"]["atkHero"] == 4000
    assert result["stats"]["critDamage"] == 10
    assert result["stats"]["skillDamage"] == 10


def test_global_collectible_star_effect():
    result = assemble_sio_collectible_stats(
        {"sio_ce": {"collectibles": {"Book of Ancient Wisdom": {"stars": 8}}}}
    )
    assert result["stats"]["critRate"] == 10


def test_skill_and_evo_tree_stats():
    result = assemble_sio_skill_evo_stats(
        {"sio_ce": {"skills": {"HP Bullet": True}, "evoTree": {"Expose Weakness": True}}}
    )
    assert result["stats"]["hpBulletBoost"] == 50
    assert result["stats"]["critRate"] == 8


def test_xeno_pet_direct_and_resonance_stats():
    result = assemble_sio_pet_stats(
        {
            "sio_ce": {
                "pets": {"active": "Crucker", "stars": {"Crucker": 1}, "support": []},
                "petSkills": {"Sync Rate": {"value": 20}},
            }
        }
    )
    assert result["stats"]["xenoDamage"] > 0
    assert result["stats"]["xenoResMultiplier"] == 0.8


def test_account_sources_are_merged_before_moonscar_thresholds():
    result = estimate_damage_totals(
        {
            "game_mode": "clan_expedition",
            "sio_ce": {
                "stats_stage": "raw_profile",
                "heroes": {"King": {"stars": 1, "level": 80}},
                "meta": {"mainHero": "King"},
                "collectibles": {"Book of Ancient Wisdom": {"stars": 8}},
                "items": {"Gloves": {"name": "Moonscar Bracer", "e": 1}},
                "attack": {"atkBase": 1000, "atkFinal": 0},
                "passive_multiplier": 1.0,
            },
        }
    )
    assert result["normalized_stats"]["critRate"] == 45
    assert result["normalized_stats"]["critDamage"] == 200
    assert result["account_detail"]["survivors"]["mainHero"] == "King"
    assert result["formula_pipeline"] in {
        "partial_python_sio_account_assembly_then_24804_67727_88426",
        "sio_account_assembly_then_24804_then_runtime_13024_88426_67727",
    }
