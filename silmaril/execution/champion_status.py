"""
silmaril.execution.champion_status — CHAMPION_STATUS.json (Alpha 2.17 S1).

The single champion-first artifact. Pulls the declared champion's stats from the
validation + governance outputs into one focused file. No new computation, no new
signals — just the champion, front and center, with promotion eligibility.
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

THRESH = {"Incubation": 10, "Candidate": 25, "Production": 50, "Production-Verified": 100}

def build_champion_status(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    cv = _load(out, "champion_validation.json")
    gov = _load(out, "CHAMPION_GOVERNANCE.json")
    champ = gov.get("declared_champion") or {}
    name = champ.get("strategy") or cv.get("declared_champion")
    row = next((r for r in cv.get("strategies", []) if r["strategy"] == name), {})
    sv = row.get("survivability", {})
    n = row.get("n", 0)
    # next tier + trades needed
    nxt, need = None, None
    for tier, thr in THRESH.items():
        if n < thr:
            nxt, need = tier, thr - n
            break
    payload = {
        "generated_at": _now(),
        "strategy": name,
        "survivability": sv.get("score"),
        "trade_count": n,
        "win_rate_pct": row.get("win_pct"),
        "expectancy_per_trade_pct": row.get("avg_return_pct"),
        "expectancy_ci95_pct": row.get("expectancy_ci95_pct"),
        "sharpe_proxy": row.get("sharpe_proxy"),
        "profit_factor": row.get("profit_factor"),
        "max_drawdown_pct": row.get("max_drawdown_pct"),
        "total_return_pct": row.get("total_return_pct"),
        "promotion_tier": champ.get("tier"),
        "oos_consistent": sv.get("oos_consistent"),
        "next_tier": nxt,
        "trades_to_next_tier": need,
        "promotion_eligibility": (f"{need} more trades to {nxt}" if nxt else "fully verified (100+)"),
        "governance_status": gov.get("governance_status"),
        "challenger_queue": [s["strategy"] for s in cv.get("strategies", [])
                             if s["strategy"] != name][:4],
        "honest_note": (f"{n} trades is a small sample. Stats are directional until "
                        "the champion clears 25–50+ trades across varied conditions."),
    }
    try: write_json_atomic(out / "CHAMPION_STATUS.json", payload)
    except Exception: pass
    return payload

if __name__ == "__main__":
    import sys
    p = build_champion_status(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(json.dumps(p, indent=2))
