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
    # ── 7.0.1 REGIME-CONDITIONAL CHAMPION (operator: "switch to a momentum one" — the whole point
    # of the Pokemon system). Root cause of idle metal/energy: the leaderboard pool is ~282 MR vs
    # ~12 MOM, so the survivability rank almost always crowns a mean-reversion strategy — which then
    # sits waiting for a DIP that never comes in an UPTREND book. Fix: read each book's live regime
    # and, when trending, prefer the best strategy whose DIRECTION matches the trend (dir='mom' in an
    # up/downtrend) over the overall MR winner. SIDEWAYS keeps mean-reversion (its home regime). This
    # is family-preference at selection time, not a new strategy — MOM already competes in the arena.
    # Knob: PARAM_CATALOG.regime_champion {mode:"auto"|"off"}. KILL: "off" restores pure rank.
    try:
        _rc = (json.loads((out / "PARAM_CATALOG.json").read_text()).get("regime_champion") or {})
    except Exception:
        _rc = {}
    _rc_mode = str(_rc.get("mode", "auto")).lower()
    try:
        _live_regimes = json.loads((out / "paper_sim_live.json").read_text()).get("regimes", {}) or {}
    except Exception:
        _live_regimes = {}

    def _regime_pref_dir(bk: str):
        """Which strategy DIRECTION fits this book's live regime right now.
        UPTREND/DOWNTREND → 'mom' (trend-following); SIDEWAYS/unknown → 'mr' (mean-reversion).
        Returns None when the feature is off (→ pure survivability rank, the old behavior)."""
        if _rc_mode == "off":
            return None
        reg = str(_live_regimes.get(bk, "")).upper()
        if "UP" in reg or "DOWN" in reg:
            return "mom"
        return "mr"

    def _best_by_dir(board_rows, want_dir, min_n):
        """Best trusted strategy whose dir matches want_dir, by mean net edge, with a real sample."""
        cands = [r for r in board_rows
                 if r.get("dir") == want_dir and (r.get("trades") or 0) >= min_n
                 and r.get("mean_net_pct") is not None]
        if not cands:
            return None
        return max(cands, key=lambda r: r["mean_net_pct"])
    results = {"crypto": crypto}
    for bk in [b for b in _BOOKS if b != "crypto"]:
        lb = _load(out, f"strategy_leaderboard_{bk}.json")
        bt = lb.get("best_trusted") or {}
        prev = _load(out, f"champion_{bk}.json"); prev_name = prev.get("champion")
        cand, cand_net = bt.get("strategy"), bt.get("mean_net_pct")
        board = {r["strategy"]: r for r in lb.get("leaderboard", [])}
        # 7.0.1: regime override — if the book is trending and the default winner fights the trend
        # (an MR champion in an uptrend), swap to the best trend-matching strategy from the SAME arena.
        _pref = _regime_pref_dir(bk)
        _regime_note = ""
        if _pref is not None and cand:
            _cur_dir = (board.get(cand) or {}).get("dir")
            if _cur_dir != _pref:
                _swap = _best_by_dir(lb.get("leaderboard", []), _pref, max(3, _min_tr - 2))
                if _swap:
                    cand, cand_net = _swap["strategy"], _swap.get("mean_net_pct")
                    _regime_note = (f" · regime-fit: {bk} is {_live_regimes.get(bk, '?')} → prefer "
                                    f"{_pref} strategy {cand} over the {_cur_dir} rank-leader "
                                    f"(the Pokemon switch: right type for the regime)")
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
        # 7.0.1: FINAL regime-fit override on the backtest-hypothesis path. Once a book has qualifying
        # FORWARD evidence (the _fl>=_min_tr branch above) that governs and we don't override it — real
        # forward survival beats a regime heuristic. But while a book is still on its backtest hypothesis
        # (no live trades yet — exactly metal/energy today), a trending regime must not be handed an MR
        # champion that will sit idle waiting for a dip. Swap to the trend-matching arena winner.
        if _pref is not None and not (_fl and _fl.get("n", 0) >= _min_tr):
            _chosen_dir = (board.get(chosen) or {}).get("dir")
            if _chosen_dir is not None and _chosen_dir != _pref:
                _swap2 = _best_by_dir(lb.get("leaderboard", []), _pref, max(3, _min_tr - 2))
                if _swap2 and _swap2["strategy"] != chosen:
                    chosen = _swap2["strategy"]
                    why = (f"{bk} REGIME-FIT: {_live_regimes.get(bk, '?')} regime → {_pref} strategy "
                           f"{chosen} ({(_swap2.get('mean_net_pct') or 0):+.2f}%/trade) instead of the "
                           f"{_chosen_dir} rank-leader — the Pokemon switch, right type for the regime")
                    src = f"regime-conditional ({bk} {_live_regimes.get(bk, '?')}, backtest hypothesis)"
        payload = {"generated_at": _now(), "book": bk, "champion": chosen,
                   "live_params": _params(chosen) if chosen else None,
                   "live_trades": _live_n(bk),
                   "source": src,
                   "reason": why,
                   "regime": _live_regimes.get(bk),
                   "honest_note": ("Forward-survivability governed once this book has qualifying live trades; "
                                   "regime-conditional backtest hypothesis until then. "
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
