# SILMARIL 7.1.6 — "THE SAWTOOTH, FOUND"
### Five months of it, traced to the exact rows. Plus gold trading, the $2 trade explained, and the big day no longer missed.

**Battery: 118/118** on the full tree, a reset tree, and a simulated install over your 7:45 AM backup. Click path 9/9. Live cycle + sleeve engine verified on your real data.

---

## 1 · THE SAWTOOTH — found, and it is exactly what you described

You said it this way, more than once: *"every valuable always is either sinking or rising to the same price in between every actual price point."*

That is a literal description of **a real series alternating with a constant**, and that is precisely what was happening. XTZ-USD from your tree:

| source | rows | timestamps | distinct prices |
|---|---|---|---|
| `price_samples.json` → **XTZ-USD** | 612 | irregular (07:03:03, 07:22:39…) | **148** — clean, real |
| `ccxt_samples.json` → **XTZUSDT** | 299 | **exact 5-minute grid** (07:05:00, 07:10:00…) | **4** — a stuck value |

Both were merged into one canonical series. Every real print spiked away from the stuck value; every grid row snapped back to it. That comb then fed the dossier sparkline, the chart, peak detection, rhythm, cadence, fingerprints — everything downstream.

**Two faults let it through, and I own both:**

1. **My flat-series test was absolute, not relative.** It rejected a candidate only at `levels <= 2`. A 299-row series stuck on **four** values sailed straight through. It is now a *ratio*: distinct values as a fraction of rows. A stuck value is a stuck value however many rows it has.
2. **The dead feed could become the REFERENCE.** Reference selection let an outside venue pick whichever spelling sat closest to its price — which handed the job to frozen XTZUSDT purely because 0.2211 happened to sit near the truth, demoting your real 612-print tape to "alternate." Health is now screened **first**, and the primary tape wins by default — the same doctrine that governs fills.
3. **And even two healthy feeds interleaved draw a comb** (two honest sources disagreeing by a tick, alternating every few minutes). So an admitted spelling may now only **fill gaps** — it can never speak for a moment the reference already covers.

**Result on your data:** XTZ-USD went from 911 rows with 299 grid rows and 44% repeat → **612 rows, 0 grid rows, 12% repeat, 148 levels.** Universe-wide, FROZEN rejections rose 245 → 319.

**The 102 names still showing a comb** are all graded FROZEN (60) or QUANTIZED (42) with **zero tradeable** — genuinely dead feeds, already excluded from trading, learning and the arena, and already banner-flagged on their charts. Those are honest sawteeth: a dead feed drawn honestly.

**Tripwire T122** reproduces the exact XTZ scenario and fails against the old code.

---

## 2 · YOUR $2 TRADE — fully explained, and it exposed two real flaws

`2026-07-27 07:28:23 SELL STRK-USD STRIKE $2 3.688% 22.7h TARGET · simulated ◉ capped −9.209%`

Here is the whole story from the ledger:

- Bought at **0.030977**, wager **$54.32**
- Sold at **0.032216** — exactly entry × 1.04, the +4% STRIKE limit
- `mark_seen` = **0.035183** — the market had run to **+13.6%**
- `forgone_pct: 9.209` — the 9.2% a limit order cannot capture

**"◉ capped −9.209%" does not mean a loss.** It means: *we took our +4% limit; the mark ran 9.2% further; a take-profit is a limit order and cannot fill above its limit.* The label was genuinely confusing and it is reworded.

But you were right to smell something. Two real flaws:

**Flaw A — the "never miss the big day" sleeve missed the big day.** The ride test asked *"is this name hot RIGHT NOW?"* (`sym in fastgreen`, computed from the last hour). STRK's run happened overnight; by 07:28 the hour was cool, so riding was False and the hard target fired. **Fixed:** once a position clears its target it becomes a *trailing* trade — best gain recorded, exit only on a 25% give-back. Replayed on your actual STRK price path: **+9.65% instead of +4.0%.**

**Flaw B — $54 on a $10k book.** The mean-reversion slots had already spent the sleeve down to pocket change ($3,621 + $3,440), so the strike slots took crumbs. A sleeve whose job is catching big days cannot be funded with crumbs — when it is right, being right has to matter. **Fixed:** STRIKE now draws against a reserved 15% slice of *starting* capital, not against leftovers.

---

## 3 · GOLD AND METALS — trading, verified this cycle

Your five-month ask. With 7.1.5's per-symbol calendar and 7.1.6's fixes, running the sleeve engine on your tree right now:

```
crypto  open=38  closed=34
stock   open=35  closed=0     ← markets opened
metal   open=15  closed=0     ← XAG, XPT, XPD across five sleeves
energy  open=0   closed=0
```

Metals were correct to trade before the equity open — spot metal runs 24/5, and spot **gold is 24/7 as of 2026-07-26** per your CME note. That was not a bug; that was the calendar finally being right. ETFs (GLD, SLV, GDX) still wait for the NYSE session, because an ETF is an equity whatever it tracks.

**The new rails are visibly working too:** 8 trajectory vetoes fired this cycle, all refusing ADA-USD — *"down across every window (−4.50%, −4.04%, −3.87%) and its peaks are stepping down."* That is the graph vetoing a trade, written down with its reason.

---

## 4 · SLEEVE FILLS NOW APPEAR ON CHARTS

You said the sleeves weren't plotting their buys and sells like the main accounts. Correct — `chart_overlays` read the funded **books** only, so the entire workshop was invisible. Since the books are unarmed, that meant *all the actual trading* was missing from every chart.

Now on your data: **9 symbols carrying sleeve fills · 62 open sleeve entry markers across 20 symbols**, each tagged with its sleeve letter and flagged when the fill was capped.

---

## 5 · THE CRYPTO PORTAL "TWO EXITS BUT STILL $10,000"

Not a lie and not a disconnect — a **display conflation**, and the numbers are right:

- Those two exits (`STRK-USD +1.86%`, `EOS-USD +1.79%`, both `HELD_GAIN`) are **sleeve** trades, in the unfunded workshop.
- The **crypto book** is unarmed (`NO_POSITIVE_SLEEVE` — its best sleeve is under water), so it has taken zero trades and correctly reads exactly $10,000.00.

The pyramid is working as designed: the workshop trades, the book waits for a promotion it has not earned. The portal should not have shown workshop exits under a book heading, and the sleeve fills now being on charts makes the separation visible.

---

## 6 · THE BOOTSTRAP YOU ASKED FOR — my honest answer

You want a backtest bootstrap so books don't sit dead for days after a wipe. I think you're right that the waiting is the problem, but I want to be straight about the shape of the fix, because a wrong one would undo everything above.

**What must never happen:** synthesising closed trades to "warm up" the books. That would put fabricated evidence into the same river that the maturity gate and the 100-trade clock read — the exact class of corruption we just spent three releases removing (PNUT $242, BRENT $198).

**What is legitimate, and what you already have most of:** the wide arena already backtests 316 strategy shapes across your stored tape every cycle. What's missing is that its output doesn't *choose* anything — it ranks strategies nobody consults. The honest bootstrap is a **parameter warm start**: after a wipe, the arena picks each book's *starting sleeve and dip/target/stop shape* from what actually worked on the last 30 days of real tape, so the workshop begins tuned instead of naive. Zero fabricated trades, zero effect on the gate, and it collapses "days of waiting" into "one cycle."

I did not build it in this release because it needs its own design pass and I would rather ship six verified fixes than seven with one rushed. It is the right next release, and it is the one I'd propose we do next.

---

## INSTALL (4 files + report)

```
silmaril/execution/canon_keys.py            silmaril/execution/strategy_lab_abcd.py
silmaril/execution/chart_overlays.py        scripts/selftest_5_1.py
SILMARIL_7_1_6_RELEASE_REPORT.md   (root)
```

No reset. Hard-refresh after the Pages deploy.

## THE HONESTY CAVEAT

The sawtooth was mine — my 7.1.2 flat test was too narrow and my reference selection let a dead feed outrank your real tape. It shipped because I tested that *some* frozen series get rejected, not that *this* one did. T122 now reproduces it exactly.

What this release does not do is prove edge. It removes a five-month rendering lie, lets gold trade, stops the strike sleeve from throwing away its own wins, and puts the workshop's fills on the picture. The river still reads 12.5% win over a small sample. That number is now measured on a clean tape, which is the first time it has meant anything.
