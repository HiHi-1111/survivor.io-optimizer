"""Exhaustive exact two-slot equipment reallocation frontiers.

The older item generator keeps a small nearest-frontier subset. That is useful for
UI responsiveness but cannot prove the best CE result. This module rebuilds every
source-refund/target-upgrade pair from the exact single-slot states and lets the
normal structural deduplicator collapse equivalent final states.

Source and target roles are directional. Reversing them changes which equipped
item is downgraded and which is upgraded, so this is not an order-independent
permutation problem.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping

from optimizer.sio_exact_actions import (
    _deduplicate,
    _item_patch,
    _item_resource_totals,
    _ledger,
    _make_action,
    generate_item_actions,
    stable_state_id,
)
from optimizer.sio_items import SLOTS, item_state_from_profile


def directional_reallocation_pairs(
    actions: Iterable[Mapping[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return every legal role-labelled source/target single-action pair."""
    downs: dict[str, list[dict[str, Any]]] = {}
    ups: dict[str, list[dict[str, Any]]] = {}
    for raw_action in actions:
        action = dict(raw_action)
        if action.get("action_type") != "reconfigure_item_path":
            continue
        metadata = action.get("metadata") if isinstance(action.get("metadata"), Mapping) else {}
        slot = str(metadata.get("slot") or "")
        if slot not in SLOTS:
            continue
        if action.get("refunded_items"):
            downs.setdefault(slot, []).append(action)
        if action.get("consumed_items"):
            ups.setdefault(slot, []).append(action)

    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for source_slot in SLOTS:
        for target_slot in SLOTS:
            if source_slot == target_slot:
                continue
            for source_action in downs.get(source_slot, []):
                for target_action in ups.get(target_slot, []):
                    pairs.append((source_action, target_action))
    return pairs


def generate_exhaustive_item_reallocations(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    items = item_state_from_profile(profile)
    if not items:
        return []
    before_totals = _item_resource_totals(items)
    single_actions = generate_item_actions(profile)
    actions: list[dict[str, Any]] = []
    for source_action, target_action in directional_reallocation_pairs(single_actions):
        source_metadata = source_action.get("metadata") or {}
        target_metadata = target_action.get("metadata") or {}
        source_slot = str(source_metadata["slot"])
        target_slot = str(target_metadata["slot"])
        source_target = deepcopy(dict(source_metadata["target"]))
        target_target = deepcopy(dict(target_metadata["target"]))
        after_items = deepcopy(items)
        after_items[source_slot] = source_target
        after_items[target_slot] = target_target
        consumed, refunded = _ledger(before_totals, _item_resource_totals(after_items))
        actions.append(
            _make_action(
                action_id=(
                    f"items:reallocate_full:{source_slot.lower()}_to_{target_slot.lower()}:"
                    f"{stable_state_id(source_target)}:{stable_state_id(target_target)}"
                ),
                system="items",
                action_type="reallocate_item_resources",
                patch=_item_patch(after_items),
                consumed=consumed,
                refunded=refunded,
                description=(
                    f"Refund/rebuild {source_slot} and {target_slot} using the complete exact "
                    "directional frontier."
                ),
                source_modules=[42052, 32085],
                metadata={
                    "source_slot": source_slot,
                    "target_slot": target_slot,
                    "source_target": source_target,
                    "target_target": target_target,
                    "complete_directional_frontier": True,
                    "order_independent_permutation": False,
                },
            )
        )
    return _deduplicate(actions)


__all__ = [
    "directional_reallocation_pairs",
    "generate_exhaustive_item_reallocations",
]
