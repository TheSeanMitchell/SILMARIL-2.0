# SILMARIL 7.1.7 — "THE WARM START"
### Why every reset cost you days, measured on a real reset. Three separate waits found; two of them removed.

**Battery: 120/120** on the full tree, a genuinely reset tree, and a simulated install over your 8:30 AM backup. Click path 9/9. **Measured on an actual reset of your data — the numbers below are observations, not estimates.**

---

## WHAT A RESET ACTUALLY COST YOU — three waits, not one

I ran a real reset on your tree and instrumented every stage. There were **three** independent delays stacked on top of each other, and I had only ever been looking at the third.

### Wait 1 — a hardcoded 120-minute total blackout ⛔ *the big one, and nobody knew*

```python
QUIET_AFTER_WIPE_MIN = 120.0
if quiet_left > 0:
    marks = {}      # the engine sees NOTHING for two hours
```

After the reset, every book reported `seen=0`. Not "no candidates" — **no universe at all.** For two hours the engine is blind by construction.

That code was written for a world where a wipe cleared the **tape** too, and you genuinely cannot trade honestly on an empty tape. **That world no longer exists.** `price_samples.json` is LEARNING-class and survives every wipe by design — the moment after a reset you already hold weeks of real prices and fitted fingerprints. Sitting blind on top of a full tape is not caution, it is delay.

**Now:** the blackout lifts early when *both* are true — enough names already satisfy the warmup rule on the surviving tape, **and** the warm start has seeded the books from real evidence. Either one missing and the full window is served, unchanged.

### Wait 2 — the PROVISIONAL seed was a coin flip 🎲 *and it was invisible*

`sleeve_promotion` picks the provisional sleeve by forward score. Right after a wipe every sleeve has zero closes — so I assumed `_score` returned `None` and wired the warm start behind `if seed is None`. Running the reset proved me wrong:

```
_score({closed: 0, delta_vs_hodl: 0.0})  →  0.0        ← not None
```

A freshly wiped sleeve carries `delta_vs_hodl: 0.0`, so **every** sleeve scored 0.0, `seed` landed on whichever sorted first, and my warm start was wired in and **silently never fired**. The book then waited days for whichever sleeve happened to close three trades first — good or bad. The condition is now "has any sleeve actually CLOSED a trade", which is what I meant all along.

*(This is exactly the class of bug that only a real run catches. A source review would have passed it.)*

### Wait 3 — the arming gate ✅ *this one is correct and stays*

Three real forward closes with positive edge before a book may open. **Untouched.** Nothing in this release lets a book trade sooner — it only ensures the wait is spent running the most promising personality instead of a stranger.

---

## THE MEASURED RESULT

A clean reset of your tree, then **one cycle**:

```
marks state: READY after wipe — 662 names already warm on the surviving tape and every book
             seeded from backtest; blackout skipped (119 min would have remained)

           BEFORE (7.1.6)          AFTER (7.1.7)
crypto     seen=0                  seen=183  warm=174   42 sleeve positions open
stock      seen=0                  seen=512  warm=470   34 sleeve positions open
metal      seen=0                  seen=12   warm=12
energy     seen=0                  seen=6    warm=6

seed       coin flip (all 0.0)     crypto→G  stock→I  metal→A  energy→A
                                   source: warm_start (backtest on each book's own tape)
```

**119 of 120 blind minutes eliminated, and 76 sleeve positions open in the first cycle** where before there were zero and the engine could not even see the universe.

---

## THE WARM START ITSELF — and what it refuses to do

`warm_start.py` answers one question from real stored tape: *which sleeve personality would have done best on this book's own names over the last 30 days, and how quickly did it resolve trades?* It runs in **~1.5 seconds**.

**The hard limits are the point of the design, more than the recommendation is:**

1. **It writes no trade. Ever.** `LAB_OUTCOMES.jsonl` and every evidence ledger are untouched — verified by a tripwire that snapshots the directory before and after and asserts the only new file is `WARM_START.json`.
2. **It arms no book.** Three real forward closes still stand between a seed and a funded fill.
3. **It counts toward nothing.** The 100-trade / 90-day clock cannot see the file.
4. **It selects between existing personalities; it never edits a sleeve** (Law 6).
5. **Its backtest obeys the same fill laws as the live engine** — a limit cannot overfill, a stop takes the worse of trigger and mark, sessions are never walked as one series, and open positions are marked rather than discarded (no survivorship).
6. **Killable** — `warm_start {mode: "off"}` and the old behaviour returns exactly.

Every row is stamped `evidence_class: "BACKTEST_HYPOTHESIS"`. A backtest is a claim about the past; its only power here is choosing where to start.

## WHAT IT FOUND ON YOUR TAPE — read this part

```
stock   → VOLATILITY HUNTER   Δ-null +0.1361%/trade   80.0% win   15 trades   ETA ~144h
crypto  → GEOMETRY SNIPER     Δ-null -0.1018%/trade   59.0% win  139 trades   ETA ~16h
metal   → FOREVER RIDE        Δ-null -0.0886%/trade   53.8% win   52 trades   ETA ~42h
energy  → FOREVER RIDE        Δ-null -0.4856%/trade   55.8% win   43 trades   ETA ~50h
```

**Only the stock book shows a positive edge over doing nothing.** Crypto, metal and energy are negative across *every* personality tested. That is an uncomfortable finding and I am not going to dress it up: on the last 30 days of your own tape, the current fingerprint-driven mean-reversion shape did not beat buy-and-hold on three of four books.

And one finding that explains a question you asked directly — **why H PATIENT REVERT keeps failing despite being your best-designed sleeve.** Look at it:

```
H PATIENT REVERT   stock: 88.6% win, Δ-null -0.0768%   crypto: 70.0% win, Δ-null -0.4142%
```

**The highest win rate in the entire workshop, and a negative edge.** It wins constantly and loses big — small targets, wide stops. That is not a bug in the sleeve; it is the geometry of its shape, and it is exactly what the geometry gate was built to catch. That number is the reason to change H's shape, and it is the first time we have had it.

---

## INSTALL (5 files + report)

```
silmaril/execution/warm_start.py        (NEW)   silmaril/execution/sleeve_promotion.py
silmaril/execution/paper_sim.py                 silmaril/cli.py
scripts/selftest_5_1.py                         SILMARIL_7_1_7_RELEASE_REPORT.md (root)
```

**Then reset whenever you like** — that is the point of this release. Run `Reset Internal Clean`, then a Daily Run, and within one cycle you should see the blackout skipped, all four books scanning, sleeves filling, and each book seeded from its own backtest. Watch for the line `READY after wipe — N names already warm … blackout skipped`.

## THE HONESTY CAVEAT

Two of the three waits were removable and are gone; the third — three real closes before a book risks paper — is the one that protects you and it stays. What this release does **not** do is make the system profitable. It found that three of your four books have no edge over doing nothing on the last 30 days, and it will now tell you that every cycle instead of letting you discover it days later. That is worth more than the time it saves.
