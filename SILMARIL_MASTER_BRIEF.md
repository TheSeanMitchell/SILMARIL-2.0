# SILMARIL MASTER BRIEF — the one document that grounds any new conversation
*(cumulative as of 5.11 WRAP, 2026-07-13. If you read nothing else, read this.)*

## What this is
A deterministic paper-trading research platform: GitHub Actions is the engine, GitHub Pages
(docs/index.html) is the cockpit, drag-and-drop ZIP is the only install path. Five $10k paper
books (crypto · stock · metal · energy · GEKKO/aggressive) + strategy-free NULL benchmarks
(CASH · SPY · QQQ · HODL · EQW) + a Golden Master account that only ever WATCHES until the bar
is met. **Live-money bar (never moved): 100 out-of-sample trades surviving the gate across 90
unbroken days.** $100–300/day is an unproven hope, never income.

## The laws that matter most
1. **Realized P&L is the only truth.** Win rate and vibes are noise.
2. **Nothing is decoration** — every measured signal must have a consumer; the BRAIN tab's
   SIGNAL LEDGER lists all 15 stores and selftest T22 verifies each consumer against the real
   files. A decoration renders a red light and fails the battery.
3. **Every behavior change ships knob-gated with a pre-registered kill** on the Conductor
   report card. The card decides, not enthusiasm.
4. **Every bug fixed leaves a permanent tripwire** (battery is at 29).
5. **Data integrity outranks profit.** July-13 lesson: a stale feed alternating with the live
   feed painted sawtooth tapes and manufactured ~+3.4% "wins". Cure: two-print confirmation at
   the recorder (momentum_chain), oscillation quarantine at the reader (paper_sim), SUSPECT_OSC
   tagging at every SELL, and a verified-vs-suspect realized split on the report card.

## The decision stack (what fires each cycle)
census → freshness/warmup → **oscillation quarantine** → regime classifier (+15/30m fast band)
→ per-name entry: fingerprint fit, else **vol-native bar** (clamp(1.5·σ1h, class floor, regime
base)) → veto stack (funnel names every rejection) → conviction sizing × **compounder tilt**
(confidence card score) → position caps per book → exits: TAKE / limit / stop / regime-flip
harvest / fee-clear (never before the name's own **rhythm hold**, cycle×1.15).

## The Confidence Card (the baseball card — CONFIDENCE_CARDS.json, 1050 cards)
Per valuable: confidence + 9 signal parts, rhythm cycle + amplitude + last peak/trough,
**expected hold = its cycle**, σ1h + its own vol bar, fingerprint dip→bounce + reliability,
momentum windows, best buy/sell time-of-day, our live record on it, and **compounder_score =
conf × swing × cadence** (tilts live sizing; leaders board answers "what compounds daily").
Chart card ⇄ confidence card show the same facts (silmaril_chart.js reads window.__SIL_CARDS).

## The Strategy Lab (per industry × A–F)
Same entries, different discipline, $10k each, never Master-funded: A control (live behavior),
B cap-5, C full discipline, D sniper (conf-gated ≤3), **E ADAPTIVE STRIKER** (2 slots + 2
strike slots on surge, buys ≥+3%/h movers, trails — the never-miss-the-big-day test),
**F CASH HARVESTER** (profits vaulted non-spendable; $10k working base — profits are only
profits when they leave the table). Kill: 40 closed trailing that industry's A.

## The tabs
COMMAND (books, positions, TODAY NET + **OPEN-TRADE TRUTH**) · 🧠 BRAIN (master leans, coin
machine, signal ledger, confidence anatomy, Dr. Strange self-graded, dossiers, all-charts
eyeshot) · STRATEGY (per-industry labs, confidence engine, champion truth) · MARKETS ·
FORENSICS · HEALTH (SPINE, readiness, scorecard, nulls incl QQQ) · SETTINGS (every knob with
_what + kill).

## Key stores
paper_sim_live · paper_book_* · CONFIDENCE_ENGINE / **CONFIDENCE_CARDS** · STRATEGY_LAB
(by_industry) · BRAIN_WIRING · PEAK_RHYTHM · FINGERPRINTS · MTF_REGIME · REGIME_CLASSIFIER ·
timing_fingerprint · momentum_chain (also the price recorder + pending_ticks) ·
conviction_ranking · dr_strange · CONDUCTOR_REPORT_CARD (realized_profit.integrity) ·
BENCH_BOOKS · champion_validation · PARAM_CATALOG (every knob).

## Current state notes (2026-07-13 evening)
July-13 tape is oscillation-tainted; ~31 phantom-band wins (~$1.0k of the $1.77k headline)
retro-taggable via the **integrity backfill** workflow (confirm=TAG). Operator direction:
clean internal wipe before Tuesday so the recorder rebuilds a confirmed-clean tape (~2h) and
the per-industry labs baseline fresh. Metals/energy vol bars arm when their sessions print
real moves (flat weekend tape → σ=0 → correctly no bar).
