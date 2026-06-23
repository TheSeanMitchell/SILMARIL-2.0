# SILMARIL 2.5 — Champion Governance Fix (Alpha 2.18 Priority 1)

Resolves the flagged mismatch. Drop on the repo root, overwriting.

## The fix

Your biggest surprise — `most_survivable=MR_d3_t3_s4` but `declared_champion=
MR_patient_d3` — was real and now fixed at the source. champion.py was selecting on
*backtest leaderboard window-dominance*; champion_validation ranks on *forward
survivability*. Those disagreed, and a decayed champion was sticking.

champion.py now selects the champion as a **pure function of forward survivability**:
the highest-survivability strategy with ≥5 trades, switched only on a ≥15-point
survivability margin (sticky, anti-flip-flop), aggregate books excluded, **no manual
overrides**. On current data it correctly promotes:

  MR_d3_t3_s4 (survivability 87, n=9, +23%, 78% win, OOS-consistent)
  over MR_patient_d3 (survivability 39, n=6, +2.7%) — the decayed incumbent.

The sim now trades s4's params, including its **0.04 stop** (the wider stop the arena
showed was capturing more — so this also acts on the earlier conversion finding).

New `champion_governance.py` emits **CHAMPION_GOVERNANCE.json** every cycle (P1's
required artifact): declared champion, most survivable, alignment status, trade
count, survivability, CI, tier, promotion ladder, recent promotions, and the
selection rule. It currently reads **ALIGNED**.

## Files

- `silmaril/execution/champion.py` — survivability-governed selection.
- `silmaril/execution/champion_governance.py` — the governance report (new).
- `silmaril/cli.py` — governance wired after validation.
- `docs/data/{champion,champion_validation,CHAMPION_GOVERNANCE}.json` — regenerated,
  consistent (all show s4, aligned).
- `WORKFLOW_AUDIT.md` — P4 audit doc (hardening from last session).

## The other 13 priorities — honest status

- **P1 Champion Governance** — ✅ done (this release).
- **P2 Statistical tiers (10/25/50/100)** — ✅ thresholds applied in governance/validation.
- **P4 Workflow Hardening** — ✅ done last session; documented in WORKFLOW_AUDIT.md.
- **P13 Authority research-only** — ✅ unchanged (never trades).
- **P3 Deployment explainability** — ◻️ partial (cockpit shows per-position exit plans;
  full conviction/rank/why-rejected report is next).
- **P5 Disaster recovery** — ◻️ deferred per your call (manual backups).
- **P6 Stock parity audit** — ◻️ the stock book runs the same code but is idle (3% dip
  rarely hits liquid names); a STOCK_PARITY_AUDIT + stock-tuned thresholds is a
  deliberate later step, not a new signal.
- **P7 Mobile-first UI / P8 Command Center / P9 Dark mode / P10 Gem favicon /
  P11 Daily snapshots / P12 Aggression ladder / P14 Platform scorecard** — ◻️ not yet.
  These are substantial; the cockpit is the styling template to build them on.

## Honest bottom line

The single most important integrity bug — a champion that didn't match its own
evidence — is closed. Selection is now mechanical and auditable, and it picked the
strategy the data actually favors. That moves Learning and Statistical Confidence
the most, which is the fastest path toward 9/10. The remaining gap is breadth (mobile,
command-center, snapshots, aggression ladder) plus time for trades to accumulate —
not correctness. The platform now tells the truth about its own champion.
