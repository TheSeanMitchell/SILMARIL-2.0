# SILMARIL 2.5 — UI fixed, favicon, capture reconciled, asset-class command center

Drop on repo root, overwriting. `docs/index.html` is the working command center.

## 1. Favicon (finally) — `docs/assets/favicon.svg`
Half-silver / half-gold faceted gem, linked in the page head.
**Protect it:** workflows must never write to `docs/assets/`. It will not regenerate.

## 2. The two contradictory capture numbers — reconciled honestly
They were measuring different things and both wrongly called "capture":
- **Edge Capture KPI = 16.38%** — of the total available *market* move, how much we
  captured. This is the real edge-capture number. Unchanged.
- **execution_leak "avg capture -35.3%"** — was a per-trade *average* of capture
  ratios. Losing trades produce negative ratios, so one bad trade tanked it to -35%.
  **That was a bug.** Retired.

execution_leak now reports **exit efficiency (54.7%)** = of the peak each trade
reached *while held*, how much we kept — a different, legitimate question, clearly
labeled so it can't be confused with the KPI. The panel now carries a one-line note
explaining the distinction. The tabs are in unison: each says what it measures.

## 3. Asset-class Market Command Center (your placeholder request)
Top of the COMMAND tab: four cards — **Crypto** and **Stocks** live (real equity,
champion, P&L, open count), **Metals** and **Energy** as blank "NOT STARTED"
placeholders. No synthetic data. This is the skeleton of the independent
Crypto / Stocks / Metals / Energy architecture you described — a visual placeholder
only; real separation (own arena/champion/account each) is the 2.5.1 build.

## 4. UI is verified working
The morning's blank page was a JS syntax error (one missing `)`). Fixed, and now
syntax-checked with `node --check` every change, plus per-panel try/catch so no
single bad field can blank the page again.

## On 2.5.1 — your roadmap is logged, not drifted
Your audit is right: the next phase is **Validation, Separation, Specialization**,
not new signals. The sequence you set —
(1) fully separate Crypto vs Stock arenas, (2) Exit-Quality / Post-Exit-Leak
forensics with 1/3/5/10/20-day tracking, (3) Trade Opportunity Audit (candidates
found/traded/rejected + reason breakdown), (4) asset-class command center,
(5) mobile-first, (6) API health, (7) Vegas market clock — is the plan. This drop
delivers the favicon, the capture reconciliation, and the command-center placeholder
(item 4 skeleton). The big one — true crypto/stock separation — is the next build,
and it's the highest-value item because, as you said, crypto MR and stock MR are not
the same edge and must not share a champion. We are NOT calling this 2.5.1 yet.
