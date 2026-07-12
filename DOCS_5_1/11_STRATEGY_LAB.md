# 11 · THE STRATEGY LAB (A/B/C/D) — proving which discipline compounds

**The question:** your current engine wins often but idles — capital tied up in many small mean-reversion
bets. Does concentrating, recycling dead capital, and letting winners run actually compound faster? The Lab
answers this **forward, with real trades, without risking your live books.**

## The four sleeves (`strategy_lab_abcd.py` → `STRATEGY_LAB.json`, every cycle)
All four run the SAME entry signals on the SAME crypto universe. They differ ONLY in position management:

| Sleeve | Cap | Exit discipline | Answers |
|---|---|---|---|
| **A — FOREVER RIDE** | 10 | fixed target, ride to hit/stop | the control = your current live behavior |
| **B — CAP ONLY** | 5 | same fixed target | does concentration alone help? |
| **C — FULL DISCIPLINE** | 5 | 72h recycle (accept ~−0.3% to free capital) + let winners ride on MTF fast-green | concentrate + recycle + run winners |
| **D — SNIPER** | 2-3 | confidence-gated entries only, ride hard, 48h recycle | the full-prediction-stack sniper |

## How it's judged
- **Δ-vs-HODL and realized compounding — NOT win rate.** A sleeve that wins less often but compounds faster
  wins the Lab.
- Each sleeve is a real $10k paper book with an equity curve, drawdown, and closed-trade record.
- **Pre-registered kill (Law 15):** after 40 closed trades, any sleeve trailing A's Δ-vs-HODL is disproven
  for now. The winner is promotable to live — but only after it proves out.

## Why it's honest
The sleeves never touch your real books, never fund the Master, never enter championship. Pure measurement.
They exist so the machine — not enthusiasm — decides whether the discipline tweaks actually turn $10k into
more. The A/B/C/D table lives in the STRATEGY tab.

## The plan
Watch Δ-vs-HODL over ~2-3 weeks. If C or D beats A, you have *evidence* that discipline compounds — and a
proven sleeve to promote. If A wins, you've learned your current behavior was right, cheaply. Either way the
answer is real.
