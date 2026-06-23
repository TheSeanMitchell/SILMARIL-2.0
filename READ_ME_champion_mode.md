# SILMARIL ALPHA 2.14 — Champion Mode

Drop on the repo root. All compile. The learning loop is now closed.

## What champion mode does

Every cycle: leaderboard tests all 50 strategies → champion mode picks the one the
live sim trades → the sim trades it forward. The whole system finally points at one
number: the champion's forward P&L.

`champion.py` selects the champion with an **anti-overfit stability gate**:
- It remembers which strategy was the trusted leader each cycle (rolling window).
- A challenger only takes the crown if it has led in clearly MORE recent windows
  than the incumbent (a margin), AND currently has positive net edge on a real
  sample. Otherwise the champion holds.
- So the champion changes slowly, only when a strategy genuinely dominates across
  windows — the exact signal that separates real edge from a one-window fluke.

The sim now trades the champion's params (it reads `champion.json`), and the
cockpit shows a 👑 banner: who's champion, why, its backtest, and the challengers
on deck. Current champion on your data: **MR_patient_d3** (+0.96%/trade, 72 trades).

## Your questions, answered straight

**"Is the paper sim synthetic/fake data?"** No. The *prices* are 100% real —
from your live market feeds and real Binance candles via CCXT. The only thing
"simulated" is the *fill*: no real money, no order actually sent, but the fill
lands at the real market price minus a modeled fee. That is exactly what "paper
trading" means — Alpaca paper does the identical thing. **Real data, simulated
execution. Zero synthetic prices anywhere.**

**"Show both crypto accounts / is it just A/B crypto-vs-stocks?"** Right now the
cockpit is one crypto book (the champion) + one stock book. It is NOT mirroring
your two real Alpaca accounts (#2/#3) — those still live on the main dashboard.
But here's the better answer: the *leaderboard* already runs all 50 strategies
head-to-head (that's your real A/B, at scale), and champion mode promotes the
winner to trade forward. If you specifically want two crypto books racing forward
(say champion vs runner-up) on the cockpit, that's a small add — say the word and
I'll split the crypto side into Champion vs Challenger. The harvest-vs-hold
distinction from your old accounts is a momentum-era idea; competing strategy
configs is the more useful A/B now.

**"Did we ever weight the better agents? Does it matter anymore?"** Yes — we built
the learning loop (Alpha 2.1) that folded each agent's scorecard grade into its
vote weight. But here's the honest part: the mean-reversion strategy **doesn't use
the 39-agent debate at all.** It just buys oversold names. The agent weighting only
affects the OLD momentum/sentiment consensus path — the one we proved loses. So for
the path that might actually work, the agents aren't in the loop, and their
weighting no longer matters. We've effectively outgrown the agent-debate
architecture for crypto. That's not a criticism of the work — it's where the
evidence led. The agents are still there driving the legacy momentum path if you
ever want it, but I wouldn't invest more in them.

**"Best stat moving forward? Sit a week, then what?"** The one stat that matters
now: **does the champion hold positive net-of-fee edge across many fresh windows?**
Not one backtest — stability across your reset-and-run-3-days cycles. Watch two
things for ~1–2 weeks:
1. Does the champion stay mean-reversion and stay positive as windows roll? (Check
   the leaderboard + champion banner.) If a momentum strategy ever climbs to
   champion and holds, that's a regime worth knowing too.
2. Does the forward paper P&L roughly match the backtest, or decay? Decay = the
   backtest was optimistic (overfit/luck). Match = the edge is real.

**Then the decision tree:**
- **If it holds** (champion stable + positive across weeks): the next real test is
  execution cost. Move live paper to an exchange that lists the wide universe
  (Coinbase/Binance via CCXT) and measure *actual* fill costs vs the sim's
  assumption. That's the gap that decides real profitability.
- **If it decays or flip-flops**: the edge was noise. You'll know cleanly, and
  that's a real answer too — better than years of hoping.

Either way: nothing near real money until the champion proves itself forward for
months, not days. You already hold that line — keep holding it.

## Where to look

- `paper_sim.html` — cockpit, now with the 👑 champion banner.
- `strategy_leaderboard.html` — the 50-strategy field the champion is drawn from.

That's the full loop: test everything → crown the best → trade it forward → let the
forward number decide. Exactly what you asked for, with the overfit guardrail on.
