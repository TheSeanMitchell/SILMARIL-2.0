"""
silmaril.execution.intrabar_audit — MISSED INTRABAR EVENT AUDIT (2.5.3). Measurement.

Cycles are ~10-12 min apart. If price spiked through the TARGET between two cycles and
fell back before the next run, the sim never saw it and the sell was missed. This audit
walks each closed trade's actual price path (entry->exit) and asks: did target get hit
intrabar while we exited lower? How much edge did that cost? Emits INTRABAR_AUDIT.json.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from ._trade_helpers import closed_trades, price_series, _dt
from .atomic_io import write_json_atomic

def _now(): return datetime.now().astimezone().isoformat()

def build_intrabar_audit(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    trades, series = closed_trades(out), price_series(out)
    rows = []
    for tr in trades:
        if not tr["target_pct"] or not tr["entry"]:
            continue
        ser = series.get(tr["sym"]); et, xt = _dt(tr["entry_t"]), _dt(tr["exit_t"])
        if not ser or not et or not xt:
            continue
        path = [(t, p) for t, p in ser if et <= t <= xt]
        if len(path) < 2:
            continue
        tgt = tr["entry"] * (1 + tr["target_pct"] / 100.0)
        stp = tr["entry"] * (1 - (tr["stop_pct"] or 99) / 100.0)
        hi = max(p for _, p in path); lo = min(p for _, p in path)
        target_hit = hi >= tgt
        exited_below = tr["exit"] < tgt * 0.999
        stop_hit = lo <= stp
        missed_target = target_hit and exited_below
        leak = round((tgt - tr["exit"]) / tr["entry"] * 100, 2) if missed_target else 0.0
        rows.append({**{k: tr[k] for k in ("sym", "strategy", "book", "realized_pct", "target_pct", "stop_pct")},
                     "target_hit_intrabar": target_hit, "stop_breached_intrabar": stop_hit,
                     "missed_target": missed_target, "captured_leak_pct": leak,
                     "intrabar_high_pct": round((hi / tr["entry"] - 1) * 100, 2),
                     "intrabar_low_pct": round((lo / tr["entry"] - 1) * 100, 2)})
    def agg(rs):
        if not rs: return {}
        miss = [r for r in rs if r["missed_target"]]
        return {"trades": len(rs), "target_hit_intrabar": sum(1 for r in rs if r["target_hit_intrabar"]),
                "missed_target_exits": len(miss),
                "missed_target_rate_pct": round(len(miss) / len(rs) * 100, 1),
                "avg_leak_when_missed_pct": round(sum(r["captured_leak_pct"] for r in miss) / len(miss), 2) if miss else 0.0,
                "total_edge_left_pct": round(sum(r["captured_leak_pct"] for r in miss), 2)}
    payload = {"generated_at": _now(), "overall": agg(rows),
               "by_book": {b: agg([r for r in rows if r["book"] == b]) for b in ("crypto", "stock")},
               "worst": sorted([r for r in rows if r["missed_target"]],
                               key=lambda r: r["captured_leak_pct"], reverse=True)[:12],
               "what": "Target hit between cycles but we exited lower = missed intrabar sell.",
               "why": "Quantifies edge lost to coarse 10-12min polling. High rate -> finer polling or limit orders matter.",
               "action": "If missed_target_rate is high, this is real recoverable edge, not strategy failure.",
               "note": "Measurement only. No exit logic changed."}
    try: write_json_atomic(out / "INTRABAR_AUDIT.json", payload)
    except Exception: pass
    return payload
