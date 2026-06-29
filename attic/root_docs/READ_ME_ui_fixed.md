# SILMARIL 2.5 — UI Fixed + Cron Confirmed

Drop on the repo root, overwriting. `docs/index.html` is the working command center.

## The blank-page bug — fixed and verified

The whole UI was blanked by a single JavaScript syntax error (a missing `)` in a
nested ternary on the champion-note line). One syntax error halts the *entire*
script, so every data panel rendered empty — exactly what you saw all morning.

This time it's verified with a real JS syntax check (`node --check`), not just tag
counting. And it's now **bulletproofed**: every panel renders inside its own
try/catch, so even a malformed or missing data field can only blank *that one
panel*, never the whole page. If core data ever fails to load, you get a visible
"Data not loaded yet" notice instead of a blank screen.

## Cron — already at 15 min

There is no `*/10` cron anywhere. `daily.yml` already runs `*/15 13-20 * * 1-5`
(every 15 minutes during market hours, weekdays). Shipping it so your deployment
matches. With 12–15 min runtimes the cadence is tight, but the `silmaril-state`
concurrency group means a run that overruns just queues the next one — no overlap,
no corruption.

## Stocks getting crushed — the honest read

The stock book is down ~$93 (−1.37%) with **53 open positions**. Here's what's
actually happening, plainly:

Mean reversion buys dips expecting bounces. That works in choppy/ranging markets and
**structurally loses in downtrends** — when the whole market sells off, every name
dips, so MR fires on *everything* (hence 53 positions) and each dip keeps dipping.
You're not seeing a bug; you're seeing MR's known failure mode, live.

What this means, and what to do:

1. **It's paper. Sandbox tier. No real capital is at risk.** This is exactly why the
   promotion ladder exists — a strategy that bleeds stays in Sandbox and never earns
   real money. The gate is doing its job.
2. **A bad day is data, not failure.** The arena measures stock-MR's survivability.
   If it's negative — which today says loudly — it simply won't promote. That's the
   system protecting you, working as designed.
3. **Do NOT curve-fit to this.** Tweaking the stock strategy after one rough session
   is how edges get destroyed. The disciplined move is to let survivability accumulate
   and judge.
4. **Careful with "law of averages."** MR doesn't average out in a trend — it bleeds
   until the trend stops. The honest possibilities are: stock-MR needs a regime/trend
   filter (a deliberate, evidence-led change *later*, not a panic tweak), or stock-MR
   simply doesn't clear costs and the arena will retire it. Both are fine outcomes —
   the point of the lab is to find out, on paper, for free.

One observation worth noting (not changing): the stock book deployed into 53
simultaneous falling positions — it has no trend guard and no obvious position cap.
That's the single biggest structural difference from how you'd want stocks to behave
eventually. Flagging it as the thing to study once there's data — not something to
bolt on mid-validation.

## Bottom line

You can finally watch it again, on any device, light or dark. Crypto is modestly
green (+$114), stocks are red (−$93) and that's MR meeting a downtrend on paper. The
gate keeps the red away from real capital. Let both books keep stacking trades — the
survivability scores will tell you which asset MR actually works on, and that answer
is worth far more than any single day's P&L.
