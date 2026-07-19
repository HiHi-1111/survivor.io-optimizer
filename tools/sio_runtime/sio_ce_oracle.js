#!/usr/bin/env node
'use strict';

/* Exact offline Clan Expedition oracle for the user-supplied sIO bundle.
 *
 * Raw ownership profiles are assembled with the same pure webpack functions used
 * by sIO Tools. The CE core then executes Tech/Twinborn -> item and uptime
 * conditions -> direct damage -> final stat transforms -> final CE damage. A
 * profile explicitly marked post-24804 bypasses transforms already applied.
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ACCOUNT_ASSEMBLY_MODULES = [
  37013, 63941, 5005, 42052, 41950, 57223, 89505, 42806, 70324,
  30039, 40498, 80438, 51642, 94578, 92316, 30396, 13024, 19425,
];

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
        if (!Object.prototype.hasOwnProperty.call(definitions, key)) definitions[key] = () => value[key];
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

function normalizeMounts(runtime, rawMounts) {
  const mounts = rawMounts && typeof rawMounts === 'object' ? rawMounts : {};
  const sourceData = mounts.data && typeof mounts.data === 'object' ? mounts.data : {};
  const data = {};
  for (const name of runtime.req(32085).xp) data[name] = sourceData[name] || {};
  return { active: mounts.active || '', data };
}

function assembleRuntimeAccount(runtime, rawInput) {
  const input = rawInput && typeof rawInput === 'object' ? rawInput : {};
  const merge = runtime.req(63941).x;
  const upgradedCollectibles = new Set(input.upgradedCollectibles || []);
  const gameMode = 'ce';
  const settings = { calcMode: 'damage', revives: [40, 70, 90], ...(input.settings || {}) };
  const heroes = input.heroes || {};
  const items = input.items || {};
  const collectibles = input.collectibles || {};
  const skills = input.skills || {};
  const pets = input.pets || {};
  const petSkills = input.petSkills || {};
  const mainHero = input.mainHero || 'None';
  const synergy = input.synergy === true;
  const evolvePassives = input.evolvePassives === true;

  const baseStats = runtime.req(37013).c.baseStats;
  const synergyStats = runtime.req(5005).Q({ synergy, synergyLevel: number(input.synergyLevel, 0) });
  const itemStats = runtime.req(42052).vY({
    items,
    collectibles,
    upgradedCollectibles,
    maxGear: number(input.maxGear, 0),
  });
  const harmonyStats = runtime.req(41950).j(
    synergy,
    mainHero,
    input.harmonyL || 'None',
    input.harmonyR || 'None',
    heroes
  );
  const itemCollectibleStats = runtime.req(57223).m({ collectibles, upgradedCollectibles });
  const collectibleStats = runtime.req(89505).Y3({ collectibles });
  const customSetStats = runtime.req(42806).x({ collectibles, customSets: input.customSets || {} });
  const evoStats = runtime.req(70324).t({ evoTree: input.evoTree || {} });
  const turfStats = runtime.req(30039).s({ turf: input.turf || {} });
  const lmeStats = runtime.req(40498).N({
    gameMode,
    lmeTestaments: input.lmeTestaments || {},
    lmeStatsOverrides: input.lmeStatsOverrides || {},
  });
  const eeStats = runtime.req(80438).b({ gameMode, eeSkills: input.eeSkills || {} });
  const mountStats = runtime.req(51642).F({ mounts: normalizeMounts(runtime, input.mounts) });
  const skillStats = runtime.req(94578).p({ skills });
  const survivorStats = runtime.req(92316).xt({
    beta: input.beta === true,
    synergy,
    heroes,
    mainHero,
    teamwork: input.teamwork || [],
    clanLevel: number(input.clanLevel, 0),
    skills,
  });
  const accountContext = runtime.req(30396).i({
    withNotes: false,
    mainHero,
    synergy,
    teamwork: input.teamwork || [],
    heroes,
    evoTree: input.evoTree || {},
    skills,
    pets,
    petSkills,
    evolvePassives,
  });
  const techResult = runtime.req(13024).T({
    cooldownReduction: number(accountContext.cooldownReduction, 0),
    evolvePassives,
    techs: input.techs || {},
    skills,
    collectibles,
    upgradedCollectibles,
    settings,
    gameMode,
    eeSkills: input.eeSkills,
    eeOmnipower: input.eeOmnipower,
  });
  const petStats = runtime.req(19425).a6({ pets, petSkills, collectibles, lmeStats });
  const stats = merge([
    baseStats,
    survivorStats,
    collectibleStats,
    customSetStats,
    synergyStats,
    itemCollectibleStats,
    harmonyStats,
    itemStats,
    evoStats,
    turfStats,
    petStats,
    mountStats,
    skillStats,
    techResult.stats || {},
    lmeStats,
    eeStats,
    { cooldownReduction: number(accountContext.cooldownReduction, 0) },
    input.statsOverrides || {},
  ]);
  return {
    stats,
    techResult,
    skills,
    settings,
    collectibles,
    items,
    mainHero,
    evolvePassives,
    accountContext: { cooldownReduction: number(accountContext.cooldownReduction, 0) },
  };
}

function scoreOne(runtime, payload) {
  const skipRuntime24804 = payload.skipRuntime24804 === true;
  const accountInput = !skipRuntime24804 && payload.account_input && typeof payload.account_input === 'object'
    ? payload.account_input
    : null;
  const techFunction = skipRuntime24804 || accountInput ? null : runtime.req(13024).T;
  const applyConditions = skipRuntime24804 ? null : runtime.req(24804).zP;
  const directFunction = runtime.req(88426).y;
  const finalizeStatsFunction = skipRuntime24804 ? null : runtime.req(24804).IE;
  const damageFunction = runtime.req(67727).f;
  const baseStats = runtime.req(37013).c.baseStats || {};
  let stats = { ...baseStats, ...(payload.stats || {}) };
  const attack = { ...(payload.attack || {}) };
  const directSeed = { ...(payload.direct_skill_factors || payload.ceDamage || {}) };
  let skills = { ...(payload.skills || {}) };
  const techInput = payload.tech_input || payload.techInput || null;
  let settings = { revives: [40, 70, 90], ...(payload.settings || {}) };
  let collectibles = { ...(payload.collectibles || {}) };
  let items = { ...(payload.items || {}) };
  const gameMode = payload.gameMode || (techInput && techInput.gameMode) || 'ce';
  let activeSurvivor = payload.activeSurvivor || '';
  let evolvePassives = payload.evolvePassives === true || (techInput && techInput.evolvePassives === true);
  let techResult = { stats: {}, ceDamage: {}, passivePools: new Float64Array(56).fill(1) };
  let accountContext = {};
  let accountAssemblyExact = false;
  let preFinalizeStats;
  let finalStats;
  let direct;
  let formulaModules;
  let formulaOrder;

  if (skipRuntime24804) {
    if (techInput && techInput.techs && Object.keys(techInput.techs).length) {
      throw new Error('post-24804 snapshots cannot apply raw Tech state again');
    }
    preFinalizeStats = stats;
    direct = directFunction(preFinalizeStats, directSeed);
    finalStats = stats;
    formulaModules = [88426, 67727];
    formulaOrder = ['post_24804_snapshot', '88426.y', '67727.f'];
  } else {
    if (accountInput) {
      const assembled = assembleRuntimeAccount(runtime, accountInput);
      stats = { ...assembled.stats };
      techResult = assembled.techResult;
      skills = { ...assembled.skills };
      settings = { ...assembled.settings };
      collectibles = { ...assembled.collectibles };
      items = { ...assembled.items };
      activeSurvivor = assembled.mainHero;
      evolvePassives = assembled.evolvePassives;
      accountContext = assembled.accountContext;
      accountAssemblyExact = true;
      Object.assign(directSeed, techResult.ceDamage || {});
    } else if (techInput) {
      const normalized = {
        evolvePassives,
        cooldownReduction: number(techInput.cooldownReduction, number(stats.cooldownReduction, 0)),
        techs: techInput.techs || {},
        skills: techInput.skills || skills,
        collectibles: techInput.collectibles || collectibles,
        upgradedCollectibles: new Set(techInput.upgradedCollectibles || payload.upgradedCollectibles || []),
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
      venato: activeSurvivor === 'Venato' || payload.venato === true,
      stats,
      collectibles,
      items,
      settings,
      gameMode,
      eeSkills: payload.eeSkills,
      eeOmnipower: payload.eeOmnipower,
    });
    preFinalizeStats = (conditioned && conditioned.stats) || stats;
    direct = directFunction(preFinalizeStats, directSeed);
    finalStats = finalizeStatsFunction({ evolvePassives, gameMode, stats: preFinalizeStats, settings });
    formulaModules = [13024, 24804, 88426, 67727];
    formulaOrder = ['13024.T', '24804.zP', '88426.y', '24804.IE', '67727.f'];
  }

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
    account_assembly_exact: accountAssemblyExact,
    account_assembly_modules: accountAssemblyExact ? ACCOUNT_ASSEMBLY_MODULES : [],
    account_context: clonePlain(accountContext),
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
