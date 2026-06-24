"""
silmaril.execution.chart_overlays — CHART OVERLAY DATA (2.5.4).

Consolidates everything the chart should draw on top of price, keyed by symbol, into ONE
file the front-end can load: closed-trade entry/exit markers + the GOLD cash-out target line,
the live open position, Dr Strange's Monte-Carlo direction/expected-move, and the conviction
signal (how many agents back it). Emits CHART_OVERLAYS.json.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from ._trade_helpers import closed_trades
from .atomic_io import write_json_atomic

def _now(): return datetime.now(timezone.utc).isoformat()
def _load(out, n, d=None):
    try: return json.loads((out / n).read_text())
    except Exception: return d if d is not None else {}

def build_chart_overlays(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    ov: Dict[str, Any] = {}

    # 1) closed trades per symbol (entry/exit markers + gold target line)
    for tr in closed_trades(out):
        s = ov.setdefault(tr["sym"], {})
        tgt = tr["entry"] * (1 + tr["target_pct"] / 100) if (tr["entry"] and tr["target_pct"]) else None
        s.setdefault("trades", []).append({
            "entry": tr["entry"], "entry_t": tr["entry_t"],
            "exit": tr["exit"], "exit_t": tr["exit_t"],
            "pnl_pct": tr["realized_pct"], "target": tgt,
            "book": tr["book"], "strategy": tr["strategy"],
        })

    # 2) live open positions (entry/target/stop/mark)
    live = _load(out, "paper_sim_live.json")
    def ts(nm):
        import re
        t = re.search(r"_t(\d+)", nm or ""); ss = re.search(r"_s(\d+)", nm or "")
        return (int(t.group(1)) if t else None, int(ss.group(1)) if ss else None)
    for bk in ("crypto", "stock", "metal", "energy"):
        champ = (live.get("champion_" + bk) or "")
        tp, sp = ts(champ)
        for o in (live.get(bk, {}) or {}).get("open_positions", []) or []:
            if not o or not o.get("sym"): continue
            s = ov.setdefault(o["sym"], {})
            s["open"] = {"entry": o.get("entry"), "mark": o.get("mark"), "upl_pct": o.get("upl_pct"),
                         "book": bk, "tpct": tp, "spct": sp,
                         "target": (o["entry"] * (1 + tp / 100)) if (tp and o.get("entry")) else None,
                         "stop": (o["entry"] * (1 - sp / 100)) if (sp and o.get("entry")) else None}

    # 3) Dr Strange — Monte-Carlo direction + expected move
    ds = _load(out, "dr_strange.json")
    for q in (ds.get("qualified") or []) + (ds.get("picks") or []):
        t = q.get("ticker")
        if not t: continue
        ov.setdefault(t, {})["dr_strange"] = {
            "direction": q.get("direction"), "expected_move_pct": round((q.get("median") or 0) * 100, 2),
            "agreement": q.get("agreement"), "horizon_days": (ds.get("params") or {}).get("horizon_days", 3)}

    # 4) Conviction — signal + how many agents back it
    cv = _load(out, "conviction_ranking.json")
    for r in (cv.get("ranked_opportunities") or []):
        t = r.get("ticker")
        if not t: continue
        ov.setdefault(t, {})["conviction"] = {
            "signal": r.get("signal"), "score": r.get("score"),
            "backers": r.get("backers"), "trend": r.get("three_month_signal")}

    payload = {"generated_at": _now(), "symbols": ov, "count": len(ov),
               "legend": {"gold_line": "target / cash-out hope", "entry_marker": "where bought",
                          "exit_marker": "where sold", "dr_strange": "Monte-Carlo 3d direction+move",
                          "conviction": "agent-backed BUY/SELL signal"},
               "note": "Everything the chart overlays, keyed by symbol. Refreshed each cycle."}
    try: write_json_atomic(out / "CHART_OVERLAYS.json", payload)
    except Exception: pass
    return payload
