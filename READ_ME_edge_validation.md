# SILMARIL — EDGE VALIDATION: the answer, measured

Three files, drop on the repo root. All compile. This is the first empirical
answer to "can this make money," run on 210,000 points of your own price history.

## The finding (net of 0.3% round-trip cost, 3 days, 628 names)

| Signal | What it is | Net edge @1h | t-stat |
|---|---|---|---|
| capitulation (1h < −5%) | buy a hard crash | **+2.86%** | +9.6 |
| falling knife (10m<−1% & 1h<−3%) | buy mid-drop | **+2.10%** | +11.7 |
| deep oversold (1h < −3%) | buy a dip | **+1.05%** | +12.7 |
| oversold (10m < −1%) | buy a small dip | **+0.66%** | +17.2 |
| persistence (10m>0 & 1h>0) | **what we trade** | **−0.36%** | −7.7 |
| momentum (10m > +1%) | **what we trade** | **−0.94%** | −13.7 |
| strong persist | the strongest momentum | **−1.16%** | −8.4 |

**Momentum has negative edge here. Mean reversion has strong positive edge.**
This universe, on this horizon, reverts: the harder a name just dropped, the more
it bounces; the harder it ran, the more it falls. SILMARIL trades the losing side
by design. That is now measured, with t-stats of ±14 over 200k samples — not a
hunch.

## What shipped

- **`silmaril/execution/edge_lab.py`** — the validation harness. No-lookahead
  forward-return test on the rolling price history; emits `edge_lab.json` with the
  net-of-cost edge and t-stat per signal, plus a one-line verdict. Runs every
  cycle. Edge capture is now the primary metric, measured automatically.
- **`silmaril/cli.py`** — calls edge_lab each cycle (logs the verdict).
- **`silmaril/analytics/api_health.py`** — FreeCryptoAPI added to the health
  matrix (100k/month, full-universe feed, key = secret `freecryptoapi_API_Key`).

## The three caveats that decide whether this is real money or a mirage

1. **3 days is ONE regime.** Mean reversion works until the market starts
   trending, then it flips to losing. Run edge_lab on a longer, full-universe
   history (this is what FreeCryptoAPI is for) before sizing anything. If it
   holds out-of-sample, it's real.
2. **Microstructure.** Part of a small-dip bounce on an illiquid coin is just the
   bid-ask spread oscillating — NOT capturable. The 0.3% cost assumed here is for
   liquid names; illiquid coins have 1–2% spreads that eat the edge. Trade this on
   LIQUID names only (BTC/ETH/SOL-class) — which is exactly the ~20 coins Alpaca
   already supports.
3. **The crash tail.** Most dips bounce; the occasional coin keeps falling −50%
   (rug, collapse) and one of those erases many small wins. Mean reversion is
   mandatory-stop territory: buy the dip, but cut hard if it drops another fixed
   amount. Without that stop the left tail kills you.

## The path that can actually make money (if it survives caveat #1)

Flip the engine: stop buying momentum, buy oversold/capitulation on liquid names,
hold ~1–4h for the bounce, hard stop for the tail. Verify on FreeCryptoAPI's
longer history first via edge_lab. This is promising and measured — but it is
"validated signal pending out-of-sample confirmation," not "guaranteed profit."
Most backtested edges die in live trading; this one has an unusually strong t-stat
and survives costs, which is the best starting point this project has had.
