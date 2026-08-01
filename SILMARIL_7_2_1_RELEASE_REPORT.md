# SILMARIL 7.2.1 — "THE FUNNEL THAT STARVED THE WORKSHOP"
### Why seven sleeves had zero trades. It was not selectivity — it was starvation, and it was my design error.

**Battery: 124/124** on the full tree, a reset tree, and a simulated install over your 3 PM backup. **No reset — see §4, with numbers.**

---

## 1 · THE BUG: every sleeve was fed the wrong question

You said a lot of crypto sleeves aren't finding trades. I assumed my gates were too strict and went looking for a threshold to loosen. That was wrong. Here is what the tree actually said:

```
crypto decision_trace_live rows  =  0
```

**Zero.** Every one of the twenty sleeves is fed candidates from exactly one place: `decision_trace_live`, the funded book's **mean-reversion dip scan**. When the book finds no dips, *the entire workshop sees nothing at all* — not "no good candidates," no candidates.

And the damning part: at that same moment, measured directly against published structure,

```
R SUPPORT READER  could have traded  5 of 130 crypto names
T CEILING READER  could have traded  7 of 130
```

They never saw them. **A support reader was being handed the output of a dip scanner** — the wrong question entirely. A structure sleeve doesn't want the names that fell 0.5% this cycle; it wants the names sitting on a strong tested floor with clear air above.

That is my design error. I added seven sleeves across three releases and never once checked whether they could *see* anything, then described them to you as "hypotheses with better instruments." They weren't hypotheses; they were disconnected.

**Two further mis-feeds found while fixing it:**
- The pool was sliced to `cap` (4 names) **before** the gate ran. R passes about 5 of 130, so even a full funnel would have found nothing almost every cycle.
- `GRAPH_READ` ranked the whole universe by deepest tape and published the top 400 — giving crypto 130 symbols and **metal 5, energy 3**. The non-crypto readers had essentially no universe. Quotas are now per book (stock 200 · crypto 152 · metal 12 · energy 6).

**Result, same tape, same cycle:**

| | before | after |
|---|---|---|
| R SUPPORT READER (crypto) | 0 positions | **4** |
| T CEILING READER (crypto) | 0 positions | **3** |
| graph-read refusals exercised | 0 | **238** |

Refusal breakdown — the gate is now genuinely working rather than never being reached: 92 weak support · 51 insufficient headroom · 32 too high in band · 30 broken floor · 1 still falling.

**Stock, metal and energy readers correctly show zero: today is Saturday.** Only XAU (24/7) and crypto may open. That is the calendar, not a fault.

## 2 · M FLOOR ARTIST — you are right, and here is the corrected number

You said M looks terrible and that my early assessment was optimistic. Both true. On **realized** P&L, crypto:

```
M  FLOOR ARTIST     -0.149%   11 closes   45.5% win     <- least bad
E  ADAPTIVE STRIKER -0.220%   12 closes   33.3%
P  SURVIVOR         -0.508%    1 close     0.0%
...
G  GEOMETRY SNIPER -11.168%   30 closes   20.0%         <- worst
```

M is the **least-bad sleeve in a losing book**, not a winner. I called it "the most promising success" when it was −0.149%. The whole crypto workshop is negative and the total realized across all books is **−$6,527**. That is the honest state.

What M did have going for it was a *structure* thesis rather than a threshold. R is that thesis with the four things M was blind to. Whether it works is unknown and will stay unknown until it has 30+ closes.

## 3 · WHY I KEEP MISSING THESE — and what changes

The pattern across the last several releases: I add a mechanism, verify the mechanism in isolation, watch it produce zero output, and interpret zero as *selectivity*. Three times now zero has meant *disconnection* — the graph never reaching the decision path, the reader sleeves never reaching a candidate, the ratio gate never reaching enough history.

**A new rule, enforced from here: a sleeve that takes zero trades for a full cycle gets instrumented, not praised.** T128 asserts the wiring; more usefully, `SLEEVE_VETOES.json` now shows 238 refusals where it showed 0, so "silent" and "refusing" are finally distinguishable at a glance. If a sleeve is quiet and there are no vetoes with its letter on them, it is not being fed — that is now a one-line check instead of an archaeology session.

## 4 · SHOULD YOU RESET? — no, and here is the arithmetic

```
closed sleeve trades on record   : 221     <- a reset DESTROYS these
days since last wipe             : 5.0/90  <- a reset RESTARTS this at zero
realized P&L across the workshop : -$6,527
price_samples.json               : 21.6 MB <- SURVIVES either way (LEARNING class)
fingerprints / structure         : rebuild from the surviving tape in ONE cycle
```

**A reset buys you nothing here.** The tape — the only thing that takes real time to accumulate — survives a reset anyway. What a reset destroys is the 221 closed trades, which are your only forward evidence, and the 5 days of an unbroken 90-day window.

More to the point: **your books are not corrupted, they are losing.** A reset fixes corruption. It does not fix a negative edge; it just deletes the record of it and starts the clock again. You have done that before and it is why you are five months in with twelve days of tape.

The one thing that *would* justify a reset is fabricated fills or a poisoned ledger — and 7.1.4's quarantine plus the fill laws cover that; nothing in this tree shows it. **My recommendation: no reset. Install, let R/S/T run through Monday's open when all four books are live, and judge them on realized P&L at 30 closes.**

---

## INSTALL (3 files + report) · no reset

```
silmaril/execution/graph_read.py        silmaril/execution/strategy_lab_abcd.py
scripts/selftest_5_1.py                 SILMARIL_7_2_1_RELEASE_REPORT.md (root)
```

**The one-line health check from now on:** open `SLEEVE_VETOES.json`. If a sleeve has zero trades *and* zero vetoes with its letter, it is not being fed — tell me and I will find the disconnection. If it has zero trades and hundreds of vetoes, it is working and being picky.

## THE HONESTY CAVEAT

R and T now hold 7 crypto positions between them and have **zero closed trades**. They are unproven and I am not going to call them anything else. What changed today is that they can now see the market they were built to read — which they could not do in any of the three releases where I introduced them.

The workshop is at −$6,527 realized. Nothing in this release makes money; it makes three sleeves capable of trying, and makes the difference between "silent" and "refusing" visible so the next disconnection takes minutes instead of weeks to find.
