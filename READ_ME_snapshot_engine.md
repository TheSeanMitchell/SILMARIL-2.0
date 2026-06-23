# SILMARIL — Snapshot Engine (ergonomic prep, no logic touched)

Drop on the repo root. Additive only — touches no trading logic, no champion
selection, no strategy params. Just record-keeping you'll be glad to have.

## What it does

Every cycle it records the platform's state, so you build a trend trail while you
wait. Two outputs, designed to stay git-friendly (no thousands of folders):

- **`docs/data/snapshot_history.jsonl`** — one compact line per cycle (capped to the
  last ~5000, i.e. weeks): champion, survivability, trade count, win%, crypto/stock
  equity, realized P&L, open positions, edge capture, arena top 3. This is the file
  the UI round will plot as "survivability over time" and "equity over time."
- **`docs/data/snapshots/<date>.json`** — one immutable full baseline per day,
  written once on the first cycle of the day (champion_validation + governance +
  capital_allocation + live positions). Forensic gold for "what did the system look
  like the morning of X."

Wired to run at the very end of each cycle, fully fail-safe (skips silently if a
source file is missing). Uses atomic writes.

## Why this, now

You asked for functionality/ergonomic prep while you wait on logic and data — this
is the cleanest fit. It costs nothing, risks nothing, and the sooner it starts the
more history exists when the UI round arrives. Today's first snapshot already
captured the moment: champion MR_d3_t3_s4 (survivability 87, 9 trades, 77.8% win),
crypto equity $10,100, **realized $124.51 on the day**, edge capture up to 17% (from
0% a few days ago).

## Honest note

This is observability, not proof. It makes the wait legible and the eventual
forensics easy — it does not change the fact that the champion still needs 25 → 50 →
100 trades before the numbers mean something. That's still the only bottleneck, and
it's still just time. UI overhaul is queued for next round as you asked.
