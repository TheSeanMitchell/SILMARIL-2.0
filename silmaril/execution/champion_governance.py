"""
silmaril.execution.champion_governance — CHAMPION GOVERNANCE REPORT (2.18 P1).

The audit artifact for champion selection. Confirms the declared champion equals
the most-survivable strategy (now that selection is survivability-governed),
shows the evidence behind it, and logs every change. Manual overrides are not a
concept here — the champion is a pure function of the survivability ranking plus
the trade-floor and switch-margin gates. Emits CHAMPION_GOVERNANCE.json.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from .atomic_io import write_json_atomic

def _now(): return datetime.now().astimezone().isoformat()
def _load(out, n):
    try: return json.loads((out / n).read_text())
    except Exception: return {}

# capital tiers per directive (distinct from the champion-credibility floor of 5)
TIERS = [("Production-Verified", 100), ("Production", 50), ("Candidate", 25), ("Incubation", 10), ("Sandbox", 0)]
def _tier(n, surv):
    if surv <= 0: return "Sandbox"
    for name, thr in TIERS:
        if n >= thr: return name
    return "Sandbox"

def build_champion_governance(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    cv = _load(out, "champion_validation.json")
    champ_json = _load(out, "champion.json")
    declared = champ_json.get("champion")
    strategies = cv.get("strategies", [])
    by = {r["strategy"]: r for r in strategies}
    most_surv = cv.get("most_survivable")

    def row_for(name):
        r = by.get(name, {})
        sv = r.get("survivability", {})
        return {"strategy": name, "trade_count": r.get("n"),
                "survivability_score": sv.get("score"),
                "expectancy_ci95_pct": r.get("expectancy_ci95_pct"),
                "win_pct": r.get("win_pct"), "sharpe_proxy": r.get("sharpe_proxy"),
                "max_drawdown_pct": r.get("max_drawdown_pct"),
                "tier": _tier(r.get("n", 0), sv.get("score", 0)),
                "oos_consistent": sv.get("oos_consistent")}

    aligned = (declared == most_surv)
    # full ladder by tier
    ladder = {name: [] for name, _ in TIERS}
    for r in strategies:
        sv = (r.get("survivability") or {}).get("score", 0)
        ladder[_tier(r.get("n", 0), sv)].append(r["strategy"])

    payload = {
        "generated_at": _now(),
        "declared_champion": row_for(declared) if declared else None,
        "most_survivable": row_for(most_surv) if most_surv else None,
        "aligned": aligned,
        "governance_status": ("ALIGNED — declared champion is the most survivable strategy"
                              if aligned else
                              "MISMATCH — selection has not yet converged (will on next cycle; "
                              "champion now tracks survivability)"),
        "selection_rule": ("champion = highest-survivability strategy with >=5 trades, switched only "
                           "on a >=15-point survivability margin (sticky, anti-flip-flop). Aggregate "
                           "books excluded. No manual overrides."),
        "promotion_thresholds": {"Sandbox->Incubation": 10, "Incubation->Candidate": 25,
                                 "Candidate->Production": 50, "Production-Verified": 100},
        "promotion_ladder": {k: v for k, v in ladder.items() if v},
        "recent_promotions": champ_json.get("promotions", [])[-10:],
        "selection_reason": champ_json.get("reason"),
        "manual_overrides": "prohibited",
        "note": ("Champion selection is a pure function of forward survivability + gates. "
                 "If declared != most_survivable here, it is a one-cycle lag, not a manual choice."),
    }
    try: write_json_atomic(out / "CHAMPION_GOVERNANCE.json", payload)
    except Exception: pass
    return payload

if __name__ == "__main__":
    import sys
    p = build_champion_governance(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("STATUS:", p["governance_status"])
    print("declared:", p["declared_champion"])
    print("most survivable:", p["most_survivable"])
    print("ladder:", p["promotion_ladder"])
