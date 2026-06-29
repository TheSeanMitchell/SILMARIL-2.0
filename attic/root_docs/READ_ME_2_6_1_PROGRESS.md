# SILMARIL 2.6.1 — progress (cumulative: doctor fix + universe + reset)

ONE install gives you everything below. All verified to compile/parse; runtime needs a repo to confirm.

## INCLUDED
1. **Corruption fix** (paper_sim.py) — stocks gated to the real US session + a <3-distinct-values
   stale-oscillation guard on EVERY book (protects crypto too). Kills the weekend CSGP/MTCH fake P&L.
2. **Universe expansion** (ccxt_universe.py) — top liquid Binance USDT pairs 150 -> 250. More deep-dip
   candidates. Held at 250 (not 600) because: the OHLCV fetch is one sequential call per coin, so a huge
   list risks blowing your <9min clean-week runs, and pairs past ~300 are micro-cap junk the freshness
   filter rejects anyway. Safe, real expansion now; we can push higher AFTER confirming runtime.
3. **Clean reset** (reset_internal_clean.py + reset_internal_clean.yml) — the WORKFLOW you run from the
   Actions tab (type WIPE). Wipes internal+arena books to $10k, empties polluted price_samples, resets
   Master inception, clears polluted snapshots.

## DO THIS, IN ORDER
1. Install this zip.  2. Run "Reset Internal Clean" (Actions tab, type WIPE).  3. Let it run the week.

## WHEN I NEED A NEW REPO (to confirm + continue)
Send a fresh repo after a day or two of clean post-reset running so I can CONFIRM:
- the universe actually grew to ~250 and runs stayed under your time budget (the only real risk of the
  expansion), and the freshness fix produced zero weekend/after-hours trades.
Then, on that clean foundation, the remaining 2.6.1 — which I will NOT build blind because they need to
be validated against real data and would be guesswork otherwise:
- **Metals/Energy strategies** (currently dormant) — they need their own entry thresholds + a champion;
  building these requires seeing their real price feeds populate, which only happens post-reset.
- **Per-quadrant parameter champions / judge mode + A/B** — needs a week of clean forward data first
  (building it on the poisoned history we just wiped would overfit to noise).
- **Deeper-entry default** (the bad-timing fix for MANTA/SNX-type losses) — trivial once you decide the
  threshold from the clean threshold-sweep, but that sweep must run on clean data first.

## HONEST STATUS
2.6.1 is NOT complete — but the two things that HAD to happen blind are done (corruption fixed, universe
expanded) and the reset is one click. Everything left genuinely depends on clean post-reset data; doing
it now would be faking confidence we don't have. Reset, run a clean week, send a repo, and I'll finish it
on ground you can trust.

## Files
silmaril/execution/paper_sim.py · silmaril/execution/ccxt_universe.py · scripts/reset_internal_clean.py
· .github/workflows/reset_internal_clean.yml
