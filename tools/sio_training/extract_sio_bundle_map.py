#!/usr/bin/env python3
"""Map a source-locked sIO export without executing its application UI.

The report inventories webpack modules, dotted feature/translation keys,
optimizer keys and Web Worker registrations. It also reports worker chunks that
are referenced by the app and service worker but absent from the supplied zip.
That distinction prevents the optimizer from pretending an omitted worker's
search algorithm has been reproduced.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any
import zipfile

MODULE_RE = re.compile(
    r"(?:^|[,\{])\s*(\d{2,6})\s*:\s*(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"
    r"|(?:^|[,\{])\s*(\d{2,6})\s*:\s*function\s*\(",
    re.MULTILINE,
)
DOT_KEY_RE = re.compile(
    r"(?P<q>[\"'])(?P<key>[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_{}\[\]-]+){1,6})(?P=q)"
)
REGISTER_RE = re.compile(
    r"\.register\(\s*[\"']([^\"']+)[\"']\s*,\s*\(\)\s*=>\s*new Worker\([^\n]*?\.u\((\d+)\)",
    re.DOTALL,
)
CHUNK_HASH_RE = re.compile(r"(\d+)\s*:\s*[\"']([0-9a-f]{16})[\"']")
PRECACHE_RE = re.compile(r"/_next/static/chunks/(\d+)\.([0-9a-f]{16})\.js")

REGISTRY_HINTS = {
    "heroes": {"survivor_progression", "survivor_teamwork", "survivor_synergy_harmony", "survivor_optimizer"},
    "items": {"ss_equipment_evc_paths", "chaos_fusion_power", "xeno_transmute"},
    "techs": {"normal_tech_resonance", "twinborn_tech_modes", "resonance_overload", "tech_optimizer"},
    "pets": {"normal_pet_progression", "xeno_pets", "xeno_pet_skills"},
    "collectibles": {"collectibles", "custom_collection_sets", "collectible_optimizer", "collectible_deconstructor"},
    "mounts": {"mounts", "mount_puzzle_optimizer"},
    "optimizer": {"survivor_optimizer", "tech_optimizer", "collectible_optimizer", "mount_puzzle_optimizer"},
    "profile": {"input_schema_and_aliases"},
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_sources(bundle: Path) -> tuple[list[str], dict[str, str]]:
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        javascript: dict[str, str] = {}
        for name in names:
            if not name.endswith(".js"):
                continue
            try:
                javascript[name] = archive.read(name).decode("utf-8")
            except UnicodeDecodeError:
                continue
    return names, javascript


def build_map(bundle: Path, registry: Path | None = None) -> dict[str, Any]:
    names, javascript = _read_sources(bundle)
    source = "\n".join(javascript.values())
    module_ids: set[int] = set()
    for left, right in MODULE_RE.findall(source):
        module_ids.add(int(left or right))
    dotted_keys = sorted({match.group("key") for match in DOT_KEY_RE.finditer(source)})
    namespaces = Counter(key.split(".", 1)[0] for key in dotted_keys)
    optimizer_keys = [
        key for key in dotted_keys
        if ".optimize" in key or key.startswith("optimizer.")
    ]
    chunks = {int(chunk): digest for chunk, digest in CHUNK_HASH_RE.findall(source)}
    precache = {(int(chunk), digest) for chunk, digest in PRECACHE_RE.findall(source)}

    workers = []
    for worker_name, chunk_text in REGISTER_RE.findall(source):
        chunk_id = int(chunk_text)
        digest = chunks.get(chunk_id)
        expected = f"_next/static/chunks/{chunk_id}.{digest}.js" if digest else None
        present = bool(
            digest and any(
                name.endswith(f"/{chunk_id}.{digest}.js") or name == expected
                for name in names
            )
        )
        workers.append({
            "name": worker_name,
            "chunk_id": chunk_id,
            "hash": digest,
            "expected_path": expected,
            "present_in_bundle": present,
            "listed_in_service_worker": (chunk_id, digest) in precache if digest else False,
        })

    registry_ids: set[str] = set()
    namespace_gaps: dict[str, list[str]] = {}
    if registry and registry.is_file():
        rows = json.loads(registry.read_text(encoding="utf-8"))
        registry_ids = {
            str(row.get("id"))
            for row in rows
            if isinstance(row, dict) and row.get("id")
        }
        for namespace, hints in REGISTRY_HINTS.items():
            if namespaces.get(namespace, 0):
                namespace_gaps[namespace] = sorted(hints - registry_ids)

    return {
        "schema": "sio_bundle_map_v1",
        "bundle": str(bundle.resolve()),
        "bundle_sha256": _sha256(bundle),
        "files_total": len(names),
        "javascript_files": len(javascript),
        "webpack_module_count": len(module_ids),
        "webpack_modules": sorted(module_ids),
        "dotted_key_count": len(dotted_keys),
        "dotted_namespaces": dict(sorted(namespaces.items(), key=lambda pair: (-pair[1], pair[0]))),
        "optimizer_keys": optimizer_keys,
        "workers": sorted(workers, key=lambda row: row["name"]),
        "missing_worker_chunks": sorted(
            (worker for worker in workers if not worker["present_in_bundle"]),
            key=lambda row: row["name"],
        ),
        "registry_id_count": len(registry_ids),
        "registry_namespace_gaps": namespace_gaps,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_map(args.bundle, args.registry)
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
