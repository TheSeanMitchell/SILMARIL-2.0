"""
silmaril.execution.champion_split — 2.5.1 MARKET SEPARATION: per-book champions.

Crypto and stock no longer share a champion. Crypto keeps its forward-survivability
champion (from champion.py / champion.json — we have live crypto data). Stock takes
the winner of the independent STOCK arena (strategy_leaderboard_stock.json) as its
starting hypothesis, since the stock book has no trustworthy forward sample yet — to
be re-governed on forward survivability once stock trades accumulate. Sticky: the
stock champion only switches on a decisive backtest margin, so it won't flip-flop on
noise. Emits champion_crypto.json and champion_stock.json.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from .strategy_lab import STRATEGIES
STEP_MIN = 11.0  # steps -> minutes (matches champion.py)
from .atomic_io import write_json_atomic

STOCK_SWITCH_MARGIN = 0.5   # new stock arena winner must beat incumbent by this %/trade to switch

def _now(): return datetime.now().astimezone().isoformat()
def _load(out, n):
    try: return json.loads((out / n).read_text())
    except Exception: return {}

def _params(name: str) -> Optional[Dict[str, Any]]:
    cfg = STRATEGIES.get(name)
    if not cfg:
        return None
    return {"dir": cfg["dir"], "entry": cfg["entry"], "target": cfg["target"],
            "stop": cfg["stop"], "max_hold_min": round(cfg.get("hold", 22) * STEP_MIN, 1)}

def build_champion_split(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    # CRYPTO: mirror the forward-survivability champion (champion.json)
    cj = _load(out, "champion.json")
    cry_name = cj.get("champion")
    crypto = {"generated_at": _now(), "book": "crypto", "champion": cry_name,
              "live_params": _params(cry_name) if cry_name else None,
              "source": "forward survivability (champion.py)",
              "reason": cj.get("reason", "")}
    try: write_json_atomic(out / "champion_crypto.json", crypto)
    except Exception: pass

    # NON-CRYPTO BOOKS: each takes its own independent arena winner, sticky.
    from .paper_sim import BOOKS as _BOOKS
    results = {"crypto": crypto}
    for bk in [b for b in _BOOKS if b != "crypto"]:
        lb = _load(out, f"strategy_leaderboard_{bk}.json")
        bt = lb.get("best_trusted") or {}
        prev = _load(out, f"champion_{bk}.json"); prev_name = prev.get("champion")
        cand, cand_net = bt.get("strategy"), bt.get("mean_net_pct")
        board = {r["strategy"]: r for r in lb.get("leaderboard", [])}
        inc_net = (board.get(prev_name) or {}).get("mean_net_pct")
        chosen, why = prev_name, f"{bk} champion holds"
        if prev_name is None and cand:
            chosen, why = cand, f"initial {bk} champion: {cand} ({cand_net:+.2f}%/trade backtest)" if cand_net is not None else f"initial {bk} champion: {cand}"
        elif cand and cand != prev_name and cand_net is not None and (inc_net is None or cand_net >= inc_net + STOCK_SWITCH_MARGIN):
            chosen, why = cand, f"{bk} arena switch: {cand} {cand_net:+.2f}%/trade"
        payload = {"generated_at": _now(), "book": bk, "champion": chosen,
                   "live_params": _params(chosen) if chosen else None,
                   "source": f"independent {bk} arena (backtest hypothesis, not forward-proven)",
                   "reason": why,
                   "honest_note": ("Backtest-selected hypothesis; the live book validates it. "
                                   "Empty until this book has a data feed.")}
        try: write_json_atomic(out / f"champion_{bk}.json", payload)
        except Exception: pass
        results[bk] = payload
    return results

if __name__ == "__main__":
    import sys
    p = build_champion_split(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("CRYPTO champion:", p["crypto"]["champion"], "| params:", p["crypto"]["live_params"])
    print("STOCK  champion:", p["stock"]["champion"], "| params:", p["stock"]["live_params"])
    print("  ", p["stock"]["reason"])
