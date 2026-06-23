# SILMARIL — tradability "not active" fix  +  pristine-reset safety answer

Two files. Drop on the repo root. Both compile clean; the fix is proven on your
11:30 data. This is a small, surgical drop — the honest assessment is in the
chat message, not here.

## What this fixes
Recovery mode was firing correctly but filling **nothing**, because the names it
picked (MKR, TRX, ALGO …) kept getting rejected by Alpaca with
`422 "asset ... is not active"` (code 40010001) — and the tradability registry
only learned `422 "not found"` (42210000). So those coins were re-submitted
**every cycle**, wasted the open budget, and starved the probes.

- `silmaril/execution/tradability.py` — now learns **both** 422 codes (not found
  AND not active), so a coin Alpaca won't fill is recorded once and skipped
  forever after.
- `docs/data/untradeable_assets.json` — pre-seeded the four persistent offenders
  from your error log (MKR ×15, NEAR ×5, TRX ×2, ALGO ×1) so they're skipped on
  the **next** run, not after another failed attempt. Registry is now 59 names.
  (This file is plain JSON — if any coin later becomes tradable on Alpaca, delete
  its line to re-enable it.)

## Pristine reset — IS IT SAFE WITH THE NEW CHANGES? Yes.
I read `scripts/pristine_reset.py` against every change shipped. A reset:
- Sets each account to clean $10k, no positions.
- **Clears the halt** — `daily_halted=False, weekly_halted=False,
  cohort_safe_mode=False`, and re-anchors `daily_open_equity` to $10k. This
  resolves the deadlock cleanly by itself.
- Does **not** touch agents, scoring, learning, or the tradability registry
  (0 references) — so the seeded blocklist and everything learned survives.

After a reset the state is exactly what the new code expects: equity $10k, daily
%=0 → no halt → `composite_halt`/`recovery_mode` both false → normal trading; no
positions → the exit ladder is idle until it buys; the fresh gate and router run
normally. **No schema field the new code reads is removed.** It is safe.

## But read this before you reset
A reset fixes the *scoreboard*, not the *strategy*. It clears the halt and the
drawdown, but the engine will resume with the same entry logic — and the data
(see chat) says that logic has no edge yet. You already saw it: "small bump,
then steady decline." A reset will reproduce that. Reset when you've **changed
the thing that loses**, not before — otherwise you're just re-zeroing the clock
on the same bleed.
