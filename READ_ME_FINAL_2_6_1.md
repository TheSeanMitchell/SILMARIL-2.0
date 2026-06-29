# SILMARIL 2.6.1 — FINAL (backtest/champion data-integrity fix) + completion status

## THE FIX IN THIS DROP (critical — install it)
The arena leaderboard, the per-quadrant champion selection, and the capital router were all backtesting
on price_samples that now include a YEAR of DAILY backfill candles. Shallow mean-reversion replayed on
daily candles across the whole universe loses badly — that is why you saw MR_d1_t1_s2 at 53,229 trades /
-5.5% edge / 16% win. It was the backtest reading the wrong data, NOT your strategies failing.

Fixed: every backtest series now excludes daily-backfill candles (timestamps at midnight) and uses
intraday only — matching what the live engine actually trades. Verified on your real file: the same
strategies now read e.g. MR_d1_t2_s6 = 39 trades, +0.67% edge, 77% win. Positive, sensible, real.
Files: silmaril/execution/strategy_lab.py · paper_sim.py · capital_router.py

Because champion selection reads the leaderboard, this also repairs WHICH strategy each quadrant
champions — it will now pick winners on real intraday evidence, not daily-candle noise.

## IS 2.6.1 "COMPLETE"? — honest answer
For the purpose you set — a clean, observable dress-rehearsal week — YES, with the data caveat you named.
Everything that had to be CODED is in place and verified:
- corruption bug fixed (weekend/stale prices) · 2h warmup (no cold-start trades, stocks safe at open)
- per-cycle key canonicalization (graphs never silently break again, through any wipe)
- full universe + 1y graph history · 18 chart timeframes · stop line on closed trades
- clickable quadrant decision portals · Master title/detail panel · "Market Engines" rename
- Pokemon strategy legibility (all 54 decoded) · HEATSHIELD default-on + real what-if forensic
- scorecard moved to forensics · the two Master views synced on live_equity, honest on fees
- Today's Session: ALL-QUADRANTS vs MASTER-ONLY side by side (your quantity-vs-quality test)
- bot-handoff seed in Settings · AND now the backtest/champion integrity fix above

## WHAT GENUINELY REMAINS (needs the live week, not codeable blind)
These were always going to require the clean data you're about to gather — building them now would be
guessing:
- Dr. Strange audit (is the projection any good? — needs outcomes to check against)
- recording target-at-entry per trade (for the exact %-of-goal and the "left on table" honesty fix)
- the Master confidence / heatshield / wager tuning KNOBS as decimal parameters (you wanted to tune
  these against real performance — tuning blind is pointless)
- confirming prior strategies (fingerprints, peak-rhythm, MKR-style repeat-striking) actually FEED
  live decisions (an audit against real behavior)
These are 2.7 — set your notes against the week's real data and they become buildable with evidence.

## DO THIS
Install this zip. The leaderboard/champion now read clean. Let the week run. Watch the
ALL-QUADRANTS-vs-MASTER side-by-side: the whole thesis is whether the Master does FEWER, more ACCURATE
trades than the workhorses. That comparison, over a clean week, is the real verdict — not any number I
can give you today.

## ONE THING THAT MATTERS MORE THAN THE CODE
This is a dress rehearsal. The strategies show a small positive intraday edge before fees — promising,
not proven, and the fee bite is real. Do not put money you need for rent or food into this on the
strength of a few good-looking days. Let it earn clean first. The engine is finally honest enough to
tell you the truth about itself; give it the week to do that.
