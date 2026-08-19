# SILMARIL 7.3 — SLEEVES U–Z + THE PYRAMID UNBLOCKED

**Three files. Upload them into `silmaril/execution/`, replacing what's there.**
That is the entire install. Nothing else changes. No resets, no workflow changes,
no STEWARD involvement. Your main page, your sleeves, your 10-minute runner — all
stay exactly as they are.

```
silmaril/execution/strategy_lab_abcd.py     <- sleeves U-Z + real venue fees
silmaril/execution/master_account.py        <- the pyramid unblocked
silmaril/execution/graph_decision_audit.py  <- the hindsight bug removed
```

---

## 1. Your alphabet is now complete: A–Z, 26 sleeves

Six new sleeves. Each one encodes **exactly one effect measured in your own 2,435
closed trades**, and each one names its evidence in its own description so you can
argue with it later.

| | Name | The measured finding it encodes |
|---|---|---|
| **U** | PATIENCE FLOOR | Trades held under 2h averaged **−0.45%** (t=−5.29, n=605) — noise shaking you out. 12–24h averaged **+0.40%**, 24–48h **+0.57%**. U forbids any exit before hour 24 except the hard stop. |
| **V** | WIDE STOP EARLY HARVEST | 880 stop-outs averaged **−2.01%**; 745 give-back exits banked **+1.82%**. The book gave losers twice the rope it gave winners. V doubles the stop distance and harvests winners at a tight 15% give-back. |
| **W** | HIGH GROUND | Honestly-graded, entries in the **top third** of the range with trend UP were the only green bucket. Buying the **dip** won 35.7% and lost −0.96%/trade. W buys strength — never the falling knife. |
| **X** | QUIET TAPE | Net-bullish headline days preceded **negative** 3–5 day returns (t=−2.51, in-sample). X refuses any name the crowd bought today. |
| **Y** | INSIDER TAILWIND | Form 4 insider filing activity required, using your own EDGAR fetcher. External evidence, weakest of the six, and labelled so. |
| **Z** | REGIME GATE | Entries in an UP regime averaged **+0.66%**/trade; SIDEWAYS −0.29%; DOWN −0.98%. Z trades only while its book reads UPTREND. This is your rotation wish, finally measured. |

**The mining debt, stated honestly:** U–Z were designed on the same data that produced
the evidence, so they get a HARDER bar than A–T, written into the code: disproven if
they trail their book's A sleeve after 40 closes, and never called proven without
delta-vs-null > 0 **and** per-trade t ≥ 3.0 on forward trades only.

**Verified before shipping:** 26 sleeves present; Z refuses a DOWNTREND and enters an
UPTREND; W buys the top of the range and refuses the bottom; X vetoes a hyped name and
passes a quiet one; Y respects its EDGAR budget; U's 24h floor and V's stop widening
are wired into the live exit and entry paths. 26 of 26 checks pass.

---

## 2. The pyramid was blocked by two bugs. Both are fixed.

Rung 2 was working the whole time — **stock, metal and energy are all PROMOTED**, with
`I VOLATILITY HUNTER` leading metal at +5.49% and `B CAP ONLY` leading energy at +5.84%.
Your workshop has been doing its job.

Rung 3 was the wall. The Master accepted **0 trades in stock, metal and energy** — and
here is why:

**Bug 1 — a gate that could never open.** The Master required a pool of **20**
candidates before it would rank anything. Your tradeable universes are crypto 18,
metal 5, energy 3, stock 0. **No book can ever reach 20.** It logged "pool<20 — gate
stands down" 288 times while reporting itself healthy. Now the floor scales to the
book (4 names), and with a thin pool the bar is *tightened* — a small book must clear
the top name outright, not a looser cut.

**Bug 2 — missing evidence treated as damning evidence.** The hold-time gate read
`(expected_hold_min or 1e9) > max_hold`, so a candidate whose hold estimate was simply
**missing** became a 1-billion-minute hold and was rejected as a "long-hold setup". The
tell is sitting in your ledger in plain English: `long-hold setup (Nonem > 720m)` —
rejected 92 times over a number that was never measured. An unknown hold now passes
that gate and is still judged by every other one.

After the fix: crypto (18 names) and metal (5) now produce a real cut. Energy (3)
still stands down — three names is genuinely nothing to rank, and **that** is the next
thing to fix: expand the energy universe.

---

## 3. The graph-learning bug is still in your repo — now removed

`graph_decision_audit.py` graded roughly half its trades **using the exit price**,
because river rows carry no entry time and the code fell back to the close. A winning
trade closed high is, by definition, in the top third of its range — so the "signal"
was the answer. Graded honestly at entry, the same feature separates by 0.082%; graded
at the exit it printed an 84%/20% split that does not exist. Every `PREDICTIVE` verdict
that module ever published came from that fallback. It is gone.

---

## 4. The Pokémon system — the honest verdict

`senate/breeding.py` (274 lines) is **real, well-built, and not currently wired into
anything that trades.** It breeds child agents from the top-2 parents by measured
equity edge, with seeded reproducible mutation and probationary shadow scoring. The
engineering is sound.

**Keep it. Don't turn it on yet.** Breeding searches a strategy space, and a search is
only as good as the fitness function underneath it. Your fitness function was fees
charged at 6× reality plus a learning module reading the answer. Fix those (this
release does), let A–Z run on honest numbers for a few weeks, and *then* breeding has
something true to select on. Turn it on now and it will faithfully evolve toward noise.

`agent_scorecard.json` shows 19 agents graded on 3,000 clean outcomes, 0% stale — that
machinery is alive and healthy. It is the fitness signal that was wrong, not the engine.

---

## 5. What to expect after installing

- **U–Z start at $10,000 in all four books** (24 new sleeve-books). They have no
  history; they begin trading on the next cycle.
- **Y will trade rarely**, almost only in stock. That is the design.
- **Z will sit in cash** whenever its book isn't in an uptrend. Cash is a position.
- **The Master may start accepting trades in crypto and metal.** After months at
  $9,991 that will look like a malfunction. It isn't — it is the wall coming down.
- Equity fees stay at the corrected **0.068%** (7.2.7, already in your repo).

---

## 6. The one number to watch

Not equity. **Delta vs null** — per sleeve, on the STRATEGY page. A sleeve that made
+5% while its market made +10% lost you money. That single column is how you tell a
real sleeve from a lucky one, and with 26 sleeves × 4 books you now have 104 of them
racing on honest costs.

Give it three weeks before drawing any conclusion. 15 closed trades is not evidence;
100 is a start.
