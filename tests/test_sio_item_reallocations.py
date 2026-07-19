from __future__ import annotations

import optimizer.source_pack_optimizer as source_optimizer
from optimizer.sio_item_reallocations import directional_reallocation_pairs


def _single(action_id, slot, *, consumed=None, refunded=None):
    return {
        "action_id": action_id,
        "system": "items",
        "action_type": "reconfigure_item_path",
        "state_patch": {"items": {slot: {"name": action_id}}},
        "consumed_items": consumed or {},
        "refunded_items": refunded or {},
        "metadata": {"slot": slot, "target": {"name": action_id}},
    }


def test_directional_pair_generation_has_no_nearest_frontier_cap() -> None:
    actions = [
        *[
            _single(f"source_{index}", "Weapon", refunded={"eternal_core": index + 1})
            for index in range(5)
        ],
        *[
            _single(f"target_{index}", "Gloves", consumed={"eternal_core": index + 1})
            for index in range(11)
        ],
    ]
    pairs = directional_reallocation_pairs(actions)
    assert len(pairs) == 5 * 11
    assert {(left["action_id"], right["action_id"]) for left, right in pairs} == {
        (f"source_{source}", f"target_{target}")
        for source in range(5)
        for target in range(11)
    }


def test_reversing_source_and_target_is_not_treated_as_the_same_state() -> None:
    actions = [
        _single("weapon_down", "Weapon", refunded={"core": 1}),
        _single("weapon_up", "Weapon", consumed={"core": 1}),
        _single("gloves_down", "Gloves", refunded={"core": 1}),
        _single("gloves_up", "Gloves", consumed={"core": 1}),
    ]
    pairs = {(left["action_id"], right["action_id"]) for left, right in directional_reallocation_pairs(actions)}
    assert ("weapon_down", "gloves_up") in pairs
    assert ("gloves_down", "weapon_up") in pairs


def test_source_optimizer_reports_structural_deduplication(monkeypatch) -> None:
    profile = {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats_stage": "post_24804",
            "stats": {},
            "attack": {"atkBase": 1000, "atkFinal": 0},
            "passive_multiplier": 1.0,
        },
    }
    duplicate_a = {
        "action_id": "duplicate_a",
        "system": "test",
        "action_type": "exact",
        "state_patch": {"test_damage": 10},
        "consumed_items": {},
        "refunded_items": {},
    }
    duplicate_b = {**duplicate_a, "action_id": "duplicate_b"}

    monkeypatch.setattr(source_optimizer, "generate_exact_actions", lambda _profile: [duplicate_a, duplicate_b])
    monkeypatch.setattr(source_optimizer, "generate_exhaustive_item_reallocations", lambda _profile: [])
    monkeypatch.setattr(source_optimizer, "generate_tech_progression_actions", lambda _profile: [])
    monkeypatch.setattr(source_optimizer, "generate_progression_frontiers", lambda _profile: [])
    monkeypatch.setattr(source_optimizer, "load_source_pack_actions", lambda: [])

    def fake_batch(states):
        return [
            {
                "supported": True,
                "total_damage": 1000.0 + float(state.get("test_damage", 0)),
                "formula_provenance": {"test": True},
                "runtime_exact": True,
            }
            for state in states
        ]

    monkeypatch.setattr(source_optimizer, "calculate_clan_expedition_damage_batch", fake_batch)
    result = source_optimizer.optimize_source_pack_actions(profile)
    assert result["templates_considered"] == 1
    assert result["deduplicated_count"] == 1
    assert result["deduplicated_actions"] == [
        {
            "action_id": "duplicate_b",
            "duplicate_of": "duplicate_a",
            "reason": "equivalent_complete_after_state_and_ledger",
        }
    ]
