# SILMARIL 2.5.1 — Critical fix: quadrants were invisible (function never called)

The four-book quadrant code WAS in the HTML, but `renderQuadrants()` was defined and
never invoked. So metal/energy rendered to a div that no one was calling.

**Fixed:** added `safe(()=>renderQuadrants(),'quadrants');` to the load cycle (line 183).

Now when the page loads:
- The COMMAND tab shows four equal color-coded quadrants (CRYPTO amber, STOCKS blue,
  METALS silver, ENERGY green).
- All four start at their equity ($10k for metals/energy if you just reset, current P&L
  for crypto/stock), zero to current open positions, champion (or None if awaiting feed),
  and status (TRADING or READY · awaiting data feed).
- They're all prominent and equal — none muted, 4-up grid (2×2 on phone).

If you ran "Pristine Reset" earlier, the paper_sim_live.json will show:
  crypto:  $10,076 (lived a bit)
  stock:   $9,750  (lived a bit)
  metal:   $10,000 (clean reset, no feed yet)
  energy:  $10,000 (clean reset, no feed yet)

All will display correctly now.

Drop this on repo root. The only file that changed is docs/index.html and docs/cockpit.html
(one-line addition to call the render function). Sorry for the miss — the code was there, 
just not wired.
