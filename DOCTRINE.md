# SILMARIL — THE DOCTRINE
### The whole system, in plain language. What decides, what it decides with, and how it is judged.

*You said: "we are only as good as our decisions system, so we need to be able to read it like a book." This is that book. It is written to be read start to finish in about fifteen minutes, and it is written to be **true** — where something does not work yet, it says so.*

---

## PART 0 — THE ONE-PARAGRAPH VERSION

Prices come in. A **fingerprint** measures each name's own habits. A **confidence card** scores it. Eleven **sleeves** — small strategies with different personalities — compete for a handful of slots using those scores. Their **closed trades** are the only evidence that counts. When a sleeve proves itself on real closes, its discipline is **promoted** to the funded book for that industry. The four books feed the **Master**, which mirrors only what has been proven. Everything the system believes is written to a file, drawn on a graph, and graded against what actually happened. Nothing is trusted because it sounds right; it is trusted because it survived.

---

## PART 1 — THE FOUR LAYERS (the pyramid)

```
   PRICES  →  FINGERPRINTS  →  CONFIDENCE  →  SLEEVES  →  BOOKS  →  MASTER
   (tape)     (its habits)     (its score)   (probes)   ($10k)    (mirror)
```

**Why a pyramid at all?** Because a bad idea should cost a little before it can cost a lot. A sleeve risks unfunded paper. A book risks $10k of paper. The Master mirrors only what books have already proven. Each rung must be *earned*, never assumed.

| layer | what it is | what it risks | what it must prove to move up |
|---|---|---|---|
| **Sleeves** | 11 small strategies per industry, each with its own personality | nothing (unfunded probes) | ≥3 real closed trades with positive Δ-vs-null |
| **Books** | crypto / stock / metal / energy, $10k paper each | paper capital | its own forward record |
| **Master** | a mirror of book-held names | paper capital | only mirrors PROMOTED sleeves' books |

**The arming gate.** A book may not open a position until its own workshop has PROMOTED a sleeve. That is why books sit quiet after a wipe — that is the law working, not a bug.

---

## PART 2 — HOW A NAME BECOMES A TRADE (follow one coin all the way through)

### Step 1 — The tape
Every cycle we fetch prices. They land in `price_samples.json` (primary) and `ccxt_samples.json` (crypto exchanges).

**The One-Key Law.** One asset = one canonical key (`DOGE-USD`). Another spelling may join it *only* if a time-aligned check proves it is the same asset at the same price. This exists because we once blended `APT-USD` at $0.000131 with `APTUSD` at $4.376 and got square-wave charts, fake peaks and fake trades.

**The One Fresh Price Law.** Only the tape may price a fill. Confidence cards and traces may *rank* — never *price*. No fill on a print older than 45 minutes. Unknown age counts as stale. This exists because a stale entry paired with a live exit once fabricated a $242 "profit."

**Price Truth.** Every feed is graded each cycle: OK / COARSE / QUANTIZED / FROZEN / DISPUTED. Only OK feeds may be traded or learned from. The test is **resolution, not price** — can this feed even express the move we need? A $0.0000001 coin with a fine tick is fine; a $200 stock reported at three levels is not.

### Step 2 — The fingerprint (the name's own habits)
For each name we measure, from its own tape: how far it typically dips before bouncing, how far the bounce usually goes, how often the bounce actually arrives, its typical stop distance, and the round-trip cost to trade it.

> *"PNUT-USD: dips ~0.49% → aims 1.60% (of ~2.43% typical bounce) · stop 6.0% · up · reliable"*

**Every name gets its own bar. There is no blanket threshold.** A 3% dip means something different for gold than for a memecoin.

### Step 3 — The geometry gate (the arithmetic that must clear)
Before anything else, one question: **what win rate does this trade's shape demand?**

```
required win rate  =  (stop + cost) / (target + stop)
```

If the shape demands 80% and the name has historically delivered 73%, the trade is **UNTRADEABLE:geometry** and never happens. This is the law that stopped us trading gold ETFs whose round trip ate half the available move — a real finding, not a failure.

### Step 4 — The confidence card (nine components, one score)
Confidence is not a mood. It is nine measured components:

| component | plain meaning |
|---|---|
| bounce reliability | when it dips this much, how often does it actually come back? |
| rhythm regularity | are its peaks evenly spaced, or random? |
| rhythm phase | where are we in that cycle right now? |
| MTF confluence | do 1h / 4h / 1d agree, or contradict? |
| dip extension | how far past its usual dip has it gone? |
| timing alignment | is this its historically good hour to buy? |
| momentum exhaustion | has the fall run out of steam? |
| conviction backing | do independent agents agree? |
| trend alignment | is the larger trend with us or against us? |

These combine into `confidence` (0-100%) and `rhythm-tradeability`. **Honest caveat:** the weights were set by design, not fitted from outcomes. Calibration (do 60% calls win 60%?) is measured but not yet feeding back. That loop is open.

### Step 5 — The sleeves (eleven personalities, few slots)
Each industry runs eleven sleeves. Same tape, same prices, different rules:

| sleeve | personality | slots |
|---|---|---|
| A FOREVER RIDE | buy and hold, never panic | few |
| B QUICK FLIP | small target, fast out | few |
| C TREND ONLY | only buys when the trend agrees | few |
| D SNIPER | high confidence only, rare shots | few |
| E ADAPTIVE STRIKER | 2 slots, +2 more on an industry surge | 2 (+2) |
| G GEOMETRY SNIPER | only shapes whose arithmetic clears | few |
| H PATIENT REVERT | waits for the deep dip, holds longer | few |
| (+4 others) | volatility, cost-aware, regime, null-benchmark | few |

**How slots are prioritised** — you asked this directly:
- **Confidence-gated sleeves** (snipers) take the *top decile of this cycle's confidence, best first*.
- **STRIKE slots** rank by *1-hour momentum, strongest first*.
- **Plain mean-reversion sleeves** rank by *deepest dip first*.

So it is **not** first-come-first-served. But each sleeve ranks on **one number**, and — see Part 4 — the graph is only now beginning to enter that decision.

**The rails every sleeve must pass before it may open** (added 7.1.5 — the books had these for six releases; the sleeves had none):
1. **Market calendar, per symbol.** Gold (spot XAU) trades 24/7 as of 2026-07-26; silver/platinum/copper and energy spot trade 24/5; ETFs and equities follow the NYSE session; crypto never closes.
2. **Re-entry cooldown.** A name we just closed is off-limits for 180 minutes — 360 if it *stopped us out*. This exists because sleeve G stopped out of XTZ and re-bought it *in the same second*, three times.
3. **Trajectory veto.** If a name is down across every window **and** its peaks are stepping down, no entry. Mean reversion wants oversold-in-a-*range*; bought in free-fall it is just early. This is what cost H both of its trades.
4. **Fresh, tape-priced, feed graded OK.**

Every refusal is written to `SLEEVE_VETOES.json`, because *"quiet by correct design"* and *"actually broken"* look identical from outside unless the system states its reasons.

### Step 6 — Promotion (the only thing that counts is a closed trade)
Each cycle, every book's workshop is scored on **closed trades vs the do-nothing null** (HODL / SPY / CASH).

- Best sleeve with ≥3 closes and positive Δ-vs-null → **PROMOTED**. Its *discipline* (position cap, patience, ride-winners, confidence gate) is handed to the funded book, and the book is **armed**.
- Best sleeve with fewer closes → **PROVISIONAL**. Seeds the hand, does **not** arm the book.
- Whole workshop under water → **NO_POSITIVE_SLEEVE**. Nobody is promoted. A losing workshop promotes no one.

**Sleeve behaviour is never edited — only selected.** We choose which personality wins; we don't tune it until it wins.

### Step 7 — The book, then the Master
The armed book trades with the promoted sleeve's discipline. Every winning close sweeps **100% of net take-home** into a non-spendable vault, so gains never re-enter risk.

The **Master** mirrors only names held by books whose sleeve is strictly PROMOTED. It is a *mirror*, not a second opinion — if the books buy badly, the Master inherits it. Fixing the books *is* fixing the Master.

---

## PART 3 — HOW THE GRAPH HARVESTS AND WHAT IT KNOWS

Every ticker click opens the **Everything Chart**, which draws, on one price line:

| layer | what it means |
|---|---|
| **peaks ▲ / troughs ▼** | swing points, found with prominence scaled to the name's own noise |
| **floors / ceilings ·N×** | levels tested N times — the more tests, the more real |
| **heartbeat** | median time between peaks — the name's rhythm |
| **next-peak ETA** | last peak + heartbeat, drawn as a vertical line |
| **trajectory ladder** | 2h/4h/8h/12h/1D/2D/3D/1W at a glance |
| **fingerprint fit** | *this* name's dip trigger and bounce target, drawn as lines |
| **geometry verdict** | TRADEABLE / UNTRADEABLE, with the win rate the shape demands |
| **outside venues** | real Coinbase / Kraken / Yahoo series traced over ours, with a time-aligned AGREE/DISAGREE verdict |
| **our fills ◆** | where *we* bought and sold (diamonds — the market's structure uses triangles) |
| **feed verdict** | if the feed is QUANTIZED or FROZEN, an amber banner says so |

**On "is it defaulting to zero between runs?"** — no. Every vertex is a real print. The line between two prints is drawn straight because we have *no data in between*; a long gap therefore looks like a snap. The chart now prints its own sampling cadence and worst gap in the footer so you never have to wonder again.

---

## PART 4 — THE HONEST GAP: the graph does not yet drive trading

This is the most important sentence in this document.

> **`CHART_INTEL.json` — peaks, troughs, floors, ceilings, trajectory — is read by the dashboard and by almost nothing in the decision path.**

As of 7.1.5 exactly **one** graph-derived read gates a decision: the **trajectory veto** (falling peaks + down across every window ⇒ no entry). Everything else — range position, floor support, ceiling overhead, cadence phase — is drawn and ignored.

**Why we did not just wire it all in.** Because bolting unmeasured signals onto live selection is precisely how the last several regressions happened. Instead:

`GRAPH_DECISION_AUDIT.json` reconstructs, for every closed trade, what the graph said **at the moment of entry** (using only prints that existed then — no hindsight can leak in), buckets outcomes, and grades each feature **PREDICTIVE / NEUTRAL / TOO_EARLY**. A verdict requires **25 graded entries with ≥5 in each bucket**.

*An honest note:* the first draft of that audit used n≥8 and duly reported four features "PREDICTIVE" off nine trades with buckets of three. That is noise wearing a verdict. The bar was raised; it currently reads **TOO_EARLY across the board**, which is the truth.

**The path is therefore explicit:** measure → earn PREDICTIVE → gate on it with a knob, a kill switch and an A/B. The panel names the feature when it qualifies. No feature gets promoted on a feeling.

---

## PART 5 — HOW THE SYSTEM JUDGES ITSELF

| instrument | question it answers |
|---|---|
| `PRICE_TRUTH.json` | can each feed even express the move we need? |
| `PRICE_SOURCE_AUDIT.json` | does any store disagree with the tape about the current price? |
| `SLEEVE_VETOES.json` | what did each sleeve refuse, and which rail stopped it? |
| `GRAPH_DECISION_AUDIT.json` | did reading the graph before entry separate winners from losers? |
| `LAB_OUTCOMES.jsonl` | the river — every sleeve close, feeding maturity |
| `SLEEVE_PROMOTION.json` | who earned the book, and who is still waiting |
| `CALIBRATION.json` | when we say 60%, do we win 60%? *(measured, not yet feeding back)* |
| `selftest` (117 tripwires) | does every law still hold? |

**The tripwire law.** Every bug ships a test that *reproduces the original failure*. If a test cannot fail against the broken version, it is decoration. This is why the click-path harness runs the real chart code instead of grepping it — a source grep once passed while every graph link on the site was dead.

**The fill laws** (these are also the live-trading honesty bar):
- A take-profit is a **limit** order: it can never fill above its limit.
- A stop is a **market** order: it takes the *worse* of trigger and mark. Slippage is worn, never gifted.
- Fills across a gap in the tape are stamped, so unobserved evidence weighs less.

---

## PART 6 — THE STANDING LAWS (the short version to re-read)

1. **Realized, fee-paid P&L is the only score.** Open marks are unrealized. Say so.
2. **One asset, one key.** Verified same-scale or it does not join.
3. **Only the tape prices a fill.** Never a derived store. Never a stale print.
4. **A limit cannot overfill.** A stop wears its slippage.
5. **Sleeves trade first. Books arm on ≥3 real closes. The Master mirrors only PROMOTED.**
6. **Sleeve behaviour is selected, never edited.**
7. **A losing workshop promotes nobody.**
8. **Every bug ships a tripwire that reproduces it.**
9. **Every behavioural change is knob-gated with a pre-registered kill.**
10. **Δ-vs-null or it did not happen.** Beating nothing is the bar.
11. **Nothing is deleted.** Bad evidence is quarantined with a reason, never erased.
12. **"I don't know yet" beats an invented number.**
13. **The gate is 100 out-of-sample trades across 90 unbroken days.** No override exists in code.
14. **$100–300/day is unproven hope, never income.**

---

## PART 7 — WHAT IS STILL OPEN (so nobody has to guess)

| gap | status |
|---|---|
| Graph features driving selection | only the trajectory veto; the rest measured, awaiting evidence |
| Calibration feeding sizing | measured, not wired |
| Magnitude-weighted champion reward | a +15% win still counts like a +2% one |
| Sub-hour regime (12m/15m) | bands render but sub-hour cells read "—" |
| Order book depth / partial fills / queue position | not modelled — the real live-trading gap |
| Confidence weights | designed, not fitted from outcomes |

**The honest summary.** The instrument is now largely trustworthy: the corruption classes that produced fake profits, square-wave charts and impossible win rates are each closed by a rail with a test that reproduces the original failure. What has *not* been established is edge. The books have a handful of closed trades and the graph has not yet earned the right to trade. That is the work, and this document is how you check it is being done.
