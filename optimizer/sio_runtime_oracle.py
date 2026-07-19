"""Python bridge to the exact offline sIO Clan Expedition runtime.

The user-supplied sIO bundle is extracted into a SHA-addressed local cache and
executed with Node. Calls are batched and cached. The bridge never downloads
anything and rejects a different bundle hash unless the caller explicitly opts
in through ``SIO_ALLOW_UNVERIFIED_BUNDLE=1``.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Iterable, Mapping
import zipfile

from optimizer.sio_ce_constants import SIO_BUNDLE_SHA256
from optimizer.training_cache import JsonlCache, stable_hash

ROOT = Path(__file__).resolve().parents[1]
ORACLE_SCRIPT = ROOT / "tools" / "sio_runtime" / "sio_ce_oracle.js"
DEFAULT_CACHE_ROOT = ROOT / ".cache" / "sio_runtime"
DEFAULT_RESULT_CACHE = ROOT / ".cache" / "sio_runtime" / "ce_oracle_results.jsonl"


class SioRuntimeUnavailable(RuntimeError):
    pass


class SioRuntimeInputError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unwrap(value: Any) -> Any:
    if isinstance(value, Mapping) and isinstance(value.get("data"), Mapping):
        return value["data"]
    if isinstance(value, Mapping) and isinstance(value.get("owned"), Mapping):
        return value["owned"]
    return value


def _candidate_bundle_paths() -> Iterable[Path]:
    explicit = os.environ.get("SIO_TOOLS_BUNDLE")
    if explicit:
        yield Path(explicit).expanduser()
    archive = ROOT / "data" / "sio_training" / "archive"
    for name in (
        "sio_tools.exp0.dev.zip",
        "sio_tools.exp0.dev(1).zip",
        "sio-tools.exp0.dev.zip",
    ):
        yield archive / name
    home = Path.home()
    for directory in (home / "Downloads", home / "downloads"):
        for name in (
            "sio_tools.exp0.dev.zip",
            "sio_tools.exp0.dev(1).zip",
            "sio-tools.exp0.dev.zip",
        ):
            yield directory / name


def find_sio_bundle() -> Path:
    for path in _candidate_bundle_paths():
        if path.is_file():
            return path.resolve()
    raise SioRuntimeUnavailable(
        "The supplied sIO bundle was not found. Set SIO_TOOLS_BUNDLE or place "
        "sio_tools.exp0.dev.zip in data/sio_training/archive."
    )


def find_node() -> str:
    explicit = os.environ.get("SIO_NODE")
    if explicit and Path(explicit).is_file():
        return explicit
    node = shutil.which("node")
    if node:
        return node
    local_root = ROOT / ".tools" / "node"
    if local_root.exists():
        matches = sorted(local_root.glob("node-*/node.exe")) + sorted(local_root.glob("node-*/bin/node"))
        if matches:
            return str(matches[-1])
    raise SioRuntimeUnavailable("Node.js is required for the exact sIO runtime oracle.")


def _safe_extract(zip_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if target != root and root not in target.parents:
                raise SioRuntimeUnavailable(f"Unsafe path in sIO zip: {member.filename}")
        archive.extractall(destination)


def _runtime_root(extracted: Path) -> Path:
    candidates = [extracted, *[path for path in extracted.rglob("*") if path.is_dir()]]
    for candidate in candidates:
        if (candidate / "_next" / "static" / "chunks").is_dir():
            return candidate
    raise SioRuntimeUnavailable("The sIO zip does not contain _next/static/chunks.")


def ensure_extracted_bundle(
    bundle_path: Path | None = None,
    *,
    cache_root: Path | None = None,
) -> tuple[Path, str]:
    bundle = (bundle_path or find_sio_bundle()).resolve()
    bundle_hash = _sha256(bundle)
    if bundle_hash != SIO_BUNDLE_SHA256 and os.environ.get("SIO_ALLOW_UNVERIFIED_BUNDLE") != "1":
        raise SioRuntimeUnavailable(
            f"Unexpected sIO bundle SHA256 {bundle_hash}; expected {SIO_BUNDLE_SHA256}. "
            "Use the supplied Bible bundle or explicitly set SIO_ALLOW_UNVERIFIED_BUNDLE=1."
        )
    cache = (cache_root or Path(os.environ.get("SIO_RUNTIME_CACHE", DEFAULT_CACHE_ROOT))).resolve()
    destination = cache / bundle_hash / "extracted"
    marker = destination.parent / "complete.json"
    if marker.is_file():
        try:
            payload = json.loads(marker.read_text(encoding="utf-8"))
            root = Path(payload["runtime_root"])
            if root.is_dir():
                return root, bundle_hash
        except (OSError, ValueError, KeyError, TypeError):
            pass

    temporary = Path(tempfile.mkdtemp(prefix="sio-runtime-", dir=str(cache.parent if cache.parent.exists() else ROOT)))
    try:
        unpacked = temporary / "extracted"
        _safe_extract(bundle, unpacked)
        found = _runtime_root(unpacked)
        if destination.parent.exists():
            shutil.rmtree(destination.parent)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(unpacked), str(destination))
        relative = found.relative_to(unpacked)
        final_root = destination / relative
        marker.write_text(
            json.dumps(
                {"bundle_sha256": bundle_hash, "runtime_root": str(final_root)},
                indent=2,
                sort_keys=True,
            ) + "\n",
            encoding="utf-8",
        )
        return final_root, bundle_hash
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def _exact_techs(profile: Mapping[str, Any]) -> Mapping[str, Any] | None:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    explicit = sio.get("tech_input")
    if isinstance(explicit, Mapping):
        return explicit
    raw = _unwrap(sio.get("techs") or profile.get("techs"))
    if not isinstance(raw, Mapping):
        return None
    if not raw:
        return {}
    if all(isinstance(value, Mapping) for value in raw.values()):
        return raw
    return None


def build_oracle_request(profile: Mapping[str, Any]) -> dict[str, Any]:
    sio = profile.get("sio_ce") if isinstance(profile.get("sio_ce"), Mapping) else {}
    stats = sio.get("stats") if isinstance(sio.get("stats"), Mapping) else profile.get("stats", {})
    attack: dict[str, Any] = {}
    for row in (profile.get("attack"), sio.get("attack")):
        if isinstance(row, Mapping):
            attack.update(row)
    if "atkBase" not in attack or "atkFinal" not in attack:
        raise SioRuntimeInputError("Exact sIO scoring requires attack.atkBase and attack.atkFinal.")

    skills = _unwrap(sio.get("skills") or profile.get("skills") or {})
    if not isinstance(skills, Mapping):
        skills = {}
    settings = _unwrap(sio.get("settings") or profile.get("settings") or {})
    if not isinstance(settings, Mapping):
        settings = {}
    evolve = sio.get("evolvePassives", profile.get("evolvePassives", settings.get("evolvePassives")))
    if evolve not in (True, False):
        raise SioRuntimeInputError(
            "Exact evolved-passive scoring requires sio_ce.evolvePassives=true/false; it is not guessed."
        )
    techs = _exact_techs(profile)
    if techs is None and (sio.get("techs") or profile.get("techs") or profile.get("tech")):
        raise SioRuntimeInputError("Tech state is not in the exact sIO deployed/rarity/resonance/overload schema.")
    collectibles = _unwrap(sio.get("collectibles") or profile.get("collectibles") or {})
    if not isinstance(collectibles, Mapping):
        collectibles = {}
    upgraded = sio.get("upgradedCollectibles", profile.get("upgradedCollectibles", [])) or []
    direct = sio.get("direct_skill_factors") if isinstance(sio.get("direct_skill_factors"), Mapping) else profile.get("direct_skill_factors", {})
    if not isinstance(direct, Mapping):
        direct = {}

    tech_input = {
        "evolvePassives": bool(evolve),
        "cooldownReduction": float((stats or {}).get("cooldownReduction", 0) or 0),
        "techs": dict(techs or {}),
        "skills": dict(skills),
        "collectibles": dict(collectibles),
        "upgradedCollectibles": list(upgraded),
        "settings": {**dict(settings), "calcMode": "damage"},
        "gameMode": "ce",
    }
    return {
        "stats": dict(stats or {}),
        "attack": attack,
        "skills": dict(skills),
        "direct_skill_factors": dict(direct),
        "tech_input": tech_input,
        "gameMode": "ce",
    }


class SioCeRuntimeOracle:
    def __init__(
        self,
        *,
        bundle_path: Path | None = None,
        cache_path: Path | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.bundle_path = bundle_path
        self.cache_path = cache_path or Path(os.environ.get("SIO_ORACLE_RESULT_CACHE", DEFAULT_RESULT_CACHE))
        self.timeout_seconds = float(timeout_seconds)
        self._runtime_root: Path | None = None
        self._bundle_hash: str | None = None
        self._node: str | None = None
        self._cache = JsonlCache(self.cache_path, flush_every=25, max_file_bytes=256 * 1024 * 1024)

    def _prepare(self) -> None:
        if self._runtime_root is not None:
            return
        if not ORACLE_SCRIPT.is_file():
            raise SioRuntimeUnavailable(f"Missing oracle script: {ORACLE_SCRIPT}")
        self._runtime_root, self._bundle_hash = ensure_extracted_bundle(self.bundle_path)
        self._node = find_node()

    def score_profiles(self, profiles: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
        requests = [build_oracle_request(profile) for profile in profiles]
        results: list[dict[str, Any] | None] = [None] * len(requests)
        missing_requests: list[dict[str, Any]] = []
        missing_indices: list[int] = []
        missing_keys: list[str] = []
        for index, request in enumerate(requests):
            key = stable_hash({"schema": "sio_ce_oracle_v1", "request": request, "bundle": SIO_BUNDLE_SHA256})
            cached = self._cache.get(key)
            if cached is not None and isinstance(cached.get("result"), Mapping):
                results[index] = deepcopy(dict(cached["result"]))
            else:
                missing_indices.append(index)
                missing_requests.append(request)
                missing_keys.append(key)

        if missing_requests:
            self._prepare()
            completed = subprocess.run(
                [str(self._node), str(ORACLE_SCRIPT), str(self._runtime_root)],
                input=json.dumps({"requests": missing_requests}, ensure_ascii=False),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            if completed.returncode != 0:
                raise SioRuntimeUnavailable(
                    f"sIO oracle failed with code {completed.returncode}: {completed.stderr[-4000:]}"
                )
            try:
                payload = json.loads(completed.stdout)
                fresh = payload["results"]
            except (ValueError, KeyError, TypeError) as error:
                raise SioRuntimeUnavailable(f"Invalid sIO oracle output: {error}") from error
            if len(fresh) != len(missing_requests):
                raise SioRuntimeUnavailable("sIO oracle returned the wrong number of rows.")
            for index, key, result in zip(missing_indices, missing_keys, fresh):
                enriched = {
                    **dict(result),
                    "formula_provenance": {
                        "source": "user-supplied sIO Tools runtime bundle",
                        "bundle_sha256": self._bundle_hash,
                        "modules": [13024, 88426, 67727],
                        "oracle": "tools/sio_runtime/sio_ce_oracle.js",
                    },
                }
                results[index] = enriched
                self._cache.set(key, {"result": enriched})
            self._cache.flush()
        return [dict(result or {}) for result in results]

    def score_profile(self, profile: Mapping[str, Any]) -> dict[str, Any]:
        return self.score_profiles([profile])[0]

    def close(self) -> None:
        self._cache.close()


_DEFAULT_ORACLE: SioCeRuntimeOracle | None = None


def default_oracle() -> SioCeRuntimeOracle:
    global _DEFAULT_ORACLE
    if _DEFAULT_ORACLE is None:
        _DEFAULT_ORACLE = SioCeRuntimeOracle()
    return _DEFAULT_ORACLE


def score_profile_exact(profile: Mapping[str, Any]) -> dict[str, Any]:
    return default_oracle().score_profile(profile)


__all__ = [
    "SioCeRuntimeOracle",
    "SioRuntimeInputError",
    "SioRuntimeUnavailable",
    "build_oracle_request",
    "default_oracle",
    "ensure_extracted_bundle",
    "find_sio_bundle",
    "score_profile_exact",
]
