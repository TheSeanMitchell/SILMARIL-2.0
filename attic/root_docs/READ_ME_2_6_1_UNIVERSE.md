# 2.6.1 — full universe + 1y fingerprint backfill + cleanup (all workflows)

Everything here is a WORKFLOW you run from the Actions tab. No scripts to run by hand.

## RUN THESE (in order)
1. **Backfill Universe** — fills price_samples with up to 1 YEAR of daily history for EVERY valuable in
   EVERY quadrant: the FULL Binance.US + Coinbase USD coin universe (every listed coin), all SP500
   stocks, all metals (HARD_CURRENCY_FULL), all energy (OIL_COMPLEX_FULL). Graphs/fingerprints full
   immediately; the live 5-min sampler keeps the intraday detail filling. Real data only. (~up to 1–2h.)
2. **Cleanup Clutter** — type CLEAN. Removes obsolete alpaca reset/diagnose/wipe workflow files. (It
   does NOT delete kraken/alpaca code modules yet — they're still imported by cli.py, so deleting them
   would crash the cron. Fully unwiring kraken/alpaca is the one careful cli.py edit I'll do with the
   next repo.)

## ALSO CHANGED
- Live crypto universe cap raised 250 -> **600** (full liquid coverage; runtime per your call).

## STILL NEEDS THE REPO (honest)
- Making the colored quadrant cards CLICKABLE into each quadrant's thinking + surfacing the gold Master
  decision tree on the main page: this is editing the live dashboard JS, which I won't do blindly in the
  same drop as these data changes (one broken edit = broken main page). It's the very first thing with
  the next repo, alongside unwiring kraken/alpaca.

## Files
scripts/backfill_universe.py · scripts/cleanup_clutter.py · .github/workflows/backfill_universe.yml ·
.github/workflows/cleanup_clutter.yml · silmaril/execution/ccxt_universe.py (TOP_N=600)
