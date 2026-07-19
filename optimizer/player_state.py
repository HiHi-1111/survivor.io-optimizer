"""Lossless player-state models for the Survivor.io optimizer runtime."""
from __future__ import annotations
from copy import deepcopy
from typing import Any
from pydantic import BaseModel, Field, TypeAdapter, model_validator


class FlexibleStateModel(BaseModel):
    # Unknown/new sIO fields are retained so a game update is visible to audits
    # instead of being silently removed during validation.
    model_config = {"extra": "allow"}


class PlayerBuildStats(FlexibleStateModel):
    atk: float = 0
    crit_rate: float = 0
    crit_damage: float = 0
    skill_damage: float = 0
    vulnerability: float = 0
    shield_damage: float = 0
    damage_to_chilled: float = 0
    damage_to_poisoned: float = 0
    boss_damage: float = 0
    all_damage: float = 0
    final_damage: float = 0


class PlayerGear(FlexibleStateModel):
    weapon: dict[str, Any] | None = None
    necklace: dict[str, Any] | None = None
    gloves: dict[str, Any] | None = None
    armor: dict[str, Any] | None = None
    belt: dict[str, Any] | None = None
    boots: dict[str, Any] | None = None


class PlayerSurvivor(FlexibleStateModel):
    id: str | None = None
    level: int = 0
    stars: int = 0
    awakening: int = 0
    passives: list[str] = Field(default_factory=list)


class PlayerPetSetup(FlexibleStateModel):
    main_pet: str | None = None
    active: str | None = None
    assisting_pets: list[str] = Field(default_factory=list)
    support: list[str] = Field(default_factory=list)
    awakened: dict[str, int] = Field(default_factory=dict)
    stars: dict[str, int] = Field(default_factory=dict)


class PlayerTechSetup(FlexibleStateModel):
    equipped: list[str] = Field(default_factory=list)
    resonance: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)


class PlayerCollectibles(FlexibleStateModel):
    owned: dict[str, Any] = Field(default_factory=dict)
    salvage: dict[str, Any] = Field(default_factory=dict)


class PlayerResources(FlexibleStateModel):
    astral_core: int = 0
    xeno_core: int = 0
    resonance_chip: int = 0
    relic_core: int = 0
    gems: int = 0
    keys: int = 0


class PlayerInventory(FlexibleStateModel):
    core_selector_chests: int = 0
    selector_chests: dict[str, int] = Field(default_factory=dict)
    items: dict[str, Any] = Field(default_factory=dict)
    resources: dict[str, Any] = Field(default_factory=dict)


class PlayerMountSetup(FlexibleStateModel):
    active: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class PlayerSioCE(FlexibleStateModel):
    """Complete, forward-compatible sIO Clan Expedition input envelope."""

    stats_stage: str = "unknown"
    stats: dict[str, Any] = Field(default_factory=dict)
    attack: dict[str, Any] = Field(default_factory=dict)
    direct_skill_factors: dict[str, Any] = Field(default_factory=dict)
    passive_multiplier: float | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    items: dict[str, Any] = Field(default_factory=dict)
    heroes: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
    skills: dict[str, Any] = Field(default_factory=dict)
    evoTree: dict[str, Any] = Field(default_factory=dict)
    pets: dict[str, Any] = Field(default_factory=dict)
    petSkills: dict[str, Any] = Field(default_factory=dict)
    techs: dict[str, Any] = Field(default_factory=dict)
    collectibles: dict[str, Any] = Field(default_factory=dict)
    customSets: dict[str, Any] = Field(default_factory=dict)
    mounts: dict[str, Any] = Field(default_factory=dict)
    upgradedCollectibles: list[str] = Field(default_factory=list)
    exact_actions: list[dict[str, Any]] = Field(default_factory=list)
    evolvePassives: bool | None = None
    activeSurvivor: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_known_aliases(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = deepcopy(value)
        aliases = {
            "stats_stage": ("statsStage",),
            "direct_skill_factors": ("directSkillFactors", "ceDamage"),
            "evoTree": ("evo_tree",),
            "petSkills": ("pet_skills",),
            "customSets": ("custom_sets",),
            "upgradedCollectibles": ("upgraded_collectibles",),
            "evolvePassives": ("evolve_passives",),
            "activeSurvivor": ("active_survivor",),
            "exact_actions": ("exactActions",),
        }
        for canonical, alternatives in aliases.items():
            if canonical in data:
                continue
            for alternative in alternatives:
                if alternative in data:
                    data[canonical] = deepcopy(data[alternative])
                    break
        return data


class PlayerState(FlexibleStateModel):
    build_stats: PlayerBuildStats = Field(default_factory=PlayerBuildStats)
    gear: PlayerGear = Field(default_factory=PlayerGear)
    survivor: PlayerSurvivor = Field(default_factory=PlayerSurvivor)
    pets: PlayerPetSetup = Field(default_factory=PlayerPetSetup)
    tech_parts: PlayerTechSetup = Field(default_factory=PlayerTechSetup)
    collectibles: PlayerCollectibles = Field(default_factory=PlayerCollectibles)
    mounts: PlayerMountSetup = Field(default_factory=PlayerMountSetup)
    sio_ce: PlayerSioCE = Field(default_factory=PlayerSioCE)
    resources: PlayerResources = Field(default_factory=PlayerResources)
    inventory: PlayerInventory = Field(default_factory=PlayerInventory)
    owned_items: list[str] = Field(default_factory=list)
    game_mode: str = "clan_expedition"
    goal_scenario: str = "clan_expedition"
    notes: str = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_top_level_aliases(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = deepcopy(value)
        if "sio_ce" not in data and isinstance(data.get("sioCE"), dict):
            data["sio_ce"] = deepcopy(data["sioCE"])
        if "goal_scenario" not in data and "goalScenario" in data:
            data["goal_scenario"] = data["goalScenario"]
        if "game_mode" not in data and "gameMode" in data:
            data["game_mode"] = data["gameMode"]
        return data


# TypeAdapter construction builds a core schema, so the adapters are created once
# and reused for every single and batch validation call.
PLAYER_STATE_ADAPTER = TypeAdapter(PlayerState)
PLAYER_STATE_LIST_ADAPTER = TypeAdapter(list[PlayerState])


def validate_player_state(data: dict[str, Any] | PlayerState) -> PlayerState:
    if isinstance(data, PlayerState):
        return data
    return PLAYER_STATE_ADAPTER.validate_python(data)


def validate_player_states(data: list[dict[str, Any] | PlayerState]) -> list[PlayerState]:
    return PLAYER_STATE_LIST_ADAPTER.validate_python(data)


__all__ = [
    "PLAYER_STATE_ADAPTER",
    "PLAYER_STATE_LIST_ADAPTER",
    "PlayerState",
    "validate_player_state",
    "validate_player_states",
]
