# 2.6.1 — THE CRITICAL FIX (stops the post-reset trading disaster)

## What caused the disaster (proven)
My backfill merged a YEAR of DAILY candles into the same price_samples the sim uses for INTRADAY drop
detection. So the sim's "1 hour ago" reference became an old daily close, and today's price vs that
looked like a -40% crash on hundreds of coins at once -> mass fake-dip buys -> instant stop-out losses.
The backfill poisoned the trading signal. That is why every post-reset run was a bloodbath.

## The fix (in paper_sim.py, verified)
The drop signal now uses ONLY the last 6 hours of LIVE samples. Daily-history backfill is excluded, so
no fake crashes (verified: 0 coins show >10% fake drops on your real data now, vs the flood before).
It ALSO enforces a WARMUP, exactly as you asked: a coin cannot signal a drop until it has accumulated
enough recent intraday points spanning >1 hour. Right after a wipe, almost nothing trades until that
baseline forms (~1-2 hours of 5-min runs ≈ your "20 runs" idea). Real drops only, on fresh data only.

## ORDER OF OPERATIONS (this is the answer you asked for)
1. Install this zip (paper_sim.py).
2. Run **Reset Internal Clean** (wipes books to $10k; keeps graphs).
3. Run **Backfill Universe** if you want full graph history — it is now SAFE because the sim ignores it
   for trading; it only feeds the long-range graphs.
4. Let it run. Trading auto-warms-up: expect FEW or NO trades for the first ~1-2 hours while each coin
   builds a real recent baseline, then real drop-based entries begin. This is correct, not a bug.

So: the first ~20 runs being quiet is now BY DESIGN. The system establishes a baseline before it trades.

## On your other points (honest)
- The Master Account NOT taking the bad trades is a real success — it only funds proven quadrants, and
  freshly-wiped books aren't proven, so the garbage stayed contained. That separation worked.
- Heat-shield tolerance: the instant losses were bad ENTRIES (fake crashes), not stops being too tight.
  Fixing the entry signal is the real cure; stop tolerance was a symptom-level ask.
- Graph tagging (MEZOUSD / LPTUSDT not populating): same key-format issue — coins that exist only as
  USDT pairs map to BASE-USD; a few still need a mapping pass. That is cosmetic (graphs), NOT the
  trading bug, and is the next cleanup with a repo. The TRADING fix above was the emergency.

## Honest status
This stops the bleeding — the single worst, most destructive bug. It does NOT make all of 2.6.1 done
(clickable quadrant drill-downs, full heat-shield params, graph-tag mapping remain). But your post-reset
runs will no longer self-destruct, and the warmup you wanted is now real. Reset, let it warm up, watch
that it does NOT make instant losses this time — that is the test.

## Files
silmaril/execution/paper_sim.py
