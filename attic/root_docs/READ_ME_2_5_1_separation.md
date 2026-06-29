# SILMARIL 2.5.1 — Priority 1: Market Separation (crypto ≠ stock)

Drop on repo root, overwriting. This is the big one: crypto and stock no longer
share a champion, an arena, or learning. Touches no new alpha — it splits what
already existed by market.

## What it proves immediately

Running every existing MR variant on each universe *independently*:

- **Crypto arena** (54 names): best = **MR_patient_d3** (+0.78%/trade, 89 trades)
- **Stock arena** (534 names): best = **MR_d5_t3_s6** (+4.32%/trade, 68 trades)

Different champions, different parameters. Stocks want a **deeper 5% drop trigger**
and a **wider 6% stop** — crypto wants the opposite. Your thesis was right: these
are not the same edge, and they were never supposed to share a champion.

## What changed

- **`strategy_lab.run_split_leaderboards`** — runs each strategy on the crypto
  universe and the stock universe separately, emitting
  `strategy_leaderboard_crypto.json` and `strategy_leaderboard_stock.json`. Stock
  uses a market-hours-aware universe filter (the crypto 80%/24-7 bar would exclude
  every stock).
- **`champion_split.py`** — crypto champion stays **forward-survivability governed**
  (we have live crypto data → MR_d3_t3_s4). Stock champion is the **independent
  stock-arena winner** (MR_d5_t3_s6) as a *backtest hypothesis*, sticky so it won't
  flip-flop. Writes `champion_crypto.json` + `champion_stock.json`.
- **`paper_sim`** — the stock side now trades the **stock champion** (deeper trigger,
  wider stop) instead of the default params it was using. Crypto trades the crypto
  champion. Verified live: crypto=MR_d3_t3_s4, stock=MR_d5_t3_s6.
- **Command center** — the CRYPTO and STOCKS quadrants now show their *own*
  champions, not a shared one.

## Honest framing

The stock champion is **backtest-selected — a hypothesis, not a proven edge.**
Backtests have been mirages here before. The point of separation is that the stock
book will now accumulate its *own* forward sample under its *own* champion, and
stock survivability will judge it independently. Today's stock losses came from
trading *default* params; now it trades the stock-arena winner, but whether stock-MR
actually clears costs forward is still the open question — exactly the one 2.5.1 is
built to answer.

## 2.5.1 progress

DONE this drop: **P1 Market Separation** (independent arenas + champions + per-book
trading), and the P2 command-center quadrants now reflect it.

STILL OPEN for 2.5.1 (your sequence, no drift): P3 Exit Forensics (1/3/5/10/20-day
post-exit tracking + EXIT_QUALITY_REPORT), P4 Opportunity Audit (candidates
found/traded/rejected + reasons), P6 Regime intelligence, P7 champion history
timeline, P8 mobile-first, P10 health footer, P11 Vegas market clock, P15 scorecard.
We are **not** calling this 2.5.1 complete yet — separation is the foundation the
rest sits on, and it's now in.
