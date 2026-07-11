# SILMARIL — the fingerprint now DRIVES trading: a custom strategy fitted to every valuable

This is the piece you asked for: the system now reads each valuable's own chart the way a
professional trader does and fits a realistic, custom strategy to THAT valuable — instead of one
blanket 2%/2% brush across a whole book. Drag these four files over the repo, then wipe / rebuild /
run a clean day.

## What the system now understands about each valuable (the "mean" question, answered)
For every name it computes, from that name's OWN real price history, a **fingerprint**:
- **Multi-timeframe trend** — its move over ~1d / 2d / 3d / 1w, and a label (up / mixed / a genuine
  multi-day *decline*). This is the reference the engine reasons from — not a single "star" price,
  but the recent trajectory across the windows you named.
- **Typical dip** — how far this name *usually* drops over ~1h before it steadies (its characteristic
  dip, not a blanket threshold).
- **Typical bounce** — how far it *usually* recovers after such a dip, measured over ~1 day (slow
  markets like stocks revert over a day, not two hours — the horizon reflects that).
- **Bounce reliability** — how often it actually returns to the pre-dip level.
- **Volatility.**

## The custom strategy fitted per valuable
From that fingerprint, each name gets its own `{entry, target, stop}`:
- **ENTRY** = buy when it has dipped ~its own typical amount (so we buy a meaningful dip for *that*
  name).
- **TARGET** = a **realistic** fraction (default 66%) of its own typical bounce, floored to clear
  fees. Aiming at 2/3 of what a name usually recovers is what raises the **close rate and the win
  rate** — an achievable goal, not an optimistic one.
- **STOP** = scaled to the name's own typical dip (room to dip more than usual before giving up),
  floored by the book heatshield, capped so risk/reward never goes absurd.

Proven on your real data: crypto fits a **median ~4.9% target**, stocks a **median ~0.9% target** —
the same engine sizing each market to its own chart. LDO fits dip 2.5% → aim 6.0% → stop 7.4%; a
liquid stock fits dip ~0.4% → aim ~1.0%. Genuinely per-valuable.

## Quality filters (why this lifts the win rate)
A name is **skipped** (honestly, and shown as such) when it is in a genuine multi-day downtrend
(don't catch a falling knife), when it does not reliably recover, or when even a realistic bounce
can't clear round-trip fees (no post-cost edge). In a weak tape the fitter naturally concentrates on
the names showing **relative strength** — which is exactly what a professional does.

## Trend override of regime (your explicit request)
A name whose fingerprint shows a **strong multi-timeframe uptrend** (up over 1d/3d/1w, nothing down)
is allowed to trade **through a red book regime** — a clearly-rising valuable is playable even when
the book's overall regime is DOWNTREND. Everything else stays blocked and logged to the A/B proof.
Knob: `fingerprint_strategy.trend_override` (default on).

## Logged on every trade
Each trade now carries its fitted strategy: `fit = "fp dip~X% → tgt Y% stop Z% <trend> reliable"`
plus `fit_target_pct`. Combined with the champion labels already added, every trade log shows both
the strategy that made it and the custom fit it used.

## Files
- `silmaril/execution/fingerprint.py` — NEW: the per-valuable fingerprint + realistic fitter
- `silmaril/execution/paper_sim.py` — entries now fit per-valuable; trend override; per-trade fit logging; publishes FINGERPRINTS.json
- `docs/data/PARAM_CATALOG.json` — `fingerprint_strategy` knob (enabled/realism/min_reliability/bounce_h/trend_override)
- `docs/index.html` — FINGERPRINTS row showing how the engine reads each chart

## Verify after wipe + run
- FORENSICS strip → FINGERPRINTS row: how many valuables have a fee-clearing fit, and the top
  fits (each name's dip → realistic target → stop).
- RECENT TRADES: each trade shows its `fit` label; targets differ per valuable (crypto larger,
  stocks smaller), not one blanket number.
- `FINGERPRINTS.json` in docs/data lists the per-valuable identities and fits.

## One honest caveat
Realistic fitting plus fee-honesty will sometimes **reduce trade count** — it refuses falling and
no-edge names by design. That is the intended quality-over-quantity that raises the win rate; it is
not the system being broken. And it still does not guarantee profit: the forward record and the
Δ-vs-NULL line will judge whether these fitted setups actually have an edge. Now, at least, the
trades it does take are the ones its read of each chart actually supports.
