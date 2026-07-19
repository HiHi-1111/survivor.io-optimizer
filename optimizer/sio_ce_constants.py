"""Constants extracted from the user-supplied sIO Tools runtime bundle."""

from __future__ import annotations

from typing import Any

SIO_BUNDLE_SHA256 = "7665a1d4ad479f799b9360347dad98ffdca8125d35c6fb0072c68343708c847d"
SIO_FORMULA_MODULES = (67727, 88426, 24804, 42052, 51642, 40514, 32085, 37013, 5834, 62994)
SUPPORTED_GAME_MODE = "clan_expedition"
SUPPORTED_CALC_MODE = "damage"

SIO_BASE_STATS: dict[str, float] = {
    "critDamage": 200.0,
    "poisonedUptime": 0.0,
    "weakenedUptime": 0.0,
    "chilledUptime": 0.0,
    "lacerationUptime": 0.0,
    "divineFireUptime": 0.0,
    "shieldDamageUptime": 1.0,
    "voidNeckBoostUptime": 1.0,
}

# module 32085.mg
SIO_DIRECT_DAMAGE_COEFFICIENTS: dict[str, float] = {
    "ssWeapon": 148.02,
    "taloxaOverload": 1634.416,
    "crimsonBat": 3545.66,
    "Taloxa": 1.0,
    "Joey": 1.0,
    "Metalia": 28.4,
    "Master Yang": 57.2,
    "King": 112.03,
    "Common": 54.72,
    "Drone": 26.21,
    "Molotov": 38.0,
    "Molotov Mode": 40.92,
    "Drill": 50.02,
    "Rocket": 31.66,
    "Durian Mode": 9.38,
    "Soccer Mode": 19.7,
    "Drone Mode": 48.22,
    "Forcefield Mode": 18.94,
    "Drill Shot Mode": 46.21,
    "Rocket Mode": 49.04,
    "Lightning Mode": 53.76,
    "Boomerang Mode": 24.36,
    "Guardian Mode": 18.94,
    "Laser Mode": 38.16,
    "Brick Mode": 70.0,
    "Capy": 188.26,
    "Crucker": 158.7,
    "Puffo": 308.67,
    "King Blizzblast": 198.74,
    "Nutjob": 300.0,
    "Gourmeow": 300.0,
    "Electric Scooter": 77.0,
    "Tech Hoverboard": 100.0,
    "Doomsteed": 100.0,
}

MOUNT_COMPONENT_STATS = (
    "critDamage",
    "skillDamage",
    "shieldDamage",
    "weakened",
    "poisoned",
    "chilled",
    "laceration",
    "damageBoss",
)

# module 40514.Of. Index 0 is base; indices 1-8 are stars.
MOUNT_SYNC_RATES: dict[str, tuple[float, ...]] = {
    "Legend": (0.40, 0.44, 0.48, 0.55, 0.62, 0.71, 0.80, 0.90, 1.00),
    "Excellent": (0.30, 0.33, 0.36, 0.40, 0.45, 0.50, 0.55, 0.60, 0.75),
    "Better": (0.20, 0.22, 0.24, 0.28, 0.32, 0.38, 0.44, 0.52, 0.60),
}
MOUNT_MAX_COMPLETED_LINES = (4, 4, 5, 5, 6, 6, 7, 7, 8)

# module 37013.c.mounts
MOUNT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "Doomsteed": {
        "rarity": "Legend",
        "lines": {
            1: {"poisoned": 20.0},
            3: {"poisoned": 40.0, "skillDamage": 50.0},
            4: {"skillDamage": 150.0},
            6: {"poisoned": 60.0, "laceration": 30.0},
            7: {"poisoned": 80.0, "damageBoss": 5.0},
            8: {"damageBoss": 25.0},
        },
        "damage": (325.0, 346.0, 360.0, 360.0, 380.0, 380.0, 380.0, 442.0, 442.0),
    },
    "Tech Hoverboard": {
        "rarity": "Excellent",
        "lines": {
            1: {"chilled": 15.0, "skillDamage": 10.0},
            3: {"chilled": 25.0, "skillDamage": 15.0},
            4: {"shieldDamage": 40.0},
            5: {"chilled": 60.0},
            6: {"chilled": 40.0, "skillDamage": 30.0},
            7: {"chilled": 60.0, "skillDamage": 45.0},
            8: {"shieldDamage": 60.0},
        },
        "damage": (193.6, 194.084, 199.496, 204.424, 204.424, 387.0, 387.0, 500.0, 500.0),
    },
    "Electric Scooter": {
        "rarity": "Better",
        "lines": {
            1: {"weakened": 10.0},
            3: {"weakened": 15.0, "critDamage": 20.0},
            4: {"critDamage": 35.0},
            5: {"laceration": 10.0},
            6: {"weakened": 20.0, "critDamage": 55.0},
            7: {"weakened": 35.0, "critDamage": 90.0},
            8: {"laceration": 20.0},
        },
        "damage": (153.0, 160.0, 160.0, 180.0, 180.0, 200.0, 200.0, 230.0, 230.0),
    },
}
