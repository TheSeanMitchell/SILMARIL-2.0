"""
silmaril.execution.zero_pnl_audit — ZERO-PNL TRADE AUDIT (2.5.3). Explainability.

Why so many ~$0 stock trades? Categorises near-zero-PnL exits by cause (timeout with no
move, tiny move, flat). Emits ZERO_PNL_AUDIT.json.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from ._trade_helpers import closed_trades, _dt
from .atomic_io import write_json_atomic

def _now(): return datetime.now().astimezone().isoformat()
NEAR_ZERO = 0.15   # |realized%| below this = "zero PnL"

def build_zero_pnl_audit(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    trades = closed_trades(out)
    by_book = {}
    for bk in ("crypto", "stock"):
        bt = [t for t in trades if t["book"] == bk]
        zero = [t for t in bt if abs(t["realized_pct"]) < NEAR_ZERO]
        cats = {"flat_timeout": 0, "tiny_move": 0}
        durs = []
        for t in zero:
            et, xt = _dt(t["entry_t"]), _dt(t["exit_t"])
            mins = (xt - et).total_seconds() / 60 if (et and xt) else None
            if mins is not None: durs.append(mins)
            if mins is not None and mins >= 220:   # ~max hold -> timed out flat
                cats["flat_timeout"] += 1
            else:
                cats["tiny_move"] += 1
        by_book[bk] = {
            "total_trades": len(bt), "zero_pnl_trades": len(zero),
            "zero_pnl_rate_pct": round(len(zero) / len(bt) * 100, 1) if bt else 0.0,
            "causes": cats,
            "avg_hold_min_of_zero": round(sum(durs) / len(durs), 0) if durs else None,
        }
    payload = {"generated_at": _now(), "by_book": by_book, "near_zero_threshold_pct": NEAR_ZERO,
               "what": "Trades that closed at roughly breakeven, and why.",
               "why": "Many $0 stock trades usually = entries that never moved (timeout), i.e. weak dip qualification.",
               "action": "High flat_timeout in stock supports the thesis: stock dips often don't revert.",
               "note": "Cause is inferred from hold duration (no per-trade exit-reason stored yet)."}
    try: write_json_atomic(out / "ZERO_PNL_AUDIT.json", payload)
    except Exception: pass
    return payload
