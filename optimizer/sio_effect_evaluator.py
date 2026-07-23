"""Source-backed CE effect evaluator and exact-safe preflight ordering.

The evaluator is deliberately subordinate to the original sIO runtime.  It uses
only formulas already ported from the user-supplied Bible bundle to:

* explain which attack or multiplier bucket an action changes;
* compare flat ATK with percentage ATK on the current build;
* identify conditional bonuses that have no matching source/uptime; and
* avoid an exact runtime call only when a zero-damage proof is available.

Unknown effects are never treated as zero.  Every uncertain or potentially
positive state remains eligible for exact before/after scoring.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from optimizer.sio_ce_account import prepare_sio_ce_profile
from optimizer.sio_ce_damage import calculate_clan_expedition_damage as calculate_ce_core
from optimizer.sio_ce_constants import SIO_BUNDLE_SHA256

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "knowledge" / "sio_effect_dependencies.json"
EPSILON = 1e-9


@dataclass(frozen=True)
class PreflightDecision:
    action: dict[str, Any]
    after_profile: dict[str, Any]
    certificate: dict[str, Any]
    estimate: dict[str, Any]
    skip_exact: bool
    skip_reason: str | None


def _number(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _close(left: Any, right: Any, *, scale: float = 1.0) -> bool:
    a, b = _number(left), _number(right)
    return abs(a - b) <= EPSILON * max(scale, abs(a), abs(b), 1.0)


@lru_cache(maxsize=1)
def load_effect_registry() -> dict[str, Any]:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if payload.get("bundle_sha256") != SIO_BUNDLE_SHA256:
        raise RuntimeError("Effect registry was not built from the active sIO Bible bundle.")
    return payload


def clear_effect_registry_cache() -> None:
    load_effect_registry.cache_clear()


def _prepare_and_score(profile: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    prepared = prepare_sio_ce_profile(profile, defer_runtime_conditions=False)
    report = calculate_ce_core(prepared)
    return prepared, report


def _stats(report: Mapping[str, Any]) -> dict[str, float]:
    raw = report.get("normalized_stats")
    return {
        str(key): _number(value)
        for key, value in (raw.items() if isinstance(raw, Mapping) else [])
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }


def _changed_stats(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[dict[str, Any]]:
    left, right = _stats(before), _stats(after)
    registry = load_effect_registry()
    conditional = {
        str(row["effect"]): row
        for row in registry.get("conditional_effects", [])
        if isinstance(row, Mapping)
    }
    multiplier_map = {
        str(key): str(value)
        for key, value in (registry.get("multiplicative_effects") or {}).items()
    }
    attack_fields = set((registry.get("attack_formula") or {}).get("fields", []))
    direct_fields = set(registry.get("direct_effects", []))
    rows: list[dict[str, Any]] = []
    for field in sorted(set(left) | set(right)):
        old, new = left.get(field, 0.0), right.get(field, 0.0)
        if _close(old, new):
            continue
        dependency = conditional.get(field)
        if dependency:
            uptime_field = str(dependency["uptime"])
            before_uptime = left.get(uptime_field, 0.0)
            after_uptime = right.get(uptime_field, 0.0)
            active = max(before_uptime, after_uptime) > EPSILON
            bucket = str(dependency["bucket"])
        elif field in attack_fields:
            uptime_field = None
            before_uptime = after_uptime = None
            active = True
            bucket = "base_attack"
        elif field in multiplier_map:
            uptime_field = None
            before_uptime = after_uptime = None
            active = True
            bucket = multiplier_map[field]
        elif field in direct_fields:
            uptime_field = None
            before_uptime = after_uptime = None
            active = True
            bucket = "direct_damage_factor"
        else:
            uptime_field = None
            before_uptime = after_uptime = None
            active = None
            bucket = "unknown"
        rows.append({
            "field": field,
            "before": old,
            "after": new,
            "delta": new - old,
            "formula_bucket": bucket,
            "dependency": uptime_field,
            "dependency_before": before_uptime,
            "dependency_after": after_uptime,
            "active_for_this_build": active,
        })
    return rows


def _changed_buckets(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[dict[str, Any]]:
    left = before.get("multiplier_breakdown") if isinstance(before.get("multiplier_breakdown"), Mapping) else {}
    right = after.get("multiplier_breakdown") if isinstance(after.get("multiplier_breakdown"), Mapping) else {}
    rows: list[dict[str, Any]] = []
    for bucket in sorted(set(left) | set(right)):
        old, new = _number(left.get(bucket), 1.0), _number(right.get(bucket), 1.0)
        if _close(old, new):
            continue
        rows.append({
            "bucket": str(bucket),
            "before_multiplier": old,
            "after_multiplier": new,
            "relative_gain": new / old - 1.0 if old else None,
        })
    for bucket, key, default in (
        ("base_attack", "base_attack", 0.0),
        ("direct_damage_factor", "direct_damage_multiplier_applied", 1.0),
        ("passive_multiplier", "passive_multiplier", 1.0),
    ):
        old, new = _number(before.get(key), default), _number(after.get(key), default)
        if not _close(old, new):
            rows.append({
                "bucket": bucket,
                "before_multiplier": old,
                "after_multiplier": new,
                "relative_gain": new / old - 1.0 if old else None,
            })
    return rows


def _known_formula_fields() -> set[str]:
    registry = load_effect_registry()
    known = set((registry.get("attack_formula") or {}).get("fields", []))
    known.update((registry.get("multiplicative_effects") or {}).keys())
    known.update(registry.get("direct_effects", []))
    for row in registry.get("conditional_effects", []):
        if isinstance(row, Mapping):
            known.add(str(row.get("effect")))
            known.add(str(row.get("uptime")))
    return known


def _neutral_proof(
    action: Mapping[str, Any],
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    changed_stats: list[dict[str, Any]],
    changed_buckets: list[dict[str, Any]],
) -> tuple[bool, str | None, dict[str, Any]]:
    registry = load_effect_registry()
    system = str(action.get("system") or "unknown")
    coverage = registry.get("safe_neutral_systems") or {}
    unknown_fields = sorted(
        row["field"] for row in changed_stats
        if row.get("field") not in _known_formula_fields()
    )
    before_total = _number(before.get("total_damage"))
    after_total = _number(after.get("total_damage"))
    inactive = [
        row for row in changed_stats
        if row.get("dependency") and row.get("active_for_this_build") is False
    ]
    declared_modules = {int(value) for value in action.get("source_modules", []) if isinstance(value, (int, float))}
    coverage_modules = {int(value) for value in coverage.get(system, [])} if system in coverage else set()
    metadata = action.get("metadata") if isinstance(action.get("metadata"), Mapping) else {}
    exact_after_state = bool(metadata.get("exact_after_state"))
    source_covered_action = exact_after_state and bool(declared_modules & coverage_modules)
    proof = {
        "system": system,
        "source_coverage_modules": sorted(coverage_modules),
        "action_source_modules": sorted(declared_modules),
        "exact_after_state_declared": exact_after_state,
        "source_covered_action": source_covered_action,
        "python_formula_supported": bool(before.get("supported") and after.get("supported")),
        "estimated_damage_delta": after_total - before_total,
        "unknown_changed_fields": unknown_fields,
        "changed_formula_buckets": [row.get("bucket") for row in changed_buckets],
        "inactive_conditional_effects": [row.get("field") for row in inactive],
    }
    if os.environ.get("SIO_EFFECT_PREFLIGHT_PRUNE", "1").strip().lower() in {"0", "false", "off", "no"}:
        return False, None, proof
    if system not in coverage or not source_covered_action:
        return False, None, proof
    if not before.get("supported") or not after.get("supported"):
        return False, None, proof
    if unknown_fields or changed_buckets:
        return False, None, proof
    if not _close(before_total, after_total, scale=max(abs(before_total), abs(after_total), 1.0)):
        return False, None, proof
    if inactive:
        labels = ",".join(
            f"{row['field']}_requires_{row['dependency']}" for row in inactive
        )
        return True, f"source_proven_inactive_effect:{labels}", proof
    return True, "source_proven_zero_ce_delta", proof


def compare_attack_options(
    prepared_profile: Mapping[str, Any],
    *,
    percent_points: float = 10.0,
    flat_attack: float = 5000.0,
) -> dict[str, Any]:
    """Compare ATK options using the exact module-67727 attack bucket."""
    baseline = calculate_ce_core(prepared_profile)
    if not baseline.get("supported"):
        return {"supported": False, "reason": baseline.get("reason", "baseline_not_scoreable")}

    def changed(field: str, amount: float) -> dict[str, Any]:
        candidate = deepcopy(dict(prepared_profile))
        sio = candidate.setdefault("sio_ce", {})
        stats = dict(sio.get("stats") or {})
        stats[field] = _number(stats.get(field)) + amount
        sio["stats"] = stats
        sio["stats_stage"] = "post_24804"
        result = calculate_ce_core(candidate)
        return result

    percent = changed("atkPercent", percent_points)
    flat = changed("atkFinal", flat_attack)
    old = _number(baseline.get("total_damage"))
    percent_gain = _number(percent.get("total_damage")) - old
    flat_gain = _number(flat.get("total_damage")) - old
    return {
        "supported": bool(percent.get("supported") and flat.get("supported")),
        "baseline_damage": old,
        "percent_option": {
            "field": "atkPercent",
            "amount_percentage_points": percent_points,
            "base_attack_after": _number(percent.get("base_attack")),
            "estimated_damage_gain": percent_gain,
            "estimated_percent_gain": percent_gain / old * 100.0 if old else None,
        },
        "flat_option": {
            "field": "atkFinal",
            "amount": flat_attack,
            "base_attack_after": _number(flat.get("base_attack")),
            "estimated_damage_gain": flat_gain,
            "estimated_percent_gain": flat_gain / old * 100.0 if old else None,
        },
        "better_option": "atkPercent" if percent_gain > flat_gain else "atkFinal" if flat_gain > percent_gain else "tie",
        "difference_in_estimated_damage": abs(percent_gain - flat_gain),
        "source": {
            "bundle_sha256": SIO_BUNDLE_SHA256,
            "module": 67727,
            "formula_bucket": "base_attack",
        },
    }


def evaluate_effect_transition(
    baseline_report: Mapping[str, Any],
    action: Mapping[str, Any],
    after_profile: Mapping[str, Any],
    certificate: Mapping[str, Any],
) -> PreflightDecision:
    try:
        _prepared_after, after_report = _prepare_and_score(after_profile)
        old = _number(baseline_report.get("total_damage"))
        new = _number(after_report.get("total_damage"))
        changed_stats = _changed_stats(baseline_report, after_report)
        changed_buckets = _changed_buckets(baseline_report, after_report)
        skip, reason, proof = _neutral_proof(
            action, baseline_report, after_report, changed_stats, changed_buckets
        )
        estimate = {
            "supported": bool(baseline_report.get("supported") and after_report.get("supported")),
            "estimated_before_damage": old,
            "estimated_after_damage": new,
            "estimated_damage_gain": new - old,
            "estimated_percent_gain": (new - old) / old * 100.0 if old else None,
            "changed_effects": changed_stats,
            "changed_formula_buckets": changed_buckets,
            "inactive_effects": [
                row for row in changed_stats
                if row.get("dependency") and row.get("active_for_this_build") is False
            ],
            "neutral_proof": proof,
            "source": {
                "bundle_sha256": SIO_BUNDLE_SHA256,
                "role": "proposal_ordering_and_proven_zero_suppression_only",
                "final_winner": "exact_sio_runtime",
            },
        }
    except (OSError, TypeError, ValueError, RuntimeError) as error:
        estimate = {
            "supported": False,
            "reason": f"preflight_estimator_error:{type(error).__name__}:{error}",
            "estimated_damage_gain": 0.0,
            "changed_effects": [],
            "changed_formula_buckets": [],
            "inactive_effects": [],
        }
        skip, reason = False, None
    annotated = deepcopy(dict(action))
    annotated["preflight_estimate"] = estimate
    return PreflightDecision(
        action=annotated,
        after_profile=deepcopy(dict(after_profile)),
        certificate=deepcopy(dict(certificate)),
        estimate=estimate,
        skip_exact=skip,
        skip_reason=reason,
    )


def evaluate_preflight_transitions(
    profile: Mapping[str, Any],
    transitions: Iterable[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    """Order transitions and remove only source-proven exact-neutral states."""
    enabled = os.environ.get("SIO_EFFECT_PREFLIGHT", "1").strip().lower() not in {"0", "false", "off", "no"}
    rows = list(transitions)
    if not enabled:
        return {
            "transitions": rows,
            "skipped": [],
            "report": {
                "enabled": False,
                "reason": "disabled_by_SIO_EFFECT_PREFLIGHT",
                "input_transitions": len(rows),
                "exact_transitions": len(rows),
                "source_proven_neutral": 0,
            },
        }

    prepared, baseline = _prepare_and_score(profile)
    decisions = [
        evaluate_effect_transition(baseline, action, after, certificate)
        for action, after, certificate in rows
    ]
    kept = [decision for decision in decisions if not decision.skip_exact]
    kept.sort(key=lambda decision: (
        -_number(decision.estimate.get("estimated_damage_gain")),
        str(decision.action.get("action_id")),
    ))
    skipped = [
        {
            "action_id": str(decision.action.get("action_id")),
            "reason": str(decision.skip_reason),
            "preflight_estimate": decision.estimate,
        }
        for decision in decisions if decision.skip_exact
    ]
    transitions_out = [
        (decision.action, decision.after_profile, decision.certificate)
        for decision in kept
    ]
    estimates = sorted(
        (
            {
                "action_id": str(decision.action.get("action_id")),
                "estimated_damage_gain": _number(decision.estimate.get("estimated_damage_gain")),
                "inactive_effects": [row.get("field") for row in decision.estimate.get("inactive_effects", [])],
                "sent_to_exact_runtime": not decision.skip_exact,
            }
            for decision in decisions
        ),
        key=lambda row: (-row["estimated_damage_gain"], row["action_id"]),
    )
    registry = load_effect_registry()
    return {
        "transitions": transitions_out,
        "skipped": skipped,
        "report": {
            "enabled": True,
            "role": "source_backed_ordering_and_exact_neutral_suppression",
            "input_transitions": len(rows),
            "exact_transitions": len(transitions_out),
            "source_proven_neutral": len(skipped),
            "estimated_runtime_states_saved": len(skipped),
            "attack_option_comparison": compare_attack_options(prepared),
            "effect_dependencies": registry.get("conditional_effects", []),
            "safe_neutral_systems": registry.get("safe_neutral_systems", {}),
            "ordered_estimates": estimates,
            "unknown_effect_policy": "keep_for_exact_runtime",
            "final_winner_policy": "exact_before_after_sio_ce_damage_only",
            "bundle_sha256": SIO_BUNDLE_SHA256,
        },
    }


__all__ = [
    "PreflightDecision",
    "clear_effect_registry_cache",
    "compare_attack_options",
    "evaluate_effect_transition",
    "evaluate_preflight_transitions",
    "load_effect_registry",
]
