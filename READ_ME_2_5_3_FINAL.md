# SILMARIL 2.5.3 — FINAL: visible bugs fixed, last engines built, reset made one-step

## Visible bugs you flagged — FIXED
- **$NaN in 3-Day Backtest Proof** — the panel read `bt.equity`; the field is `bt.equity_after`
  (8976.73). Now shows the real number.
- **Domain clocks all "closed"** — the panel was reading the top-level keys (version, checked_at…)
  instead of `domain_clocks.domains.{stocks,valuables,…}.open`. Now shows each domain's real
  open/closed state with 🟢/⚪.
- **"Combined" framing that implied connected accounts** — relabeled everywhere:
  "Combined Equity" → "All 4 Books (independent) — total equity", and the equity-over-time
  header likewise. These are SUMS of four independent $10k books, not a shared pool. Nothing
  in the trading path pools the books — crypto/stock/metal/energy each run their own champion
  and their own $10k. (The capital-router panel is now explicitly labeled HYPOTHETICAL research.)

## Reset is now ONE step (your question answered)
Your route was: pristine reset → squash → daily → backfill fingerprint → daily.
I folded the backfill INTO the reset. New command:

    python scripts/pristine_reset.py --with-backfill

That resets all four paper books + Alpaca ledgers AND rebuilds price history/fingerprint in
the same step. So the whole route collapses to:

    1. python scripts/pristine_reset.py --with-backfill      (reset + fingerprint, one step)
    2. (optional) git squash — housekeeping only; your repo is 261MB, well inside GitHub limits.
       NOT required for the reset to work.
    3. let the daily cron run — it starts clean with history already present.

Options: `--baseline 10000` (per-book starting cash), `--backfill-days 30` (history depth),
`--accounts all`. If you ever want reset-only, just omit `--with-backfill`.

## Last 2.5.3 engines — BUILT, wired, surfaced (FORENSICS tab)
**1. Decision Trace Engine** (DECISION_TRACE.json) — per-trade chain: why entered, why exited,
outcome. On your data it surfaces the key truth: of 30 recent trades, only **3 hit target**;
**24 timed out** (14 at a loss, 10 at a gain *before* reaching target). That is hard evidence
the THESIS is fine but the EXITS fire too early — exactly the EARLY_EXIT forensics finding, now
visible trade-by-trade. (This is the #4 item on your 2.5.4 list — Exit Optimization — already
half-proven here.)

**2. Capital Router Explainer** (CAPITAL_ROUTER_EXPLAINED.json) — surfaces the allocation math
that already lived in `allocation_proof`: each strategy's weight, survivability, realized P&L,
and the verdict ("Concentrating on the champion beats equal-weight" on your current data).
Clearly labeled HYPOTHETICAL — it does not pool the four books.

**3. Stock Sector Recovery** (SECTOR_RECOVERY.json) — groups stock recovery by sector. It is
wired and ready but reports `awaiting_sector_data` (34 stock trades queued) until a production
run caches sector tags from FMP into `sector_map.json`. The moment that cache exists, the engine
activates automatically — no code change. (You have FMP, so this is a one-run fetch away.)

All three render functions were grep-verified as actually CALLED in both index.html and
cockpit.html — and while doing it I found cockpit.html had ALL its 2.5.3 panels defined but
never called (the recurring "defined-but-not-wired" bug); fixed — cockpit now renders the full
2.5.3 set too.

## Honest 2.5.3 status — what's done, what genuinely isn't
DONE (this is the complete 2.5.3 measurement/explainability layer):
separation (4 books) · opportunity audit · exit forensics (+expansion) · stock reality audit ·
regime observer · scorecard · performance audit · intrabar miss · time-of-day · threshold
shadow-sim · zero-PnL · health matrix (accurate + unified, real api_health source) · fallback
framework (your real provider names, all green) · champion governance fix · Alpaca notional fix ·
paper_sim 4-quadrant · NaN/domain-clock/combined fixes · **decision trace · capital router
explainer · sector recovery** · cleanup script · one-step reset.

NOT done — and correctly deferred:
- **Learning Feedback Engine (Level 2: actually change behavior from lessons, then measure if it
  helped)** — you and your advisor both flagged this needs a real forward track record (weeks,
  50+ trades, multiple regimes). Building it on today's thin noisy sample would be curve-fitting.
  This is the centerpiece of 2.5.4, not 2.5.3.
- **Sector Recovery activation** — needs the one production sector fetch (above).

So: 2.5.3's measurement and explainability scope is COMPLETE. The only thing left out is the one
engine that genuinely requires the data you're about to collect — which is exactly where 2.5.4
begins. I'm not going to call the learning loop done; it isn't, and it shouldn't be yet.
