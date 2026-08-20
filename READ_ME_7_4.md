# SILMARIL 7.4 — every book gets its own NULL

**ONE file. Upload `silmaril/execution/strategy_lab_abcd.py`, replacing what's there.**

## The bug

`delta_vs_hodl` was hard-gated to `book == "crypto"`. That is why your champion
cards read:

    CRYPTO  F   +7.176%   d vs null -8.436%
    STOCK   D   +7.895%   d vs null ---
    METAL   I   +5.354%   d vs null ---
    ENERGY  B   +5.783%   d vs null ---

Three of four books printed a DASH where the only number that matters belongs.
Crypto was measured against a 50/50 BTC-ETH hold; the other three were never
measured against anything at all.

## What it should say (measured on your real tape, since the 03 Aug epoch)

    CRYPTO  F   +7.18%  vs null +3.96%  =  +3.21 pts   BEATING
    STOCK   D   +7.89%  vs null +1.42%  =  +6.48 pts   BEATING
    METAL   I   +5.35%  vs null +4.57%  =  +0.78 pts   BEATING
    ENERGY  B   +5.78%  vs null +3.42%  =  +2.36 pts   BEATING

All four champions beat doing nothing. Stock D by 6.5 points.

## Why crypto's old -8.436% was misleading too

That compared a CRYPTO SLEEVE to a 50/50 BTC-ETH hold (+15.6%). But the sleeves
trade 79 alt-coins, not BTC and ETH. Held equally, that actual universe returned
+3.96%. Judging an alt-coin sleeve against BTC/ETH is judging a bus driver on lap
times. Both numbers now ship: crypto keeps its published BTC-ETH null AND every
book gets a null built from its own universe.

## Fees are not charged on the null - on purpose

Doing nothing costs nothing. That makes the null the harder, honest bar.

## What to watch now

The `d vs null` column, per sleeve, on the STRATEGY page. Positive = the sleeve is
earning its keep. Negative = you would have done better asleep. That one column is
how you tell a real sleeve from a rising tide, and it now works for all 104.
