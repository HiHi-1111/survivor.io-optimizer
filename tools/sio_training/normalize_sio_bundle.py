#!/usr/bin/env python3
"""
Normalize sIO Tools static-export data into raw training tables for the Survivor.io optimizer.

This script has two modes:
1. Runtime mode if Node.js exists: execute webpack modules and dump exact exports.
2. Static mode if Node.js is missing: still extract module snippets, keyword maps, field hints,
   and parser targets so training can continue without installing anything.

This script must not rank builds or invent advice. It only prepares data for the optimizer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

MODULE_HINTS = {
    "37013": "main data module: baseStats/heroes/items/techs/pets/xenoPetAwakening",
    "32085": "constants/helpers module: tech names, resonance arrays, xeno skill arrays, item lists",
    "39513": "enum/constants module: rarity/type names",
}

KEYWORDS = [
    "baseStats", "heroes", "items", "af", "techs", "resonance", "deployedResonance",
    "xenoPetAwakening", "xenoResMultiplier", "xenoDamage", "petSkills", "pets",
    "collectibles", "skills", "mounts", "synergy", "overload", "Relic Core",
    "Resonance Chip", "xeno_pet_core", "awakening_core", "Voidwaker", "Eternal", "Chaos",
]

NODE_RUNTIME = r'''
const fs = require('fs');
const path = require('path');
const vm = require('vm');
function fixSyntax(code) {
  return code
    .replace(/\?\s+\?\s+\.\s*\[/g, '??[')
    .replace(/\?\s+\?\s+\./g, '??.')
    .replace(/\?\s+\?/g, '??')
    .replace(/\?\?\s+=/g, '??=')
    .replace(/\|\|\s+=/g, '||=')
    .replace(/&&\s+=/g, '&&=')
    .replace(/\?\s+\.\s*\[/g, '?.[')
    .replace(/\?\s+\./g, '?.');
}
const root = process.argv[2];
const out = process.argv[3];
let modules = {};
function pushChunk(arr) { Object.assign(modules, arr[1] || {}); }
const fakeDocument = {
  head: { firstChild: null, insertBefore() {}, querySelectorAll() { return []; } },
  querySelectorAll() { return []; }, createElement() { return {}; }, currentScript: { src: '' }
};
const context = { self: { webpackChunk_N_E: { push: pushChunk } }, window: null, console,
  document: fakeDocument, navigator: {}, location: { href: '' }, crypto: { getRandomValues(a) { return a; } },
  setTimeout, clearTimeout };
context.window = context.self;
vm.createContext(context);
function walk(dir, list = []) { for (const ent of fs.readdirSync(dir, { withFileTypes: true })) { const p = path.join(dir, ent.name); if (ent.isDirectory()) walk(p, list); else if (p.endsWith('.js')) list.push(p); } return list; }
const evalErrors = [];
for (const file of walk(root).sort()) {
  try { vm.runInContext(fixSyntax(fs.readFileSync(file, 'utf8')), context, { filename: file, timeout: 3000 }); }
  catch (err) { evalErrors.push({ file: path.relative(root, file), error: String(err.message || err) }); }
}
let cache = {};
function req(id) { id = String(id); if (cache[id]) return cache[id].exports; const fn = modules[id]; if (!fn) throw new Error('Missing webpack module ' + id); const module = { exports: {} }; cache[id] = module; fn(module, module.exports, req); return module.exports; }
req.d = (exports, defs) => { for (const k in defs) { if (!Object.prototype.hasOwnProperty.call(exports, k)) Object.defineProperty(exports, k, { enumerable: true, get: defs[k] }); } };
req.r = (exports) => { Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' }); Object.defineProperty(exports, '__esModule', { value: true }); };
req.n = (mod) => { const getter = mod && mod.__esModule ? () => mod.default : () => mod; req.d(getter, { a: getter }); return getter; };
req.o = (obj, prop) => Object.prototype.hasOwnProperty.call(obj, prop);
req.p = '';
function safeJson(x) { return JSON.parse(JSON.stringify(x, (k, v) => { if (v instanceof Set) return Array.from(v); if (v instanceof Map) return Object.fromEntries(v); if (typeof v === 'function') return '[Function]'; if (v === undefined) return null; return v; })); }
function len(x) { if (Array.isArray(x)) return x.length; if (x && typeof x === 'object') return Object.keys(x).length; return null; }
fs.mkdirSync(out, { recursive: true });
const m370 = req(37013), m320 = req(32085), m395 = req(39513);
const c = safeJson(m370.c), f = safeJson(m370.f), e320 = safeJson(m320), e395 = safeJson(m395);
fs.writeFileSync(path.join(out, 'module_37013_c.json'), JSON.stringify(c, null, 2));
fs.writeFileSync(path.join(out, 'module_37013_f.json'), JSON.stringify(f, null, 2));
fs.writeFileSync(path.join(out, 'module_32085_exports.json'), JSON.stringify(e320, null, 2));
fs.writeFileSync(path.join(out, 'module_39513_exports.json'), JSON.stringify(e395, null, 2));
const normalized = { schema: 'sio_normalized_runtime_tables_v2', mode: 'node_runtime', rule: 'data only; no optimizer preference or ranking is created here', modules_registered: Object.keys(modules).length, eval_errors: evalErrors, tables: { module_37013_keys: Object.keys(c), base_stats: c.baseStats || {}, heroes_count: len(c.heroes), collectibles_count: len(c.collectibles), items_count: len(c.items), techs_count: len(c.techs), pets_count: len(c.pets), skills_count: len(c.skills), xeno_pet_awakening_count: len(c.xenoPetAwakening), module_32085_keys: Object.keys(e320), module_39513_keys: Object.keys(e395) } };
fs.writeFileSync(path.join(out, 'sio_normalized_tables.json'), JSON.stringify(normalized, null, 2));
const unknowns = [];
if (evalErrors.length) unknowns.push('Some browser/service-worker files failed during sandbox eval. Data modules still loaded if 37013/32085/39513 are present.');
const report = ['# sIO normalizer unknowns report', '', 'Status: ' + (unknowns.length ? 'issues to review' : 'no normalizer-level unknowns found'), '', 'Mode: Node runtime exact export dump', '', '## Counts', '- modules registered: ' + Object.keys(modules).length, '- 37013 items: ' + len(c.items), '- 37013 techs: ' + len(c.techs), '- 37013 pets: ' + len(c.pets), '- 37013 xenoPetAwakening rows: ' + len(c.xenoPetAwakening), '', '## Unknowns / verify', ...(unknowns.length ? unknowns.map(x => '- ' + x) : ['- None.']), '', '## Rule reminder', '- This step only normalizes data. It must not recommend relic cores, xeno cores, resonance chips, or gear selectors.', '- Materials already inside the current build are not free unless a modeled move/undo path returns them.'].join('\n');
fs.writeFileSync(path.join(out, 'normalizer_unknowns_report.md'), report);
console.log(JSON.stringify({ status: 'ok', mode: 'node_runtime', out, modules_registered: Object.keys(modules).length, unknowns }, null, 2));
'''


def log(start: float, message: str) -> None:
    elapsed = int(time.time() - start)
    print(f"[{elapsed:>3}s] {message}", flush=True)


def sha256(path: Path) -> str:
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


def static_normalize(start: float, extract_dir: Path, out: Path, zip_path: Path) -> None:
    log(start, "Node.js not found; using Python-only static normalizer")
    text_files = [p for ext in ("*.js", "*.html", "*.txt") for p in extract_dir.rglob(ext) if p.is_file()]
    log(start, f"static files to scan: {len(text_files)}")
    modules = {}
    keyword_totals = {k: 0 for k in KEYWORDS}
    chunk_index = []
    field_hints = {"37013": {}, "32085": {}, "39513": {}}

    for idx, path in enumerate(text_files, 1):
        if idx == 1 or idx % 25 == 0 or idx == len(text_files):
            log(start, f"static scan {idx}/{len(text_files)}: {path.name}")
        rel = str(path.relative_to(extract_dir))
        text = read_text(path)
        hits = {}
        lower = text.lower()
        for kw in KEYWORDS:
            n = lower.count(kw.lower())
            if n:
                hits[kw] = n
                keyword_totals[kw] += n
        if hits:
            chunk_index.append({"file": rel, "bytes": len(text), "hits": hits, "hit_total": sum(hits.values())})
        for mid, desc in MODULE_HINTS.items():
            if mid in modules:
                continue
            mod = extract_module(text, mid)
            if mod:
                p = out / f"module_{mid}.snippet.js"
                p.write_text(mod, encoding="utf-8")
                modules[mid] = {"file": rel, "description": desc, "bytes": len(mod), "snippet_path": str(p)}
                keys = sorted(set(re.findall(r"([A-Za-z_$][\w$]*)\s*:", mod)))[:500]
                strings = sorted(set(re.findall(r"['\"]([^'\"]{3,80})['\"]", mod)))[:800]
                field_hints[mid] = {"object_key_candidates": keys, "string_literal_candidates": strings}
                log(start, f"found module {mid}: {rel}; wrote {p}")

    unknowns = []
    for mid in MODULE_HINTS:
        if mid not in modules:
            unknowns.append(f"Missing module {mid}; parser cannot train that part yet.")
    unknowns.append("Static fallback was used because Node.js is not installed/on PATH. This still preserves source modules and field hints, but exact webpack exports require Node or a later pure-Python parser.")

    normalized = {
        "schema": "sio_normalized_static_tables_v1",
        "mode": "python_static_fallback",
        "rule": "data only; no optimizer preference or ranking is created here",
        "source_zip": str(zip_path),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": sha256(zip_path),
        "modules_found": modules,
        "keyword_totals": {k: v for k, v in keyword_totals.items() if v},
        "chunk_index_top": sorted(chunk_index, key=lambda r: r["hit_total"], reverse=True)[:40],
        "field_hints": field_hints,
        "normalizer_next_step": [
            "Use module_37013.snippet.js as the source for main tables.",
            "Use module_32085.snippet.js as constants/list source.",
            "Build pure-Python object parser or install Node for exact export dump.",
            "Do not generate recommendations until legal candidate simulation exists."
        ]
    }
    (out / "sio_normalized_tables.json").write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    report = [
        "# sIO normalizer unknowns report",
        "",
        "Status: static fallback completed",
        "",
        "Mode: Python-only static fallback, because Node.js is not installed/on PATH.",
        "",
        "## What worked",
        f"- modules found: {', '.join(sorted(modules)) if modules else 'none'}",
        f"- scanned files: {len(text_files)}",
        f"- wrote: `{out / 'sio_normalized_tables.json'}`",
        "",
        "## Unknowns / verify",
        *[f"- {x}" for x in unknowns],
        "",
        "## Rule reminder",
        "- This step only normalizes/extracts data. It must not recommend relic cores, xeno cores, resonance chips, or gear selectors.",
        "- Materials already inside the current build are not free unless a modeled move/undo path returns them.",
        "- If the parser does not understand a field, add it here and ask for a data patch instead of guessing.",
    ]
    (out / "normalizer_unknowns_report.md").write_text("\n".join(report), encoding="utf-8")
    (out / "normalizer_run.log").write_text(json.dumps({"mode": "python_static_fallback", "modules_found": modules, "unknowns": unknowns}, indent=2), encoding="utf-8")
    log(start, f"wrote static normalized tables: {out / 'sio_normalized_tables.json'}")
    log(start, f"wrote unknowns report: {out / 'normalizer_unknowns_report.md'}")


def node_normalize(start: float, extract_dir: Path, out: Path) -> None:
    runtime = out / "_sio_runtime_dump.js"
    runtime.write_text(NODE_RUNTIME, encoding="utf-8")
    log(start, "Node found; running exact webpack export normalizer")
    proc = subprocess.run(
        ["node", str(runtime), str(extract_dir), str(out)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    (out / "normalizer_run.log").write_text(proc.stdout, encoding="utf-8")
    print(proc.stdout)
    if proc.returncode != 0:
        raise SystemExit(f"Node normalizer failed with exit code {proc.returncode}; see {out / 'normalizer_run.log'}")
    log(start, f"wrote normalized tables: {out / 'sio_normalized_tables.json'}")
    log(start, f"wrote unknowns report: {out / 'normalizer_unknowns_report.md'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("zip_path")
    ap.add_argument("--out", default="data/sio_training/normalized")
    args = ap.parse_args()

    start = time.time()
    zip_path = Path(args.zip_path)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log(start, "START sIO normalizer")
    log(start, f"zip path: {zip_path}")
    log(start, f"output folder: {out}")

    if not zip_path.exists():
        raise SystemExit(f"Zip not found: {zip_path}")

    tmp = Path(tempfile.mkdtemp(prefix="sio_normalize_"))
    try:
        extract_dir = tmp / "zip"
        log(start, "extracting zip...")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
        js_count = sum(1 for p in extract_dir.rglob("*.js") if p.is_file())
        log(start, f"JS files found: {js_count}")

        if shutil.which("node"):
            node_normalize(start, extract_dir, out)
        else:
            static_normalize(start, extract_dir, out, zip_path)
        log(start, "DONE sIO normalizer")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
