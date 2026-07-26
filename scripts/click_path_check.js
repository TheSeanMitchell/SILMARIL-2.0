/* ============================================================================
   SILMARIL — CLICK PATH CHECK (7.1.3)

   WHY THIS FILE EXISTS. On 2026-07-26 every graph link on the dashboard went
   dead. The cause was one missing variable declaration in silmaril_chart.js:
   a patch appended PRICE_TRUTH.json to the boot fetch list but never declared
   its binding, so boot() threw ReferenceError on page load, READY never became
   true, and every ticker click on every panel silently did nothing.

   It shipped because the checks were (a) a syntax parse and (b) grepping the
   source for expected strings. Both passed. Neither RAN the code. An undeclared
   identifier is valid syntax and only fails at runtime, and a grep can only ever
   prove that text exists — never that a click opens a chart.

   That is the honest reason the same things kept breaking: the tripwires were
   testing the source, not the behaviour. This harness runs the real
   silmaril_chart.js against the real data store in a minimal DOM and asserts the
   behaviour the operator actually performs:

     1. boot() resolves and READY becomes true            (catches the outage above)
     2. window.openChart(sym) opens a chart               ('.tick' / data-sym path)
     3. window.openChart(sym, entry, mark) opens a chart  (sleeve + live-position path)
     4. a name WITH tape renders a real svg with layers
     5. a name with NO tape degrades gracefully, never throws
     6. no console errors were emitted during any of it

   Run: node scripts/click_path_check.js [docs]        exit 0 = pass, 1 = fail
   Also invoked by selftest T116 so it can never be forgotten.
   ============================================================================ */
'use strict';
const fs = require('fs');
const path = require('path');

const DOCS = path.resolve(process.argv[2] || 'docs');
const CHART = path.join(DOCS, 'silmaril_chart.js');

const errors = [];
const results = [];
function ok(name, pass, detail) {
  results.push({ name, pass: !!pass, detail: detail || '' });
}

/* ── a DOM just real enough to boot a chart ─────────────────────────────────── */
function makeEl(tag) {
  const el = {
    tagName: (tag || 'div').toUpperCase(), style: {}, dataset: {}, children: [],
    childNodes: [], firstChild: null, _html: '', textContent: '',
    classList: { _s: {}, contains(c) { return !!this._s[c]; }, add(c) { this._s[c] = 1; } },
    offsetHeight: 240, clientWidth: 820, clientHeight: 430,
    appendChild(c) { this.children.push(c); return c; },
    removeChild() {}, replaceChild() {}, setAttribute() {}, getAttribute() { return null; },
    addEventListener() {}, removeEventListener() {}, closest() { return null; },
    querySelector() { return makeEl('div'); }, querySelectorAll() { return []; },
    getBoundingClientRect() { return { left: 0, top: 0, width: 820, height: 430 }; },
    focus() {}, click() {},
  };
  Object.defineProperty(el, 'innerHTML', {
    get() { return this._html; },
    set(v) { this._html = String(v == null ? '' : v); },
  });
  return el;
}

function installDom() {
  const g = global;
  g.window = g;
  g.__silmarilChartBooted = false;
  const body = makeEl('body');
  g.document = {
    readyState: 'complete',
    body,
    addEventListener() {}, removeEventListener() {},
    createElement: makeEl, createTextNode: () => makeEl('text'),
    getElementById: () => makeEl('div'),
    querySelector: () => makeEl('div'),
    querySelectorAll: () => [],
  };
  g.addEventListener = () => {};
  g.removeEventListener = () => {};
  g.matchMedia = () => ({ matches: false, addListener() {}, addEventListener() {} });
  g.innerWidth = 1280; g.innerHeight = 860;
  g.location = { href: 'file://local/', hash: '' };
  try { g.navigator = { userAgent: 'click-path-check' }; } catch (e) { /* node 22 exposes navigator as a getter */ }
  const realTimeout = setTimeout;
  g.setTimeout = (fn) => realTimeout(fn, 0);
  g.setInterval = () => 0;
  g.clearInterval = () => {};
  g.requestAnimationFrame = (fn) => realTimeout(fn, 0);
  g.console = Object.assign({}, console, {
    error: (...a) => { errors.push(a.map(String).join(' ')); },
    warn: () => {},
  });
  g.fetch = (p) => {
    const f = path.join(DOCS, String(p).split('?')[0]);
    return Promise.resolve({
      ok: fs.existsSync(f),
      json: () => new Promise((res, rej) => {
        try { res(JSON.parse(fs.readFileSync(f, 'utf8'))); } catch (e) { rej(e); }
      }),
    });
  };
}

/* ── pick real symbols out of the store: one with tape, one without ─────────── */
function pickSymbols() {
  let withTape = null;
  try {
    const ps = JSON.parse(fs.readFileSync(path.join(DOCS, 'data/price_samples.json'), 'utf8'));
    const s = ps.samples || {};
    const cands = Object.keys(s).filter((k) => (s[k] || []).length > 40);
    cands.sort((a, b) => (s[b] || []).length - (s[a] || []).length);
    withTape = cands[0] || null;
  } catch (e) { /* store may be absent on a fresh tree */ }
  return { withTape, withoutTape: 'ZZZNOTAREALSYMBOL-USD' };
}

(function main() {
  if (!fs.existsSync(CHART)) {
    console.log('FAIL  silmaril_chart.js not found at ' + CHART);
    process.exit(1);
  }
  installDom();
  const src = fs.readFileSync(CHART, 'utf8');

  // expose internals for assertions without altering behaviour
  const probe = "window.__cpc = { chartSVG: chartSVG, boot: boot, canon: canon, ready: function () { return READY; } };\n  ";
  // Anchor on an export present in every build so this harness can also judge OLD files —
  // the point is to catch a regression, which means it must run against the regressed version.
  const anchor = 'window.SilmarilChart = {';
  if (src.indexOf(anchor) < 0) {
    console.log('FAIL  chart module exposes no SilmarilChart export to probe');
    process.exit(1);
  }
  const patched = src.replace(anchor, probe + anchor);

  try {
    new Function(patched)();
  } catch (e) {
    console.log('FAIL  module threw at load: ' + e.message);
    process.exit(1);
  }

  const T = window.__cpc;
  if (!T || typeof T.boot !== 'function') {
    console.log('FAIL  chart module did not expose its boot function');
    process.exit(1);
  }

  T.boot().then(() => {
    const { withTape, withoutTape } = pickSymbols();

    ok('boot() resolves and READY becomes true', T.ready() === true,
       'this is the exact assertion the 2026-07-26 outage would have failed');

    ok('window.openChart is the documented entry point', typeof window.openChart === 'function');

    // 2 — plain click path (.tick / data-sym elements call openChart(sym))
    let threw = null;
    try { window.openChart(withTape || 'BTC-USD'); } catch (e) { threw = e; }
    ok('openChart(sym) does not throw', !threw, threw ? threw.message : '');

    // 3 — sleeve + live-position path: openChart(sym, entry, mark)
    threw = null;
    try { window.openChart(withTape || 'BTC-USD', 0.0000123, 0.0000130); } catch (e) { threw = e; }
    ok('openChart(sym, entry, mark) does not throw (sleeve OPEN POSITIONS link)', !threw,
       threw ? threw.message : '');

    // 4 — a name with tape must produce a real chart with layers
    let c = null; threw = null;
    try { c = T.chartSVG(withTape || 'BTC-USD', '1W', 820, 430, false); } catch (e) { threw = e; }
    const hasSvg = !!(c && c.svg && c.svg.indexOf('<svg') === 0);
    ok('a name WITH tape renders an svg', hasSvg && !threw,
       threw ? threw.message : (withTape ? 'symbol=' + withTape : 'no tape in store'));
    ok('that chart carries stats and structure', !!(c && c.st && c.sw),
       hasSvg ? '' : 'skipped: no svg');

    // 5 — a name with NO tape must degrade, never throw
    let c2 = null; threw = null;
    try { c2 = T.chartSVG(withoutTape, '1W', 820, 430, false); } catch (e) { threw = e; }
    ok('a name with NO tape degrades without throwing', !threw && !!c2,
       threw ? threw.message : '');
    ok('the empty result is shape-complete (st present as null, not missing)',
       !!c2 && Object.prototype.hasOwnProperty.call(c2, 'st') && c2.st === null,
       'head()/statsPanel() read c.st — a missing key is how the modal died silently');

    // 6 — nothing may have gone to console.error along the way
    ok('no console errors during boot or any click', errors.length === 0,
       errors.slice(0, 2).join(' | '));

    let failed = 0;
    for (const r of results) {
      if (!r.pass) failed++;
      console.log((r.pass ? 'PASS  ' : 'FAIL  ') + r.name + (r.detail ? '  \u2014 ' + r.detail : ''));
    }
    console.log('\n== CLICK PATH: ' + (results.length - failed) + ' pass \u00b7 ' + failed + ' fail ==');
    process.exit(failed ? 1 : 0);
  }).catch((e) => {
    console.log('FAIL  boot() rejected: ' + (e && e.message ? e.message : e));
    console.log('\n== CLICK PATH: 0 pass \u00b7 1 fail ==');
    process.exit(1);
  });
})();
