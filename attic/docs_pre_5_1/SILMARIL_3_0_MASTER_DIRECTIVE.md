# SILMARIL 3.0 — MASTER DIRECTIVE
*The single authoritative document. Everything before it is history; everything in the repo obeys this.*

## What this is
An autonomous four-quadrant paper-trading research engine (crypto · stock · metal · energy) feeding a
Master Account that funds only quadrants whose **confidence** (survivability + sample + win-rate + net)
clears a gate (default 90). It exists to answer one question with evidence: **is there exploitable edge,
per market, after real fees?** Nothing here is income until forward data says so.

## Hard invariants (violating any of these is a bug)
1. **No synthetic data, ever.** Modules that lack real data run in observe mode or defer.
2. **No timeouts.** Exits are target or heatshield floor only. The floor is deliberate — it is the only
   loss bound (WLD, Jul 1: the floor is what capped a collapse; the freeze, not the floor, made it −9.8%).
3. **Champions are elected by forward survivability on REAL trades** — never backtest window-dominance,
   never manually.
4. **Every book is independent**: own universe, own arena, own champion, own params (verified live:
   crypto=MR_patient_d3, stock=HOLD_d2_t5, metal=MR_d2_t2, energy=commodity default until elected).
5. **Nothing unproven influences a decision.** Every experimental signal (news, Dr. Strange, lifecycle,
   fingerprint-weighting) lives behind FEATURE_GATES.json in `observe` until its evidence ledger clears
   the promotion rule. News failed its earlier informal trials; it restarts from zero, honestly.
6. **Daily-backfill candles never touch intraday signals** (`"T00:00:00" not in t`).
7. **Every trade records its intent**: target/stop/expected/conviction/wager at entry; realized %, % of
   goal, best, left-on-table at exit. Dollars are display; **percent is truth**.

## The tuning surface (change behavior with ZERO code edits)
- **docs/data/PARAM_CATALOG.json** — the one tuning file: arena grid (280 MR + MOM strategies breeding
  hourly), knife veto threshold, per-book minimum post-fee take-home. Edit → commit → next cycle runs it.
- **docs/data/FEATURE_GATES.json** — per-signal mode (observe/shadow/live), evidence minimums, promotion
  rules. Flipping a gate by hand is allowed but the status file will say so.
- **docs/data/PROJECT_META.json** — the version label everywhere. One value.

## Operations
- **FAST/FULL split**: the 10-min cadence runs ingest+trade+truth-views only; heavy
  leaderboards/backtests/forensics run at the top of the hour (`SILMARIL_FAST` / `SILMARIL_ANALYTICS`).
  Permanent fix for daytime cycles ballooning past 10 minutes.
- **Market calendar** (`market_calendar.py`): equity books idle on weekends/NYSE holidays and know
  half-days; crypto runs 24/7. No wasted cron, no polluted equity data on dead days.
- **Engine Pulse**: marks health is on the dashboard every cycle. Exits and displays run on any fresh
  price (≤90 min); only NEW entries require the 2h warm-up. A silent freeze is now impossible — it shows
  as DEGRADED/STALLED in yellow/red instead of dead bars.
- **Falling-knife veto**: MR never buys a name down ≥6% over 6h with no bounce (tunable; validated on the
  exact WLD collapse that motivated it).
- **Wipe discipline**: `reset_internal_clean.py` wipes books, Master, decisions ledger; preserves price
  history and this file. Every reset restarts the observation clock. Wipe freely.

## Live-handoff readiness (the checklist the switch depends on)
| Requirement | Status |
|---|---|
| Exit policy identical to live intent (target/floor, no timeouts) | ✅ |
| Per-trade intent + outcome fully recorded | ✅ |
| Per-book champions live-wired | ✅ verified |
| Fee-realistic accounting (Binance.US chain modeled in Master) | ✅ |
| Order-type plan (maker limits for entry/target, stop-market floor) | ✅ documented |
| Confidence gate + decision ledger (why funded / why not) | ✅ every cycle |
| Forward survivability ≥ gate on ≥100 OOS trades | ⏳ **the only thing left — time** |
| Broker adapter for live keys | ⏳ build at flip time (deliberately last) |

## Open items (tracked, not forgotten)
Drop/Bounce possibility matrix (Excel, forensics centerpiece) · sub-percent grid naming upgrade ·
per-symbol adaptive tuning beyond conviction+knife · mobile UI pass · root-docs archive sweep at the
final audit · Pokémon sprite icons (gold-gem favicon shipped; sprites deferred).

*Version lives in PROJECT_META.json — flip to "3.0" at the final audit when you judge this directive met.*
