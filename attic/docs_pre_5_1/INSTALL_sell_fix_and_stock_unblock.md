# SILMARIL — CRITICAL trading fix: sells now fire + stocks unblocked + per-trade champion labels

This is the fix for the "hit target but never sells" bug (LDO / ENJ / ETHFI / PENDLE) and the
frozen stock book. Drag these three files over the repo. Then wipe, backfill, and run — buying
AND selling now work for every industry, so the data you collect next is trustworthy.

## 1. THE SELL BUG — root cause (the keystone)
The exit loop compared each position's gain against the **current champion's target**, not the
target the position was **entered** with. Crypto champion `MR_patient_d3` carries a 3% target, but
positions bought under the SIDEWAYS override are stored (and displayed) at a **2% target**. So a
position that reached 2% — its own displayed target — was checked against 3%, never sold, and rode
back down to the stop. That is exactly what you watched: prices hit their high target on the LIVE
POSITIONS bar and sold off at their lows instead.

**Proven on your real 11:40 AM data:** with the fix, `ETHFI-USD` (peaked 2.58%) and `PENDLE-USD`
(peaked 2.53%) both closed at their 2% target this cycle (+1.49% / +1.52% after real fees).

### What changed
- **Exits use the position's OWN `target`/`stop`** — never the current cycle's champion values. A
  champion rotation can no longer strand an open position with a moved goal.
- **Resting LIMIT-SELL at the target.** A target touched *between* 10-minute cycles now fills at the
  target price (a real order type — the high-water mark proves the price traded there), so the
  targets you watched get hit repeatedly are captured instead of missed. Fees still apply; nothing
  synthetic. Toggle in `PARAM_CATALOG.exit_policy.limit_sell_at_target` (default on; set false for
  market-order-only exits).
- Stops and holds are unchanged — it still stops out on a breach and holds when between stop and
  target. Verified across all cases.

## 2. STOCK UNBLOCK
Every stock candidate (even liquid names like AVGO/COF/HUM) was being blind-blocked because the
daily-candle backfill hadn't populated them, and `_longterm_up` refused anything with <20 daily
closes. **Fix:** when daily candles are missing, the book now judges the name's **own intraday
trajectory** over the last ~1–2 days (operator's request — use the valuable's own multi-timeframe
trend). A name that's up or flat trades; a name in a sustained intraday downtrend is still refused;
a name with no usable history is still refused (never buys blind).

**Proven on real data:** of the 8 previously-blocked candidates, the 4 with an up/flat trajectory
(AVGO, HUM, MOH, BOIL) now trade, while the 4 trending down (COF, CHTR, SYF, SPCX) are correctly
held back. The stock book **bought 4 this cycle** where it was frozen at 0.

## 3. PER-TRADE CHAMPION LABELS (so you can finally see rotation)
Every trade is now stamped with the strategy that made it. BUY rows carry `champion`; SELL rows
carry `champion_entry`, `champion_exit`, and `champion_changed` (true when a different champion
sold the position than bought it — mid-lifecycle rotation, visible per trade). The RECENT TRADES
table shows the champion under each symbol. Once closed trades accumulate (which the sell fix
finally allows), survivability can compute and champions can actually rotate — the reason you only
ever saw "Lickitung" is that nothing was closing, so there was no forward evidence to rotate on.

## Files
- `silmaril/execution/paper_sim.py` — exit uses position target/stop + limit-fill + champion labels;
  `_longterm_up` intraday fallback (stock unblock)
- `docs/data/PARAM_CATALOG.json` — `exit_policy` knob
- `docs/index.html` — champion label in RECENT TRADES

## Verify after wipe + run
- LIVE POSITIONS: a name that reaches its target now disappears (sold) instead of riding back down.
- RECENT TRADES fills with SELL rows tagged TAKE / TAKE_LIMIT and a champion label; realized % is
  positive and near the target minus fees.
- Stock book takes positions during the session (funnel `bought` > 0).
- Over a day, per-book champions begin to differ from Lickitung as closed trades accrue.

## One honest caveat
This makes buying and selling *correct and honest* — profit is still not guaranteed. The limit-fill
is a real order type, not hindsight, and every close clears real round-trip fees, so if an asset
class has no post-cost edge you'll see it truthfully in the realized P&L and the Δ-vs-NULL line.
That's the point: now the numbers can be trusted.
