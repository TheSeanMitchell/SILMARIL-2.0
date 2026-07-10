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

    def _live_n(bk: str) -> int:
        """Closed live paper trades for THIS book — the number that gates champion rotation."""
        try:
            trs = json.loads((out / f"paper_book_{bk}.json").read_text()).get("trades", [])
            return sum(1 for t in trs if t.get("side") == "SELL" and t.get("realized_pct") is not None)
        except Exception:
            return 0

    # CRYPTO: mirror the forward-survivability champion (champion.json)
    cj = _load(out, "champion.json")
    cry_name = cj.get("champion")
    crypto = {"generated_at": _now(), "book": "crypto", "champion": cry_name,
              "live_params": _params(cry_name) if cry_name else None,
              "live_trades": _live_n("crypto"),
              "source": "forward survivability (champion.py)",
              "reason": cj.get("reason", "")}
    try: write_json_atomic(out / "champion_crypto.json", crypto)
    except Exception: pass

    # NON-CRYPTO BOOKS: forward survivability governs the moment THIS book has a
    # qualifying forward row (2026-07-10 — the "re-governed on forward
    # survivability once trades accumulate" promise, delivered). Until then the
    # book keeps its independent arena winner as the sticky backtest hypothesis.
    from .paper_sim import BOOKS as _BOOKS
    try:
        _cvrows = json.loads((out / "champion_validation.json").read_text()).get("strategies", [])
    except Exception:
        _cvrows = []
    try:
        _rk = (json.loads((out / "PARAM_CATALOG.json").read_text()).get("champion_rotation") or {})
    except Exception:
        _rk = {}
    _min_tr = int(_rk.get("min_trades", 5) or 5)
    _margin = float(_rk.get("switch_margin", 15) or 15)
    results = {"crypto": crypto}
    for bk in [b for b in _BOOKS if b != "crypto"]:
        lb = _load(out, f"strategy_leaderboard_{bk}.json")
        bt = lb.get("best_trusted") or {}
        prev = _load(out, f"champion_{bk}.json"); prev_name = prev.get("champion")
        cand, cand_net = bt.get("strategy"), bt.get("mean_net_pct")
        board = {r["strategy"]: r for r in lb.get("leaderboard", [])}
        inc_net = (board.get(prev_name) or {}).get("mean_net_pct")
        chosen, why, src = prev_name, f"{bk} champion holds", f"independent {bk} arena (backtest hypothesis, not forward-proven)"
        _fw = sorted((r for r in _cvrows if r.get("book") == bk and r.get("strategy") in STRATEGIES),
                     key=lambda r: (r.get("survivability") or {}).get("score", 0), reverse=True)
        _fl = _fw[0] if _fw else None
        if _fl and _fl.get("n", 0) >= _min_tr:
            src = f"forward survivability ({bk} book, n={_fl['n']})"
            _fl_s = (_fl.get("survivability") or {}).get("score", 0)
            _inc_row = next((r for r in _fw if r.get("strategy") == prev_name), None)
            _inc_s = (_inc_row.get("survivability") or {}).get("score", 0) if _inc_row else 0
            if prev_name is None or _fl["strategy"] == prev_name:
                chosen, why = _fl["strategy"], f"{bk} forward-survivability leader holds ({_fl_s:.0f}, n={_fl['n']})"
            elif _fl_s >= _inc_s + _margin:
                chosen, why = _fl["strategy"], (f"{bk} promoted on forward survivability: {_fl['strategy']} "
                                                f"{_fl_s:.0f} > {prev_name} {_inc_s:.0f} (n={_fl['n']})")
            else:
                chosen, why = prev_name, (f"{bk} holds: {_fl['strategy']} ({_fl_s:.0f}) vs {prev_name} "
                                          f"({_inc_s:.0f}) under {_margin:.0f}-pt margin")
        elif prev_name is None and cand:
            chosen, why = cand, f"initial {bk} champion: {cand} ({cand_net:+.2f}%/trade backtest)" if cand_net is not None else f"initial {bk} champion: {cand}"
        elif cand and cand != prev_name and cand_net is not None and (inc_net is None or cand_net >= inc_net + STOCK_SWITCH_MARGIN):
            chosen, why = cand, f"{bk} arena switch: {cand} {cand_net:+.2f}%/trade"
        payload = {"generated_at": _now(), "book": bk, "champion": chosen,
                   "live_params": _params(chosen) if chosen else None,
                   "live_trades": _live_n(bk),
                   "source": src,
                   "reason": why,
                   "honest_note": ("Forward-survivability governed once this book has qualifying live trades; "
                                   "backtest hypothesis until then. "
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
