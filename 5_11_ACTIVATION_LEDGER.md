# 5.11 ACTIVATION LEDGER — the sendoff build (2026-07-13, markets open)
### Every ask from the final directive, closed with receipts. Battery: 26/26 · browser: 7 tabs, 0 errors, 0 stuck — verified on the LIVE repo with live trades flowing.

## THE ZERO-TRADES NIGHT — root-caused with receipts, then cured
Sunday night, 2h post-reset, zero trades. The receipts: the deepest 1-hour dip across all 90 fresh
crypto names was **OP-USD −1.96%** against a blanket −3.0% crypto bar and −2.0% GEKKO bar (missed
by 0.04). The engine was ARMED and honest — the one-size threshold was blind to a quiet tape.
**The cure — VOL-NATIVE ENTRIES:** every name's bar = clamp(k·σ1h, class floor, min(class cap,
regime base)), where σ1h is a robust MAD of the name's ACTUAL trailing-1h moves. 81 crypto names
immediately carried their own bars (XLM 1.2%, DYDX 1.2%, WLD 1.68%, OP 2.1% — because OP's normal
hour IS ±1.4%, so −1.96% genuinely wasn't special FOR OP). Custom-fitted decision making on every
trade, literally. Knob `vol_native` (off restores blankets) + pre-registered kill on the report card.
(Also corrected for the record: the funnel "warm=None" scare was my own probe reading the wrong
keys — the funnel was never broken.)

## METAL & ENERGY "FROZEN" — diagnosed, and the honest verdict
Receipts from the 11 AM live data: metal seen 12 → warm 12 → **candidates 0** in a −1.67%/6h
DOWNTREND; energy 6 warm in a +2.49% UPTREND. Two causes, two cures:
1. The DOWNTREND regime profile had **no metal/energy-native entry** (metals physically can't dip
   3% intraday) → added `regime_overrides` metal DOWNTREND 0.5%/0.7% and energy DOWNTREND 1.0%/1.4%.
2. Vol-native covers the rest — and the weekend test exposed one more truth worth keeping: all 103
   metal 1h-moves were EXACTLY 0.0% (the feed republishing Friday's price — your documented
   stale-oscillation mode). σ=0 → vol-native correctly refuses to arm entries on prints that can't
   fill honestly. **Metals get their bars the moment Monday's session actually moves.** That's the
   system protecting you from fantasy fills, not a freeze.

## THE BRAIN — wired, visible, and machine-guarded (see DOCS_5_1/13)
- New 🧠 BRAIN tab: MASTER BRAIN leans · the COIN MACHINE (seen→warm→candidates→bought, every
  block named, coins animate per buy) · SIGNAL LEDGER (14/14 wired, shift arrows, consumers
  selftest-verified — a decoration renders RED and fails the battery) · CONFIDENCE ANATOMY (all 9
  components per name) · DR. STRANGE self-graded career now FEEDING the gate (it was already
  grading itself — 18 resolved, 55.6% hit-rate — and nothing consumed it; classic disconnection,
  now closed) · SYMBOL DOSSIER (peaks, NEXT-PEAK ETA, bounce likelihood, trajectory, its own buy
  level, why) · ALL-CHARTS EYESHOT (every open position, entry/target/stop overlaid).
- `brain_wiring.py` on the spine each cycle → `BRAIN_WIRING.json` (+ master_brain snapshot).

## INDUSTRY LAWS (the anti-lockup thesis applied beyond crypto)
`position_caps` knob — max TOTAL open per book (crypto 10 · GEKKO 10 · stock 6 · metal 5 ·
energy 5): a new name must beat a held one for a slot; every cap-skip logged. The 72h fee-clear
recycle, regime-flip harvest, and conviction sizing already governed ALL books (5.1B) — now
concentration does too. The A/B/C/D lab keeps racing the full discipline stack on crypto.

## HARDENING FOUND BY LIVE-DATA PROBING (each with a guard)
- `cR is not defined` crash in SESSION ANATOMY (transplanted block using another renderer's
  variables — only fired once real trades existed) → orphan removed.
- READINESS "NaN%" / empty after wipes (null champion metrics) → NaN-proofed + honest null state.
- Fingerprint rebuild budget 80→150/cycle so coverage returns fast after resets.
- Dr. Strange gate row now prints its live hit-rate.

## TRIPWIRES ADDED (battery now 26)
T22 brain-map truthfulness · T23 dr-strange-grades-feed-gate · T24 vol-native clamps
(floor/cap/base/off) · T25 BRAIN tab contract · T26 dossier contract.

## VERIFIED ON THE LIVE 11 AM REPO
Compile sweep PASS · node --check PASS · selftest **26/26** · brain build: **14/14 signals wired ·
24 live dossiers** · browser probe: **7/7 tabs, 0 JS errors, 0 stuck panels** · live catalog
merged (your tuned values untouched; only the new knobs added).

## ONE HONEST LINE
The wiring is now provable and the thresholds finally read each name's own pulse — but the
100-trade/90-day bar hasn't moved, and today's green (+$966 realized all-books at 11 AM) is one
morning, not an edge. The machine will now tell you the truth faster; it still can't promise what
the truth will be.
