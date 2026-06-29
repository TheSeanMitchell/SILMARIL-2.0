# 2.6.1 — graphs fixed (full year + all 18 timeframes)

## Both things you asked for, done and verified
1. **Full year of data on every crypto graph.** Your year WAS in the file all along — under SOLUSDT /
   SOLUSD — but the dashboard reads SOL-USD, so it only saw the live week. The remap merges the history
   onto the BASE-USD keys. VERIFIED on your real file: SOL-USD went from 36 points to **393 points
   spanning 2025-06-30 -> today**, and **429 crypto graphs** now hold a full year. The fixed
   price_samples.json is included, so graphs show the year the moment you install — no waiting.
2. **All 18 timeframe buttons** in the chart: 5m · 15m · 30m · 1h · 2h · 4h · 8h · 12h · 1D · 2D · 3D ·
   1W · 2W · 1M · 2M · YTD · 1Y · MAX. The tab bar now wraps so they all fit. (silmaril_chart.js)

## To install
Just drop this in. Graphs work immediately because the corrected data file is included.
- `docs/data/price_samples.json` — remapped (year of history under the right keys)
- `docs/silmaril_chart.js` — 18 timeframes
- `scripts/remap_keys.py` + `.github/workflows/remap_keys.yml` — re-run "Remap Keys" anytime new coins
  come in with USDT keys; it's idempotent and safe.

## Note
This is the GRAPH fix. It does not change trading (that was the separate critical fix that stopped the
post-reset losses). Together: graphs now show the full year at every zoom level, and trading no longer
self-destructs after a reset.

## Files
docs/data/price_samples.json · docs/silmaril_chart.js · scripts/remap_keys.py ·
.github/workflows/remap_keys.yml
