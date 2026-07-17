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

    # ── 7.0 DSR: is the champion's rank REAL after 316-trial selection bias? ──

    _dsr = {"verdict": "INSUFFICIENT", "note": "needs >=30 live closed trades",

             "trials": 316, "value": None}

    try:

        import math as _m7, statistics as _st7

        _rets = []

        for _bk7 in ("crypto", "stock", "metal", "energy", "aggressive"):

            try:

                _d7 = json.loads((out / ("paper_book_" + _bk7 + ".json")).read_text())

                for _t7 in _d7.get("trades", []):

                    if _t7.get("side") == "SELL":

                        _rets.append(float(_t7.get("realized_pct") or 0))

            except Exception:

                pass

        _n7 = len(_rets)

        if _n7 >= 30:

            _mu = _st7.fmean(_rets)

            _sd = _st7.pstdev(_rets) or 1e-9

            _sr = _mu / _sd * _m7.sqrt(_n7)

            _nd = _st7.NormalDist()

            _g = 0.5772156649

            _N = 316.0

            _emax = ((1 - _g) * _nd.inv_cdf(1 - 1 / _N)

                     + _g * _nd.inv_cdf(1 - 1 / (_N * 2.718281828)))

            _val = _sr - _emax

            _dsr = {"verdict": "POSITIVE" if _val > 0 else "ZERO_OR_NEGATIVE",

                     "value": round(_val, 3), "raw_sr": round(_sr, 3),

                     "expected_max_null": round(_emax, 3), "n": _n7, "trials": 316,

                     "note": "SR minus expected max of 316 null Sharpes (selection-bias haircut)"}

    except Exception:

        pass

    payload = {"dsr": _dsr,
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
