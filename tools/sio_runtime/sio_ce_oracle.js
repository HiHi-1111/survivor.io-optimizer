#!/usr/bin/env node
'use strict';

/* Exact offline Clan Expedition oracle for the user-supplied sIO bundle.
 *
 * Loads the compiled webpack modules and calls the original sIO Tech/Twinborn,
 * direct-damage and final CE functions. It never uses the network and never
 * produces recommendations. JSON is read from stdin and JSON is written to
 * stdout so Python can batch/cache calls.
 */

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

function walk(dir, list = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(file, list);
    else if (file.endsWith('.js')) list.push(file);
  }
  return list;
}

function elementStub() {
  return {
    style: {}, children: [], firstChild: null,
    appendChild(child) { this.children.push(child); return child; },
    insertBefore(child) { this.children.push(child); return child; },
    removeChild() {}, querySelectorAll() { return []; }, querySelector() { return null; },
    setAttribute() {}, getAttribute() { return null; }, removeAttribute() {},
    addEventListener() {}, removeEventListener() {}, remove() {}, click() {},
    getContext() { return null; }, getBoundingClientRect() { return { x: 0, y: 0, width: 0, height: 0 }; },
  };
}

function loadRuntime(root) {
  const modules = {};
  const pushChunk = (chunk) => Object.assign(modules, chunk[1] || {});
  const document = elementStub();
  document.head = elementStub();
  document.body = elementStub();
  document.documentElement = elementStub();
  document.createElement = () => elementStub();
  document.createTextNode = (text) => ({ textContent: String(text) });
  document.currentScript = { src: 'https://sio-tools.exp0.dev/_next/static/chunks/runtime.js' };
  const storage = { getItem() { return null; }, setItem() {}, removeItem() {}, clear() {} };
  const self = { webpackChunk_N_E: { push: pushChunk }, location: { href: 'https://sio-tools.exp0.dev/' } };
  const context = {
    self, window: self, globalThis: null, console, document,
    navigator: { language: 'en', languages: ['en'], userAgent: 'node-sio-oracle' },
    location: { href: 'https://sio-tools.exp0.dev/', origin: 'https://sio-tools.exp0.dev', pathname: '/' },
    crypto: { getRandomValues(array) { return array; } },
    setTimeout, clearTimeout, setInterval, clearInterval,
    URL, URLSearchParams, TextEncoder, TextDecoder, Blob: global.Blob,
    atob: (value) => Buffer.from(value, 'base64').toString('binary'),
    btoa: (value) => Buffer.from(value, 'binary').toString('base64'),
    localStorage: storage, sessionStorage: storage,
    performance: { now: () => Date.now() },
    requestAnimationFrame: (fn) => setTimeout(() => fn(Date.now()), 0),
    cancelAnimationFrame: clearTimeout,
    Image: function Image() { return elementStub(); },
  };
  context.globalThis = context;
  vm.createContext(context);

  const evalErrors = [];
  for (const file of walk(root).sort()) {
    try {
      vm.runInContext(fixSyntax(fs.readFileSync(file, 'utf8')), context, { filename: file, timeout: 10000 });
    } catch (error) {
      evalErrors.push({ file: path.relative(root, file), error: String(error && (error.message || error)) });
    }
  }

  const cache = {};
  function req(id) {
    id = String(id);
    if (cache[id]) return cache[id].exports;
    const factory = modules[id];
    if (!factory) throw new Error(`Missing webpack module ${id}`);
    const module = { exports: {} };
    cache[id] = module;
    factory(module, module.exports, req);
    return module.exports;
  }
  req.d = (exports, definitions) => {
    for (const key in definitions) {
      if (!Object.prototype.hasOwnProperty.call(exports, key)) {
        Object.defineProperty(exports, key, { enumerable: true, get: definitions[key] });
      }
    }
  };
  req.r = (exports) => {
    Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });
    Object.defineProperty(exports, '__esModule', { value: true });
  };
  req.n = (module) => {
    const getter = module && module.__esModule ? () => module.default : () => module;
    req.d(getter, { a: getter });
    return getter;
  };
  req.o = (object, property) => Object.prototype.hasOwnProperty.call(object, property);
  req.p = '';
  req.u = (id) => `${id}.js`;
  req.e = async () => {};
  req.f = {};
  req.m = modules;
  req.c = cache;
  return { req, modulesRegistered: Object.keys(modules).length, evalErrors };
}

function number(value, fallback = 0) {
  const result = Number(value);
  return Number.isFinite(result) ? result : fallback;
}

function mergeNumeric(target, source) {
  if (!source || typeof source !== 'object') return target;
  for (const [key, value] of Object.entries(source)) {
    const amount = Number(value);
    if (Number.isFinite(amount) && amount !== 0) target[key] = number(target[key]) + amount;
  }
  return target;
}

function scoreOne(runtime, payload) {
  const techFunction = runtime.req(13024).T;
  const directFunction = runtime.req(88426).y;
  const damageFunction = runtime.req(67727).f;
  const stats = { ...(payload.stats || {}) };
  const attack = { ...(payload.attack || {}) };
  const directSeed = { ...(payload.direct_skill_factors || payload.ceDamage || {}) };
  const skills = { ...(payload.skills || {}) };
  const techInput = payload.tech_input || payload.techInput || null;
  let techResult = { stats: {}, ceDamage: {}, passivePools: new Float64Array(56).fill(1) };

  if (techInput) {
    const normalized = {
      evolvePassives: techInput.evolvePassives === true,
      cooldownReduction: number(techInput.cooldownReduction, number(stats.cooldownReduction, 0)),
      techs: techInput.techs || {},
      skills: techInput.skills || skills,
      collectibles: techInput.collectibles || {},
      upgradedCollectibles: techInput.upgradedCollectibles || [],
      settings: { calcMode: 'damage', ...(techInput.settings || {}) },
      gameMode: techInput.gameMode || payload.gameMode || 'ce',
      eeOmnipower: techInput.eeOmnipower,
      eeSkills: techInput.eeSkills,
      stableTechEntries: techInput.stableTechEntries,
    };
    techResult = techFunction(normalized, {});
    mergeNumeric(stats, techResult.stats || {});
    Object.assign(directSeed, techResult.ceDamage || {});
    Object.assign(skills, normalized.skills || {});
  }

  const direct = directFunction(stats, directSeed);
  const passivePools = techResult.passivePools || new Float64Array(56).fill(1);
  const totalDamage = damageFunction(
    stats,
    attack,
    number(direct.damageFactor, 0),
    direct.ceDamage || {},
    'damage',
    skills,
    passivePools,
    payload.gameMode || (techInput && techInput.gameMode) || 'ce'
  );
  return {
    supported: Number.isFinite(Number(totalDamage)),
    total_damage: number(totalDamage, 0),
    stats,
    tech_stats: techResult.stats || {},
    ce_damage: direct.ceDamage || {},
    damage_factor: number(direct.damageFactor, 0),
    passive_pools: Array.from(passivePools || []),
    formula_modules: [13024, 88426, 67727],
    calc_mode: 'damage',
    game_mode: payload.gameMode || 'ce',
  };
}

function main() {
  const root = process.argv[2];
  if (!root || !fs.existsSync(root)) throw new Error('Usage: sio_ce_oracle.js <extracted-sio-root>');
  const runtime = loadRuntime(root);
  const text = fs.readFileSync(0, 'utf8').trim();
  const request = text ? JSON.parse(text) : {};
  const rows = Array.isArray(request) ? request : (request.requests || request.profiles || [request]);
  const results = rows.map((row) => {
    try { return scoreOne(runtime, row || {}); }
    catch (error) { return { supported: false, error: String(error && (error.stack || error.message || error)) }; }
  });
  process.stdout.write(JSON.stringify({
    schema: 'sio_ce_oracle_v1',
    modules_registered: runtime.modulesRegistered,
    eval_error_count: runtime.evalErrors.length,
    results,
  }));
}

try { main(); }
catch (error) {
  process.stderr.write(String(error && (error.stack || error.message || error)) + '\n');
  process.exit(1);
}
