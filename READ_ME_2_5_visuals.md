# SILMARIL 2.5 — Cockpit Visuals + Our Own Chart System

Drop on the repo root, overwriting docs/index.html + docs/cockpit.html (legacy
dashboard preserved as docs/legacy_dashboard.html). Pure front-end — no engine
changes, no risk to the running system.

## What's new

**Our own ticker chart system.** Click any ticker in the position tables → a modal
opens with a real price chart (drawn from your own price_samples.json, ~534 points
for JTO) and our expectations overlaid as labeled lines: ENTRY (dashed black),
TARGET +3% (green), STOP −5% (red), LIVE MARK (blue), plus a shaded target zone and
the mean-reversion thesis in plain English. Interval buttons (1D/3D/1W/ALL). This is
the thing X.com/CoinDesk/Binance can't give you — the price AND what the system
expects to do about it, on one chart. (First open lazy-loads the 15MB price file
once, then it's cached.)

**Live position health (crypto + stock, side by side).** Pulls live marks and uPL%
straight from paper_sim_live.json — JTO is currently +2.51%, WAVES −0.53%, DYM
−1.28%. Each row shows entry, live mark, uPL%, a dual target/stop distance bar
(green = room to target, red = room to stop), and a hold clock (held / timeout
minutes). Stock book sits ready and empty until stocks trigger.

**Live-trading readiness meter — honestly sample-gated.** A composite meter plus
sub-gates (out-of-sample trades, positive expectancy, OOS survival, drawdown,
Sharpe). Crucially, the score is GATED by trade count: perfect stats on 5 trades
still reads ~5% ready, because 5 trades is noise. It only climbs toward 100% as the
champion actually accumulates trades. This is your own discipline made visual — it
will not let the dashboard flatter you.

**Bolder, legible text.** Base weight bumped to 600, all +/- metrics bold, larger
percentages. The unreadable numbers should be readable now.

**Both books, everywhere.** Equity curve has a CRYPTO/STOCK toggle; positions show
both; arena and readiness already span every book. You're set to watch crypto and
stocks the same way when markets open.

## Honest notes

- **Stock strategy parity is structural, not cosmetic.** The stock book runs the
  same arena/validation/promotion code — but it has 0 trades because the MR trigger
  (a 3% dip) rarely fires on liquid names. Watching stocks "the same way" works; if
  you eventually want stocks to actually *trade*, they'll likely need their own
  thresholds (a smaller dip), which is a deliberate backend change for later — not a
  new signal, just a stock-tuned MR. Flagging, not doing, to avoid drift.
- **The `hold` bug is still open** and now visible: paper_sim_live shows champion
  max_hold_min 484 while the sim default is 240. The cockpit uses the champion's
  484 for its hold clock. Worth reconciling in the engine next.
- **Secondary pages** (paper_sim, lifecycle, leaderboard) aren't yet reskinned to
  this theme — the cockpit is the template; lifting its CSS into a shared file and
  applying it is the remaining UI step.

## Bottom line

The cockpit now feeds the urge to watch without lying to you: live position health,
a real chart with our expectations on it, and a readiness meter that stays honest
about how early it is. Open it, click JTO, watch the bounce play out against the
target line. Then let the week of data come in — crypto and stocks both.
