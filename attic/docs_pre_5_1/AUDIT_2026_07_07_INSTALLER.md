# AUDIT — 2026-07-07 — SILMARIL 5.0 INSTALLER PASS
### Read against the July-7 8:30 AM full backup (the base this ZIP patches). Pairs with `SILMARIL_5_0_BACKBONE.md` / `.xml`.

Method: unzip the operator's final 4.0 backup → verify it was pre-patch → read every file
before editing → patch by exact-anchor (each anchor asserted to appear exactly once) →
`py_compile` + `node --check` + YAML/JSON validation → smoke-run every new module against the
real `docs/data` stores. Nothing shipped that did not compile and run here.

---

## 1. WHAT THE 4.0 MACHINE HAD (verified present, left untouched)

- 316-strategy arena; cadence-proof warmup knobs (`min_points 8`, `min_span_h 1.5`).
- GEKKO aggressive book (`aggressive_book` knob) — Master-isolated, first position on first cycle.
- June-30 regime overrides (SIDEWAYS/UPTREND 2% entries) present on the crypto book.
- `regime_accuracy.py` + `trade_quality.py` wired into the cycle; `run_lock` (30-min stale
  reclaim); `atomic_io.write_json_atomic` across the state writers; the `"T00:00:00"` backfill
  filter in the sim; `remap_keys` + `*/10` fallback cron in `daily.yml`.
- The champion `hold → max_hold_min` exit-clock fix (STEP_MIN 11.0) — the sim consumes live
  params correctly.

The 4.0 layer is sound. Its problem was never features — it is **starved for forward evidence**,
and it had three specific honesty/plumbing defects plus the workflow-cadence issue.

---

## 2. DEFECTS FOUND — and the exact fix shipped

### D1 — Cold-start champion dishonesty *(the issue the operator named directly)*
`champion.py` elected an incumbent after a wipe and presented it identically to an
evidence-earned champion. `MR_patient_d3` showed as champion with survivability `—/100` and zero
forward trades, implying a validation that had not happened.
**Fix:** every election now stamps `provisional` (true when the incumbent holds without qualifying
forward evidence) and `evidence_basis`. The dashboard renders a red **PROVISIONAL** badge and
states in plain words that the champion rotates the moment any strategy books its minimum live
trades (Law 9). Smoke: current champion correctly flagged `provisional: True`.

### D2 — Champion rotation was hard-coded *(blocks "exploit rotation on a faster scale")*
The anti-flip-flop gates (`CHAMPION_MIN_TRADES = 5`, `SURV_MARGIN = 15`) were constants; tuning
rotation speed meant editing code.
**Fix:** new `PARAM_CATALOG.champion_rotation {min_trades, switch_margin}` feeds those gates at
runtime. Defaults reproduce 2.18 behavior exactly. The election already runs every cycle for all
books — speed is now a dial. Research-OS **Q002** ("does faster rotation beat sticky on realized
P&L?") accrues the evidence that tells you how far to turn it.

### D3 — Tier thresholds had drifted
`champion_validation._tier` had slid to `8 / 15 / 30`, disagreeing with the canonical ladder the
dashboard and doctrine use.
**Fix:** restored to **Sandbox → Incubation(10) → Candidate(25) → Production(50)** with a separate
`production_verified` flag at n≥100, so no consumer of the four tier names breaks.

### D4 — Concurrency was incomplete
Only 3 workflows carried the `silmaril-state` group; 6 state-mutating workflows
(`backfill_universe`, `remap_keys`, `reset_internal_clean`, `cleanup_clutter`, `cleanup_root`,
`weekly_backup`) could race the trade cycle's writers.
**Fix:** all six joined the group (`cancel-in-progress: false`).

### D5 — The 15–20-minute pulse *(the long-standing cadence blocker)*
`daily.yml` ran a minute-branch that fired the FULL analytics build at the top of every hour on
the same 10-minute lane as trading, so one-in-six cycles ran 15–20 min and no true 10-minute
cadence was possible. (`SILMARIL_ANALYTICS` was exported but never actually read by the code —
only `SILMARIL_FAST` gated anything — so the heavy top-of-hour run was pure tax.)
**Fix — the lane split that was asked for repeatedly:**
- `daily.yml` pulse is now **always** `SILMARIL_FAST=1` (ingest + trade + live views only).
- **NEW `hourly.yml`** (cron `:07`, off the congested top of hour) runs the heavy pass (full
  build + sanitize + brag sheet) behind the same `silmaril-state` lock.
- `analytics.yml` keeps the WIDE/deep 3×/day pass.
The 10-minute lane never carries a heavy step again; at most one pulse queues briefly once an hour.

### D6 — The lost click-through *(quadrant/master cards opened nothing)*
`openQuadrant()` referenced an **undefined `B`** in `const dtr=(B.decision_trace_live||[]);`,
throwing before the modal could render — the disconnect the operator saw. The same function also
assumed positions were a dict, while the live sim stores them as a **list**, and there was no card
for GEKKO (whose 3 open positions were invisible while the crypto card correctly showed 0).
**Fix:** corrected `B`→`b`; the positions renderer now handles list **or** dict and falls back to
the live sim object, so the modal can never again silently disagree with the engine; and a fifth
**🦎 GEKKO** card was added to the quadrant row and the modal name/colour maps.

---

## 3. WHAT WAS ADDED (Phase-A of the backbone — see PART 0.5 there for detail)

`bench_books.py` (Null Layer, Law 10) · `store_contracts.py` (schemas + producer/consumer
registry, Law 12) · `census.py` (universe roll-call + new-listing detector) · `utilization.py`
(Law 16) · `conductor_log.py` (Conductor rung C0) · `research_os.py` (Research OS v1 — the
Part-2 scientific-curiosity layer). All wired into `cli.py` behind per-module try/except, running
in both fast and full cycles, atomic writes, long-memory stores preserved across wipes.

---

## 4. SMOKE RESULTS (real `docs/data`, this machine)

```
BENCH   CASH/SPY/HODL/EQW all initialized & marking on the real feed
CENSUS  crypto 472 listed / 19.3% fresh · stock 1159 / 44.7% · metal 10 / 90% · energy 16 / 50%
UTILIZ  crypto DEPLOYED · GEKKO DEPLOYED · stock/metal/energy ARMED   (matches live positions)
CONDUC  C0 ledger writing; 1/300 toward the C1 gate
RESRCH  7 questions open · debt 298 obs · top auto-selected = GEKKO June-30 profile (7/35, real trades)
CHAMP   MR_patient_d3 · provisional: True · rotation gate {min_trades 5, switch_margin 15} live
CONTRA  ALL GREEN — 9 schemas honored, 11 contract rows, 0 red
JS      full-page node --check: OK    ·    Python: full-tree compileall: OK
```

## 5. KNOWN / DEFERRED (honest ledger)

- Census shows 1,657 "new ≤14d" on first run because the long-memory roster is seeding for the
  first time; it self-corrects to true new listings once the roster has a day of history.
- FX (Movement W2) is pre-registered at F0 but **blocked** on a real bid/ask practice feed — no
  synthetic spreads, and no leverage ever.
- Per-quadrant fully-independent workflows are deferred to Part VI on purpose: `silmaril-state`
  serializes state writes to keep ledgers race-free; session-gated per-book clocks already give
  per-quadrant timing. Parallel lanes wait for per-book store namespaces.
- Disaster recovery remains operator-managed (manual backups), per standing preference.

No architecture in this pass claims a post-cost edge exists. It claims the record can be believed —
and now the machine also knows, every cycle, whether the engine is beating a book that does nothing.
