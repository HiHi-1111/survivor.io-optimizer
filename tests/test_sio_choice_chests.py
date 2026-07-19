from __future__ import annotations

import optimizer.source_pack_optimizer as source_optimizer
from optimizer.sio_choice_chests import (
    exact_cover_allocations,
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
    assert variant["metadata"]["allocation_policy"] == "exact_cover_pareto_by_chest_type"


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


def test_exact_cover_search_ignores_unrelated_reward_combinations() -> None:
    chests = [
        {
            "resource_id": "selector",
            "count": 100,
            "options": {
                "needed": 1,
                "unrelated_a": 1,
                "unrelated_b": 1,
                "unrelated_c": 1,
            },
        }
    ]
    rows = exact_cover_allocations(chests, {"needed": 2})
    assert rows == [
        {
            "chests": {"selector": 2},
            "grants": {"needed": 2.0},
            "option_counts": {"selector": {"needed": 2}},
        }
    ]


def test_different_chest_types_keep_nondominated_exact_allocations() -> None:
    chests = [
        {"resource_id": "small", "count": 2, "options": {"core": 1}},
        {"resource_id": "large", "count": 1, "options": {"core": 2}},
    ]
    rows = exact_cover_allocations(chests, {"core": 2})
    assert {tuple(sorted(row["chests"].items())) for row in rows} == {
        (("small", 2),),
        (("large", 1),),
    }


def test_dominated_mixed_chest_allocation_is_removed() -> None:
    chests = [
        {"resource_id": "a", "count": 2, "options": {"core": 1}},
        {"resource_id": "b", "count": 2, "options": {"core": 1}},
    ]
    rows = exact_cover_allocations(chests, {"core": 1})
    assert {tuple(sorted(row["chests"].items())) for row in rows} == {
        (("a", 1),),
        (("b", 1),),
    }
    assert all(sum(row["chests"].values()) == 1 for row in rows)


def test_unknown_choice_conversion_is_not_guessed() -> None:
    profile = {"resources": {"selector": 5}, "choice_chests": {"selector": {}}}
    assert normalize_choice_chests(profile, profile["resources"]) == []
    rows = expand_actions_with_choice_chests(profile, [_action({"a": 1})], profile["resources"])
    assert rows == [_action({"a": 1})]


def test_reward_units_must_exactly_cover_shortage_without_hidden_leftover() -> None:
    chests = [{"resource_id": "bundle", "count": 1, "options": {"core": 5}}]
    assert exact_cover_allocations(chests, {"core": 3}) == []


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
