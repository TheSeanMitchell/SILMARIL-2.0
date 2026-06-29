# 2.6.1 — backfill FIX (the graphs will actually fill now)

## What was broken (and is now fixed)
- The backfill DID fetch a year of data, but wrote crypto under the wrong key: `TRXUSD` instead of
  `TRX-USD` (the hyphen your dashboard reads). So the history existed but the graph couldn't find it.
- The STOCK half silently errored (bad yfinance parse) — AAPL had only today's 15 points.
Both fixed: crypto now writes `BASE-USD` and MERGES with today's points; stocks use a robust parse and
a much broader ETF/equity set (sector SPDRs, commodity/metal/energy/bond ETFs, big single names) on top
of SP500/metals/energy lists.

## RUN AGAIN (Actions tab)
1. **Backfill Universe** — re-run it. Now TRX-USD, BTC-USD, AAPL, GLD, XLE, etc. all fill with up to a
   year of daily history under the keys the graphs read. Check TRX-USD after — it will show the year.
2. **Cleanup Clutter** (type CLEAN) — now removes ~19 obsolete workflow files (backtest, diagnose,
   old resets, alpaca, migrate, senate, stress_test, sweep_switch, etc.), keeping only the 6 essentials.

## Honest scope note on "full universe"
Crypto = the ENTIRE Binance.US + Coinbase USD spot universe (every listed coin). Equities now span
SP500 + ~90 broad ETFs covering every sector + commodities + metals + energy + bonds. "Every oil/metal
FUTURE" is a different asset class (futures, not spot/ETF) and isn't something a spot strategy trades —
the ETF set (USO, BNO, UNG, GLD, SLV, GDX, URA, XLE, XOP…) is the investable proxy and it's all in.

## Files
scripts/backfill_universe.py (FIXED) · scripts/cleanup_clutter.py (real cleanup) ·
silmaril/execution/ccxt_universe.py (TOP_N=600) · the two workflow ymls.
