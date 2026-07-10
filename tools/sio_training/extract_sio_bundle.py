#!/usr/bin/env python3
"""
Extract a training corpus from a static sIO Tools export zip.

This does not copy the site UI. It finds where the bundled game data and formula code live so the optimizer can be trained from the same data model.

Usage:
  python tools/sio_training/extract_sio_bundle.py sio_tools.exp0.dev.zip --out data/sio_training/generated
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

KEYWORDS = [
    "items:", "af:", "techs:", "resonance:", "deployedResonance",
    "xenoPetAwakening", "xenoResMultiplier", "xenoDamage",
    "petSkills", "collectibles", "synergy", "Relic Core", "Resonance Chip",
    "xeno_pet_core", "awakening_core", "voidwaker", "Eternal"
]

MODULE_HINTS = {
    "37013": "main data module: baseStats/heroes/items/techs/pets/xenoPetAwakening",
    "32085": "constants/helpers module: tech names, resonance arrays, xeno skill arrays, item lists",
    "39513": "enum/constants module: rarity/type names"
}

FORMULA_MAP = {
    "gear": "Use items[name].stats plus items[name].af.e/v/c for current and candidate E/V/C state.",
    "tech": "For each tech mode add rarity/deployedRarity, resonance/deployedResonance breakpoints, overload, collectible/set bonuses, then compute resonanceMultiplier.",
    "xeno_awakening": "For each xenoPetAwakening row, count Xeno pets with stars greater than the row index and add values[count] to that row stat.",
    "xeno_resonance": "xenoResMultiplier = clamp(chance,0,100) * max(0,damage) * (4 + clamp(duration)) / 500.",
    "xeno_damage": "xenoDamage = activePetDamageAtStars * xenoPetBaseMultiplier * (syncRate/100) * skillDamageFactor(xenoSkillDamage).",
    "training_rule": "Enumerate every legal spend allocation, simulate the full after-state, score with extracted stat model, then choose highest delta damage."
}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def extract_module(text: str, module_id: str) -> str | None:
    m = re.search(rf"(?<!\\w){re.escape(module_id)}:\s*\(", text)
    if not m:
        return None
    start = m.start()
    brace = text.find("{", m.end())
    if brace < 0:
        return None
    depth = 0
    quote = None
    esc = False
    for i in range(brace, len(text)):
        ch = text[i]
        if quote:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                quote = None
        else:
            if ch in "'\"`":
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("zip_path")
    ap.add_argument("--out", default="data/sio_training/generated")
    args = ap.parse_args()

    zip_path = Path(args.zip_path)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="sio_extract_"))
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)

        text_files = [p for ext in ("*.js", "*.html", "*.txt") for p in tmp.rglob(ext) if p.is_file()]
        chunk_index = []
        modules = {}

        for path in text_files:
            rel = path.relative_to(tmp)
            text = read_text(path)
            hits = {kw: text.lower().count(kw.lower()) for kw in KEYWORDS if kw.lower() in text.lower()}
            if hits:
                chunk_index.append({"file": str(rel), "bytes": len(text), "hits": hits})
            for mid, desc in MODULE_HINTS.items():
                mod = extract_module(text, mid)
                if mod:
                    modules[mid] = {"file": str(rel), "description": desc, "bytes": len(mod)}
                    (out / f"module_{mid}.snippet.js").write_text(mod[:120000], encoding="utf-8")

        manifest = {
            "schema": "sio_extracted_training_corpus_v1",
            "zip": str(zip_path),
            "files_seen": len(text_files),
            "module_hints_found": modules,
            "chunk_index_top": sorted(chunk_index, key=lambda r: sum(r["hits"].values()), reverse=True)[:50],
            "formula_map": FORMULA_MAP,
            "optimizer_next_step": [
                "Convert module_37013 snippets into normalized JSON tables for items, techs, pets, collectibles.",
                "Generate candidate allocations from player_state + choice outputs.",
                "Score every candidate by simulating after-state and computing delta damage.",
                "Output total end-items, final gear E/V/C, final tech state, final xeno pet state."
            ]
        }
        (out / "sio_training_corpus_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(manifest, indent=2))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
