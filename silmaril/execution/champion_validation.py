"""
silmaril.execution.champion_validation — CHAMPION VALIDATION + PROMOTION LADDER
(Alpha 2.16: Validation over Expansion. North Star = the Arena.)

No new signals. This validates the strategies that already exist. For every
strategy book it computes the real performance stats the directive asks for —
return, expectancy, win rate, volatility, Sharpe proxy, drawdown, profit factor,
with confidence intervals — then runs an OUT-OF-SAMPLE split (first half of the
closed trades vs second half) to answer the only question that matters now:

    does the edge survive when the data it didn't 'learn' arrives?

Each strategy gets a survivability score and an automatic promotion tier
(Sandbox -> Incubation -> Candidate -> Production), hedge-fund-incubation style.
Capital is earned by survival, not granted.
"""
from __future__ import annotations
import json, math
from .atomic_io import write_json_atomic
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional

TIER_CAPITAL = {"Sandbox": 0, "Incubation": 10000, "Candidate": 25000, "Production": 50000}

def _now(): return datetime.now().astimezone().isoformat()

def _closed_returns(trades: List[dict]) -> List[Dict[str, Any]]:
    """Pair BUY->SELL (FIFO) -> list of {ret, pnl, t} per closed trade."""
    opens, out = {}, []
    for tr in trades:
        sym = tr.get("sym", "")
        if tr.get("side") == "BUY":
            opens.setdefault(sym, []).append(tr)
        elif tr.get("side") == "SELL" and opens.get(sym):
            b = opens[sym].pop(0)
            try:
                cost = float(b["price"]) * float(b["qty"])
                ret = (tr["pnl"] / cost) if (tr.get("pnl") is not None and cost) else None
            except Exception:
                ret = None
            if ret is not None:
                out.append({"ret": ret, "pnl": tr.get("pnl", 0.0), "t": tr.get("t", "")})
    return out

def _stats(rets: List[float]) -> Dict[str, Any]:
    if not rets:
        return {"n": 0}
    m = mean(rets); sd = pstdev(rets) or 1e-9
    wins = [r for r in rets if r > 0]; losses = [r for r in rets if r <= 0]
    # equity curve / drawdown
    eq, peak, mdd = 1.0, 1.0, 0.0
    for r in rets:
        eq *= (1 + r); peak = max(peak, eq); mdd = min(mdd, eq / peak - 1)
    gross_w = sum(wins); gross_l = abs(sum(losses))
    t = m / (sd / math.sqrt(len(rets)))
    ci = 1.96 * sd / math.sqrt(len(rets))
    return {"n": len(rets),
            "total_return_pct": round((eq - 1) * 100, 2),
            "avg_return_pct": round(m * 100, 3),
            "expectancy_ci95_pct": [round((m - ci) * 100, 3), round((m + ci) * 100, 3)],
            "win_pct": round(len(wins) / len(rets) * 100, 1),
            "avg_win_pct": round(mean(wins) * 100, 2) if wins else 0.0,
            "avg_loss_pct": round(mean(losses) * 100, 2) if losses else 0.0,
            "volatility_pct": round(sd * 100, 2),
            "sharpe_proxy": round(m / sd, 2),
            "max_drawdown_pct": round(mdd * 100, 2),
            "profit_factor": round(gross_w / gross_l, 2) if gross_l else (float("inf") if gross_w else 0),
            "t_stat": round(t, 2)}

def _survivability(full: Dict, h1: Dict, h2: Dict) -> Dict[str, Any]:
    """0-100 survivability: positive + significant + holds out-of-sample + enough data."""
    if full.get("n", 0) < 4:
        return {"score": 0, "oos_consistent": False, "reason": "insufficient closed trades"}
    score = 0.0
    if full["avg_return_pct"] > 0: score += 25
    score += min(25, max(0, full["t_stat"]) * 10)                 # significance
    oos = (h1.get("n", 0) >= 2 and h2.get("n", 0) >= 2
           and h1["avg_return_pct"] > 0 and h2["avg_return_pct"] > 0)
    if oos: score += 35                                           # survives the split
    elif h2.get("avg_return_pct", -1) > 0: score += 15            # at least recent half positive
    score += min(15, full["n"] / 2)                              # sample size
    return {"score": round(min(score, 100), 0), "oos_consistent": oos,
            "first_half_avg_pct": h1.get("avg_return_pct"), "second_half_avg_pct": h2.get("avg_return_pct"),
            "reason": ("survives out-of-sample split" if oos else
                       "recent half positive but not both" if h2.get("avg_return_pct", -1) > 0 else
                       "fails out-of-sample")}

def _tier(surv: Dict, n: int) -> str:
    s = surv.get("score", 0)
    if s >= 70 and n >= 30 and surv.get("oos_consistent"): return "Production"
    if s >= 55 and n >= 15: return "Candidate"
    if s >= 40 and n >= 8: return "Incubation"
    return "Sandbox"

def build_champion_validation(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    rows = []
    for bp in out.glob("paper_book_*.json"):
        strat = bp.stem.replace("paper_book_", "")
        try: trades = json.loads(bp.read_text()).get("trades", [])
        except Exception: continue
        closed = _closed_returns(trades)
        rets = [c["ret"] for c in closed]
        if not rets: continue
        full = _stats(rets)
        half = len(rets) // 2
        h1, h2 = _stats(rets[:half]), _stats(rets[half:])
        surv = _survivability(full, h1, h2)
        tier = _tier(surv, full["n"])
        rows.append({"strategy": strat, **full, "survivability": surv,
                     "tier": tier, "tier_capital_usd": TIER_CAPITAL[tier]})
    rows.sort(key=lambda r: (r["survivability"]["score"], r["sharpe_proxy"]), reverse=True)
    champ = rows[0]["strategy"] if rows else None
    try: declared = json.loads((out / "champion.json").read_text())
    except Exception: declared = {}
    declared_champ = declared.get("champion") if isinstance(declared, dict) else None
    payload = {"generated_at": _now(),
               "most_survivable": champ,
               "declared_champion": declared_champ,
               "champion_is_most_survivable": (champ == declared_champ) if declared_champ else None,
               "promotion_ladder": {t: [r["strategy"] for r in rows if r["tier"] == t]
                                    for t in ["Production", "Candidate", "Incubation", "Sandbox"]},
               "strategies": rows,
               "verdict": (f"Most survivable: {champ}. " +
                           ("Matches declared champion. " if champ == declared_champ else
                            f"Declared champion is {declared_champ}. ") +
                           ("None has reached Candidate tier yet — survival unproven, keep accumulating."
                            if all(r["tier"] in ("Sandbox", "Incubation") for r in rows) else
                            "At least one strategy is earning its way up the ladder.")),
               "note": ("Out-of-sample = first-half vs second-half of THIS book's closed trades. "
                        "A real July test needs July data; this is the strongest split available now. "
                        "Capital is earned by tier, not granted. No new signals added.")}
    try: write_json_atomic(out / "champion_validation.json", payload)
    except Exception: pass
    return payload

if __name__ == "__main__":
    import sys
    p = build_champion_validation(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("VERDICT:", p["verdict"], "\n")
    print(f"{'strategy':20s}{'n':>4}{'tot%':>8}{'exp%':>8}{'win%':>7}{'sharpe':>8}{'mdd%':>8}{'surv':>6}  tier")
    for r in p["strategies"]:
        s = r["survivability"]
        print(f"{r['strategy']:20s}{r['n']:>4}{r['total_return_pct']:>+8.2f}{r['avg_return_pct']:>+8.3f}{r['win_pct']:>7.1f}{r['sharpe_proxy']:>8.2f}{r['max_drawdown_pct']:>+8.2f}{s['score']:>6.0f}  {r['tier']}")
    print("\nPROMOTION LADDER:", {k: v for k, v in p["promotion_ladder"].items() if v})
