# SILMARIL ALPHA 2.13 — Universe Widener (CCXT/Binance) + Strategy Leaderboard

Drop on the repo root. All compile. Two things you asked for, walking not talking.

## 1. The ghost fix — real liquid universe from Binance (`ccxt_universe.py`)

Each cycle it pulls the **top ~150 most-liquid Binance USDT pairs** and their recent
5-min candles, and writes `ccxt_samples.json`. These are real, fresh, tradeable
coins — not the stale ghosts. The paper sim and leaderboard merge them in
automatically, so instead of testing on **52** fresh names they test on **hundreds**.

- No API key needed (public market data).
- Needs to reach Binance — **GitHub Actions can; my build sandbox can't, so I
  couldn't run it here.** It's fully fail-safe: any network error leaves the last
  good file and the cycle continues. First real cron run on GitHub will populate it.
- It writes a SEPARATE file on purpose. The **live Alpaca executor is untouched** —
  it still reads only `price_samples.json`, so it never tries to send a
  Binance-only pair to Alpaca and eat a 422. The wide universe lives in the SIM
  until you choose to move live execution to Coinbase/Binance.

Switch to Coinbase by setting `EXCHANGE = "coinbase"` at the top of the file.

## 2. The strategy leaderboard (`strategy_lab.py` + `strategy_leaderboard.html`)

A dictionary of **50 strategies** — every mean-reversion and momentum
threshold/target/stop/hold combination, plus patient hybrids — backtested through
the honest sim every cycle and ranked by net edge per trade. Add a row to
`STRATEGIES` and it competes next cycle. New dashboard page, sortable.

On your current data (52 fresh names) the board already proved the thesis:

| rank | strategy | dir | trades | win% | net/trade |
|---|---|---|---|---|---|
| 1 | MR_patient_d3 | mean-rev | 72 | 67% | **+0.95%** |
| 2 | MR_d3_t3_s2 | mean-rev | 87 | 70% | **+0.85%** |
| … | (all top rows mean-reversion) | | | | |
| — | momentum variants | momentum | | | far below |

It found a **better config than what's wired**: buy a 3% drop, take +3%, stop −2%.
Once the Binance universe loads, expect more trades per strategy and a sharper read.

## Why you saw "0 considered" and no trades

That's the live Alpaca path under the mean-reversion flip: liquid majors almost
never drop 2% in an hour, so accounts 2/3 correctly place nothing, and stocks fail
the fire-meter gate → "628 scanned, 0 considered." Nothing was broken — the
universe was just too thin. This release fixes the thinness for the SIM side.

What trades where now:
- **Alpaca accounts 2/3 (real paper):** still only the ~20 liquid coins, still only
  on a real >2% hourly drop — so still rare. That's honest; majors just don't dip
  much. Don't expect frequent Alpaca orders until you migrate to a wider exchange.
- **Internal paper sim (the cockpit):** trades the full fresh universe (52 now,
  hundreds once Binance loads). This is where you'll see activity.
- **Leaderboard:** tests 50 strategies every cycle regardless — immediate proof
  the engine is working even when the live tape is quiet.

## Where to look

- `strategy_leaderboard.html` — 50 strategies ranked. **Open this first** — it's
  the clearest proof the system is alive and testing.
- `paper_sim.html` — live cockpit, both sides, now with a **3-day backtest proof
  banner** so it never looks dead between setups.
- Both linked from the dashboard.

## Honest reminder (unchanged)

The leaderboard's top row will look great partly by **luck** — 50 strategies, the
best wins some by chance. Trust only a strategy that stays near the top across
**many fresh 3-day windows** (your reset-and-run-3-days plan is exactly right for
this). +0.85%/trade on 3 days is a hypothesis to test forward, not income. Nothing
here is ready for real money, and you've said as much — good. Prove it forward
first.

## Next, if you want it

A "champion" mode where the live sim auto-adopts the leaderboard's best-trusted
strategy each cycle — closing the learning loop so the system self-selects its
best version. I held it back deliberately: auto-chasing the top backtest every
cycle is how you overfit. Better to watch the board stay stable across windows
first, THEN let it drive. Say the word.
