# 2.6.1 — clickable quadrant decision portals (the window into the brain)

Every quadrant card (CRYPTO / STOCKS / METALS / ENERGY) is now CLICKABLE. Click one and a modal opens
showing that quadrant's actual thinking, from data it already produces:
- OPEN POSITIONS — ticker, qty, entry, cost
- DECISION TREE — market mode, deployment pressure, and the ranked opportunities it is weighing right
  now WITH the reason/score for each (why it picks what it picks), from conviction_ranking.json
- RECENT EXITS — why trades closed (exit-reason breakdown + per-trade), from DECISION_TRACE.json
- ACCEPT / REJECT LEDGER — counts by category, from decision_ledger.json
- TRADE HISTORY — last 25 fills with side / price / pnl / time

This is the first of the three things you named: clicking into each quadrant's portfolio + decision tree.
It uses data the engine ALREADY writes, so it reflects real thinking, not mock-ups.

## Install
Drop in (docs/index.html). Click any quadrant card.

## Honest scope
This delivers the QUADRANT decision visibility. Still remaining and NOT done: the Master Account
feed/decision-tree laid out as its own organic display, the full investor-grade UI overhaul, and plotting
every prediction line on the price charts. Those are the next builds. I won't call 2.6.1 finished — but
you can now see, per quadrant, exactly what it holds, what it's considering, why, and how every trade
closed. That's a real window into the brain.

## Files
docs/index.html
