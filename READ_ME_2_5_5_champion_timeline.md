# SILMARIL 2.5.5 — CHAMPION TIMELINE (real code: "did rotation help?")

Real engine + Forensics panel, not a doc. Answers your directive's #1 question from actual fills.

## What it does
Builds every champion reign from the real promotion log, then attributes each real crypto fill to
the champion active when it CLOSED, and reports per reign: duration, trades, win rate, realized P&L,
and $/hour (normalized for reign length). OBSERVATIONAL ONLY — no behavior changed, no synthetic data.

## What it found (real data)
| champion | reign | trips | win% | realized | $/hr |
|----------|-------|-------|------|----------|------|
| MR_patient_d3 / s2 / s4 (4 early reigns) | Jun 21–22 | 0 | — | $0 | — |
| **MR_d3_t3_s4** | 37.4h | 16 | 43.8% | **−$67.12** | **−$1.79/hr** |
| **MR_d3_t3_s2** (current) | 36.8h | 50 | 46.0% | **+$370.05** | **+$10.06/hr** |

**Verdict: rotation DID help — once.** The June 23 survivability-based switch (s4 → s2) moved off a
champion that was *losing money* (−$67) onto the one that's made +$370. Then HOLDING it is what paid.
The four early switches (Jun 21–22) were churn that produced zero trades — noise, not signal.

The lesson, with evidence: the *good* rotation was the evidence-driven survivability switch; the
*bad* pattern was rapid window-dominance churn. This validates the champion-governance fix (select by
forward survivability, switch only on a margin, stay sticky). Stability on a proven champion > churn.

## Why this is the answer to "did champion rotation help?"
Before this you could only guess. Now each champion is credited with exactly the fills it oversaw, so
you can see that the current champion isn't just stable — it's the most productive reign by a wide
margin, and the prior one was a net loser. That's the difference between "we think rotation helped"
and "here is the P&L each champion produced."

## Honest notes
- Trades attributed by champion-active-at-exit, from the real promotion log + real fills.
- Small samples still (50 and 16 trips). One more losing reign or a regime change could shift this.
- $/hr is a normalizer, not a forecast.
