#!/usr/bin/env python3
"""
Normalize sIO Tools static-export data into raw JSON tables for the Survivor.io optimizer.

This does not rank builds and does not invent advice. It only loads the uploaded sIO zip,
executes the bundled webpack data modules in a sandboxed Node runtime, and writes tables/reports.

Usage:
  python tools/sio_training/normalize_sio_bundle.py data/sio_training/archive/sio_tools.exp0.dev.zip --out data/sio_training/normalized
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

NODE_RUNTIME = r'''
const fs = require('fs');
const path = require('path');
const vm = require('vm');

function fixSyntax(code) {
  // The scraped static export sometimes has spaces inserted into modern JS operators.
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
  querySelectorAll() { return []; },
  createElement() { return {}; },
  currentScript: { src: '' }
};
const context = {
  self: { webpackChunk_N_E: { push: pushChunk } },
  window: null,
  console,
  document: fakeDocument,
  navigator: {},
  location: { href: '' },
  crypto: { getRandomValues(a) { return a; } },
  setTimeout,
  clearTimeout
};
context.window = context.self;
vm.createContext(context);

function walk(dir, list = []) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(p, list);
    else if (p.endsWith('.js')) list.push(p);
  }
  return list;
}

const evalErrors = [];
const files = walk(root).sort();
for (const file of files) {
  try {
    const code = fixSyntax(fs.readFileSync(file, 'utf8'));
    vm.runInContext(code, context, { filename: file, timeout: 3000 });
  } catch (err) {
    evalErrors.push({ file: path.relative(root, file), error: String(err.message || err) });
  }
}

let cache = {};
function req(id) {
  id = String(id);
  if (cache[id]) return cache[id].exports;
  const fn = modules[id];
  if (!fn) throw new Error('Missing webpack module ' + id);
  const module = { exports: {} };
  cache[id] = module;
  fn(module, module.exports, req);
  return module.exports;
}
req.d = (exports, defs) => {
  for (const k in defs) {
    if (!Object.prototype.hasOwnProperty.call(exports, k)) {
      Object.defineProperty(exports, k, { enumerable: true, get: defs[k] });
    }
  }
};
req.r = (exports) => {
  Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });
  Object.defineProperty(exports, '__esModule', { value: true });
};
req.n = (mod) => {
  const getter = mod && mod.__esModule ? () => mod.default : () => mod;
  req.d(getter, { a: getter });
  return getter;
};
req.o = (obj, prop) => Object.prototype.hasOwnProperty.call(obj, prop);
req.p = '';

function safeJson(x) {
  return JSON.parse(JSON.stringify(x, (k, v) => {
    if (v instanceof Set) return Array.from(v);
    if (v instanceof Map) return Object.fromEntries(v);
    if (typeof v === 'function') return '[Function]';
    if (v === undefined) return null;
    return v;
  }));
}
function len(x) {
  if (Array.isArray(x)) return x.length;
  if (x && typeof x === 'object') return Object.keys(x).length;
  return null;
}
function names(x) {
  if (Array.isArray(x)) return x.map(v => Array.isArray(v) ? v[0] : v).filter(v => typeof v === 'string');
  if (x && typeof x === 'object') return Object.keys(x);
  return [];
}

fs.mkdirSync(out, { recursive: true });
const m370 = req(37013);
const m320 = req(32085);
const m395 = req(39513);
const c = safeJson(m370.c);
const f = safeJson(m370.f);
const e320 = safeJson(m320);
const e395 = safeJson(m395);

fs.writeFileSync(path.join(out, 'module_37013_c.json'), JSON.stringify(c, null, 2));
fs.writeFileSync(path.join(out, 'module_37013_f.json'), JSON.stringify(f, null, 2));
fs.writeFileSync(path.join(out, 'module_32085_exports.json'), JSON.stringify(e320, null, 2));
fs.writeFileSync(path.join(out, 'module_39513_exports.json'), JSON.stringify(e395, null, 2));

const normalized = {
  schema: 'sio_normalized_runtime_tables_v1',
  rule: 'data only; no optimizer preference or ranking is created here',
  modules_registered: Object.keys(modules).length,
  eval_errors: evalErrors,
  tables: {
    module_37013: {
      keys: Object.keys(c),
      base_stats: c.baseStats || {},
      heroes_count: len(c.heroes),
      collectibles_count: len(c.collectibles),
      items_count: len(c.items),
      techs_count: len(c.techs),
      pets_count: len(c.pets),
      skills_count: len(c.skills),
      xeno_pet_awakening_count: len(c.xenoPetAwakening)
    },
    module_32085_export_summary: Object.fromEntries(Object.entries(e320).map(([k, v]) => [k, {
      type: Array.isArray(v) ? 'array' : typeof v,
      count: len(v),
      names: names(v).slice(0, 40)
    }])),
    ss_items_from_32085_Di: Array.isArray(e320.Di) ? e320.Di : [],
    tech_names_from_32085_GJ: Array.isArray(e320.GJ) ? e320.GJ : [],
    tech_names_from_32085_Ui: Array.isArray(e320.Ui) ? e320.Ui : [],
    pet_names_from_32085_f: Array.isArray(e320.f) ? e320.f : [],
    xeno_pet_names_from_32085_Ep: Array.isArray(e320.Ep) ? e320.Ep : [],
    collectible_names_from_32085_G3: Array.isArray(e320.G3) ? e320.G3 : [],
    stat_keys_from_32085_PT: Array.isArray(e320.PT) ? e320.PT : [],
    resonance_like_arrays: {
      Dh: e320.Dh || null,
      EF: e320.EF || null,
      Hs: e320.Hs || null,
      sm: e320.sm || null,
      jc: e320.jc || null,
      gs: e320.gs || null
    }
  }
};
fs.writeFileSync(path.join(out, 'sio_normalized_tables.json'), JSON.stringify(normalized, null, 2));

const unknowns = [];
if (!modules['37013']) unknowns.push('Missing webpack module 37013. Cannot read main sIO data module.');
if (!modules['32085']) unknowns.push('Missing webpack module 32085. Cannot read constants/helper tables.');
if (!Array.isArray(e320.Di) || e320.Di.length === 0) unknowns.push('32085.Di SS item table was not found or was empty.');
if (len(c.items) !== null && len(c.items) < 20) unknowns.push('37013.c.items is small; treat it as a build/default state, not the entire item database. Use 32085.Di and other constants for item catalog extraction.');
if (evalErrors.length) unknowns.push('Some browser/service-worker files failed during sandbox eval. Data modules still loaded if 37013/32085/39513 are present. See eval_errors in sio_normalized_tables.json.');

const report = [
  '# sIO normalizer unknowns report',
  '',
  `Status: ${unknowns.length ? 'issues to review' : 'no normalizer-level unknowns found'}`,
  '',
  '## Counts',
  `- modules registered: ${Object.keys(modules).length}`,
  `- 37013 items: ${len(c.items)}`,
  `- 32085.Di SS items: ${Array.isArray(e320.Di) ? e320.Di.length : 0}`,
  `- 32085.GJ tech names: ${Array.isArray(e320.GJ) ? e320.GJ.length : 0}`,
  `- 32085.f pet names: ${Array.isArray(e320.f) ? e320.f.length : 0}`,
  `- 37013 xenoPetAwakening rows: ${len(c.xenoPetAwakening)}`,
  '',
  '## Unknowns / verify',
  ...(unknowns.length ? unknowns.map(x => `- ${x}`) : ['- None.']),
  '',
  '## Rule reminder',
  '- This step only normalizes data. It must not recommend relic cores, xeno cores, resonance chips, or gear selectors.',
  '- The optimizer must later enumerate legal candidate allocations and score them with this data.',
  '- Materials already inside the current build are not free unless a modeled move/undo path returns them.'
].join('\n');
fs.writeFileSync(path.join(out, 'normalizer_unknowns_report.md'), report);

console.log(JSON.stringify({
  status: 'ok',
  out,
  modules_registered: Object.keys(modules).length,
  module_37013_keys: Object.keys(c),
  ss_item_count_32085_Di: Array.isArray(e320.Di) ? e320.Di.length : 0,
  tech_name_count_32085_GJ: Array.isArray(e320.GJ) ? e320.GJ.length : 0,
  unknowns
}, null, 2));
'''


def log(start: float, message: str) -> None:
    elapsed = int(time.time() - start)
    print(f"[{elapsed:>3}s] {message}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("zip_path")
    ap.add_argument("--out", default="data/sio_training/normalized")
    args = ap.parse_args()

    start = time.time()
    zip_path = Path(args.zip_path)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log(start, "START sIO runtime normalizer")
    log(start, f"zip path: {zip_path}")
    log(start, f"output folder: {out}")

    if not zip_path.exists():
        raise SystemExit(f"Zip not found: {zip_path}")
    if shutil.which("node") is None:
        report = out / "normalizer_unknowns_report.md"
        report.write_text("# sIO normalizer unknowns report\n\n- Node.js is not installed or not on PATH. Install Node.js, then rerun normalizer.\n", encoding="utf-8")
        raise SystemExit("Node.js is required for runtime webpack normalization. Install Node.js and rerun.")

    tmp = Path(tempfile.mkdtemp(prefix="sio_normalize_"))
    try:
        extract_dir = tmp / "zip"
        log(start, "extracting zip...")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
        js_count = sum(1 for p in extract_dir.rglob("*.js") if p.is_file())
        log(start, f"JS files found: {js_count}")

        runtime = tmp / "sio_runtime_dump.js"
        runtime.write_text(NODE_RUNTIME, encoding="utf-8")
        log(start, "running Node sandbox to load webpack modules 37013/32085/39513...")
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
        log(start, "DONE sIO runtime normalizer")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
