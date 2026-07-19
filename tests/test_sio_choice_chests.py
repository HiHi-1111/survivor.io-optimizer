from __future__ import annotations

import optimizer.source_pack_optimizer as source_optimizer
from optimizer.sio_choice_chests import (
    expand_actions_with_choice_chests,
    normalize_choice_chests,
)


def _action(required):
    return {
        "action_id": "upgrade",
        "system": "items",
        "action_type": "upgrade",
        "state_patch": {"marker": "upgraded"},
        "consumed_items": dict(required),
        "refunded_items": {},
        "metadata": {"exact_after_state": True},
    }


def test_selector_chests_cover_shortages_with_one_canonical_count_allocation() -> None:
    profile = {
        "resources": {"eternal_core": 1, "core_selector_chest": 3},
        "choice_chests": {
            "core_selector_chest": {
                "options": {
                    "eternal_core": 1,
                    "void_core": 1,
                    "chaos_core": 1,
                }
            }
        },
    }
    rows = expand_actions_with_choice_chests(
        profile,
        [_action({"eternal_core": 3})],
        {"eternal_core": 1, "core_selector_chest": 3},
    )
    variants = [row for row in rows if ":choice:" in row["action_id"]]
    assert len(variants) == 1
    variant = variants[0]
    assert variant["gross_required_items"] == {"eternal_core": 3.0}
    assert variant["consumed_items"] == {
        "eternal_core": 1.0,
        "core_selector_chest": 2.0,
    }
    assert variant["choice_chest_grants"] == {"eternal_core": 2.0}
    assert variant["metadata"]["choice_chest_allocation"] == {
        "core_selector_chest": {"eternal_core": 2}
    }
    assert variant["metadata"]["combination_search"] is True
    assert variant["metadata"]["permutation_search"] is False


def test_selector_chest_pick_order_does_not_create_duplicate_actions() -> None:
    profile = {
        "resources": {"selector": 2},
        "choice_chests": {"selector": {"options": {"a": 1, "b": 1}}},
    }
    rows = expand_actions_with_choice_chests(
        profile,
        [_action({"a": 1, "b": 1})],
        {"selector": 2},
    )
    variants = [row for row in rows if ":choice:" in row["action_id"]]
    assert len(variants) == 1
    assert variants[0]["metadata"]["choice_chest_allocation"] == {
        "selector": {"a": 1, "b": 1}
    }


def test_unknown_choice_conversion_is_not_guessed() -> None:
    profile = {"resources": {"selector": 5}, "choice_chests": {"selector": {}}}
    assert normalize_choice_chests(profile, profile["resources"]) == []
    rows = expand_actions_with_choice_chests(profile, [_action({"a": 1})], profile["resources"])
    assert rows == [_action({"a": 1})]


def test_public_optimizer_scores_chest_assisted_complete_after_state(monkeypatch) -> None:
    profile = {
        "game_mode": "clan_expedition",
        "sio_ce": {
            "stats_stage": "post_24804",
            "stats": {},
            "attack": {"atkBase": 1000, "atkFinal": 0},
            "passive_multiplier": 1.0,
            "exact_actions": [
                {
                    "action_id": "spend_eternal_cores",
                    "system": "items",
                    "action_type": "upgrade",
                    "state_patch": {"test_damage": 200},
                    "consumed_items": {"eternal_core": 3},
                }
            ],
            "choice_chests": {
                "core_selector_chest": {
                    "options": {"eternal_core": 1, "void_core": 1, "chaos_core": 1}
                }
            },
        },
        "resources": {"eternal_core": 1, "core_selector_chest": 2},
    }

    calls = []

    def fake_batch(states):
        rows = [dict(state) for state in states]
        calls.append(rows)
        return [
            {
                "supported": True,
                "total_damage": 1000.0 + float(state.get("test_damage", 0)),
                "formula_provenance": {"test": True},
                "runtime_exact": True,
            }
            for state in rows
        ]

    monkeypatch.setattr(source_optimizer, "calculate_clan_expedition_damage_batch", fake_batch)
    result = source_optimizer.optimize_source_pack_actions(profile, device="cpu")
    assert len(calls) == 1
    assert result["best"]["action_id"].startswith("spend_eternal_cores:choice:")
    assert result["best"]["expected_dps_gain"] == 200
    assert result["best"]["consumed_items"] == {
        "eternal_core": 1.0,
        "core_selector_chest": 2.0,
    }
