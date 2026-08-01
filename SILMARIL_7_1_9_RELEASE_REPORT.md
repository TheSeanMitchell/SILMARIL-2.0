# SILMARIL 7.1.9 — "THE GIVE-BACK"
### The full three-day audit: 638% left on the table, the stock sawtooth found, and three sleeves that experiment on *selection* instead of entries.

**Battery: 122/122** on the full tree, a reset tree, and a simulated install over your August 1 backup. Click path 9/9. **No reset needed.**

---

## 1 · THE AUDIT YOU ASKED FOR — every closed trade, every account

You asked whether we were cashing out high or letting profits erode. I replayed all **186 closed sleeve trades** against the tape, tick by tick, comparing what we *got* to the best the position was *ever worth*:

| exit reason | n | got | had been | **gave back** |
|---|---|---|---|---|
| STOP | 94 | −4.51% | +0.34% | **4.84%** |
| RECYCLE_FLAT | 52 | −0.03% | +2.33% | **2.36%** |
| RIDE_TRAIL | 22 | +4.22% | +6.42% | **2.20%** |
| TARGET | 18 | +3.78% | +4.48% | 0.69% |

**Median trade gave back 2.90% from its own peak. 638 percentage points left on the table in total. 124 of 186 trades gave back more than 2%.**

And the sharpest version: **thirteen positions that had been up more than 2% still closed NEGATIVE.**

```
REZ-USD   +3.69%  →  -3.61%      AAVE-USD  +2.82%  →  -6.56%
ENA-USD   +3.25%  →  -2.10%      AAPL      +2.08%  →  -9.03%
CSGP      +4.12%  →  -1.06%      BRENT     +2.77%  →  -1.84%
```

You were exactly right, and it was worse than you thought.

**Why:** the trail I added in 7.1.6 only existed for `ride_winners` sleeves and only armed **above target**. A position that ran +3% and rolled over had *nothing watching it* — it rode all the way back to the stop. Half of all closes (94 of 186) were stops, and on average those stops had been green first.

## 2 · THE FIX — and I got the parameters wrong the first time

**THE GIVE-BACK GOVERNOR**, on every sleeve. Each position now carries a high-water mark with two rails:
1. **BREAK-EVEN LOCK** — once armed, if price returns to entry+costs, exit. *A winner may never become a loser.*
2. **GIVE-BACK CAP** — surrender at most a fixed fraction of the best gain seen.

Then I did what I should always do: **fitted it on your 186 real trades instead of guessing.**

| arm | give-back | total | winners | vs baseline |
|---|---|---|---|---|
| 1.2% | 40% | −296.6% | 83 | **−32.4 pts** ← my first guess |
| **2.0%** | **25%** | **−236.0%** | **82** | **+28.2 pts** ← selected |
| 3.0% | 25% | −261.7% | 73 | +2.5 pts |
| break-even lock alone @2.0% | — | −256.4% | 70 | +7.8 pts |

**My instinct was wrong in an instructive way.** Arming at 1.2% rescued 31 trades and produced 14 more winners — *and made the total 32 points worse*, because it strangled the runners. Below 2% you're inside the noise band and the trade hasn't declared itself. **arm 2.0% / give-back 25%: +28.2 points and 13 more winners on identical trades.** Verified firing in production this cycle: 2 break-even locks, 2 give-back caps.

## 3 · THE STOCK SAWTOOTH — found, and it is not the crypto bug

NWS: **570 prints, of which 487 (85%) were taken OUTSIDE the regular session.** Outside hours a provider doesn't return a live price — it returns the last close. Ours returned *two different closes alternating* as its cache updated:

```
30.19 → 29.75 → 30.19 → 29.75 …    42 V-shaped round trips back to the identical price
```

Nothing traded. That comb fed peaks, troughs, floors and cadence for **every equity we track**. It arrived through a different door than the crypto grid-feed comb, which is why the earlier fixes didn't touch it.

**Fix:** closed-session blocks collapse to their first print — a closed market has exactly one honest price, its last one. In-session prints are untouched; crypto and 24/5 spot are exempt because for them an out-of-hours price is real.

```
NWS   570 prints → 100    combs 42 → 1    repeat 69% → 11%
520 equity series cleaned across the universe
```

Your FLOW/ZIL/ENJ/AXS/GALA charts are already clean in the *data* (7.1.8's guard is rejecting 265 FROZEN + 75 DEAD feeds) — what remained on those was genuine gap-drawing at 20-minute sampling, which the chart footer now states.

## 4 · THE MASTER'S "$9 SELL WITH NO BUY"

Not a phantom trade. The BUY **is** logged — `ENJ-USD, 2026-07-31 05:15, "mirrors canon fill"` — but the row carried **no `price` and no `qty`**, so any panel keyed on those fields rendered the matching SELL as an orphan. The position was real, the −$9.96 was real, the *record* was incomplete. Master BUY rows now carry price, qty, entry and cost.

## 5 · WHY L AND N NEVER TRADED

`ratio gate — not enough dip history to MEASURE a stop (needs ~8 excursions)`. On a 12-day tape that blocked them from **every** trade in **all four** books. Lowered to 5 completed excursions: **measured stops now available for 51 names, up from 15.** It tightens itself automatically as history accumulates.

Meanwhile **M FLOOR ARTIST — the one sleeve whose entries are chosen by the graph — is green in all four books** and leads crypto on Δ-vs-null (+4.06%). That is the single most encouraging number in this release.

## 6 · THREE NEW SLEEVES — experiments in SELECTION, not entries

Your real question has moved on. It's no longer "does a sleeve work" — it's **"how do we know which sleeve will win *before* it trades?"** These three attack that directly.

### **O — REGIME SWITCHER**
One sleeve, three personalities, chosen by the weather the book is actually in. **SIDEWAYS**: mean-revert, take the ceiling. **UPTREND**: buy the pullback, trail wide, never sell into strength. **DOWNTREND**: refuse to open, sit in cash. Every other sleeve runs one fixed personality in every weather. If the regime classifier has predictive value, O converts it into money — and if it doesn't, O underperforms its own components and proves that too.

### **P — SURVIVOR** ← *this is the rotation system, as a testable hypothesis*
It has **no opinion about markets**. Each cycle it copies whichever sleeve in its own book currently leads on Δ-vs-null over ≥4 closed trades, and re-elects every cycle — reading **last** cycle's scoreboard, never this one (that would be look-ahead). **If past sleeve performance predicts future sleeve performance, P beats the average sleeve. If leadership is noise, P lands mid-pack — and that tells us rotation is a fantasy before we bet the Master on it.** It already elected M FLOOR ARTIST in crypto on its first run.

### **Q — COMPOUNDER**
The food-on-the-table sleeve, built for turnover rather than size. Two slots, **2:1 minimum ratio**, 12-hour max hold, profits reinvested. The arithmetic it chases: 0.5% per trade twice a day compounds to roughly +45% a quarter, while one 6% winner a month does not. It will fail loudly if fees eat a target that thin — which is exactly what we need to know before real money.

## 7 · YOUR ODDS — the honest answer

You asked what I really think the odds are. I'm not going to flatter you.

**Finding a strategy that beats buy-and-hold after fees, and proving it over 90 days: I'd put it around 25–35%.** Not 5%, not 70%.

What's genuinely in your favour, and it's more than most people ever assemble:
- **The instrument is finally honest.** Six classes of corruption that manufactured fake profits are closed, each with a test that reproduces the original failure. Most people quit before this point — or worse, never discover they were trading fiction.
- **M FLOOR ARTIST is green in all four books.** A graph-driven, structure-based entry with a stop placed at real invalidation is *the* professional pattern, and yours is working.
- **B CAP ONLY leads metal (+1.16%) and energy (+2.17%).** Concentration is beating diversification in your quiet books.
- **You now measure instead of assume.** The stop was a blanket 6% for five months; measuring it moved MKR's break-even bar from 66.7% to 41.2%.

What's against you, stated plainly:
- **Every book is still negative in total.** −264% across 186 trades, +28 points better with the governor — better, still negative.
- **51% of closes are stops.** Your entries are early more often than they're right.
- **12 days of tape.** Everything above is measured on a sample too small to be sure of.
- Retail mean-reversion on liquid names is genuinely close to a zero-sum game after fees. That's not pessimism, it's the base rate.

**What would move me to 50%+:** thirty days of clean data with the governor running, P SURVIVOR showing rotation actually predicts, and any one book crossing positive Δ-vs-null over 30+ closes. You'd know by mid-September. That's inside your year.

**The thing I'd tell you if you were paying me for advice rather than code:** you're five months in and you've built the part almost nobody builds — an honest measuring instrument. The edge search is a separate project that has barely started, and it starts *now*, with the sleeves finally competing on clean data. Don't judge the last five months by the P&L; judge it by whether the next thirty days can produce a trustworthy answer. They can, which was not true in June.

---

## INSTALL (4 files + report) · no reset

```
silmaril/execution/canon_keys.py          silmaril/execution/strategy_lab_abcd.py
silmaril/execution/master_account.py      scripts/selftest_5_1.py
SILMARIL_7_1_9_RELEASE_REPORT.md  (root)
```

Watch `SLEEVE_VETOES.json` for `break-even lock —` and `give-back cap —` lines: that is money being kept that used to evaporate. Watch P SURVIVOR's `_following7` to see which sleeve it elects each cycle.

## THE HONESTY CAVEAT

The give-back governor is fitted to 186 trades over 12 days. That is a real sample and a small one — it may not hold. What it will do regardless is stop a winner becoming a loser, which happened thirteen times in three days and is not a market condition; it is a missing rail. The three new sleeves are hypotheses. P SURVIVOR is the one I'd watch: it is the only thing here that can *disprove* the rotation idea, and knowing that early is worth more than another green sleeve.
