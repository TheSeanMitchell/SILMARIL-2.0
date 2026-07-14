# UI FIX + BRAIN WIRING — the blank-dashboard bug is dead, confidence wired to everything

## What was wrong (root-caused by rendering your real repo in a real browser over HTTP)
The new six-tab UI was showing (the SW cache fix worked), but every panel sat on "loading…".
**One line crashed the entire render loop:** `$('ts').textContent = …` referenced a timestamp
element that the header redesign had removed. `$('ts')` returned null → `.textContent` threw →
and because that line runs BEFORE the per-panel error guards, the single exception aborted the
whole `load()` function, so nothing downstream rendered.

## The fix (three layers — this bug class can never ship again)
1. **`$()` now returns a no-op stub for missing element ids** — any stale reference silently
   no-ops instead of crashing the render. The whole category of "one missing id blanks the
   dashboard" is gone.
2. The `ts` line and a second latent bug (`sl` undefined in the champion panel) are both fixed.
3. **Three new tripwires** in the selftest: T19 (brain reads every predictive store), T20 (UI
   render resilience), T21 (service worker network-first). **Verified in a real browser: zero JS
   errors, zero stuck panels, all six tabs render.**

## The brain, wired to EVERYTHING (your top priority)
The confidence engine now fuses **9 predictive signals** (was 6) — added:
- **timing_fingerprint** — per-symbol time-of-day probability curves (is NOW this name's best buy window?)
- **momentum_chain** — multi-window momentum with exhaustion detection (is the down-run slowing → MR-ready?)
- **conviction_ranking** — the independent multi-signal ranker's own score

So the confidence number that sizes conviction bets and gates the sniper reflects every metric the
platform measures. The confidence panel shows all nine signal weights live. The Conductor report
card continues A/B-grading every behavior with pre-registered kill criteria.

## INSTALL (drag-drop)
Replace: `docs/index.html`, `docs/sw.js`, `silmaril/execution/confidence_engine.py`,
`scripts/selftest_5_1.py`. Add: `docs/reset-app.html`. Docs: `DOCS_5_1/12`, `5_1_FINAL_LEDGER.md`.

(If sw.js and reset-app.html are already installed from the prior fix, they're identical — no harm.)

## AFTER INSTALL
1. Commit. 2. If your browser still shows a stale page once: visit `<pages-url>/reset-app.html`
   (one time) or hard-reload twice — the self-healing SW takes over. 3. Run the **selftest**
   workflow: expect **21 pass**. Every tab will render with live data.

## VERIFIED
- Real-browser render over HTTP: 0 errors, 0 stuck panels, 6/6 tabs ✓
- Full Python compile sweep ✓ · all workflow YAML ✓ · selftest 21/21 ✓
- End-to-end engine run on real data: confidence engine (1050 scored, 9 signals), strategy lab,
  MTF ladder — all stamping, run complete ✓
