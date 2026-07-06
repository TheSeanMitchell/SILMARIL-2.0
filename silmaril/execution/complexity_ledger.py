"""
COMPLEXITY ACCOUNTING (Movement V, Phase 28) — REPORT-ONLY during the harvest, by explicit operator
decision. Measures each subsystem's footprint and evidence output; NEVER retires, disables, or
down-weights anything for complexity reasons. Growth preserved; cost merely measured.
"""
import json, os
from datetime import datetime, timezone
from pathlib import Path

SUBS = {
 "regime_classifier": "REGIME_CLASSIFIER.json", "master_gate": "MASTER_DECISIONS.json",
 "integrity_layer": "INTEGRITY_QUARANTINE.json", "regime_combos": "REGIME_COMBOS.jsonl",
 "calibration": "CALIBRATION.json", "research_queue": "RESEARCH_QUEUE.json",
 "evolution_ledger": "EVOLUTION_LEDGER.jsonl", "daily_baseline": "DAILY_BASELINE.json",
 "aggression_ladder": "AGGRESSION_LADDER.json", "weekly_scorecard": "WEEKLY_SCORECARD.json",
 "news_trial": "NEWS_TRIAL.json", "regime_ab": "REGIME_AB.json",
 "wide_arena": "strategy_leaderboard_wide_crypto.json", "chart_overlays": "CHART_OVERLAYS.json",
}

def build_complexity_ledger(out_dir):
    out = Path(out_dir)
    rows = []
    for name, f in SUBS.items():
        p = out / f
        rows.append({"subsystem": name, "output": f,
                     "evidence_bytes": p.stat().st_size if p.exists() else 0,
                     "producing": p.exists(),
                     "contribution": "unmeasured — accrues over harvest",
                     "action": "REPORT-ONLY (operator decision: no auto-simplification during harvest)"})
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "mode": "REPORT-ONLY — no automatic retirement during the 3.0 harvest",
               "rows": rows}
    (out / "COMPLEXITY_LEDGER.json").write_text(json.dumps(payload, indent=1))
    return payload
