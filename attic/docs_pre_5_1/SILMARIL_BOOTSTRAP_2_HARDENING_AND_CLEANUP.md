# SILMARIL — BOOTSTRAP #2: REPO HARDENING, CLEANUP AUDIT & LEGACY SALVAGE

Companion to `SILMARIL_BOOTSTRAP_2_7.md`. That one is the mission/state brief; THIS one is the
"clean the house and check the wiring" brief — what to tidy, what to verify, what legacy value not to
throw away, and the order to do it in. A fresh Claude should read both, then ask for the live repo and
verify everything below against it (this audit was done on the June 29 ~5:15 AM copy; file STRUCTURE is
stable but confirm before deleting anything).

---

## A) REPO ROOT CLEANUP — what's clutter, what stays, what to verify

**The problem:** the repo root holds ~91 historical markdown/notes files (every `READ_ME_*`, `AUDIT_*`,
`MASTER_AUDIT_*`, `ROADMAP_*`, `STATUS_*`, `NARRATIVE*`, old `*_BOOTSTRAP*`, etc.). They're documentation
debris from every past update. None are imported by code.

**Shipped fix (reversible):** `scripts/cleanup_root.py` + `.github/workflows/cleanup_root.yml` (run from
Actions, type CLEAN). It MOVES those ~91 files into `attic/root_docs/` — nothing is deleted, so history is
preserved and recoverable. After it runs, the root keeps only: `README.md`, `FOUNDING_CHARTER.md`,
`ROADMAP_TO_BETA_1_0.md`, `SILMARIL_BOOTSTRAP_2_7.md` (add it to root), `requirements.txt`, `cli.py`,
`.gitignore`, plus the dirs `.github docs scripts silmaril learning attic`. Run it once; the root goes
from ~90 docs to a clean handful.

**Workflows are ALREADY clean.** Only 7 remain, all current: `daily.yml`, `reset_internal_clean.yml`,
`backfill_universe.yml`, `remap_keys.yml`, `cleanup_clutter.yml`, `compact_history.yml`,
`weekly_backup.yml`, plus the new `cleanup_root.yml`. The obsolete ones (backtest, diagnose, old resets,
alpaca, migrate, senate, stress_test, sweep_switch…) were already removed. Nothing to do here.

**VERIFY-THEN-REMOVE (do NOT auto-delete — confirm against the live repo first):**
- Root `execution/` (alpaca_paper.py, directive_consumer.py, leaned_in_router.py) and root `learning/`
  (bayesian_winrate.py) look like **legacy stray duplicates** — the live package imports `silmaril.
  execution.*`, and a grep found nothing importing top-level `execution`/`learning`. BUT the root
  `cli.py` might reference them. Action for fresh Claude: check whether root `cli.py` is used at all
  (`daily.yml` runs `python -m silmaril --live`, i.e. `silmaril/cli.py`, NOT root `cli.py`). If root
  `cli.py` is itself a stray, move it + root `execution/` + root `learning/` into `attic/legacy_strays/`.
  If anything live imports them, leave them and note it. Reversible move > delete.
- `learning/bayesian_winrate.py` — see Legacy Salvage (D); may be worth WIRING IN, not discarding.

---

## B) HARDENING / WIRING CHECKLIST — verify these are present & live in the real repo
(These fixes were delivered across the 2.6.1 session; the operator installed each, but a fresh Claude
should confirm them in the live repo because some post-date the audited copy.)

1. **Per-cycle key canonicalization.** `daily.yml` must contain a step `python scripts/remap_keys.py`
   AFTER the sanitize step. `remap_keys.py` canon()s `BASEUSD/BASEUSDT/BASE/USD/BASE-USDT → BASE-USD`,
   merging. Without this, graphs silently break on the next ingest. CONFIRM the step exists.
2. **Intraday-only backtests.** GREP for `"T00:00:00"` in `paper_sim.py` (`_marks_from_samples` AND
   `backtest_through_sim`), `strategy_lab.py` (both series builds in `run_leaderboard`), and
   `capital_router.py`. Every series that feeds a SIGNAL or BACKTEST must exclude daily-backfill candles.
   If any backtest is missing it, it will report ~-5%/trade on 50k daily-candle trades — the tell.
3. **Warmup gate.** `_marks_from_samples` must require ≥24 recent intraday points spanning ≥2h within a
   6h window before a coin can signal. Confirms no cold-start trades; makes stocks safe at the open.
4. **Freshness/market-hours gate.** `fresh_ok`: stocks only trade weekday ~13:30–20:00 UTC; every book
   needs ≥3 distinct values in the recent window (stale-oscillation guard).
5. **HEATSHIELD.** `paper_sim.py` has `HEATSHIELD=True`, `HEATSHIELD_FLOOR=0.05`, applied as
   `eff_stop=max(stop_,FLOOR)` in the exit logic; `heatshield_whatif()` writes `HEATSHIELD.json`;
   `daily.yml` runs it each cycle; dashboard shows the panel.
6. **Reset preserves graphs.** `reset_internal_clean.py` wipes books + Master + snapshots but PRESERVES
   `price_samples.json` and favicons.
7. **Master sync.** `docs/index.html`: both the gold card (`renderMasterCard`) and the forensics panel
   (`renderMaster`) lead with `live_equity`; the forensics panel shows the gross→net-spendable fee chain.
8. **Render isolation.** All dashboard renders run through `safe(fn,name)` so one failure can't blank the
   page. Preserve this when adding panels.
9. **Compile/lint gate before shipping.** `python -m py_compile` every .py you touch; `node --check` on
   extracted `<script>` blocks of `index.html` and on `silmaril_chart.js`. Do this every time.

**Suggested one-shot wiring audit a fresh Claude can run on the live repo:**
`python -m py_compile $(git ls-files 'silmaril/**/*.py')` then grep the items above, then
`python -c "from silmaril.execution.strategy_lab import run_leaderboard; print(run_leaderboard('docs/data')['leaderboard'][:3])"`
and confirm trades are realistic intraday counts (tens), not tens of thousands.

---

## C) FEE / RUNTIME / DATA SAFEGUARDS to keep an eye on
- **Fees:** crypto round-trip ~54bps in the conservative model; Binance.US ~0.10% flat keeps the most.
  Master figures are net-of-fees; quadrant "realized" may be sim-gross — keep that labeled honestly.
- **Runtime:** the cycle was driven under ~9 min by parallelizing news fetch (ThreadPoolExecutor) and
  gating heavy analytics to top-of-hour (minute-of-hour checks in `daily.yml`). If runtime creeps up
  (universe=600, OHLCV is one sequential call per coin), parallelize the ccxt OHLCV fetch or trim TOP_N —
  do NOT cross the cron budget.
- **Backfill is GRAPHS-ONLY** and is one sequential ccxt/yfinance call per symbol; never let it block the
  trading path, and never let its daily candles into a signal/backtest (see B2).
- **No synthetic data, ever.** Every number traces to real data.

---

## D) LEGACY SALVAGE — value from older versions NOT to leave behind
1. **Dr. Strange projection** (`dr_strange` in chart overlays / engine `expected_move_pct`). A relic that
   MAY have signal. 2.7: audit its projections vs actual outcomes over the clean week; keep/fix/cut.
2. **Kraken modules** (`ingestion/kraken_spread.py`, `execution/kraken_mirror.py`) — still imported by
   `cli.py` (lines ~2324/2332). They re-price internal trades at real Kraken spread (a reality check).
   Decision for 2.7: either keep them as a fee-reality cross-check, or unwire from `cli.py` THEN delete.
   Do not delete while imported.
3. **Alpaca paper modules** (`execution/alpaca_paper.py`, imported at `cli.py` line 163) — the old live-ish
   paper bridge; no signals since ~June 16. Either build a dedicated Alpaca-only pristine wipe + one retry,
   or unwire + remove. Operator leans toward gutting unless it earns its keep. Unwire before deleting.
4. **`learning/bayesian_winrate.py`** — a Bayesian win-rate estimator. Likely valuable for governance
   (confidence calibration feeding the Master's confidence knob). 2.7: verify if it's wired into decisions;
   if not, consider wiring it into the conviction/confidence path.
5. **Authority engine** (Google-News RSS via feedparser) — research division ONLY, must NEVER trade.
   Keep it sandboxed from execution.
6. **`attic/` and `attic/root_docs/`** — the historical record. Don't purge; it's the project's memory and
   has prior rationale a fresh Claude may need.

---

## E) 2.7 WORK ORDER (prioritized; all need the clean week's real data)
1. Run the clean week. Read ALL-QUADRANTS vs MASTER-ONLY side-by-side. Does the Master survive fees with
   fewer, sharper trades? This is the verdict everything else waits on.
2. **Target-at-entry recording** in the sim (store target/stop/expected-move on each trade at entry) →
   unlocks honest "% of goal hit" and fixes SESSION ANATOMY's over-optimistic "left on table."
3. **Master tuning knobs** as single decimal params: confidence gate (default ~90.0), HEATSHIELD floor,
   wager size — tuned against the week's real performance, not blind.
4. **Dr. Strange audit** (D1) against real outcomes.
5. **Strategy-wiring audit:** confirm fingerprints / peak-rhythm / heat tolerance / repeat-striking proven
   names (MKR) actually FEED live decisions; wire `bayesian_winrate` into confidence if useful.
6. **Metals/energy activation** once feeds populate (tuned thresholds + champion; not a new signal).
7. **Governance loop → 10/10:** prove decisions CHANGE from outcomes (learn→teach→adjust), not just log.
8. **Make the bot-handoff real** (the SETTINGS easter egg + the confidence/wager knobs) for an eventual
   tiny live test — see Beta gate in bootstrap #1.

---

## F) STANDING REMINDER (carry it every session)
This is a dress rehearsal. The edge is small, positive-before-fees, and unproven over time. Never help
push real money — especially money the operator needs to live — into it before it earns clean over a real
window. Build honestly, verify, say what you didn't do, and protect the person first.
