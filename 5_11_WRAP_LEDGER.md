# 5.11 WRAP LEDGER — every directive closed, with receipts (2026-07-13)
**Verified on the live 4 PM repo: compile sweep ✓ · node --check (index + chart) ✓ ·
selftest 29/29 ✓ · browser probe 7/7 tabs, 0 JS errors, 0 stuck ✓ · engines re-run on live
data (1050 cards · 24 lab sleeves · 15/15 brain signals).**

## 1 · "Make sure our wins are not the result of any bugs" — they partly were. Receipts:
Your sawtooth screenshots were real: every crypto name alternated two price clusters
(BTC 64198↔62057, ETH 1834↔1760 …) with a UNIFORM low/high ratio 0.963–0.968 across all
names — one recorder source was serving ~2h-stale prices on a −3.4% day, interleaved with the
live source. paper_sim then "won" the gap: **crypto 15/33 + GEKKO 16/36 closed wins sat in the
+2.5–4.5% phantom band (~$1.0k of the day's $1.77k realized).**
**Cures (all landed, tripwired by T27):**
- Recorder **two-print confirmation** (momentum_chain): any tick jumping >1.5% goes pending;
  accepted only if the next fetch confirms within 0.75%. A real crash confirms; an alternating
  stale source never can. Rejections logged as `unconfirmed_jump`.
- Reader **oscillation quarantine** (`_osc_ratio`): two-cluster tapes are barred from entries,
  marks median-smoothed for exits, count + names surfaced in DATA-SOURCE HEALTH.
- Every SELL now carries **integrity: ok | SUSPECT_OSC**; the report card prints
  `suspect_trades / suspect_usd / verified_realized_usd`.
- **integrity_backfill workflow** (dispatch, confirm=TAG) retro-tags July-13's phantom-band
  wins so history tells the truth too.
- Unit proof: today's exact BTC sawtooth → QUARANTINED; a real −6% trend → safe. (Perfect
  ±alternating chop also quarantines — indistinguishable from a feed fault, by design.)

## 2 · The UNIVERSAL CONFIDENCE CARD (the focus): 1050 cards, 27 fields each
Rhythm (cycle, amplitude, last peak/trough), **expected hold = the name's own cycle**, σ1h and
its **own vol-native bar**, fingerprint dip→bounce + bounce likelihood, momentum trajectory,
best buy/sell windows, our live record on the name, and **compounder_score = confidence ×
swing × cadence** with a leaders board (today: OP · LDO · FLOW on top — the NEAR-style
daily-compounding bread and butter, exactly as specified). **Wired in, not decorative:**
compounder tilts live sizing (knob `compounder`, max_tilt 1.25, kill via sizing A/B); E-sleeve
strike pools come from the cards; the per-symbol chart now renders the full CONFIDENCE CARD
block (chart ⇄ card parity); the BRAIN dossiers use the same facts; T28 guards the contract.

## 3 · Rhythm-holds: "if it says 312m, expect to hold 312m"
Every BUY stores `exp_hold_min` = the name's median peak cycle; fee-clear recycling can never
fire before `cycle × 1.15`. Patience is now per-name, not blanket.

## 4 · Per-industry STRATEGY LAB with E + F (T29)
crypto · stock · metal · energy each run A–F: control, cap-only, full discipline, sniper,
**E ADAPTIVE STRIKER** (opens +2 strike slots on surge; buys the ≥+3%/h movers; rides with a
trail — the "+7% energy day never missed again" law under test), **F CASH HARVESTER** (every
realized profit vaulted non-spendable; $10k working base — your honesty experiment made a
sleeve). Legacy crypto A–D state migrates automatically. UI shows four stacked industry tables
with a VAULT column.

## 5 · Honesty layer
**OPEN-TRADE TRUTH** under TODAY NET: dollars committed across open trades per book +
"profits are only real when flat" + the suspect/verified split. Nulls now include **QQQ**
buy-and-hold beside SPY/HODL/EQW.

## 6 · Ops & fixes
Selftest SyntaxError on the runner (backslash f-string, py<3.12) fixed — no backslash
f-strings remain (asserted). INV8 tolerance = max(5¢, 1¢×trades) — 3¢ rounding on 36 trades is
arithmetic, not corruption. Clock now shows **"engine updated Xm ago"**. Repo hygiene:
`cleanup_5_11` workflow (confirm=SUNSET) attics superseded root docs + stale cleanup
workflows; README + this ledger + SILMARIL_MASTER_BRIEF are the cumulative record.

## 7 · The wipe question — YES, tonight, after installing this ZIP
Reasons: (a) today's tape is oscillation-tainted and the recorder now rebuilds a
confirmed-clean tape in ~2h; (b) the lab restructure re-baselines sleeves anyway; (c) you want
Tuesday to start the clean week with cards, holds, tilt, E/F, and integrity all armed from
minute one. If you choose NOT to wipe, run the integrity backfill (confirm=TAG) so July-13's
headline splits into suspect vs verified.

## One honest close
Today's great number was partly the bug — the verified line is the real one, and the machine
now computes that line itself, every cycle, forever. The 100-trade/90-day bar hasn't moved.
