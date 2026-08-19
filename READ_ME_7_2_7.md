# 7.2.7 — REAL VENUE FEES (the correction)

## What I got wrong

I audited your sleeves against `cost_of()` in `strategy_lab_abcd.py`, which returned
a flat **0.4%** round trip for every book. I treated that as your declared cost.

It wasn't. Your own `fee_model.py` — itemised, venue-routed, already written —
says the real round trip is:

    stock / metal / energy   0.068%   ($0 commission + measured spread + slippage)
    crypto                   0.325%   (Binance.US taker 0.10%/side + spread)

The equity books were being judged against a number **6x too high**. My conclusion
that "fast trading cannot pay at these costs" was true of the blanket, and false of
reality.

## What the same 2,403 trades say at the real cost

    energy   15 sleeves   +$2,739
    metal    15 sleeves     +$992
    stock    14 sleeves     +$625
    crypto   19 sleeves  -$16,836   <-- the entire loss, and then some

31 of 63 sleeves are profitable. The problem was never turnover. It was CRYPTO
turnover — where the fee is 5x the equity fee AND the gross edge is negative
(-0.22%/trade, t=-3.09) before any fee is charged at all.

## What this file changes

`cost_of()` now routes through `fee_model.py` per symbol and per book, and BOTH
sides are charged (entry pays half, exit pays half) as paper_sim has always done.

Effect vs what your dashboard shows today:
  * equity books get CHEAPER and more accurate (0.20% charged -> 0.070% real)
  * crypto gets slightly dearer and more accurate (0.30% -> 0.329% real)
  * the entry-side gap that made the workshop disagree with the funded books closes

## Install

Replace ONE file: `silmaril/execution/strategy_lab_abcd.py`

Do NOT install the older 7.2.6 patch — this supersedes it. If you already have
7.2.6, this file replaces it cleanly.
