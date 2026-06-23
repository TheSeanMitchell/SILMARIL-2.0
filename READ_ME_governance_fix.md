# SILMARIL 2.5.1 — Priority #1 FIX: Champion governance mismatch (resolved)

One file changed: `silmaril/execution/champion.py`. This is the trust fix you flagged,
and it also upgrades what the crypto book trades tomorrow.

## The bug (exactly)
The champion-switch rule required the challenger to have **at least as many trades as
the incumbent**:

    chal["n"] >= max(inc["n"], CHAMPION_MIN_TRADES)

MR_d3_t3_s2 had 11 trades; MR_d3_t3_s4 had 14. So `11 >= 14` was False and the switch
was blocked — even though s2 beat s4 by **59 survivability points (81 vs 22)**. And
because the incumbent keeps trading, its count stays ahead forever: a permanent
deadlock that pinned a survivability-22 champion under a survivability-81 challenger.
That's why your governance file kept reading `aligned: FALSE` and "will converge next
cycle" never happened.

## The fix
The challenger now needs a **credible sample** (>= CHAMPION_MIN_TRADES) and a **decisive
margin** (>= 15 survivability points) — but NOT the incumbent's ever-growing trade
count. Survivability already penalises thin samples through its confidence interval, so
matching trade counts was a redundant gate that only created the deadlock. The 15-point
margin still prevents flip-flopping on noise (an 8-point lead would not switch).

## Verified result
After the fix, on your real data:
- Declared champion → **MR_d3_t3_s2**
- Reason → "promoted on survivability: MR_d3_t3_s2 81 > MR_d3_t3_s4 22 (evidence-driven)"
- Governance declared == most-survivable == MR_d3_t3_s2 → **ALIGNED: True**

The UI governance panel will now read aligned, and every other number regains its
credibility.

## Why this also improves tomorrow's results
The crypto book now trades MR_d3_t3_s2 instead of MR_d3_t3_s4:
  win rate     81.8%  vs  35.7%
  Sharpe       0.46   vs  -0.08
  max drawdown -2.99% vs  -14.33%
  OOS-consistent  yes  vs  no
Same family, but the evidence-superior member. Lower drawdown and a far higher win
rate is exactly the "drastic improvement" lever — trading the strategy the data already
says is best.

## Important guardrail (your overfitting concern, respected)
This changes WHICH strategy is champion, not HOW MUCH capital it gets. Both strategies
are still "Incubation" tier (small sample), so the capital tiers (10/25/50/100 trades)
keep allocation conservative regardless. We are NOT scaling capital — we're just making
the champion designation honest and routing trades to the better strategy. Full scaling
still waits for 50+ trades and multiple regimes, per your guidance.

## Everything else from your "build next" list is unchanged and deferred
No new strategies, no metals/energy build, no new signals. This is the single
trust-and-results fix for today. The rest (regime accuracy, intrabar-miss audit,
time-of-day, learning feedback, health matrix, mobile) stays queued for 2.5.3.
