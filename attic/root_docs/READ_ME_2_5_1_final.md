# SILMARIL 2.5.1 — Capstones: Scorecard + Exit Expansion + Performance Audit

Drop on repo root. Measurement only, no new alpha. This closes most of 2.5.1.

## Project Scorecard (SCORECARD.json) — the "are we improving" number
The platform grades itself every cycle from real data, with a trend line. Current
honest read: **6.3/10.** Strong: explainability 10, governance 9, separation 9,
survivability 8.2, operational health 8.5. Weak (correctly): profitability 1.1
(stock drag), statistical confidence 1.2 (only ~12 trades vs the 100 we need),
production readiness 3.6. It does not flatter — confidence stays low until trades
are real. On the COMMAND tab up top.

## Exit Forensics Expansion (EXIT_FORENSICS.json)
Added +1h/+4h windows and per-exit classification, ranked worst offenders. The split
is damning and consistent with everything else:
- **CRYPTO: 41 of 51 exits sold too early** (32 EARLY + 9 CATASTROPHIC), only 9 good.
- **STOCK: 21 LATE exits** (held into losses that never bounced), 0 catastrophic.
- Worst offender: DYM sold at +0.77%, then ran +8.5% (CATASTROPHIC).

Crypto's problem is exits (too tight); stock's problem is thesis (dips that don't
recover). Proven three different ways now.

## Performance Audit (PERFORMANCE_AUDIT.json)
Data dir is ~104 MB across 164 JSONs — the cycle's IO cost. No runtime hotspots at
this size; IO dominates and is already atomic + concurrency-guarded. The big files
are price history + snapshots; your planned pristine reset/compaction will shrink it.

## Self-explaining UI
New/updated panels (scorecard, regime, exit forensics) carry What / Why / Action so
the dashboard teaches itself, per the directive.

## 2.5.1 status — honest
DONE: Market Separation · Opportunity Audit · Exit Forensics (+expansion) · Stock
Reality Audit · Regime Observer · Scorecard · Performance Audit · self-explaining
panels · the unified command center.

ONE item genuinely blocked on data: **stock-sector recovery breakdown** needs a
sector / market-cap mapping for the 536 stocks — i.e., a real data source (one of the
"API plug-ins" you mentioned). I did NOT fake it with a hardcoded map. When you wire
a sector feed (e.g., a fundamentals API), this becomes a 1-file add that buckets the
existing recovery analysis by sector. Until then it stays honestly absent rather than
synthetic.

PARTIAL: a from-scratch mobile redesign and a full Internal/Alpaca/Live three-way
truth layer can go deeper, but the command center already labels the internal sim as
the lab and the panels self-explain.

## Recommended close-out (your reset question)
Now that the engine chain is essentially complete, this is the moment for the clean
slate you wanted: one pristine reset + compaction (crypto/stock), reset Alpaca paper
to match, start tomorrow on fresh data under the separated parameters. The
concurrency group makes the reset safe against running cycles. Metals/Energy stay
placeholders until they have feeds.
