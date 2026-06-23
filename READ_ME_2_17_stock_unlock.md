# SILMARIL 2.17 — Stock Unlock + Champion Status (validation mode)

Drop on the repo root, overwriting. No new signals, no new engines. One diagnosis,
one safe fix, two artifacts. Crypto is byte-for-byte untouched.

## Why stocks weren't firing — answered with evidence

`STOCK_PIPELINE_AUDIT.json`. The funnel, on your data:

```
stock_universe                                   536
with_enough_samples                              536
passed OLD freshness (crypto 80%/24-7 bar)         0   <- the blocker (0 even when open)
had a >=3% dip (signal exists)                     96
NEW freshness capable during market hours        536   <- the unlock
```

It was never the signal — 96 stocks dipped ≥3% (ACN −17.7%, EPAM −10%, CTSH −9.7%).
It was the **freshness filter**: the crypto-tuned "price must update ≥80% of
intervals" bar is impossible for stocks, which only quote ~6.5h of 24 and look
frozen the rest of the time. So all 536 were rejected as stale ghosts — even during
market hours.

## The fix (surgical, stock-only, crypto-safe)

In `paper_sim.py`, `fresh_ok()` now branches: **crypto keeps the exact 80%/24-7
check** (verified: still 51/92 fresh, unchanged), and **stocks use a market-hours-
aware check** — a stock is tradeable when it's *actively quoting now* (its price
moved in the last few samples). That naturally gates stock trading to market hours
and unlocks all 536 names when the market is open.

Note: this backup was taken at 3:50 AM with markets closed, so "right now" shows 0
fresh stocks — which is *correct* (don't trade closed markets). The "capable during
market hours" count (536) is what fires after the open. You should see stock
candidates appear during the session, still gated by the same MR entry/target/stop,
so they stay selective.

## Champion-first artifact

`CHAMPION_STATUS.json` (Section 1) — the champion in one focused file:
MR_d3_t3_s4 · survivability 87 · 9 trades · 77.8% win · tier Sandbox · **1 more
trade to Incubation** · governance ALIGNED. Includes CI, Sharpe, drawdown, profit
factor, challenger queue, and an honest small-sample note.

## Status vs the 2.17 directive

- **S1 Champion-first / CHAMPION_STATUS** — ✅ done.
- **S2 Workflow hardening audit** — ✅ done prior session (WORKFLOW_AUDIT.md;
  concurrency groups + atomic writes + run lock). WORKFLOW_HEALTH.json pass/fail
  format is a small follow-up on top of it.
- **S3 Stock pipeline audit** — ✅ done (this release) + the fix applied.
- **S4 Snapshot engine** — ◻️ next; lightweight immutable per-cycle snapshot/.
- **S5 Champion dashboard / S6 Mobile / S7 Dark mode / S8 Gem favicon** — ◻️ UI work,
  sequenced; you've (rightly) put these below validation.
- **S9 Validation over expansion** — ✅ honored: nothing new was added to chase alpha.

## Honest bottom line

The largest unknown is closed, with a precise, evidence-backed cause and a fix that
can't touch the crypto book that's working. Stocks should begin trading this week —
and, just as importantly, the stock book will now *accumulate its own sample* so the
arena can judge whether MR works on equities the way it appears to on crypto. That's
sample size, which you correctly named as the only real bottleneck. Cautious
optimism is the right setting: $124 in a day is wonderful and real, and 9 trades is
still 9 trades. Let both books stack trades toward 25 → 50 → 100, and the picture
will speak for itself.
