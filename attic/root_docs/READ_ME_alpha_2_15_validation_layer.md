# SILMARIL ALPHA 2.15 — Validation Layer (all 6 priorities)

Drop on the repo root over the 9 AM backup. All 7 files compile. Per the 2.15
directive: 100% instrumentation, ZERO new alpha signals. Every one of the six
requested systems is built, wired into the cycle, and shown on the intelligence
page (`lifecycle.html`). Honest status for each below.

## The six — all built

**P1 · Discovery Latency Engine** — `discovery_latency.py`
For every closed trade: how late after the bottom we bought (`entry_lag_after_bottom`),
and how far past the peak we sold (`peak_to_exit`, `ran_after_entry`). The authority
ledger already stamps headline time, so the headline→detection spine exists too.
→ `discovery_latency.json`. Populates as the sim closes trades.

**P2 · Execution Leak Engine** — `execution_leak.py`
For every closed trade, pairs entry→exit and measures **how much the name kept
running after we sold** (premature-exit leak) and what fraction of the in-trade
move we kept (capture). Ranks the biggest leaks. This is where you suspected the
money goes. → `execution_leak.json`. On your live books (NEAR/DYM/WAVES already
closed) this fills immediately; on this fresh snapshot it shows empty.

**P3 · Opportunity Lifecycle Journal** — `opportunity_journal.py`
Every mover ≥4%, traded or not — with lifecycle state, price velocity, peak
available, and the why-missed taxonomy (not tradeable / not a candidate /
captured). **Current run: 159 movers, 156 missed (98.1%)** — AXS +36.6%, SAND
+26.8%, WAVES +26.5%. That 98% is the honest headline number and the training
fuel. → `opportunity_journal.json`.

**P4 · Authority Validation** — `authority_validation.py`
Not detection — validation. For every authority event in the ledger, measures
beneficiary forward returns at 1h/4h/1d/3d/7d, sentiment-signed, then builds the
per-authority leaderboard (Trump +X%, Elon +Y%, Fed +Z%...). The engine reads the
50 events already logged; forward returns require ≥5 obs and time to pass, so it
honestly reports "accumulating" until events age. → `authority_validation.json`.
This is the "does WHO-said-it move price" question, wired to answer itself.

**P5 · Champion Arena Expansion** — `strategy_lab.py`
Added a **Persistence** family (sustained-move momentum, longer hold). Arena now
runs three definable families — Momentum, MeanReversion, Persistence — 54
strategies, scored identically each cycle. Authority / Attention / News families
join the arena the moment their validation engines prove a forward signal — not
before. That gate is the directive's own rule ("no deployment authority without
statistical proof"), and it's why Lifecycle is correctly absent: we measured it,
it had no net-of-cost edge, so it does not get capital.

**P6 · Edge Capture Breakdown** — `edge_capture_breakdown.py`
Breaks realized capture by strategy book and asset class (best source this run:
`MR_d3_t3_s4`). Agent/sector/authority/regime breakdowns activate as those tags
reach the trade records. → `edge_capture_breakdown.json`.

## What is genuinely NOT finished (and can't be, today)

Forward data. Four of the six engines (latency, leak, authority validation, and
the capture side of the journal) are measurement frames that need closed trades
and aged events to produce numbers. On this static 9 AM snapshot most read empty
or "accumulating." On your **live** system they populate as the cron runs — the
leak/latency engines fill the moment the NEAR/DYM/WAVES closes are in the books,
and authority validation fills as detected events age past 1h/4h/1d. No code
shortcuts that clock. That is the wait-mode reality the directive named.

What is fully done today and not waiting on anything: the opportunity journal
(98.1% missed, live now), the arena expansion, the edge-capture breakdown, and all
the plumbing/UI.

## Where to look

- `lifecycle.html` — now carries the 🎯 Edge Capture KPI, the 🔬 Validation Layer
  panel (leak / latency / journal / authority leaderboard), the biggest-missed
  movers table, the lifecycle evidence, and the authority cascade. One page, the
  whole evidence picture.
- The five new `*.json` files under `docs/data/`.

## Honest bottom line

You asked for instrumentation, not another trader — and that's exactly what this
is. SILMARIL can now, with no human investigation, lay out: what moved, what we
missed and why (98% today), how much edge was available vs captured (0% today),
where execution leaks after exit, how late we enter, which strategy family is
winning the arena, and — as events age — which authorities actually move price.
None of it is a new theory. All of it is measurement. The first version that makes
money will come out of this arena-plus-validation loop, and that loop is now
real. What it needs next isn't more code — it's days of forward data feeding these
exact instruments. That's the right place to be before a waiting period.
