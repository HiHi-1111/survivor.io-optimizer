"""Exact Survivor role, Harmony, and Teamwork configuration states.

Source contracts mapped from sIO modules 32085, 92316, and the Heroes UI:

* Main Survivor candidates are the owned sIO main list.
* Harmony left/right are role-specific, allow None, exclude the main Survivor,
  and cannot contain the same non-None Survivor.
* Teamwork capacity is ``floor(clamp(mainStars - 6, 0, 8) / 2)``.
* Teamwork is consumed as a JavaScript ``Set`` by module 92316, so it is an
  unordered subset. This module uses combinations, never slot permutations.
* Donatello and Vulcan are not selectable as Teamwork members in the sIO UI.

The complete state count is calculated before enumeration. When it exceeds the
configured budget, no partial actions are returned. That prevents a truncated
configuration search from being presented as the exact optimum.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from itertools import combinations
import math
import re
from typing import Any, Mapping, Sequence

from optimizer.sio_survivor_data import SIO_SURVIVOR_DATA
from optimizer.sio_survivors import hero_state_from_profile

NONE = "None"
MAIN_HEROES = ("Master Yang", "Metalia", "Joey", "Taloxa", "Venato")
HARMONY_HEROES = ("Common", "King", "Master Yang", "Metalia", "Joey", "Taloxa", "Venato")
TEAMWORK_EXCLUDED = frozenset({"Donatello", "Vulcan"})
DEFAULT_MAX_STATES = 250_000


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "none"


def teamwork_slot_count(stars: Any) -> int:
    return math.floor(max(0.0, min(8.0, _number(stars) - 6.0)) / 2.0)


def _meta(profile: Mapping[str, Any]) -> dict[str, Any]:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    raw = sio.get("meta") if isinstance(sio.get("meta"), Mapping) else profile.get("meta")
    result = deepcopy(dict(raw)) if isinstance(raw, Mapping) else {}
    for key in (
        "mainHero",
        "main_hero",
        "harmonyL",
        "harmonyR",
        "teamwork",
        "synergy",
        "synergyLevel",
        "clanLevel",
        "withXeno",
    ):
        if key in profile:
            result[key] = deepcopy(profile[key])
        if key in sio:
            result[key] = deepcopy(sio[key])
    return result


def _constraints(profile: Mapping[str, Any]) -> dict[str, Any]:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    raw = sio.get("configuration_constraints") or profile.get("configuration_constraints") or {}
    if isinstance(raw, Mapping) and isinstance(raw.get("survivor"), Mapping):
        raw = raw["survivor"]
    return deepcopy(dict(raw)) if isinstance(raw, Mapping) else {}


def _beta_allowed(profile: Mapping[str, Any]) -> bool:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    return bool(
        sio.get("beta_features")
        or sio.get("betafeatures")
        or profile.get("beta_features")
        or profile.get("betafeatures")
    )


def _owned_candidates(
    heroes: Mapping[str, Mapping[str, Any]],
    source: Sequence[str],
    *,
    beta_allowed: bool,
) -> tuple[str, ...]:
    definitions = SIO_SURVIVOR_DATA.get("heroes", {})
    result = []
    for name in source:
        state = heroes.get(name)
        if not isinstance(state, Mapping) or _number(state.get("stars")) <= 0:
            continue
        if not beta_allowed and bool((definitions.get(name) or {}).get("beta")):
            continue
        result.append(name)
    return tuple(result)


def _allowed(values: tuple[str, ...], explicit: Any, current: str | None = None) -> tuple[str, ...]:
    if isinstance(explicit, (list, tuple, set, frozenset)):
        requested = {str(value) for value in explicit}
        values = tuple(value for value in values if value in requested)
    if current and current != NONE and current not in values:
        values = (*values, current)
    return tuple(dict.fromkeys(values))


def _harmony_assignments(
    candidates: tuple[str, ...],
    main: str,
    *,
    enabled: bool,
    allow_none: bool,
) -> tuple[tuple[str, str], ...]:
    if not enabled:
        return ((NONE, NONE),)
    values = tuple(value for value in candidates if value != main)
    if allow_none:
        values = (NONE, *values)
    return tuple(
        (left, right)
        for left in values
        for right in values
        if left == NONE or right == NONE or left != right
    )


def _teamwork_candidates(
    heroes: Mapping[str, Mapping[str, Any]],
    main: str,
    explicit: Any,
    *,
    beta_allowed: bool,
) -> tuple[str, ...]:
    definitions = SIO_SURVIVOR_DATA.get("heroes", {})
    values = []
    for name, state in heroes.items():
        if name == main or name in TEAMWORK_EXCLUDED:
            continue
        if _number(state.get("stars")) <= 6:
            continue
        if not beta_allowed and bool((definitions.get(name) or {}).get("beta")):
            continue
        values.append(str(name))
    values = sorted(set(values))
    if isinstance(explicit, (list, tuple, set, frozenset)):
        requested = {str(value) for value in explicit}
        values = [value for value in values if value in requested]
    return tuple(values)


def _teamwork_subsets(candidates: tuple[str, ...], slots: int) -> tuple[tuple[str, ...], ...]:
    return tuple(
        subset
        for count in range(min(slots, len(candidates)) + 1)
        for subset in combinations(candidates, count)
    )


def _combination_count(candidate_count: int, slots: int) -> int:
    return sum(math.comb(candidate_count, count) for count in range(min(slots, candidate_count) + 1))


@dataclass(frozen=True)
class SurvivorConfigurationPlan:
    actions: tuple[dict[str, Any], ...]
    complete: bool
    total_states: int
    max_states: int
    reason: str | None
    main_candidates: tuple[str, ...]

    def public(self) -> dict[str, Any]:
        return {
            "actions": [deepcopy(action) for action in self.actions],
            "complete": self.complete,
            "total_states": self.total_states,
            "max_states": self.max_states,
            "reason": self.reason,
            "main_candidates": list(self.main_candidates),
            "search_model": "role_assignments_plus_teamwork_subsets",
            "teamwork_permutation_search": False,
        }


def plan_survivor_configurations(profile: Mapping[str, Any]) -> SurvivorConfigurationPlan:
    heroes = hero_state_from_profile(profile)
    meta = _meta(profile)
    constraints = _constraints(profile)
    beta_allowed = _beta_allowed(profile)
    current_main = str(meta.get("mainHero") or meta.get("main_hero") or NONE)
    main_candidates = _owned_candidates(heroes, MAIN_HEROES, beta_allowed=beta_allowed)
    main_candidates = _allowed(main_candidates, constraints.get("main_candidates"), current_main)
    main_candidates = tuple(name for name in main_candidates if name in heroes and _number(heroes[name].get("stars")) > 0)
    if not main_candidates:
        return SurvivorConfigurationPlan((), True, 0, int(constraints.get("max_states", DEFAULT_MAX_STATES)), None, ())

    harmony_candidates = _owned_candidates(heroes, HARMONY_HEROES, beta_allowed=beta_allowed)
    current_left = str(meta.get("harmonyL") or NONE)
    current_right = str(meta.get("harmonyR") or NONE)
    harmony_candidates = _allowed(
        harmony_candidates,
        constraints.get("harmony_candidates"),
        current_left if current_left != NONE else current_right,
    )
    if current_right != NONE and current_right not in harmony_candidates:
        harmony_candidates = (*harmony_candidates, current_right)
    harmony_candidates = tuple(dict.fromkeys(harmony_candidates))
    synergy = bool(meta.get("synergy"))
    allow_none_harmony = bool(constraints.get("allow_none_harmony", True))
    max_states = max(1, int(_number(constraints.get("max_states"), DEFAULT_MAX_STATES)))

    state_dimensions: list[tuple[str, tuple[tuple[str, str], ...], tuple[tuple[str, ...], ...]]] = []
    total_states = 0
    for main in main_candidates:
        harmony = _harmony_assignments(
            harmony_candidates,
            main,
            enabled=synergy,
            allow_none=allow_none_harmony,
        )
        teamwork_candidates = _teamwork_candidates(
            heroes,
            main,
            constraints.get("teamwork_candidates"),
            beta_allowed=beta_allowed,
        )
        slots = teamwork_slot_count(heroes[main].get("stars"))
        maximum_slots = constraints.get("max_teamwork_slots")
        if maximum_slots is not None:
            slots = min(slots, max(0, int(_number(maximum_slots))))
        teamwork = _teamwork_subsets(teamwork_candidates, slots)
        expected = len(harmony) * _combination_count(len(teamwork_candidates), slots)
        if expected != len(harmony) * len(teamwork):
            raise AssertionError("Teamwork combination count mismatch")
        total_states += expected
        state_dimensions.append((main, harmony, teamwork))

    if total_states > max_states:
        return SurvivorConfigurationPlan(
            (),
            False,
            total_states,
            max_states,
            "exact_survivor_configuration_state_budget_exceeded",
            main_candidates,
        )

    current_teamwork = tuple(sorted(str(value) for value in (meta.get("teamwork") or []) if value and value != NONE))
    current_key = (current_main, current_left, current_right, current_teamwork)
    actions: list[dict[str, Any]] = []
    for main, harmony, teamwork_sets in state_dimensions:
        for left, right in harmony:
            for teamwork in teamwork_sets:
                key = (main, left, right, teamwork)
                if key == current_key:
                    continue
                patched_meta = deepcopy(meta)
                patched_meta["mainHero"] = main
                patched_meta.pop("main_hero", None)
                patched_meta["teamwork"] = list(teamwork)
                if synergy:
                    patched_meta["harmonyL"] = left
                    patched_meta["harmonyR"] = right
                suffix = f"main-{_slug(main)}--left-{_slug(left)}--right-{_slug(right)}--team-{'_'.join(_slug(value) for value in teamwork) or 'none'}"
                actions.append(
                    {
                        "action_id": f"survivor:configuration:{suffix}",
                        "system": "survivor",
                        "action_type": "configure_survivor_roles",
                        "state_patch": {"sio_ce": {"meta": patched_meta}},
                        "consumed_items": {},
                        "required_items": {},
                        "refunded_items": {},
                        "costs": [],
                        "description": "Apply the complete Main, Harmony, and Teamwork configuration.",
                        "confidence": "exact",
                        "supported": True,
                        "source": "user-supplied sIO runtime",
                        "source_modules": [32085, 92316, 41950],
                        "metadata": {
                            "exact_after_state": True,
                            "configuration_frontier": True,
                            "main_hero": main,
                            "harmony_left": left,
                            "harmony_right": right,
                            "teamwork": list(teamwork),
                            "teamwork_slots": teamwork_slot_count(heroes[main].get("stars")),
                            "teamwork_combination_search": True,
                            "teamwork_permutation_search": False,
                            "complete_search": True,
                            "total_configuration_states": total_states,
                        },
                    }
                )
    return SurvivorConfigurationPlan(tuple(actions), True, total_states, max_states, None, main_candidates)


def generate_survivor_configuration_actions(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    plan = plan_survivor_configurations(profile)
    return [deepcopy(action) for action in plan.actions] if plan.complete else []


__all__ = [
    "DEFAULT_MAX_STATES",
    "HARMONY_HEROES",
    "MAIN_HEROES",
    "NONE",
    "SurvivorConfigurationPlan",
    "TEAMWORK_EXCLUDED",
    "generate_survivor_configuration_actions",
    "plan_survivor_configurations",
    "teamwork_slot_count",
]
