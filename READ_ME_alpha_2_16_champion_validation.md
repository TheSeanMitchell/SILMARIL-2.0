# SILMARIL ALPHA 2.16 — Champion Validation + Promotion Ladder

Validation over expansion. One engine, no new signals. Drop on the repo root over
the June 26 backup; both files compile.

## What I read in the new repo (what's working / what's not)

**Working — and this is new:** the internal paper sim went from −$56.60 (June 21)
to **positive across the whole Mean Reversion family** (June 26): crypto book
+$112.41 realized, MR_d3_t3_s4 +$59.45, MR_d3_t3_s2 +$54.18, MR_d3_t3_s6 +$49.78,
champion MR_patient_d3 +$14.76. The entire top of the arena is Mean Reversion, win
rates 53–74%. Your single most important discovery holds: **MR is the champion.**

**Not working — and it's structural, not a bug:** the **stock book has 0 trades.**
That is the sim-vs-live disconnect you called: liquid majors don't drop 3–5% the
way the volatile alt universe does, so the MR trigger almost never fires on the
names the live Alpaca accounts can trade. The live accounts staying flat is correct
behavior, not failure — but it means *the edge that's working lives in a universe
the production accounts barely touch.* That's the real gap to sit with.

## What this release adds: `champion_validation.py`

For every strategy book it computes total return, expectancy (with a 95% CI), win
rate, volatility, a Sharpe proxy, max drawdown, profit factor, and t-stat — then
runs an **out-of-sample split** (first half of the book's closed trades vs second
half) and assigns a **survivability score** and an automatic **promotion tier**.

### The verdict (live numbers, this run)

| strategy | n | total | exp/trade | win% | Sharpe | maxDD | t | surv | tier |
|---|---|---|---|---|---|---|---|---|---|
| **MR_patient_d3** (champion) | 5 | +4.33% | +0.85% | 80.0 | 1.35 | −0.15% | 3.0 | 88 | Sandbox |
| MR_d3_t3_s4 | 8 | +20.31% | +2.39% | 75.0 | 0.71 | −0.70% | 2.0 | 84 | Incubation |
| MR_d3_t3_s2 | 9 | +16.36% | +1.77% | 55.6 | 0.46 | −5.03% | 1.4 | 78 | Incubation |
| crypto (main) | 11 | +11.11% | +1.04% | 63.6 | 0.26 | −10.37% | 0.9 | 54 | Incubation |
| MR_d3_t3_s6 | 3 | +15.96% | +5.15% | 66.7 | 1.22 | −0.70% | — | 0 | Sandbox |

**Two findings worth your attention:**

1. **The declared champion is, in fact, the most survivable** — MR_patient_d3 has
   the best risk profile (t=3.0, 80% win, Sharpe 1.35, −0.15% drawdown). Your
   champion-selection logic is choosing correctly. But it sits in **Sandbox**
   because n=5 is too few to promote. **No strategy has earned past Incubation.
   Survival is not yet proven** — exactly as you'd want the ladder to enforce.

2. **Wider stops are quietly winning.** s4 (+2.39%/trade) and s6 (+5.15%/trade)
   out-earn s2 (+1.77%), and s2 carries the worst drawdown (−5.03%). The arena is
   now producing its own evidence for the conversion diagnosis from last session:
   tight stops sell the dip the MR strategy was built to buy. You don't need to
   *assume* the fix — the s-grid is testing it live, and wider is ahead.

### Promotion ladder (capital earned, not granted)

Sandbox → Incubation ($10k) → Candidate ($25k) → Production ($50k → live).
Right now: **Incubation** = MR_d3_t3_s4, MR_d3_t3_s2, crypto; **Sandbox** =
MR_patient_d3, MR_d3_t3_s6. Nothing reaches Candidate until it has the trades and
the out-of-sample consistency. That gate is the point.

## The seven directive priorities — honest status

1. **Champion Validation** — ✅ built (stats, CIs, OOS split, survivability).
2. **Arena Expansion (MR family)** — ◻️ already broad (d2/d3 × t1/t2/t3 × s2/s4/s6 ×
   patient). The s-grid already spans stop widths; that's the most useful axis right
   now. Vol/regime-aware variants deferred — they'd need regime detection, which
   edges toward a new signal, and validation matters more this phase.
3. **Promotion Ladder** — ✅ built and operating automatically.
4. **Edge Capture Improvement** — ◻️ measured; the actionable lever (wider MR stop)
   is now arena-supported. The cleanest next experiment, when you want it.
5. **Authority Research Division** — ✅ stays a research division: the authority
   engine is wired to log and validate, **not** to trade. Leave it there.
6. **Production Alignment** — ⏳ diagnosed (stock book 0 trades = the disconnect);
   quantifying live-vs-sim divergence needs live fills to compare against, which
   barely exist yet by design.
7. **Reliability / stress testing** — ◻️ not built; needs regime-segmented data.
   Next, once there are enough trades to segment.

## The honest bottom line

You said it best: this is the healthiest the project has ever been — not because
it's profitable, but because it can finally tell whether it is. This release makes
that literal. The champion is real and it's the most survivable strategy in the
arena — but it's Sandbox/Incubation, on 3–11 trades, in June. **The one thing that
proves it is July**, and no engine shortcuts that. My recommendation matches yours:
do not expand. Let the ladder run, let the s-grid settle the stop question, keep
authority in the lab, and re-grade when the champion has 30+ trades across a regime
it didn't learn. That's the test. Not today.
