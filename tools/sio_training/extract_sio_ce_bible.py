#!/usr/bin/env python3
"""Extract exact sIO CE formula modules and provenance from a supplied bundle ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import zipfile
from pathlib import Path

FORMULA_MODULES = {
    "67727": "Clan Expedition attack and multiplicative damage formula",
    "88426": "Clan Expedition direct-damage factor",
    "24804": "item thresholds, trigger conditions and uptime normalization",
    "51642": "mount aggregation and sync",
    "40514": "mount constants, sync rates and line caps",
    "32085": "direct damage coefficients and constants",
    "37013": "base stats, equipment, tech, pet, survivor and mount tables",
    "5834": "percent helper",
    "62994": "clamp helper",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_module(text: str, module_id: str) -> str | None:
    match = re.search(rf"(?<!\w){re.escape(module_id)}\s*:\s*\(", text)
    if not match:
        return None
    start = match.start()
    brace = text.find("{", match.end())
    if brace < 0:
        return None
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(brace, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    found: dict[str, dict[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="sio-ce-") as tmp:
        root = Path(tmp)
        with zipfile.ZipFile(args.zip) as archive:
            archive.extractall(root)
        files = sorted(path for path in root.rglob("*.js") if path.is_file())
        for path in files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for module_id, description in FORMULA_MODULES.items():
                if module_id in found:
                    continue
                snippet = extract_module(text, module_id)
                if not snippet:
                    continue
                output = args.out / f"module_{module_id}.factory.js"
                output.write_text(snippet, encoding="utf-8")
                found[module_id] = {
                    "description": description,
                    "source_file": str(path.relative_to(root)),
                    "bytes": len(snippet.encode("utf-8")),
                    "sha256": hashlib.sha256(snippet.encode("utf-8")).hexdigest(),
                    "output": output.name,
                }

    missing = sorted(set(FORMULA_MODULES) - set(found))
    manifest = {
        "schema": "sio_ce_bible_manifest_v1",
        "source_zip": str(args.zip),
        "source_zip_sha256": sha256(args.zip),
        "supported_mode": "clan_expedition",
        "formula_modules": found,
        "missing_modules": missing,
        "ready": not missing,
        "source_policy": [
            "sIO runtime bundle",
            "user Discord formulas and source PDFs",
            "external sources only when aligned with a Bible source",
        ],
    }
    (args.out / "sio_ce_bible_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
