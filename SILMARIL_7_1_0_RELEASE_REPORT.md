# SILMARIL 7.1.0 — "ONE WRITER · ONE KEY · ONE LADDER"
### Every July 25 complaint root-caused with receipts, fixed at the architecture level, and tripwired.

**Battery: 107/107 green on BOTH the full tree and a fresh post-wipe tree** (T1–T111; six new tripwires guard everything in this package).
**Reset required: NO.** Every fix is code-side. Your open positions, sleeve records, fingerprint maturity and the 90-day clock all survive. **Do not reset** — a reset would destroy exactly the forward evidence this release exists to protect.

---

## THE THREE LAWS THIS RELEASE INSTALLS

### 1 · THE ONE WRITER LAW — why yesterday-vs-today went "night and day" with no code change

**The incident, with receipts.** daily.yml (every 10 min, 12–13 min runtime), hourly.yml (:07) and analytics.yml (3×/day) ALL ran `python -m silmaril --live` — three concurrent live trade cycles on three separate checkouts. The 7.0.3 serial lane lock has a 600-second "fairness cap": because the daily lane is almost always in progress, hourly and analytics hit the cap and **"proceeded anyway" nearly every single time**. Then each lane's push step ran `git rebase -X theirs origin/main` — which resolves every same-file conflict by **keeping the pushing lane's copy and erasing the other lane's version** of the books, the sleeves, and the ledgers.

That one mechanism explains, at once: trades that vanished · sleeve marks frozen at entry→entry +0.00% (a stale checkout republished pre-mark state over the fresh one) · "fixed" panels re-showing pre-fix output (stale checkouts re-pushed old builder output over the fix) · and the night-and-day performance swing with zero code change. It was never the market and never the strategies — it was three writers overwriting each other's memory.

**The fix is architectural, not another lock:** exactly ONE scheduled lane may write state, ever.

- **daily.yml** now carries every cadence itself, from one clock, one checkout, one commit:
  - every 10 min → FAST pulse (ingest + trade + live views)
  - top of each hour (:0x tick) → FULL pass (hourly-class brains + sanitize + brag sheet + **the new source overlay**)
  - 07/11/23 UTC :2x tick → deep analytics suite + data diet
  - 08 UTC :1x tick → nightly universe backfill
  - 09 UTC :2x tick → venue-universe listings refresh
- **hourly.yml** is retired to a notice-only lane: no cron, `contents: read`, no steps that write. Dispatching it just tells you where the work went.
- **analytics.yml / backfill_universe.yml / venue_universe.yml**: crons removed; manual dispatch kept (analytics manual runs the read-only suite only, never `--live`).
- **selftest.yml** (read-only) and **weekly_backup.yml** (disjoint archive paths) keep their crons — they cannot collide with the writer. verify_install.yml's weekly cron is grep-only, also safe.

Direct answers to your July 24 questions: *"If Daily Runs are running alongside hourly runs, isn't that going to corrupt files?"* — yes, and it did, exactly as you feared; they can no longer coexist because only one of them is scheduled. *"Is a DAILY RUN running at the same time as Deep Analytics going to cause an issue?"* — it was the same issue; the deep pass now runs inside the daily lane after the live cycle, on the same checkout.

**Tripwire T110:** parses every workflow; exactly one scheduled lane may invoke the live cycle; the four folded lanes must have no cron; hourly must contain no live invocation and no push.

### 2 · THE ONE-KEY LAW — the DOGEUSDT disease, cured at the loader

**The incident, with receipts.** `load_all_samples()` raw-merged price_samples.json (canonical `DOGE-USD`) with ccxt_samples.json (`DOGEUSDT`), so the SAME coin existed twice as two "different" assets. `_is_crypto` = `"USD" in sym`, so `DOGEUSDT` became a legal crypto-book candidate — and the book bought the spelling that every canonical-keyed consumer was blind to: the ticker modal found no chart, the sleeve mark-stamper missed keys (marks frozen at +0.00%), and the movers journal paraded dash-less REQUSDT/LMWRUSDT ghosts past the dedupe. The 7.0.2 canonical merge fixed this for FINGERPRINTS only (a local `_canon7`); the rest of the engine kept eating the raw merge.

**The fix:** new module `silmaril/execution/canon_keys.py` — ONE `canon()`, ONE loader, imported everywhere.

- `canonical_samples()` collapses every spelling (USDT/USDC/USD/slash-pairs) to `BASE-USD`, **unions history by timestamp** across spellings, and lets the primary tape win collisions — ccxt deepens the series, never overrides it. `paper_sim.load_all_samples`, `strategy_lab_abcd` (both its tape and its reach/trend/cost measurements) and the movers journal all load through it now.
- `canonicalize_positions()` runs at the top of every live cycle: any OPEN position or resting maker order already booked under a non-canonical key (your DOGEUSDT position) is **re-keyed to canonical** — qty and entry preserved, `migrated_from` stamped, every rename journaled to `CANON_MIGRATIONS.jsonl`. It is idempotent, flags (never blind-merges) a canonical twin already open in the same book, and **never rewrites closed-trade history**. Your frozen position becomes markable and exitable on the first post-install cycle instead of being force-flattened.
- Guard set `{USD, USDT, USDC, USO, USL, USOI}` — real dash-less assets containing "USD" are never re-keyed (the energy ETFs stay themselves).
- `docs/index.html` chart door: `drawChart()`'s pre-check used to look up ONE spelling and bail to "no intraday series" — every spelling is now tried via the same `altKeys` law before declaring a chart absent, and `__overlaySources` does the same per feed. **DOGEUSDT now opens onto DOGE-USD's full graph.**

**Tripwires T107 (loader union + primary-wins + canon truth table), T108 (position + maker-order migration, journaled, idempotent, history untouched), and T111's key-door half.**

### 3 · THE ARMING GATE — the pyramid's missing LICENSE

**The incident, with receipts.** The crypto book opened DOGEUSDT with ZERO sleeve closes since the wipe. Root cause is an honest conflict between two of your own directives: 7.0.4's `seed_immediately` ("books should start on our best sleeve immediately") handed a PROVISIONAL sleeve's **discipline** to the book — and nothing in `_run_side` distinguished discipline-seeding from **trade authorization**, so a book whose workshop had zero graded evidence traded anyway. The per-name maturity gate passed because tape evidence (price_samples) deliberately survives resets; the missing rung was a **book-level** license.

**The fix splits the two cleanly:**

- PROVISIONAL still seeds the hand immediately (your 7.0.4 ask, kept).
- A book may **OPEN** only when its own workshop shows `status == "PROMOTED"` — ≥3 REAL closed trades since the wipe with positive Δ-vs-null (your original pyramid law, restored). `sleeve_promotion.py` now publishes `arms_book` and `closes_needed` on every branch so the license is explicit in the store, not inferred.
- An UNARMED book still scans, marks, manages exits, feeds its candidate river to the sleeves (the dtrace fires before the block, so the workshop keeps learning), and **cancels its resting maker orders** — a limit placed before the law cannot fill around it.
- GEKKO/aggressive is exempt: it IS a probe, that's its job. The Master was already strict (`status != "PROMOTED"` → no funding) and is untouched.
- FIRST-TRADE READINESS now prints the truth: `🔒 OBSERVE — pyramid license: workshop must promote a sleeve (closes X/3)` — and a book carrying legacy positions while unarmed shows `⚠ UNARMED (managing exits only)`.
- Knob: `PARAM_CATALOG.arming_gate {mode: auto}` · KILL: `mode: "off"`.

**Order after any wipe is now enforced, not hoped:** sleeves trade first (ungated) → 3 real closes elect a PROMOTED sleeve → the book arms and adopts that discipline → the Master mirrors armed books. Bottom-up, exactly as you've specified ~30 times — now a gate, not a convention.

**Tripwire T106:** functional fixture proves PROVISIONAL→`arms_book:false` and PROMOTED→`true`; source asserts the gate blocks entries and cancels resting orders; UI assert proves the cockpit tells the truth.

---

## THE HONEST MOVERS JOURNAL — "99.7% of 399 movers missed" was three lies in one panel

Receipts: peaks were computed over the ENTIRE stored series (weeks of history, minutes after a wipe), dash-less spellings escaped a dashed-only dedupe, and unfillable ghosts (BRENT +41.8%, REQUSDT +38.3%, LMWRUSDT +37.1%) headlined the list AND inflated the missed%. Rewritten: peaks now come from the **last 48h of LIVE prints only** (daily-backfill candles excluded by the `T00:00:00` law), keys are canonical, and every unfillable name is **EXCLUDED with a named count** — `{stale_ghost, closed_market, too_thin, spike_suspect}` — never a row, never in the missed%. The dashboard renders those counts so an exclusion is visible, not silent. **Tripwire T109** (functional: a frozen ghost lands in `stale_ghost`, a 40%-pump-2.5-days-ago with a flat live window is not logged, a real 6% mover is).

## THE OUTSIDE WORLD — your multi-source overlay, finally real

Receipts: the "Everything Graph" traced our own four internal files over each other and called it cross-source; your ask — *"imports other graphs from other sites like Coinbase or Yahoo … overlay it with three sources … make sure the system is aware if there is a price difference"* — was still unmet. New module `silmaril/execution/source_overlay.py`, wired into the top-of-hour full pass:

- Scope = every open position (books + GEKKO + sleeves) ∪ recent trades ∪ top candidates, capped at 24 names, hard 75-second budget (knob `source_overlay {mode, max_symbols, budget_s, disagree_pct}` · KILL `mode:"off"`).
- Crypto → **Coinbase + Kraken** public OHLCV via ccxt; equities/ETFs → **Yahoo**; spot metals/energy (XAU, BRENT, WTI, NATGAS…) → their mapped Yahoo futures (GC=F, BZ=F, CL=F, NG=F).
- Writes `SOURCE_OVERLAY.json`; the Everything Graph draws each provider as its own tracing-paper line (own color, dashed, `⇡` legend) ON the price with all nine engine layers on top.
- The agreement verdict is **time-aligned**: our last live non-backfill print vs each provider's print nearest in time, ≤15 minutes apart — never last-vs-last from different moments. `AGREE / DISAGREE / UNVERIFIED / NO_EXTERNAL_SOURCE`, worst spread printed, disagreements listed in the store. An absent provider is an absent line — **nothing is ever synthesized**.

**Tripwire T111** (external feed drawn, exports on `window.SilmarilGraph`, aligned-spread present, no-synthetic honesty string, cli wiring).

## ONE MORE LATENT BUG THE FRESH-TREE BATTERY CAUGHT

`VENUE_UNIVERSE.json` was classed DERIVED in the store registry while the reset script deliberately preserves it (deleting the listings would make every close UNROUTABLE until the next 09:2x refresh) — so T53 called the preserved copy a stale lie on every fresh tree. It is a snapshot of the OUTSIDE world, exactly like price_samples: reclassed LEARNING in `store_registry.py`, with the incident documented in-line. Self-heals on the first post-install registry build; verified 107/107 on a genuinely reset tree.

---

## INSTALL (drag-and-drop, exact repo paths — complete files, no fragments)

| file in ZIP | goes to |
|---|---|
| `silmaril/cli.py` | `silmaril/cli.py` |
| `silmaril/execution/canon_keys.py` **(NEW)** | `silmaril/execution/` |
| `silmaril/execution/source_overlay.py` **(NEW)** | `silmaril/execution/` |
| `silmaril/execution/paper_sim.py` | `silmaril/execution/` |
| `silmaril/execution/sleeve_promotion.py` | `silmaril/execution/` |
| `silmaril/execution/opportunity_journal.py` | `silmaril/execution/` |
| `silmaril/execution/strategy_lab_abcd.py` | `silmaril/execution/` |
| `silmaril/execution/store_registry.py` | `silmaril/execution/` |
| `docs/index.html` | `docs/` |
| `docs/silmaril_graph.js` | `docs/` |
| `.github/workflows/daily.yml` | `.github/workflows/` |
| `.github/workflows/hourly.yml` | `.github/workflows/` |
| `.github/workflows/analytics.yml` | `.github/workflows/` |
| `.github/workflows/backfill_universe.yml` | `.github/workflows/` |
| `.github/workflows/venue_universe.yml` | `.github/workflows/` |
| `scripts/selftest_5_1.py` | `scripts/` |
| `SILMARIL_7_1_0_RELEASE_REPORT.md` | repo root |

Upload via GitHub web UI ("Add file → Upload files"), matching each folder path. All 17 files in one commit is fine. **Do NOT reset. Do NOT run genesis.** On the first cycles you should see: `CANON_MIGRATIONS.jsonl` appear with the DOGEUSDT re-key · readiness showing 🔒 pyramid-license states with closes X/3 · the movers journal shrink to real, live-window movers with excluded counts · and (top of the hour) `SOURCE_OVERLAY.json` land and outside-venue lines appear on held names' graphs.

## WHAT THIS RELEASE DOES NOT CLAIM

Release naming: this is release **7.1.0 of the 7.0 family** — the dashboard's `verNum 7.0` pin (guarded by T9) is deliberately unchanged.

The one honesty caveat, and it is the whole ballgame: **nothing here adds edge.** 7.1.0 makes the instrument stop lying to you — one writer, one key per asset, one earned ladder, peaks measured on windows that exist, prices checked against the outside world. The books still have essentially zero forward closed trades since the wipe, the arming gate will correctly keep them quiet until the sleeves earn 3 real closes each, and the 100-trade / 90-unbroken-day bar has not moved. A clean instrument is the precondition for a verdict, not the verdict.
