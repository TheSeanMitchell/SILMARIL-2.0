# SILMARIL 7.2.5 — "RESET & OPERATIONS"
### First: your numbers are not bogus. Second: the $26,130 was mine, not yours. Third: here is the manual you should have had months ago.

**Battery: 127/127** on the full tree, a tree reset with the updated script, and a simulated install over your 4 PM backup. Click path 9/9.

---

## 1 · YOUR TOP SLEEVES ARE REAL — I checked before writing anything else

You said you were assuming this is all bogus. It is not. Audited against your books:

| book | equity | **banked (real money)** | at-risk marks | % real |
|---|---|---|---|---|
| crypto **R SUPPORT READER** | $10,285.65 | **+$279.29** | +$6.36 | **98%** |
| metal **B CAP ONLY** | $10,150.55 | **+$145.91** | +$4.64 | **97%** |
| energy **T CEILING READER** | $10,018.18 | **+$18.18** (already vaulted) | $0 | **100%** |
| stock **E ADAPTIVE STRIKER** | $10,480.72 | +$102.83 | +$377.89 | 21% |

**Three of your four leaders are almost entirely realized, fee-paid money.** Only stock:E is mostly open marks — and that is the one I have been careful to flag every time.

**Your repair worked.** 0 of 80 books have a broken capital identity, and `CAPITAL_REPAIR.jsonl` is on disk. That is done and does not need revisiting.

## 2 · THE $26,130 — you were right to be confused, and it was my fault

You never asked about it. **It was a bug I introduced on August 1**, found while auditing my own work on August 2, and reported to you. Two capital leaks in one change of mine: a guard that deducted money for positions it then never created, and a scanner that let a book buy a name it already held, overwriting the old position. It damaged three crypto sleeve books on paper.

You have now repaired it, it is closed, and there is a tripwire (T129) that fails the battery if money ever leaves a book without arriving somewhere. **It is finished. Nothing further is required from you on that.**

I should have led that report with "this is a bug I made yesterday" instead of a dollar figure with no context. That is on me.

## 3 · HOW WE GOT HERE WITH SCRIPTS THAT COULD NOT RUN

Your question deserves a direct answer. Those scripts were written for a developer with a terminal — `python scripts/x.py` — and I wrote them that way out of habit, then wrote "run this once" in a report without ever checking that you *could*. You deploy exclusively by drag-and-drop. There was no workflow, so there was no way.

It went unnoticed because **nothing tested it.** The battery tested that each script's *logic* was correct in isolation. Nothing asked whether the script was *reachable*. That is the same failure mode as every other bug I have shipped recently: the parts were right and the wiring between them was missing.

**T131 now fails the battery if any operator-facing script has no workflow.** When I wrote it, it immediately found fourteen more.

## 4 · THE RESET SCRIPT — updated and verified on your data

Two changes:

**It now protects permanent records.** `HARVEST_LEDGER.jsonl`, `CAPITAL_REPAIR.jsonl` and `CANON_MIGRATIONS.jsonl` are added to the never-sweep set. A reset restarts the *books*; it does not un-happen a harvest or a repair.

**It now says what it did, in plain English.** Run on a copy of your tree:

```
WHAT THIS RESET DID
  RESTARTED AT $10,000: the four books, all 20 sleeves each, the Master,
                        every open position and closed-trade record
  KEPT:                 price_samples.json (20.8 MB), ccxt_samples.json (8.4 MB),
                        fingerprints, chart history, every knob, permanent ledgers
  REBUILDS ITSELF:      GRAPH_READ, PRICE_TRUTH, WARM_START, SLEEVE_VETOES,
                        INSPECTOR, HARVEST — next Daily Run, nothing to do
  WHAT TO EXPECT:       cycle 1 seeds each book's opening sleeve from real tape;
                        sleeves start trading; the four FUNDED books stay quiet
                        until a sleeve earns 3 real closes — that is the law working
```

**Verified end-to-end:** reset a copy of your tree → 127/127 tripwires still green → one Daily Run → **45 crypto sleeve positions open in the first cycle.** It comes back to life immediately.

## 5 · THE WORKFLOW AUDIT — it is already correct

I checked all fourteen. **Exactly four things run on a schedule:**

```
Daily Run          */10 * * * *      WRITES  <- the only scheduled writer, by law
Selftest           45 3 * * *        read-only
Verify Install     15 4 * * 1        read-only
Weekly Backup      0 0 * * 0         archive only
```

Every other workflow is manual-only with no cron. **The one-writer law holds.** If you ever see a fifth thing running on a timer, that is a bug — tell me.

## 6 · `OPERATIONS.md` — the manual

Six sections, written to be kept open on reset day:
- **the six-step reset** (install → daily run → selftest → reset → daily run → confirm)
- **every workflow**, what it does, and how often it should run
- **the maintenance toolbox**, tool by tool, and which need `apply: true`
- **the schedule you should see** in the Actions tab on a normal day, with the four red flags
- **the five-minute daily loop**
- **what I would delete** to simplify the menu

On automation, the honest answer is in Part 6 of that document: **the engine already needs nothing from you.** The complexity you feel is not in the running, it is in the watching — and that part is now carried by the one-writer law, the inspector, the capital invariant, the realized/unrealized split, and T131, rather than by your attention.

---

## INSTALL (4 files)

```
scripts/reset_internal_clean.py          (updated: protects ledgers, explains itself)
scripts/selftest_5_1.py                  (127 tripwires)
silmaril/execution/store_registry.py
OPERATIONS.md                     (NEW)  <- keep this one open
```

**Then, when you want to reset: follow Part 1 of `OPERATIONS.md`. Six steps.** You do not need to run any script by hand first — your capital repair is already done.

## THE HONESTY CAVEAT

Nothing here adds trading capability. It makes the system operable by you rather than by someone with a terminal, and it tells you the truth about what a reset does instead of leaving you to infer it.

And the thing worth holding onto from this audit: **you have $279 banked in crypto, $146 in metal, and $18 vaulted in energy — on realized, fee-paid money, on a clean tape, with the capital identity balancing across all 80 books.** That is the first time in this project that sentence has been true. It is small and it is unproven over 90 days. It is not bogus.
