# 7.5 — restate every trade you have, in one move

Upload `scripts/restate_fees.py` into your repo's `scripts/` folder.

Then: Actions -> Maintenance Toolbox -> Run workflow. (Or if you ever open a
terminal: `python scripts/restate_fees.py --write`)

It backs up STRATEGY_LAB.json to STRATEGY_LAB.json.pre_restate first. Nothing is
lost and it is reversible.

## What it does
Re-prices EVERY closed trade you have at the real per-symbol venue cost, charged on
both sides, and rebuilds cash + realized P&L from the corrected numbers. One pass,
whole history.

## What it is NOT
A re-simulation. The trades stay as they happened; only the pricing is corrected. It
does not ask "would this trade still have triggered at the higher fee?" — that would
need the whole tape replayed and would produce a different set of trades. This is
what an accountant does when a fee schedule was misapplied: same transactions,
corrected pricing.

peak_equity and max_dd are RESET, because the historical equity path cannot be
recovered from trade records and inventing one would be a lie.
