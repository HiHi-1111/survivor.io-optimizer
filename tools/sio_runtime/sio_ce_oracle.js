#!/usr/bin/env node
'use strict';

/* Exact offline Clan Expedition oracle for the user-supplied sIO bundle.
 *
 * This process loads the compiled webpack modules and executes the same CE order
 * used by sIO Tools: Tech/Twinborn -> item and uptime conditions -> direct damage
 * -> evolved-passive/final stat transforms -> final CE damage. A profile that is
 * explicitly marked post-24804 bypasses those transforms so they cannot be
 * applied twice. The oracle never uses the network or produces recommendations.
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
    try {
      factory.call(module.exports, module, module.exports, req);
      return module.exports;
    } catch (error) {
      delete cache[id];
      throw error;
    }
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
  req.t = function(value, mode) {
    if (mode & 1) value = this(value);
    if (mode & 8) return value;
    if (typeof value === 'object' && value) {
      if ((mode & 4) && value.__esModule) return value;
      if ((mode & 16) && typeof value.then === 'function') return value;
    }
    const namespace = Object.create(null);
    req.r(namespace);
    const definitions = {};
    const excluded = [
      null,
      Object.getPrototypeOf({}),
      Object.getPrototypeOf([]),
      Object.getPrototypeOf(Object.getPrototypeOf({})),
    ];
    let current = (mode & 2) && value;
    while (typeof current === 'object' && current && !excluded.includes(current)) {
      for (const key of Object.getOwnPropertyNames(current)) {
        if (!Object.prototype.hasOwnProperty.call(definitions, key)) {
          definitions[key] = () => value[key];
        }
      }
      current = Object.getPrototypeOf(current);
    }
    definitions.default = () => value;
    req.d(namespace, definitions);
    return namespace;
  };
  req.o = (object, property) => Object.prototype.hasOwnProperty.call(object, property);
  req.p = '';
  req.u = (id) => `${id}.js`;
  req.e = async () => {};
  req.f = {};
  req.g = context;
  req.nmd = (module) => {
    module.paths = [];
    if (!module.children) module.children = [];
    return module;
  };
  req.hmd = (module) => {
    const wrapped = Object.create(module);
    if (!wrapped.children) wrapped.children = [];
    Object.defineProperty(wrapped, 'exports', {
      enumerable: true,
      set() { throw new Error('ES Modules may not assign module.exports'); },
    });
    return wrapped;
  };
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

function clonePlain(value) {
  if (value === undefined) return undefined;
  return JSON.parse(JSON.stringify(value));
}

function uptimeSnapshot(stats) {
  const result = {};
  for (const key of [
    'lacerationUptime', 'divineFireUptime', 'poisonedUptime',
    'weakenedUptime', 'chilledUptime', 'shieldDamageUptime',
    'voidNeckBoostUptime',
  ]) {
    if (stats[key] !== undefined) result[key] = number(stats[key]);
  }
  return result;
}

function scoreOne(runtime, payload) {
  const directFunction = runtime.req(88426).y;
  const damageFunction = runtime.req(67727).f;
  const skipRuntime24804 = payload.skipRuntime24804 === true;
  const stats = { ...(payload.stats || {}) };
  const attack = { ...(payload.attack || {}) };
  const directSeed = { ...(payload.direct_skill_factors || payload.ceDamage || {}) };
  const skills = { ...(payload.skills || {}) };
  const techInput = payload.tech_input || payload.techInput || null;
  const settings = { revives: [40, 70, 90], ...(payload.settings || {}) };
  const collectibles = { ...(payload.collectibles || {}) };
  const items = { ...(payload.items || {}) };
  const gameMode = payload.gameMode || (techInput && techInput.gameMode) || 'ce';
  const evolvePassives = payload.evolvePassives === true || (techInput && techInput.evolvePassives === true);
  let techResult = { stats: {}, ceDamage: {}, passivePools: new Float64Array(56).fill(1) };
  let preFinalizeStats;
  let finalStats;
  let formulaModules;
  let formulaOrder;

  if (skipRuntime24804) {
    if (techInput && techInput.techs && Object.keys(techInput.techs).length) {
      throw new Error('post-24804 snapshots cannot apply raw Tech state again');
    }
    preFinalizeStats = stats;
    finalStats = stats;
    formulaModules = [88426, 67727];
    formulaOrder = ['post_24804_snapshot', '88426.y', '67727.f'];
  } else {
    const techFunction = runtime.req(13024).T;
    const applyConditions = runtime.req(24804).zP;
    const finalizeStats = runtime.req(24804).IE;
    if (techInput) {
      const normalized = {
        evolvePassives,
        cooldownReduction: number(techInput.cooldownReduction, number(stats.cooldownReduction, 0)),
        techs: techInput.techs || {},
        skills: techInput.skills || skills,
        collectibles: techInput.collectibles || collectibles,
        upgradedCollectibles: techInput.upgradedCollectibles || payload.upgradedCollectibles || [],
        settings: { calcMode: 'damage', ...settings, ...(techInput.settings || {}) },
        gameMode,
        eeOmnipower: techInput.eeOmnipower,
        eeSkills: techInput.eeSkills,
        stableTechEntries: techInput.stableTechEntries,
      };
      techResult = techFunction(normalized, {});
      mergeNumeric(stats, techResult.stats || {});
      Object.assign(directSeed, techResult.ceDamage || {});
      Object.assign(skills, normalized.skills || {});
    }
    const conditioned = applyConditions({
      withNotes: false,
      venato: payload.venato === true || payload.activeSurvivor === 'Venato',
      stats,
      collectibles,
      items,
      settings,
      gameMode,
      eeSkills: payload.eeSkills,
      eeOmnipower: payload.eeOmnipower,
    });
    preFinalizeStats = (conditioned && conditioned.stats) || stats;
    finalStats = finalizeStats({
      evolvePassives,
      gameMode,
      stats: preFinalizeStats,
      settings,
    });
    formulaModules = [13024, 24804, 88426, 67727];
    formulaOrder = ['13024.T', '24804.zP', '88426.y', '24804.IE', '67727.f'];
  }

  const direct = directFunction(preFinalizeStats, directSeed);
  const passivePools = techResult.passivePools || new Float64Array(56).fill(1);
  const totalDamage = damageFunction(
    finalStats,
    attack,
    number(direct.damageFactor, 0),
    direct.ceDamage || {},
    'damage',
    skills,
    passivePools,
    gameMode
  );
  return {
    supported: Number.isFinite(Number(totalDamage)),
    total_damage: number(totalDamage, 0),
    stats: clonePlain(finalStats),
    pre_finalize_stats: clonePlain(preFinalizeStats),
    uptime_values: uptimeSnapshot(finalStats),
    tech_stats: clonePlain(techResult.stats || {}),
    ce_damage: clonePlain(direct.ceDamage || {}),
    damage_factor: number(direct.damageFactor, 0),
    passive_pools: Array.from(passivePools || []),
    formula_modules: formulaModules,
    formula_order: formulaOrder,
    skipped_24804: skipRuntime24804,
    stats_stage: payload.statsStage || 'unknown',
    calc_mode: 'damage',
    game_mode: gameMode,
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
    schema: 'sio_ce_oracle_v2',
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
