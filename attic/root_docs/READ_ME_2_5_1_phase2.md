# SILMARIL 2.5.1 Phase 2 — Exit Forensics + Stock Reality Audit (measurement only)

Drop on repo root. Two measurement engines, no new alpha. Both surfaced side by side
in the FORENSICS tab (crypto vs stock).

## P2 — Exit Forensics (EXIT_FORENSICS.json)
For every closed trade, what the price did AFTER we exited (+1/+3/+5/+10/+20d; longer
windows pending until history is that long). The finding is sharp and the two books
are OPPOSITE:

- **CRYPTO: 18 of 19 losing trades bounced after we sold** — execution failure. We're
  selling winners too early (2.55% avg leak). The MR thesis was right; the exit was
  wrong.
- **STOCK: 35 of 46 losing trades kept falling** — thesis failure. The dip wasn't a
  dip. Only 0.73% leak (nothing to capture because they didn't recover).

Translation: crypto needs **exit** work (hold longer / wider target). Stock has a
**thesis** problem — which the next report nails down.

## P4 — Stock Reality Audit (STOCK_RECOVERY_ANALYSIS.json)
How often and how fast a name climbs back after a 3/5/7/10% drop — stocks vs crypto:

| After a drop of | Crypto recovery rate | Stock recovery rate |
|---|---|---|
| 3% | 67.7% (median 3.2h) | 25.3% (median 5.3h) |
| 5% | 66.5% (median 0.5h) | 15.9% (median 2.1h) |

**This is the answer to your biggest question.** Crypto mean-reverts — two-thirds of
drops recover, fast. Stocks mostly DON'T: after a 5% drop, only ~16% climb back; 84%
are still underwater days later. Short-duration stock mean reversion is fighting the
actual behavior of the market. Buying 5% stock dips expecting a bounce is, on this
evidence, buying things that mostly keep falling.

(Caveat, stated honestly: price history is only ~5 days, so slow recoveries are
censored — which makes the LOW stock recovery rate, if anything, the more reliable
signal: these stocks haven't recovered even given the chance.)

## What this means (and what I did NOT do)
Per the directive, this is measurement mode — I changed **no** exit rules and **no**
strategy. But the evidence now strongly suggests two separate truths:
1. Crypto: loosen exits (you're leaving 2.5% on the table by selling early).
2. Stock: short-horizon MR may simply not be the right model — stocks don't revert on
   this clock. That's a thesis-level finding, exactly what P4 was meant to surface.

You decide the reaction next; the lab has now produced the proof.

## 2.5.1 progress
DONE: P1 Separation · **P2 Exit Forensics** · **P4 Stock Reality Audit**, all visible
in the dashboard. STILL OPEN (no drift): P3 Opportunity Audit, P5 Regime measurement,
P6 UI clarity, P7 command-center polish, P8 Health center, P9 mobile-first, P10
scorecard. Not calling 2.5.1 complete yet.

On the "vast network of API codes / metals + energy": noted, but adding live feeds
for markets we can't yet validate is exactly the drift the directive warns against —
Metals/Energy stay as the blank placeholders you approved until there's a reason and
data to make them real. When you want them live, that's a deliberate, separate step.
