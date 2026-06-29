# SILMARIL 2.5 — Operator Cockpit (+ JTO answer, + the honest plan)

Drop on the repo root. `docs/cockpit.html` is the new black-and-white retro
cockpit; `champion_validation.json` is regenerated. This is the flagship of the
2.5 UI direction — not the whole site yet (see "What I did NOT do," below — I'd
rather tell you the truth than pretend a full multi-page rebuild fit in one pass).

## Your JTO question — answered

JTO exited at +0.82% on a **TIMEOUT**, not a target or stop. The MR exit logic
fires on the FIRST of three conditions:

- **TAKE** — price hits +3% (target). JTO peaked around +1.6% and never reached it.
- **STOP** — price hits −5% (champion) / −4% / −6% (by variant). Never hit.
- **TIMEOUT** — the hold timer expires and it sells at market, whatever the price.
  JTO's timer expired while it was at +0.82%, so that's where it sold.

So nothing was "wrong" — it just ran out of clock before reaching its target, and
the timeout rule took market. The cockpit now shows this for every open position:
entry, target price (+3%), stop price, time held, and the exact exit conditions.
For JTO: entry $0.6371 → target $0.6562 → stop $0.6052.

**One thing I want you to see (flagging, not fixing):** the champion config says
`hold: 44` but the sim's hold parameter defaults to `max_hold_min: 240`. The
per-strategy hold you intended may not be wired through — exits may be using 240
minutes (4h) for everything. That's a real config-plumbing bug for the hardening
phase, and it directly affects timeout exits like JTO's. I did not change it
mid-validation, but it's the first thing I'd fix in P4.

## The 2.5 cockpit — what's in it

Pure black-on-white, "ancient HTML" / terminal styling, double-ruled banner, no
grays. Green/red reserved strictly for +/- metrics, exactly as you asked.

1. **Champion Survival** — the P1 dashboard. Champion, tier, survivability score,
   out-of-sample (1st-half vs 2nd-half) consistency, and a **10 / 25 / 50 / 100
   trade milestone bar** that fills as trades accumulate. Full stats: total return,
   expectancy, win%, Sharpe, max drawdown, profit factor, t-stat.
2. **Open Positions + Exit Plan** — the JTO fix. Every position with entry, mark,
   P&L%, target, stop, time held, and what it exits at. (Mark shows entry until the
   live-quote source is wired — this snapshot's book stores no marks.)
3. **Realized Equity Curve** — a real chart with working **1D / 3D / 5D / 1W / ALL**
   interval buttons, green/red bars, scaled properly. Replaces the old broken bars.
4. **Arena** — strategy survival leaderboard with tiers.

Coin favicons load from a CDN by ticker (degrade silently if missing).

## The seven 2.17 priorities — honest status

- **P1 Champion Survivability** — ✅ dashboard built (stats, CIs, milestones, OOS).
- **P2 Stop-Width Validation** — ◻️ partially visible (the arena already shows s2/s4/s6
  side by side; s4/s6 lead s2). A dedicated by-stop-width expectancy/drawdown report
  is a small next step on top of `champion_validation.py`.
- **P3 Deployment Forensics** — ◻️ the cockpit now shows per-position target/stop/timeout;
  full "why this rank / why rejected" needs the sizing+rank reason stamped at buy time.
- **P4 Workflow Hardening** — ❌ NOT done. Needs auditing the GitHub Actions YAML +
  reset/compaction/backfill scripts for locks + atomic writes. The `hold`/`max_hold_min`
  bug above is exhibit A. This is the right next major focus, as you said.
- **P5 Disaster Recovery** — ❌ NOT done. Needs the lock/atomic-write layer first.
- **P6 Stock Engine Parity** — ❌ NOT audited. (The stock book shows 0 trades — the
  sim-vs-live disconnect — so parity matters but has nothing to compare yet.)
- **P7 Authority Lab** — ✅ unchanged: research only, never trades. Correct as-is.

## What I did NOT do this pass (and why)

- **The full site in black-and-white.** I built the flagship cockpit as the template.
  Converting index / paper_sim / lifecycle / leaderboard to the same CSS is
  mechanical but large; doing it carelessly in a rush would break working pages.
  Next pass: lift the cockpit's `<style>` into a shared `silmaril.css` and apply it
  page by page, then flip all banners to "2.5."
- **Workflow hardening / disaster recovery (P4/P5).** This is real infrastructure
  work (locks, atomic temp-file→rename writes, recovery tests) that deserves its own
  focused session, not the tail of a UI pass. It is the highest-value *non-UI* thing
  left, and I'd recommend it as the very next session.

## My honest synthesis

You're right on every count: the danger now is overfitting (don't build 50 MR
variants), the milestone that matters is 100 out-of-sample trades, and the job is to
make the system unable to lie to you. This release moves two of those forward — the
cockpit makes the survival question and every exit legible at a glance, and it
answers JTO concretely. The two things between you and "trustworthy" are now clearly
named: **(1) harden the workflows so a bad run can't corrupt state, and (2) let the
champion reach 25→50→100 trades so the survivability score means something.** Neither
is a new engine. Both are patience plus plumbing. That's the right place to be.
