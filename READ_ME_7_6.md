# SILMARIL 7.6 — THE LAST-CLOSE LAW

Upload TWO files into `silmaril/execution/`, replacing what is there:

    paper_sim.py
    strategy_lab_abcd.py

Nothing else. No reset, no workflow change, no script to run.

## The bug

Your METAL and ENERGY books both read exactly **$10,000.00 / +0.00%** while holding
CPER at -3.5% and PALL at -3.5%. That was not a coincidence and not a rounding
artifact: those books were pricing every open position at **its own entry price**.

Chain of cause:

1. Out of session a price provider repeats the same closing print over and over.
2. `canon_keys` correctly collapses those repeats (`OUT_OF_HOURS_REPEAT`) so fake
   flat data cannot pollute rhythm and fingerprints. Good behaviour.
3. But the collapse leaves the symbol's newest timestamp hours old.
4. The mark builder trusts nothing older than 90 minutes, so it drops the symbol.
5. `PaperBook.equity()` and the position display both fell back to `p["entry"]`.

Pricing a holding at its own cost reports it as flat, forever. Every equity/ETF
book silently froze at cost basis after every 4pm close.

## The law

    a fresh mark prices a position
      -> failing that, its LAST KNOWN CLOSE prices it
        -> entry is NEVER a mark

Exactly how a broker statement marks an out-of-session holding.

## What changed

* `PaperBook.equity()` takes a carry-forward map and refuses to price at cost.
* `_run_side` builds that map from the raw tape for every held name.
* Position rows now carry `mark_is_carried` and `mark_stale_since`, so a carried
  price is visible rather than silently implying the position has not moved.
* The book funnel reports `marks_carried` — non-zero is normal out of session;
  non-zero DURING a session means that feed is down. It can never hide again.
* The MARKET-CLOSED branch had the same fault and worse: it reported
  `equity({})` (everything at entry) AND `positions: []`, so on every weekend and
  holiday three books showed themselves flat with nothing open while holding real
  risk. Now it marks at last close and lists what it actually holds.
* `strategy_lab_abcd._equity()` had the identical fallback. Hardened the same way
  (marks -> the position's own last mark -> entry as final backstop).

## Proof

    position: CPER 41.6854 @ entry 40.786883, last close 39.35

    entry-priced (the bug)   $6,700.22
    last-close (the fix)     $6,640.32
    fresh mark               $6,640.32     <- identical, as it must be

Your metal book was overstated by about $123 at the time of the 5pm backup.

## Regression

All 26 U-Z checks still pass. Fee law still exact: stock -0.070%, crypto -0.329%.
