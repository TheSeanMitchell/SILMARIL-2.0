# SILMARIL 9 — THE LADDER — THE REGISTRATION

registration-hash: d6ebfac647c082b8

Frozen on 8 November 2026, before the history replay was run for the first time.
`ladder/config.py` holds the same rules as numbers; `scripts/test_ladder.py` fails if the
two ever disagree. Changing a number is a re-registration: a new hash, written here, on purpose.

## The ladder

| level | what it is | its do-nothing twin |
|---|---|---|
| **Sleeves** (16) | four per category: HOLD, TREND, MOMENTUM, VOLTARGET | HOLD *is* the twin |
| **Category accounts** (4) | crypto (BTC, ETH) · stocks (SPY, QQQ) · metals (GLD, SLV) · energy (XLE, USO). Each holds the average of its TREND, MOMENTUM and VOLTARGET sleeves | the category's HOLD sleeve |
| **Master** (1) | holds the two category accounts whose own track records are rising fastest, half each, only while they beat T-bills | equal-weight hold of all 8 assets; SPY hold |

Idle money in every account sits in T-bills (BIL), so cash earns what cash really earns.

## The sleeves

* **HOLD** — 50/50 of the two assets on day one; never trades again.
* **TREND** — monthly. Each asset holds its half while its close is above its 200-day average; otherwise that half sits in T-bills. (Faber, 2007.)
* **MOMENTUM** — monthly. Holds the one asset with the best blended 1/3/6-month return, only if it beats T-bills over the same windows; a 1-point margin keeps the incumbent. Checked daily for a fast exit. (Moskowitz, Ooi and Pedersen, 2012; Antonacci, 2014.)
* **VOLTARGET** — monthly. The 50/50 basket, sized so its last-63-day volatility is about 15% a year, the rest in T-bills; resized only when the size moves by more than 10 points. (Moreira and Muir, 2017.)

## Execution

* Every decision for day D reads closes up to day D−1 only. Fills happen at the close of day D. All legs of a rebalance fill on the same day.
* Round-trip costs: crypto 0.8% (0.4% a side: Kraken Pro retail taker tier plus spread), ETFs 0.1% (commission-free plus spread and slippage, about 2× what is measured), T-bills free.
* Prices are adjusted closes (splits and dividends included) for holdings and benchmarks alike.
* Trades smaller than 1% of an account are skipped, except full exits.

## What is deliberately absent

* **No governor that can lock the system out forever.** The 7.x governor halted every book on 9 September 2026 and had no way back. Here risk control lives inside the rules, which step aside and step back in by themselves.
* **No resets.** The epoch is 9 November 2026. The system is rebuilt from prices on every run, so a missed run, failed push or crashed runner loses nothing.
* **No hidden state.** Each day's values are written to an append-only record; any later recomputation that disagrees by more than a cent is shown in red as DRIFT.

## The verdict, stated before the data

* Horizon: 104 weeks from the epoch. Progress shown every 13 weeks; no verdict is read before week 104.
* **Pass:** the master beats the equal-weight hold of all 8 assets after costs, with a smaller worst drawdown.
* Expectation from the replay (May 2019 to November 2026, run once, untuned): the master grew about 16% a year with a worst drop of about −41%. Equal-weight holding grew about 22% a year with a worst drop of about −61%. SPY grew about 15% a year with a worst drop of about −34%. **The rules bought smaller drops, not more money.** The forward test asks whether that holds.
* P($1,000 a month on $10,000): about zero. No rule here pursues it.
