#!/usr/bin/env python3
"""
Extract a training corpus from a static sIO Tools export zip.

This is a data-training extractor, not an optimizer opinion layer.
It scans the uploaded sIO static site export, finds bundled game-data/formula modules,
writes progress to the terminal, and saves a report of anything missing/unknown.

Usage:
  python -u tools/sio_training/extract_sio_bundle.py data/sio_training/archive/sio_tools.exp0.dev.zip --out data/sio_training/generated
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

KEYWORDS = [
    "items:", "af:", "techs:", "resonance:", "deployedResonance",
    "xenoPetAwakening", "xenoResMultiplier", "xenoDamage",
    "petSkills", "collectibles", "synergy", "Relic Core", "Resonance Chip",
    "xeno_pet_core", "awakening_core", "voidwaker", "Eternal",
    "baseStats", "heroes", "pets", "mounts", "skills", "overload"
]

MODULE_HINTS = {
    "37013": "main data module: baseStats/heroes/items/techs/pets/xenoPetAwakening",
    "32085": "constants/helpers module: tech names, resonance arrays, xeno skill arrays, item lists",
    "39513": "enum/constants module: rarity/type names"
}

FORMULA_MAP = {
    "training_rule": "Enumerate every legal spend allocation, simulate the full after-state, score with extracted stat model, choose highest delta damage.",
    "resource_rule": "Never treat materials inside current build as free unless a modeled undo/move action explicitly returns them.",
    "gear": "Use items[name].stats plus items[name].af.e/v/c for current and candidate E/V/C state.",
    "tech": "For each tech mode add rarity/deployedRarity, resonance/deployedResonance breakpoints, overload, collectible/set bonuses, then compute resonanceMultiplier.",
    "xeno_awakening": "For each xenoPetAwakening row, count Xeno pets with stars greater than the row index and add values[count] to that row stat.",
    "xeno_resonance": "xenoResMultiplier = clamp(chance,0,100) * max(0,damage) * (4 + clamp(duration)) / 500.",
    "xeno_damage": "xenoDamage = activePetDamageAtStars * xenoPetBaseMultiplier * (syncRate/100) * skillDamageFactor(xenoSkillDamage)."
}


def now() -> str:
    return time.strftime("%H:%M:%S")


def fmt_seconds(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        return "unknown"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    sec = int(seconds % 60)
    return f"{minutes}m {sec}s"


class Logger:
    def __init__(self, log_path: Path) -> None:
        self.start = time.time()
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", encoding="utf-8")

    def write(self, msg: str) -> None:
        elapsed = fmt_seconds(time.time() - self.start)
        line = f"[{now()} +{elapsed}] {msg}"
        print(line, flush=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def extract_module(text: str, module_id: str) -> str | None:
    m = re.search(rf"(?<!\w){re.escape(module_id)}:\s*\(", text)
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


def progress(i: int, total: int, start: float, current: Path) -> str:
    elapsed = time.time() - start
    rate = i / elapsed if elapsed > 0 else 0
    remaining = (total - i) / rate if rate > 0 else float("nan")
    pct = (i / total * 100) if total else 100
    return f"scanning {i}/{total} ({pct:.1f}%), ETA {fmt_seconds(remaining)}, current: {current.name}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("zip_path")
    ap.add_argument("--out", default="data/sio_training/generated")
    ap.add_argument("--snippet-limit", type=int, default=120000)
    args = ap.parse_args()

    zip_path = Path(args.zip_path)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = Logger(out / "live_extract.log")
    unknowns: list[str] = []

    log.write("START sIO training extraction")
    log.write(f"zip path: {zip_path}")
    log.write(f"output folder: {out}")

    if not zip_path.exists():
        log.write("ERROR: zip file not found")
        (out / "unknowns_report.md").write_text(
            f"# sIO extraction unknowns\n\n- ERROR: zip file not found: `{zip_path}`\n",
            encoding="utf-8"
        )
        raise SystemExit(2)

    zip_hash = sha256_file(zip_path)
    zip_size = zip_path.stat().st_size
    log.write(f"zip size: {zip_size:,} bytes")
    log.write(f"zip sha256: {zip_hash}")

    tmp = Path(tempfile.mkdtemp(prefix="sio_extract_"))
    scan_start = time.time()
    try:
        log.write("reading zip index...")
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            log.write(f"zip entries: {len(names)}")
            log.write("extracting zip to temp folder...")
            zf.extractall(tmp)

        text_files = [p for ext in ("*.js", "*.html", "*.txt") for p in tmp.rglob(ext) if p.is_file()]
        text_files.sort(key=lambda p: p.stat().st_size, reverse=True)
        log.write(f"text/code files to scan: {len(text_files)}")

        chunk_index = []
        modules: dict[str, dict[str, object]] = {}
        keyword_totals = {kw: 0 for kw in KEYWORDS}

        for idx, path in enumerate(text_files, start=1):
            rel = path.relative_to(tmp)
            text = read_text(path)
            lower = text.lower()
            hits = {}
            for kw in KEYWORDS:
                c = lower.count(kw.lower())
                if c:
                    hits[kw] = c
                    keyword_totals[kw] += c
            if hits:
                chunk_index.append({"file": str(rel), "bytes": len(text), "hits": hits})
            for mid, desc in MODULE_HINTS.items():
                if mid not in modules:
                    mod = extract_module(text, mid)
                    if mod:
                        modules[mid] = {"file": str(rel), "description": desc, "bytes": len(mod)}
                        out_file = out / f"module_{mid}.snippet.js"
                        out_file.write_text(mod[:args.snippet_limit], encoding="utf-8")
                        log.write(f"FOUND module {mid} in {rel}; wrote {out_file}")
            if idx == 1 or idx == len(text_files) or idx % 10 == 0:
                log.write(progress(idx, len(text_files), scan_start, rel))

        for mid, desc in MODULE_HINTS.items():
            if mid not in modules:
                unknowns.append(f"Expected webpack module {mid} not found: {desc}")

        missing_keywords = [kw for kw, count in keyword_totals.items() if count == 0]
        for kw in missing_keywords:
            unknowns.append(f"Keyword not found in scanned text: {kw}")

        top_chunks = sorted(chunk_index, key=lambda r: sum(r["hits"].values()), reverse=True)[:50]
        manifest = {
            "schema": "sio_extracted_training_corpus_v2",
            "zip": str(zip_path),
            "zip_size_bytes": zip_size,
            "zip_sha256": zip_hash,
            "files_seen": len(text_files),
            "module_hints_found": modules,
            "keyword_totals": keyword_totals,
            "chunk_index_top": top_chunks,
            "formula_map": FORMULA_MAP,
            "outputs": {
                "live_log": str(out / "live_extract.log"),
                "unknowns_report": str(out / "unknowns_report.md"),
                "manifest": str(out / "sio_training_corpus_manifest.json")
            },
            "optimizer_next_step": [
                "Parse module_37013.snippet.js / full bundle into normalized JSON tables.",
                "Build legal candidate generator from player state + choice outputs + resource mobility rules.",
                "Run simulation over all candidate allocations together, not split by lane.",
                "Score by damage delta only and output SOURCE ITEM xN -> PICK Y -> END ITEM Z -> FINAL STATE."
            ]
        }
        (out / "sio_training_corpus_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        if unknowns:
            status = "Issues / unknowns found"
        else:
            status = "No extractor-level missing modules/keywords found"
        report = [
            "# sIO extraction unknowns report",
            "",
            f"Status: {status}",
            f"Zip: `{zip_path}`",
            f"SHA256: `{zip_hash}`",
            "",
            "## Unknowns / things to verify",
        ]
        if unknowns:
            report += [f"- {u}" for u in unknowns]
        else:
            report.append("- None at extractor-scan level. Normalizer may still find unknown fields later.")
        report += [
            "",
            "## Found modules",
            *[f"- {mid}: {info.get('file')} ({info.get('bytes')} bytes)" for mid, info in modules.items()],
            "",
            "## Top chunks",
            *[f"- {row['file']} hits={sum(row['hits'].values())} bytes={row['bytes']}" for row in top_chunks[:15]],
            "",
            "## Rule reminder",
            "- Do not let the optimizer invent a spend preference.",
            "- Do not count materials inside current build as free unless the simulator models a valid move/undo path.",
            "- If normalizer does not understand a field, write it here and ask for a data patch instead of guessing.",
        ]
        (out / "unknowns_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")

        log.write(f"wrote manifest: {out / 'sio_training_corpus_manifest.json'}")
        log.write(f"wrote unknowns report: {out / 'unknowns_report.md'}")
        log.write("DONE sIO training extraction")
        print(json.dumps(manifest, indent=2), flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted by user", file=sys.stderr, flush=True)
        raise
