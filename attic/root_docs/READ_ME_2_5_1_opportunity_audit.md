# SILMARIL 2.5.1 — Priority 1: Opportunity Audit (explainability, no black boxes)

Drop on repo root. One measurement engine, no new alpha. Surfaced in the FORENSICS tab.

## What it does
Every cycle, every name in the universe (92 crypto + 536 stock) is classified into
exactly one bucket with the EXACT rule that put it there — using the sim's own
functions, so the audit matches reality:

- IGNORED · insufficient_drop (didn't fall enough to trigger)
- IGNORED · insufficient_history
- REJECTED · not_fresh (stale ghost / market closed)
- REJECTED · already_held (no duplicate exposure)
- REJECTED · capacity_cap (qualified but ranked beyond the deepest 10 taken/cycle)
- TRADEABLE_NOW (top-10 by drop depth, eligible)

`OPPORTUNITY_AUDIT.json` carries the per-book funnel, the tradeable + missed lists,
and **`by_ticker`** — look up any symbol to see its decision and reason.

## It answers the directive's own questions
- **Why did we miss AXS?** insufficient_drop — moved −0.38%, rule needs ≤ −3%
- **Why did we miss SAND?** insufficient_drop — moved −1.08%, rule needs ≤ −3%
- **Why did we miss DYDX?** insufficient_drop — moved −1.38%, rule needs ≤ −3%

And it explains the quiet tape: at this snapshot, **0 of 628 names had dropped enough
to qualify** — that's why activity is low. Not a mystery, not a bug: nothing was on
sale by the −3%/−5% rule. When names do drop, they'll show up as TRADEABLE_NOW or, if
too many drop at once, as capacity_cap with their exact rank.

## 2.5.1 progress
DONE: P1 Separation · P2 Exit Forensics · **P1(this phase) Opportunity Audit** ·
P4 Stock Reality Audit. STILL OPEN (no drift): regime measurement, exit-forensics
expansion (+1h/+4h buckets + good/early/catastrophic ranking), stock-sector recovery,
main-page clarity/renaming, paper-sim truth layer (Internal vs Alpaca vs Live),
performance hardening, scorecard. Not calling 2.5.1 complete yet.

Per the directive: no new strategies, no new signals, no metals/energy/options/macro
expansion. Pure explainability. Every missed trade now has a machine-readable reason.
