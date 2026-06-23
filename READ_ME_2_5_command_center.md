# SILMARIL 2.5 — Unified Command Center (the UI round)

Drop on the repo root. Front-end only — zero logic touched. `docs/index.html` is now
the command center (old page preserved as `docs/legacy_dashboard.html`).

## What changed: 30 dashboards → one operating system

A single tabbed app instead of stacked pages:

- **COMMAND** — account (both books side by side, combined equity, realized P&L,
  cash, open counts), champion card grid, 10/25/50/100 milestone bar, the
  sample-gated readiness meter, and open positions (crypto + stock) — tap any
  ticker for its chart.
- **ARENA** — strategy survival leaderboard + the promotion ladder.
- **FORENSICS** — **survivability-over-time and equity-over-time line charts built
  from the snapshot history** (the payoff of last round's snapshot engine), plus
  edge capture, opportunity journal, execution leak.
- **AUTHORITY LAB** — authority events, clearly marked research-only.
- **SETTINGS** — theme toggle + links to the legacy/debug pages.

## The three things you asked for, done

- **Mobile-first.** Viewport locked, tab bar scrolls horizontally (page never does),
  every wide table sits in its own `overflow-x:auto` card, stat grids collapse to a
  single column under 560px. Usable at 375px and down.
- **Dark mode.** Toggle top-right, persisted in `localStorage`, survives refreshes.
  Every element is themed via CSS variables; green/red stay meaningful in both.
- **Uniform & professional.** One theme, one layout language, the retro
  black-and-white feel throughout — light or dark.

The ticker chart modal (our own price chart with ENTRY/TARGET/STOP/MARK overlaid)
is kept and themed.

## Universe — your question

Confirmed: **92 crypto + 536 stock = 628 names tracked, both books run side by side
every cycle.** Crypto trades now; stocks will fire during market hours **once the
freshness fix from the 2.17 zip is installed** (this backup didn't have it — install
that one too, then stocks start generating candidates and the STOCK column here fills).

## Honest note

This is the watch-and-wait surface you wanted, made clean. It changes nothing about
the edge — the champion still needs 25 → 50 → 100 trades. But now the wait is
legible on any device, and the snapshot charts will visibly grow as the days pass.
