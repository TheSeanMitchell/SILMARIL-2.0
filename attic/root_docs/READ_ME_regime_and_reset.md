# SILMARIL 2.5.1 — Regime Observer + your reset/compact question

Drop on repo root. One measurement engine, no new alpha. Self-explaining panel in FORENSICS.

## Regime Observer (REGIME_ANALYSIS.json)
Every trade tagged with the market regime at entry — crypto and stock measured
INDEPENDENTLY (their own universe trend, breadth, volatility). More proof, not theory:

- **CRYPTO MR wins in BEAR regimes: +2.31%/trade, 63% win over 30 trades.** Its edge
  lives in oversold selloffs — when things dump, crypto overshoots and bounces. It
  loses in WEAK grinds (-1.09%). That's a real, located edge.
- **STOCK MR loses in every regime observed:** NEUTRAL -0.74% (32% win, 68 trades),
  WEAK -0.46% (33% win). No regime rescued it. Combined with the recovery data
  (stocks recover only ~16% of 5% drops), conclusion #6 is looking confirmed:
  short-horizon stock MR is structurally weak.

This directly answers "which strategies win where": crypto MR is a *bear/oversold*
edge; stock MR hasn't shown an edge in any regime yet.

(~5 days of data, so only NEUTRAL/WEAK/BEAR have appeared. STRONG_BULL/PANIC will tag
as they occur. Observer only — no reactions, no strategy changes.)

## Your reset / compact / backfill question — recommendation

**Yes, a clean reset makes sense — but AFTER 2.5.1 is finished, not mid-chain.**
Here's the reasoning:

1. **Timing.** You just changed the architecture (separation + a stock-specific
   champion). The accumulated trade history is now from the OLD shared-champion
   world — partly stale. A pristine reset once 2.5.1 is complete gives you a clean
   day of data under the FINAL separated parameters, which is exactly what you want
   for honest survivability. Resetting now and then installing more engines would
   dirty that clean day again. So: finish the engine chain, THEN reset once.

2. **Safety.** The reset/compact/backfill workflows already share the
   `silmaril-state` concurrency group (from the earlier hardening), so they cannot
   corrupt live state mid-run — a reset can't collide with a trading cycle. You're
   safe to run them; the only question is timing, above.

3. **Alpaca.** The Alpaca paper accounts are separate from the internal sim (the sim
   is the primary lab). Stock account ~1% down, crypto hasn't traded — both are paper
   money. Since you're doing a pristine reset anyway, **yes, reset Alpaca paper too**
   for a clean matching baseline. Low stakes either way; it just keeps all surfaces
   telling the same fresh story.

4. **Backfill across "all four classes" — honest limit.** Backfill works for crypto
   and stock because we have their price tape. **Metals and Energy have no data feed
   yet** — they're the blank placeholders you approved. "Backfill fingerprint data
   across everything" isn't possible until those classes have real price sources,
   which is a deliberate, separate step (and one the directive says not to take yet).
   So: backfill/compact crypto + stock freely; metals/energy stay empty until they
   have feeds.

**Bottom line:** finish the 2.5.1 engine chain first → then do one pristine reset +
compact for crypto/stock, reset Alpaca paper to match, and start tomorrow on a clean
slate under the new separated parameters. Don't reset mid-chain.

## 2.5.1 progress
DONE: Separation · Exit Forensics · Opportunity Audit · Stock Reality Audit ·
**Regime Observer**. STILL OPEN (no drift): exit-forensics expansion (+1h/+4h buckets
+ GOOD/EARLY/LATE/CATASTROPHIC ranking), stock-sector recovery breakdown, paper-sim
truth layer (Internal vs Alpaca vs Live), full UI overhaul/clarity pass, performance
hardening, scorecard. Not 2.5.1 complete yet.
