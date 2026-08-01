# SILMARIL 7.2.0 — "ONE STRUCTURE ENGINE"
### I was wrong about M FLOOR ARTIST. Here is the proof, the bug that let me be wrong, and the sleeves built on the corrected footing.

**Battery: 123/123** on the full tree, a reset tree, and a simulated install over your August 1 backup. Click path 9/9. **No reset.**

---

## 1 · I WAS WRONG, AND HERE IS THE ARITHMETIC

Last release I told you *"M FLOOR ARTIST is green in all four books."* You told me to strip the optimism. So I attacked my own claim first:

| M sleeve | headline | **REALIZED** | unrealized |
|---|---|---|---|
| crypto:M | +0.362% | **−$12.92** | +$49.17 |
| stock:M | +1.538% | **−$50.56** | +$204.34 |
| metal:M | +0.625% | +$21.11 | +$41.43 |
| energy:M | +0.048% | +$4.76 | $0.00 |
| | | **TOTAL −$37.60** | |

**M is negative in crypto and stock.** I read `return_pct`, which is equity-based and includes unrealized marks on open positions. The doctrine's own Law 1 says realized fee-paid P&L is the only score, and I ignored it while quoting the board back to you.

It is not one sleeve. Across the whole workshop **six sleeves carry a headline with the opposite sign to their realized P&L** — and `metal:B CAP ONLY` showed **+1.163% with ZERO closed trades**, every cent unrealized. I also told you "B CAP ONLY leads metal." That was the same error twice.

**Fix:** the scoreboard now publishes `realized_pct`, `unrealized_pct` and `realized_usd` beside the headline. Both numbers ship; the split is explicit and cannot be misread again.

## 2 · THE BUG THAT MADE MY AUDITS UNRELIABLE

You said I'd likely missed another bug. I had, and it is the reason my structure audits kept giving different answers.

`_structure_levels` anchored its 72-hour window to **`_now()`** instead of to the data it was handed. Live that's roughly harmless — now ≈ the last print. For **every backtest, warm start, graph→decision audit and reconstruction** it silently used a window containing few or none of the supplied rows, then fell back to `live[-200:]` without saying so.

Measured on PENDLE-USD, same tape, only the truncation point changing:

```
truncated 0d ago:  588 rows  ->  floors 5  (>=3x: 4)
truncated 2d ago:  447 rows  ->  floors 3  (>=3x: 0)
truncated 5d ago:  243 rows  ->  floors 7  (>=3x: 3)
```

That is not a market changing. That is a lens changing. **Every structure verdict this project produced outside the live path was measured through the wrong window — including my audits of M.** When I tried to verify that M actually bought at tested floors, I got "20 of 24 entries had no qualifying floor," and I could not tell whether that was M's failure or my instrument's. That is exactly the state you should never accept from me.

**Fix:** `graph_read.read_graph()` anchors to the **last print**, with an explicit `as_of`. Verified on 8 names: truncating the tape and reading it `as_of` that moment now produce **identical** floors, band position, break state and approach. Same tape, same answer, live or six days later.

## 3 · ONE STRUCTURE ENGINE — `graph_read.py`

Structure lived as private helpers inside the sleeve lab while the chart computed its own copy in JavaScript. **Two implementations of "where are the floors" cannot stay honest.** Now there is one, published to `GRAPH_READ.json` each cycle, and it is rebuilt **before** the sleeve lab runs so the readers never act on a picture you are no longer looking at.

It computes what a person actually reads off a chart:

- **levels with strength** — tests weighted by *recency* and *lifespan*. A floor tested 6× two days ago is weaker evidence than one tested 3× in the last hour, and the old code could not tell them apart.
- **break state** — INTACT / TESTING / **BROKEN**. A floor that just gave way is the most dangerous thing on a chart to buy, and nothing measured it before.
- **approach** — FALLING_INTO / FLAT_AT / LIFTING_OFF. The difference between catching support and catching a knife is timing, not level.
- **band position** — where price sits between nearest floor and nearest ceiling.
- **headroom in the name's own noise** — a 1% target under a ceiling 0.4% away is not a trade however good the ratio looks.
- **cadence, trajectory, peak/trough stepping**, and a plain-English `verdict` string.

Real output from your tape:

```
XAG      support 57.775 (14x, strength 12.6, testing) · resistance 58.14 (1x) 0.61% up
         · sitting 3% of the way up the band · cadence peak due · peaks falling
PENDLE   support 1.39467 (3x, strength 2.4, testing) · resistance 1.405 (1x) 0.72% up
         · falling into at -0.29%/6 prints · peaks flat, troughs rising
```

*Also fixed along the way:* "nearest resistance" could sit **below** price due to a tolerance, producing band positions of **209%** and negative headroom — nonsense a sleeve would then reason from.

## 4 · THE READER BENCH — three sleeves that read the chart like a person

**R — SUPPORT READER** *(M FLOOR ARTIST 2.0)* — everything M does plus the four things M was blind to: level **strength**, **break state** (M would happily buy a floor that had just failed), **headroom in sigma**, and **band position** rather than mere proximity. This is the sleeve M should have been.

**S — BOUNCE READER** — the patient hand. R buys while price is still falling into a floor; S waits for the tape to actually turn (`LIFTING_OFF` or `FLAT_AT` off an intact level, troughs no longer stepping down). Fewer trades, later and worse entries. **R vs S is the experiment: is patience worth more than price?**

**T — CEILING READER** — the full human loop. Buys low against structure *and* sells into the resistance the chart shows, or when peaks start stepping down after a fresh peak. Your words: *"buying low, and getting excited and when realizing the ceiling is hitting, selling."* Vaulted.

Every refusal names the thing on the chart, so you can check it by eye:

```
R  support 30.0567 is weak (3x, strength 2.3, last touched 38.6h ago; needs 2.5)
S  still falling into support at -1.45%/print — waiting for the tape to turn
   rather than catching the knife
T  price sits 60% of the way up the band; this sleeve buys the bottom 40%
```

**Twenty sleeves now compete on identical data.** R/S/T read the same object the chart draws.

---

## INSTALL (4 files + report) · no reset

```
silmaril/execution/graph_read.py     (NEW)   silmaril/execution/strategy_lab_abcd.py
silmaril/cli.py                              scripts/selftest_5_1.py
SILMARIL_7_2_0_RELEASE_REPORT.md  (root)
```

Watch `GRAPH_READ.json` (the structure the sleeves trade on), and `SLEEVE_VETOES.json` for `graph read —` lines. Judge R/S/T on **`realized_pct`**, not the headline.

## THE HONESTY CAVEAT — and what I am changing about how I report

You were right that every time I have said "the data is lying," it was lying — and right that I should have assumed I'd missed something. I had: the anchoring bug is mine, and it invalidated my own audits while I was using them to praise a sleeve that was in fact losing money on realized terms.

Three things change in how I report to you from here:

1. **Realized P&L or it does not get quoted.** No more headline numbers that include open marks.
2. **When an audit gives an answer I like, I test the instrument before I report the answer.** The M audit gave me "20 of 24 entries had no floor" and I should have suspected my reconstruction *first* — that is what found the anchoring bug.
3. **No sleeve gets called "working" under 30 closed trades.** R/S/T have 2 open positions and zero closes. They are hypotheses with better instruments behind them, nothing more.

What is genuinely better today: there is one structure engine instead of two, it is anchored to data instead of wall-clock, its levels carry strength and break state, and the sleeves that read it refuse trades for reasons you can verify by looking at the picture. That is the precondition for the graph driving decisions. It is not evidence that it does.
