"""Run a Clan Expedition sample optimization from the command line."""

from __future__ import annotations

from pprint import pprint

from optimizer.main import optimize


def sample_player() -> dict:
    return {
        "game_mode": "clan_expedition",
        "goal_scenario": "clan_expedition",
        "build_stats": {
            "atk": 500000,
            "crit_rate": 0.75,
            "crit_damage": 2.5,
            "skill_damage": 1.2,
            "vulnerability": 0,
            "shield_damage": 0,
            "damage_to_chilled": 0,
            "damage_to_poisoned": 0,
            "boss_damage": 0,
            "all_damage": 0,
            "final_damage": 0,
        },
        "sio_ce": {
            "stats_stage": "legacy_stat_snapshot",
            "attack": {"atkBase": 500000, "atkFinal": 0},
            "passive_multiplier": 1.0,
        },
        "inventory": {"core_selector_chests": 3},
        "resources": {"astral_core": 1, "xeno_core": 0, "resonance_chip": 4},
    }


def main() -> None:
    pprint(optimize(sample_player()), sort_dicts=False)


if __name__ == "__main__":
    main()
