# SILMARIL ALPHA 2.11 — the mean-reversion FLIP (crypto)

Four files, drop on the repo root. All compile. This is the actual strategy
change — not measurement. The crypto engine now buys weakness instead of strength.

## What changed (and why)

edge_lab proved, on 200k+ points of your own data, that momentum LOSES here
(−0.94%/trade, t=−14) and oversold BOUNCES. So in mean-reversion mode the crypto
side flips:

- **`mean_reversion.py`** (new) — the strategy brain: `select_oversold` (liquid
  crypto names down ≥2% on the hour, ranked by depth), `mean_reversion_exit`
  (bounce +2% / hard stop −4% / 4h timeout), and a `backtest` that reports the
  honest liquid-vs-mirage edge.
- **`leaned_in_router.py`** — in MR mode the crypto pool is REPLACED with oversold
  liquid names (momentum crypto dropped), the fresh gate runs on stocks only
  (a falling crypto name is now what we want), and crypto is ranked by drop depth.
- **`alpaca_paper.py`** — a mean-reversion exit runs first for liquid crypto: bank
  the bounce, cut the falling knife, or time out.
- **`cli.py`** — writes `mean_reversion.json` every cycle so you watch the live
  edge confirm or die.

Stocks are untouched — this is a crypto-universe finding. Flip off any time with
`SILMARIL_MEAN_REVERSION=0`.

## The honest truth — read this before you get your hopes up

I have to be blunt, because pretending otherwise is the thing you're sick of:

1. **The +1384% backtest was a MIRAGE.** It was bid-ask spread bounce on illiquid
   coins — a "drop then bounce" you cannot capture once you pay their spread. On
   the liquid names Alpaca actually trades, with realistic cost, that gain nearly
   vanishes.
2. **On liquid names the edge is MARGINAL: +0.53%/trade, and 28 of 36 backtest
   exits were timeouts** — meaning most of the "edge" is small drift, not clean
   bounces. It's also threshold-sensitive (shallower dips LOSE) and from a 3-day
   window. That is the profile of something that could easily be noise.
3. **So expect roughly FLAT, not a fix.** This flip is worth running because the
   live paper result IS the out-of-sample test — the one thing that tells you if
   the marginal edge is real. It is NOT a proven path to $100/day. If anyone
   (including me) told you otherwise, that would be the false hope again.

What you now KNOW, for certain: momentum is dead, and the only price-signal edge
in your data lives in coins you can't trade. That is real, hard-won knowledge.

## Your questions, answered

- **TradingView** — you don't need to give me anything. There's no clean API path
  to wire it into SILMARIL. Its value is a MANUAL cross-check: rewrite the
  oversold-bounce rule in Pine and backtest it on their history. If TradingView
  and `mean_reversion.json` agree, that's two independent confirmations. Optional.
- **More API codes?** No. FreeCryptoAPI (full-universe validation) + Alpaca
  (liquid execution) is everything this test needs.
- **An Alpaca alternative to test this?** Not yet — and here's the lucky part:
  Alpaca only trades the ~20 liquid names, which is EXACTLY the honest test
  universe. Running this flip on Alpaca automatically tests the liquid edge and
  nothing else. A full-universe broker (Coinbase) only matters LATER, if the
  liquid edge holds and you want to chase mid-cap reversion with real spreads.

## Sequencing

1. Install these 4 files. Let it run a few days. Watch `mean_reversion.json` and
   the actual Alpaca P&L on the liquid names.
2. THEN pristine-reset to start the MR test from a clean $10k. (Resetting BEFORE
   the flip just reproduces the momentum losses — pointless. After the flip, a
   clean baseline makes the out-of-sample read honest.)
3. Decide on the data: if liquid MR is clearly positive over a week+, it's real —
   push it. If it's flat/negative, you've got your answer, cleanly, and the move
   is to stop pouring effort into price-signal trading on liquid crypto.
