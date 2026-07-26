# SILMARIL 7.1.3 — "THE CLICK PATH" · the graphs are back, and the reason this kept happening

**Battery: 112/112 green** on the full tree, a genuinely reset tree, and a simulated install over your 12:40 AM backup. **No reset. 2 files + 1 new script.**

---

## WHAT BROKE, EXACTLY

One missing variable. My 7.1.2 patch appended `PRICE_TRUTH.json` to the boot fetch list in `docs/silmaril_chart.js` but the companion edit that declares its binding **silently failed to apply** (my search string didn't match the real line, and I never checked). The result:

```js
]).then(function (r) {
  var ps = r[0], ... so = r[12];        // ← r[13] fetched, never bound
  ...
  if (pt && pt.by_symbol) { ... }       // ← ReferenceError: pt is not defined
```

`boot()` threw on every page load → `READY` never became true → **every ticker click on every panel did nothing.** Not just sleeves: the whole dashboard's chart system, dead from one undeclared identifier. Your SHIB-USD link was the symptom, not the scope.

---

## WHY THIS KEPT HAPPENING — the real answer

You asked why we keep fixing the same things. Here is the honest mechanism, and it isn't bad luck.

**My checks tested the source, not the behaviour.** For every chart change I ran two things: a syntax parse (`new Function(src)`) and source greps (`"PRICE_TRUTH.json" in gjs`). Both passed on the broken file. They had to — **an undeclared identifier is valid JavaScript and fails only at runtime**, and a grep can prove that text exists but never that a click opens a chart. Your battery reported **111 pass · 0 fail** while the entire chart system was down. A green board over a broken product is worse than a red one, because it stops you looking.

The pattern across the last four releases is the same shape every time:
- **7.1.0** — I instrumented `silmaril_graph.js` and `drawChart()`, neither of which your clicks reach. Verified by grep. Shipped broken.
- **7.1.1** — Fixed the right file. This time I *did* execute it headlessly, and it worked.
- **7.1.2** — Patched that same file again and reverted to grep-only verification. Shipped an outage.

So the fix that matters in this release is not the missing `var`. It is that the verification now runs the code.

---

## THE DURABLE FIX: `scripts/click_path_check.js` + tripwire T116

A harness that boots the real `silmaril_chart.js` against your real data store in a minimal DOM and asserts the behaviour **you actually perform**:

1. `boot()` resolves and `READY` becomes true ← *the exact assertion this outage fails*
2. `openChart(sym)` opens a chart — the `.tick` / `data-sym` path
3. `openChart(sym, entry, mark)` opens a chart — the sleeve OPEN POSITIONS link and the live-positions row
4. a name with tape renders a real SVG carrying stats and structure
5. a name with no tape degrades gracefully instead of throwing
6. nothing reached `console.error` during any of it

**Proven to catch this regression, not just described as catching it.** Run against the broken file it shipped as:

```
FAIL  boot() rejected: pt is not defined
== CLICK PATH: 0 pass · 1 fail ==
```

and against the fix: `9 pass · 0 fail`. A regression test that cannot reproduce the regression is decoration. When `node` isn't available it degrades to a static arity check (every store fetched must be bound) and says so rather than passing quietly.

I also ran the same runtime treatment over `silmaril_graph.js` — `draw()` completes clean, zero console errors — so this bug class isn't hiding in the other file I've touched.

---

## THREE MORE HARDENINGS, SO ONE LINE CAN'T DO THIS AGAIN

1. **Fail-soft boot.** Store parsing is now individually guarded and the promise has a `.catch`. A missing, malformed, or not-yet-generated store costs its own layer and nothing else; `READY` is set regardless. The price line always survives. Previously the wiring was all-or-nothing — which is why one bad `var` took out everything.
2. **`chartSVG` always returns a shape-complete object.** The no-tape branch used to return `{svg}` only, so `head()` and `statsPanel()` threw on `c.st` and took the modal down silently. It now returns `st: null` explicitly, and both functions handle it.
3. **`draw()` shows its errors.** A thrown render used to leave an empty modal that looked exactly like "nothing happened." It now prints the error in the panel with a note that the data is fine and it's a rendering fault — a visible error is debuggable; a silent one cost you a night.
4. **`openChart` honours its full contract.** index.html renders tickers three different ways and two of them call `openChart(sym, entry, mark)`. My override took only `sym`, so a sleeve position lost its ENTRY and MARK lines. It now accepts and uses them for positions the funded books don't carry, and never throws into its caller.

---

## INSTALL (3 files, drag-and-drop)

| file | path |
|---|---|
| `docs/silmaril_chart.js` | `docs/` |
| `scripts/click_path_check.js` **(NEW)** | `scripts/` |
| `scripts/selftest_5_1.py` | `scripts/` (adds T116) |
| `SILMARIL_7_1_3_RELEASE_REPORT.md` | repo root |

Hard-refresh (Ctrl/Cmd+Shift+R) after the Pages deploy — this is client-side, so the graphs come back on the very next click. Your 7.1.2 engine work (price truth, the scale guard, the arena fixes) is untouched and already running.

You can also check it yourself any time, without waiting for me: **Actions → Selftest**, or locally `node scripts/click_path_check.js docs`.

## THE HONESTY CAVEAT

This release restores function and closes a verification hole; it adds no capability and no edge. And it is worth stating plainly: three of the last four chart releases were broken on arrival because I verified text instead of behaviour. The tripwire count went from 111 to 112, but the meaningful change is that one of them now executes the thing you do with your mouse.
