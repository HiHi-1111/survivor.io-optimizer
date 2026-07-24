"""Safe acceleration layer for the exact sIO Clan Expedition oracle.

This module never estimates damage and never removes a distinct canonical oracle
request.  It only collapses byte-equivalent requests, reuses exact results inside
the current Python process, and expands the exact result back to the caller's
original ordering.

The patch is deliberately installed at package import so trainer entry points that
import ``optimizer.sio_runtime_oracle`` directly receive the same protection as the
public optimizer entry point.  Set ``SIO_DISABLE_ORACLE_ACCELERATOR=1`` to disable
it for diagnosis.
"""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
import os
from threading import RLock
from typing import Any, Iterable, Mapping

from optimizer import sio_runtime_oracle as _runtime
from optimizer.training_cache import stable_hash

_ACCELERATOR_SCHEMA = "sio_oracle_accelerator_v1"
_DEFAULT_MAX_ENTRIES = 100_000
_LOCK = RLock()
_INSTALLED = False
_ORIGINAL_SCORE_PROFILES = None
_HOT_CACHE: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
_METRICS = {
    "calls": 0,
    "profiles_received": 0,
    "unique_requests_forwarded": 0,
    "duplicates_collapsed": 0,
    "hot_cache_hits": 0,
}


def _max_entries() -> int:
    raw = os.environ.get("SIO_ORACLE_HOT_CACHE_ENTRIES", str(_DEFAULT_MAX_ENTRIES))
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return _DEFAULT_MAX_ENTRIES


def _request_key(request: Mapping[str, Any]) -> str:
    """Return a source-aware identity for an exact oracle request."""
    source_hash = (
        _runtime._sha256(_runtime.ORACLE_SCRIPT)
        if _runtime.ORACLE_SCRIPT.is_file()
        else "missing-oracle-script"
    )
    return stable_hash(
        {
            "accelerator_schema": _ACCELERATOR_SCHEMA,
            "oracle_schema": _runtime.ORACLE_SCHEMA,
            "oracle_cache_schema": _runtime.ORACLE_CACHE_SCHEMA,
            "oracle_source_sha256": source_hash,
            "bundle_sha256": _runtime.SIO_BUNDLE_SHA256,
            "request": request,
        }
    )


def _cache_get(key: str) -> dict[str, Any] | None:
    with _LOCK:
        value = _HOT_CACHE.get(key)
        if value is None:
            return None
        _HOT_CACHE.move_to_end(key)
        _METRICS["hot_cache_hits"] += 1
        return deepcopy(value)


def _cache_set(key: str, value: Mapping[str, Any]) -> None:
    limit = _max_entries()
    if limit <= 0:
        return
    with _LOCK:
        _HOT_CACHE[key] = deepcopy(dict(value))
        _HOT_CACHE.move_to_end(key)
        while len(_HOT_CACHE) > limit:
            _HOT_CACHE.popitem(last=False)


def _accelerated_score_profiles(self, profiles: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate exact requests, call the original oracle, and restore ordering."""
    profile_rows = list(profiles)
    requests = [_runtime.build_oracle_request(profile) for profile in profile_rows]
    keys = [_request_key(request) for request in requests]

    results: list[dict[str, Any] | None] = [None] * len(profile_rows)
    representative_profiles: list[Mapping[str, Any]] = []
    representative_keys: list[str] = []
    waiting_indices: dict[str, list[int]] = {}

    with _LOCK:
        _METRICS["calls"] += 1
        _METRICS["profiles_received"] += len(profile_rows)

    for index, (key, profile) in enumerate(zip(keys, profile_rows)):
        cached = _cache_get(key)
        if cached is not None:
            results[index] = cached
            continue
        if key in waiting_indices:
            waiting_indices[key].append(index)
            continue
        waiting_indices[key] = [index]
        representative_keys.append(key)
        representative_profiles.append(profile)

    duplicate_count = sum(max(0, len(indices) - 1) for indices in waiting_indices.values())
    with _LOCK:
        _METRICS["duplicates_collapsed"] += duplicate_count
        _METRICS["unique_requests_forwarded"] += len(representative_profiles)

    if representative_profiles:
        if _ORIGINAL_SCORE_PROFILES is None:
            raise RuntimeError("sIO oracle accelerator was installed without the original scorer")
        fresh = _ORIGINAL_SCORE_PROFILES(self, representative_profiles)
        if len(fresh) != len(representative_profiles):
            raise RuntimeError("exact sIO oracle returned the wrong accelerated batch length")
        for key, result in zip(representative_keys, fresh):
            exact = deepcopy(dict(result))
            _cache_set(key, exact)
            for index in waiting_indices[key]:
                results[index] = deepcopy(exact)

    return [dict(result or {}) for result in results]


def install() -> bool:
    """Install the safe accelerator once.  Returns whether it is active."""
    global _INSTALLED, _ORIGINAL_SCORE_PROFILES
    if os.environ.get("SIO_DISABLE_ORACLE_ACCELERATOR") == "1":
        return False
    with _LOCK:
        if _INSTALLED:
            return True
        _ORIGINAL_SCORE_PROFILES = _runtime.SioCeRuntimeOracle.score_profiles
        _runtime.SioCeRuntimeOracle.score_profiles = _accelerated_score_profiles
        _INSTALLED = True
    return True


def clear_hot_cache() -> None:
    with _LOCK:
        _HOT_CACHE.clear()


def metrics() -> dict[str, int]:
    with _LOCK:
        return {**_METRICS, "hot_cache_entries": len(_HOT_CACHE)}


__all__ = ["clear_hot_cache", "install", "metrics"]
