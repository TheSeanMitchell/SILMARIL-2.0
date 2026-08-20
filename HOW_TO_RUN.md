# 7.5 — restate every trade you have, in one move

## Upload TWO files

    scripts/restate_fees.py              -> into your repo's scripts/ folder
    .github/workflows/maintenance.yml    -> replaces the existing one

The daily run will NOT do this on its own. It is a one-time repair and it has its
own button, on purpose.

## Then run it — twice

**1. Dry run first (changes nothing).**

Actions tab -> Maintenance Toolbox -> if it says *Disabled*, click the `...` menu and
**Enable workflow** -> **Run workflow** ->

  * tool  = restate_fees
  * apply = false

Open the run and read the log. It prints before/after for every sleeve and the total.
Nothing is written.

**2. If the numbers look right, run it again with apply = true.**

That writes the corrected data and commits it. Your next Daily Run publishes the
corrected dashboard. You can disable Maintenance Toolbox again afterwards.

## Safety

  * Backs up STRATEGY_LAB.json to STRATEGY_LAB.json.pre_restate before writing.
  * Fully reversible: restore that file to undo.
  * Running it twice is harmless (the second pass re-prices the same trades to the
    same numbers) but there is no reason to.

## What it does

Re-prices EVERY closed trade at the real per-symbol venue cost, charged on BOTH
sides, then rebuilds cash and realized P&L from the corrected figures.

## What it is NOT

A re-simulation. The trades stay exactly as they happened; only the pricing is
corrected. It does NOT ask "would this trade still have triggered at the higher
fee?" - a bigger fee moves break-even and give-back thresholds, so a true replay
would produce a different set of trades and needs the whole tape re-run. That is a
separate job. This is what an accountant does when a fee schedule was misapplied:
same transactions, corrected pricing.

peak_equity and max_dd_pct are RESET to zero, because the historical equity path
cannot be recovered from trade records and inventing one would be a lie. You lose
your drawdown history. Everything else becomes honest.

## Expect the numbers to get worse

    BOOK      realized now     RESTATED
    crypto          -8,589      -30,466
    stock              -24         -624
    metal             +928         +100
    energy          +3,191       +2,736

Your two best sleeves barely move - stock E goes +6.74% -> +5.99%, energy B goes
+6.91% -> +6.60%. Those were real before and they are real after. Crypto loses more
than half. 40 of 104 sleeves stay profitable.
