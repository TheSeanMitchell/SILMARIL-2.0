# SILMARIL 5.0 — FINAL ENGINEERING AUDIT
### 2026-07-10 · run against the July-9 11:45 PM full backup (real data, real workflows, real stores)

This is the completion audit the 5.0 Master Directive ordered: verify every requested system
landed, is wired, is FED, and works — then fix what doesn't. Method: compile every file, parse
every workflow, smoke-run every 5.0 module against the real July-9 data, trace every dashboard
fetch to a real store, trace every store to a living writer, and reproduce failures offline
before touching anything.

---

## PART I — VERIFIED WORKING (no action needed)

| System | Evidence |
|---|---|
| Python integrity | `py_compile` clean across the entire tree (silmaril/, scripts/, root) |
| Workflow integrity | all 11 YAML files parse |
| 5.0 Phase-A spine | wired in `silmaril/cli.py` for BOTH lanes; all 7 modules (nulls, census, utilization, conductor, research-OS, contracts, invariants) smoke-run clean on real data |
| Store contracts | `ALL GREEN — every schema honored, every contract feedable` on live data |
| Invariants | `ALL GREEN — every safety invariant holds` |
| Null layer | BENCH_CASH/SPY/HODL/EQW accruing with real marks since 07-09 |
| Census + new-listing detector | live; long-memory roster seeded (1,657 first-seen entries settling) |
| Conductor C0 | 146/300 decisions logged toward the C1 gate |
| Research OS | 7/7 questions open, debt 273 obs, top priority Q003 (21/30) |
| Dashboard | **63 data fetches, 0 missing**; click-through restored (`openQuadrant`); GEKKO card live; PROVISIONAL badge wired; 5.0 header |
| The "+0.00% · 0 open" disconnect | engine store is correct (crypto: 17 open, +$158.67 realized at backup time); the new index.html reads `open_positions`/`return_pct` from the same store — the disconnect was the OLD deployed 3.0 page, already replaced |
| hold vs max_hold_min | fixed at the source: `champion.py` emits `live_params.max_hold_min = cfg["hold"] × STEP_MIN`; contract row GREEN into the sim exit clock |
| Champion cold-start | `provisional: true` post-wipe with honest reason + rotation trigger — Law 9 working as designed |
| Lane split | pulse = FAST only; heavy stages gated `_HOURLY` (45-min stamp) / `SILMARIL_DEEP`, WIDE + HOLD carry >24h self-heal |
| GEKKO isolation | `master_account.py` iterates exactly `("crypto","stock","metal","energy")` |
| Wipe safety | `reset_internal_clean` preserves the full long-memory list (EVOLUTION, RESEARCH_OS, CONDUCTOR, CENSUS_ROSTER, price_samples, …) |
| Data diet | `prune_data.py` trims intraday only, dailies untouched, ledgers capped — innocent (was a suspect) |
| Placeholder sweep | zero TODO / FIXME / PLACEHOLDER / NotImplementedError in engine code |

---

## PART II — BUG 1 (structural): the deep-analytics lane died silently on 2026-07-03

**Symptom found:** all five evidence labs — `DAILY_BASELINE.json`, `AGGRESSION_LADDER.json`,
`WEEKLY_SCORECARD.json`, `STOCK_PARITY_AUDIT.json`, `COMPLEXITY_LEDGER.json` — **did not exist**
on main, despite `analytics.yml` setting `SILMARIL_DEEP=1` three times a day since they shipped.
The suite outputs in the same lane froze at **2026-07-03 06:09 UTC** — the lane had been dead a
week and nothing said so.

**Kill chain (root cause):**
1. `analytics.yml`'s main step (`python -m silmaril --live`) had **no failure tolerance**. In
   GitHub Actions, a non-zero step skips **every** following step — suite, prune, **and commit**.
   One bad morning (a feed outage at the 07:20 slot, a broken wheel, any transient) and the whole
   pass produces nothing, forever, silently. Reproduced offline: a feed-starved run exits 1 at
   `No contexts built — aborting`.
2. The lane compounded its own risk: it alone ran an **unpinned Python 3.12** with a fallback
   `pip install` that omits half of requirements — while the two lanes proven every 10 minutes
   pin 3.11 with a cached, full install.
3. The five labs lived **only** in this lane, nested inside a fragile multi-level `try` — so its
   death starved them completely. The labs themselves are innocent: all five run clean on the
   real July-9 data in ~0.3 s combined.
4. Nothing monitored the lane. `store_contracts` watches stores, but none of the lab stores were
   registered, and the lane had no heartbeat.

This is the project's canonical failure mode — **wired-but-starved** — expressed at the workflow
layer instead of the field layer.

**Fixes shipped (four layers, belt and suspenders):**
- **Labs → spine.** The five labs now run in the every-cycle 5.0 spine in `silmaril/cli.py`,
  each individually wrapped (measured cost ~0.3 s; `daily_baseline` self-gates per date,
  `weekly_scorecard` upserts its ISO week, the rest are idempotent snapshots). The deep-lane
  copy is removed — single ownership.
- **Lane made unkillable.** `analytics.yml` v2: Python pinned 3.11 + pip cache (identical to the
  proven lanes), every step failure-tolerated, so a degraded pass still commits its partial
  artifacts.
- **Lane made visible.** `deep_heartbeat.json` stamped at start and finish of every deep run;
  registered in `store_contracts` with a 30 h freshness cap. A dead lane now flips a named RED
  on the dashboard within a day. (Seed file ships in this installer so the alarm is armed from
  minute one.)
- **Starvation made structurally visible.** `store_contracts` gained a `FRESHNESS_MAX_AGE_H`
  layer: a store that exists and passes shape but **stopped being written** now goes RED with
  its age named — this catches the class of failure the shape checks can't. All five lab stores
  + heartbeat + four spine stores registered.

**Verification:** full spine including labs runs in **2.44 s** on real data → contracts verdict
`ALL GREEN` with all five labs + heartbeat GREEN. Stale-lane test: heartbeat aged 31 h →
`RED | STALE: last write 31.0h ago (cap 30h) — its producing lane is dead`. Both transcripts in
the run log of this pass.

---

## PART III — BUG 2: `_broker_policy` was prose — Alpaca execution still fired every pulse

**Found:** the operator retired Alpaca for execution (2026-07-07 directive, pricing-only), and
`PARAM_CATALOG._broker_policy` said so — as a **string**. Nothing in code read it. The
three-account bridge (LEGACY / HARVEST_3 / HARVEST_5) still executed inside **every 10-minute
pulse**: dead-system round-trips riding the one lane that must stay light.

**Fix shipped:** `_broker_policy` is now a real object knob —
`{"execution_enabled": false, "pricing_ok": true, ...}` — and `silmaril/cli.py` gates the entire
bridge on it. Default (knob missing, or the old string form) = **disabled**, honest reason
stamped into `alpaca_state` and the run log. Re-arming is edit → commit → next cycle, no code.
Pricing paths are untouched.

**Verification:** gate unit-tested three ways — shipped knob → `False`; flipped knob → `True`;
legacy prose string → `False` (safe default).

---

## PART IV — DEAD CODE & DEAD DATA (removed per directive)

Verified dead by reference-tracing, then handled by the new one-click
**`Cleanup 5.0 Final`** workflow (Actions → type `CLEAN`; code is atticked reversibly, data is
deleted; full ledger prints in the run log):

- **Root `cli.py`** (3,246 lines) — zero references anywhere; live engine is
  `python -m silmaril`. → attic.
- **Root `execution/` and `learning/` dirs** — nothing imports them; live packages are under
  `silmaril/`. → attic.
- **`docs/data/_legacy_charts_disabled.json`** — 21 MB of disabled state. → delete.
- **Six Alpaca-era data files + `docs/data/archive/`** — no reader, and with execution gated
  off, no writer. → delete.
- The old `DELETE_THESE_LEGACY_FILES.txt` hand-list is superseded (it was also partially wrong —
  three of its entries were still being written 3×/day by the suite it predated).

Also: `requirements.txt` numpy duplicate removed.

## PART V — PUSH-RACE IMMUNITY (all lanes)

All lanes share the `silmaril-state` concurrency group, but a rebase-with-conflict on shared
generated JSON could still abort all three retries and drop a lane's commit. Every commit step
(daily, hourly, analytics, weekly-backup, both cleanups) now rebases with **`-X theirs`**:
brand-new files always survive, and a conflicted *generated* store defers to the newer copy on
main — the correct semantics for regenerated state. Output can no longer be silently discarded.

---

## DEFINITION-OF-DONE CHECK (5.0 directive)

- Every requested feature completed, improved, or removed **with documented justification** — this document.
- No partially-implemented subsystem — the five starved labs were the last; now spine-owned and monitored.
- No placeholder logic — sweep clean.
- No unwired feature — contracts + freshness make the claim enforceable, not aspirational.
- **Stable for extended unattended data collection** — every lane failure-tolerated, heartbeat-monitored, push-race-proof; the harvest can run without a babysitter.

One honest caveat, unchanged from every prior directive: none of this proves a post-cost edge
exists — it guarantees the record of whether one exists can be believed.
