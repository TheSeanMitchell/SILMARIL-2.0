# SILMARIL 7.2.2 — "THE INSPECTOR"
### I audited my own last release and found two capital leaks I shipped. Plus the auditor you asked for, which found them again from the outside.

**Battery: 125/125** on the full tree, a reset tree, and a simulated install over your 2 PM backup. Click path 9/9.

**Answer to your question first: DO NOT full-reset tonight. Run the surgical repair and roll into Monday.** Reasoning in §5.

---

## 1 · I SHIPPED TWO CAPITAL LEAKS YESTERDAY

You told me to audit with skepticism of my own work. The 7.2.1 fix that let thesis sleeves scan their own universe contained **two** money leaks, and they looked like unrelated symptoms:

**LEAK 1 — THE CAP GUARD.** The deep scan (120+ names) needed to stop once the position cap was full. I put that guard **after** `bk["cash"] -= budget` and simply `break`ed. Every cycle the sleeve deducted a budget for a position it never created.

**LEAK 2 — THE OVERWRITE.** `bk["positions"]` is keyed by **symbol**. The mean-reversion path filtered already-held names out of its pool; my new universe scanner did not. Buying a held name overwrote the live position and its capital vanished. `crypto:R` bought BONK and KSM twice and lost $5,000 that way.

Combined damage on your tree:

```
crypto:R   $3.55 cash + $3,291 positions   of a $10,000 book   →  $6,712 gone
crypto:S   $11.07 cash + $432 positions                        →  $9,568 gone
crypto:T   $3.57 cash + $139 positions                         →  $9,850 gone
                                                    TOTAL       $26,130
```

And here's the tell I would have missed without your instruction: `crypto:R` showed a **headline of −64.5% with a realized of +0.07%**. Two numbers that cannot both be right about the same book. That contradiction is what led me in.

**Fixed:** the cap is now checked **before** any money moves, using a live count; held names are excluded from the scanner; and there is a belt-and-braces refund guard at the position write itself. **Verified: all 80 sleeve-books now satisfy `cash + positions + vault − realized == starting equity` exactly, across 6 consecutive cycles.**

## 2 · THE INSPECTOR — the pattern-recognition auditor you asked for

`silmaril/execution/inspector.py`, running every cycle after the sleeves, publishing `INSPECTOR.json`.

The distinction that makes it worth having:

> **selftest** asks *"is each law still enforced?"* — 125 tests, isolated, synthetic, and all green while a sleeve took zero trades for three releases.
> **The INSPECTOR** asks *"does the RECORD look like a working system?"* — on real data, every cycle.

Nine checks, each one born from a failure that got past everything else:

| code | catches | incident it comes from |
|---|---|---|
| `SILENT_SLEEVE` | zero trades **and** zero refusals = disconnected, not picky | L/N/O/Q/R/S/T, 3 releases |
| `GOAL_MISS` | tape crossed target, no exit, no trail armed | "selling high is being ignored" |
| `LABEL_CONTRADICTION` | a BREAKEVEN_LOCK that books −3.64% | ONDO-USD |
| `IMPOSSIBLE_FILL` | a limit exit above its limit | the $242 PNUT windfall |
| `HEADLINE_SIGN_FLIP` | headline sign ≠ realized sign | my false "M is green" claim |
| `WINNER_TO_LOSER` | up >2%, closed negative | 17 of them |
| `FEED_COMB` | V-shaped round trips to the identical price | the five-month sawtooth |
| `STRUCTURE_PATTERN` | **which chart states preceded winners** | the steering signal |
| `STALE_STORE` | a panel reading a store nothing wrote | recurring |

**It found the leak from the outside**, independently of my code reading — `HEADLINE_SIGN_FLIP` flagged crypto:R/S/T with headlines of −64%/−95%/−96% against positive realized. That is the auditor doing exactly what you asked for on its first run.

**And the steering part already reads something on your 255 graded trades:**

```
entries at STRONG support     averaged +0.21%  vs  -1.34% at weak support   (n=100/155)
entries LIFTING OFF support   averaged -0.66%  vs  -2.05% falling into it   (n=83/30)
```

Both point the same way and both match how a person reads a chart: **buy strong levels, and wait for the turn.** That is a direction to investigate, not proof — it uses current structure rather than entry-time structure, and it says so in its own output.

## 3 · ARE WE SELLING WHEN WE HIT GOALS?

Audited every open position and all 290 closed trades against the tape:

```
crossed target & trail armed : 7      (MKR +9.09%, ANET +9.03%, FTNT +6.11% ...)
crossed target & NO trail    : 0      <- zero true misses
```

Capture by exit reason — and note which one is best:

| exit | n | mean got | mean peak | gave back |
|---|---|---|---|---|
| **CEILING_READ** | 4 | **+4.79%** | +5.07% | **0.28%** |
| TARGET | 21 | +3.47% | +4.13% | 0.67% |
| GIVEBACK_CAP | 41 | +1.79% | +3.35% | 1.55% |
| RIDE_TRAIL | 25 | +3.82% | +5.83% | 2.01% |
| RECYCLE_FLAT | 66 | −0.05% | +2.25% | 2.30% |
| STOP | 117 | −4.23% | +0.35% | 4.57% |

**`CEILING_READ` — the graph-reading exit — captures more and gives back least of anything in the system.** n=4, so it proves nothing yet, but it is the first sign that reading the chart beats a fixed number.

## 4 · MAKING THE FILLS REAL — the resting-order fix

Every exit was evaluated **only at the moment a cycle happened to look**. A real stop or limit sits in the book and fills when price *crosses* it. Measured across 44 governor exits, that gap cost **0.360% per exit**, and in the worst case turned a break-even lock into −3.64%.

Governor exits now walk the tape since the last cycle: if price crossed the level, fill **at the level**; if it gapped straight past, fill at the gapped print — **the worse of the two, because slippage is worn, never gifted.** Verified across four shapes including a no-cross case.

## 5 · SHOULD YOU RESET TONIGHT? — no, and here is why

```
closed sleeve trades on record : 290     <- a full reset destroys these
days since last wipe           : ~6/90   <- restarts at zero
books actually damaged         : 3 of 80
tape (price_samples.json)      : survives either way
```

**The damage is real but it is three books out of eighty, and it is repairable without touching a single trade record.** `scripts/repair_capital_leak.py` checks the invariant `cash + positions + vault − realized == start` and restores only the phantom deduction — every fill, entry, exit and realized P&L stays exactly as it was, because those numbers were honest. Verified on your pristine backup: **$26,130.38 restored across 3 books, then 0 imbalances across all 80 after 4 further cycles.**

A full reset would trade 290 closed trades and six days of clock to fix three ledgers. **My recommendation: run the repair, install, and roll into Monday** — when stock, metal and energy all open and you get the first cycle where all four books are live simultaneously. That is the test worth having, and it is 12 hours away.

*(Metals and energy: verified correct. At Sunday 21:41Z, XAU was open — 24/7 per CME — while XAG/XPT/BRENT/WTI were closed with the 24/5 window reopening at 22:00 UTC, 19 minutes later. Nothing is being wrongly blocked.)*

## 6 · WHY Q COMPOUNDER STILL WON'T TRADE — measured, not guessed

Applying your own one-line check: Q has **1 veto and 0 trades**, so it *is* being fed and *is* refusing. Its refusal is `not enough dip history to MEASURE a stop`. Across 113 crypto names with fingerprints:

```
cannot measure a stop yet : 69   (needs 5 completed dip→resolve excursions)
ratio < 2.0               : 35
ratio >= 2.0 (Q's bar)    :  3   <- SRM 15:1, APE 7.6:1, SPELL 4.3:1
```

**Q is not broken — it demands 2:1 and only 3 of 113 names currently offer it.** That is the sleeve working as designed on a 13-day tape. It will trade more as history accumulates; the retention fix (2,000→20,000 prints) is what makes that happen. I am deliberately not loosening its bar to manufacture activity.

---

## INSTALL (6 files + report)

```
silmaril/execution/inspector.py        (NEW)   silmaril/execution/strategy_lab_abcd.py
silmaril/execution/store_registry.py           silmaril/cli.py
scripts/repair_capital_leak.py         (NEW)   scripts/selftest_5_1.py
SILMARIL_7_2_2_RELEASE_REPORT.md  (root)
```

**Then run once:** `python scripts/repair_capital_leak.py docs/data --apply`

**Your new daily check is one file:** open `INSPECTOR.json`. Its `verdict` is either `CLEAN` or `ATTENTION — N critical/high`. If it says ATTENTION, the findings carry the evidence and the action.

## THE HONESTY CAVEAT

I shipped two capital leaks in a release I told you was verified, and they cost three books $26,130 of paper. The battery was green through all of it, because no test asked whether money that leaves the cash column arrives somewhere. That invariant now exists (T129) and the inspector checks it on live data every cycle.

The pattern is worth naming: **every one of my recent bugs has been a wiring error, not a logic error** — the graph never reaching decisions, the readers never reaching candidates, the cash never reaching a position. Unit tests are poor at wiring. That is precisely the gap the inspector is built to cover, and it earned its place by catching my leak on its first run.
