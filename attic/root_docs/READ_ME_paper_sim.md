# SILMARIL ALPHA 2.12 — Internal Paper Sim (stocks + crypto, full universe)

Drop these on the repo root. All compile. This brings execution in-house so you
can paper-trade the WHOLE fresh universe every cycle — no Alpaca 20-coin cap.

## What you get

- **`silmaril/execution/paper_sim.py`** — two paper books ($10k each, like your
  real accounts): a STOCK side and a CRYPTO side. Each cycle it manages exits
  (bounce +2% / stop −4% / 4h timeout) and enters fresh oversold names, charging
  honest per-name fees. Persists `paper_book_stock.json` / `paper_book_crypto.json`
  and emits `paper_sim_live.json`.
- **`docs/paper_sim.html`** — the cockpit: both sides side-by-side, equity, P&L,
  open positions, recent trades, and the universe count (tradeable vs ghosts).
  Linked from the dashboard. Auto-refreshes.
- **`silmaril/cli.py`** — runs the sim every cycle.

On your 3-day data the crypto side ran **168 trades on 53 tradeable names**
(575 ghosts excluded), +0.24%/trade net, ending ~**+4% over 3 days** at 10%
sizing. The stock side: **0 trades** — read "Stocks" below, it's expected.

## "Excluding 577 ghosts" — what that means (you asked)

Of your ~628-name crypto universe, only ~53 actually trade tick-to-tick. The other
~575 are **stale**: the price sits frozen for long stretches, then jumps when it
finally updates. A backtest reads frozen→jump as "drop→bounce" and prints a
fantasy +2000%. But you can't fill an order at a frozen quote — by the time you
act, the real price is wherever it really is. So those names are **untradeable
ghosts**, and the sim excludes them. **This is not a bug to fix — it's the fix.**
Trading ghosts is trading noise; excluding them is what makes the number real. The
only "fix" is a better data feed with more genuinely-liquid names (see below), not
turning the ghosts back on.

## Stocks show 0 — why, and it's correct

Stocks don't trade 24/7. Your 3-day sample is mostly weekend, so stock prices are
frozen (market closed) and fail the freshness gate — exactly as they should. During
market hours the stock side will have fresh prices and trade. Also note: the
mean-reversion edge was proven on **crypto**, not stocks. The stock side is
exploratory until the sim shows it has its own edge — don't assume it does.

## The part I have to say plainly (please read this twice)

You said you want $100–300/day for food and life. I'm not going to dress this up,
because you trusting bad numbers for grocery money is the one outcome I most want
to avoid:

- The +4%/3-days is a **3-day backtest on one regime**, marginal (+0.24%/trade),
  and **mostly timeout-drift, not clean bounces**. It is NOT proof of income. It
  is a reason to *test further*, nothing more.
- A sim's P&L is only as honest as its fee/fill model. **Real fills add slippage,
  partial fills, latency and market impact** — the gap between sim and live is
  precisely where most retail systems that "worked on paper" fall apart. A clean
  sim result means "worth a real-money-prices test," never "this is a paycheck."
- **Running the sim many times on the same history does not build confidence — it
  builds overfitting.** Tuning until the curve looks good produces a strategy that
  fits the past and fails the future. The only real confidence comes from
  *forward* results on data the strategy has never seen.
- **Do not fund this with money you need for food.** Prove it in paper for weeks,
  then with tiny real money for months, before it's allowed near rent. I'd be
  failing you to say anything else.

None of that means stop. It means the sim is the right tool to find out *honestly*
and *fast* whether the edge is real — which is exactly what you wanted. Build it,
watch it forward, let the data decide.

## The roadmap you sketched (honest feasibility)

- **Fill the full universe into JSON + 1-year backfill.** Good instinct — more
  regimes beat 3 days. But the free APIs you listed are rate-capped hard (Alpha
  Vantage 25/day, FMP 250/day), so a year of *intraday* history across thousands
  of names is a real data-acquisition project, not a one-cycle job. Most realistic
  free path for crypto intraday history: **Binance klines** (generous, free, no
  key for public data) via **CCXT**. For stocks, daily history is easy; intraday
  for a year is the hard/expensive part.
- **More liquid crypto names to trade** (the real ghost fix): **Coinbase** or
  **Binance via CCXT** widen the genuinely-fresh universe well past Alpaca's 20.
- **Stocks execution**: **Public** or **Alpaca** both fine for paper; the universe
  isn't the stock constraint, market-hours + real edge are.
- **Learning / self-improvement (your 10/10 ask)**: the honest gap is that the
  system has been *measuring* signals that don't have edge. The fix isn't more
  automation — it's this sim as the loop: every strategy idea → backtest through
  the sim on fresh data → keep only what clears fees forward. That IS the learning
  engine. I can wire a "strategy leaderboard" that ranks every variant by forward
  sim P&L next, so the system self-selects the best one over time.

Install it, let it run a few days during market hours too, and watch
`paper_sim.html`. The crypto side will trade; the stock side will start trading
when markets open. Then we read the forward numbers together — honestly.
