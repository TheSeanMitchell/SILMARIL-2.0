"""
silmaril.execution.stock_recovery — STOCK RECOVERY ANALYSIS (2.5.1 P4). Measurement.

The question you raised: how long do stocks actually take to mean-revert after a 3 /
5 / 7 / 10% drawdown — hours, days, or weeks? If stocks recover far slower than
crypto, our stock exit timing is misaligned with the market. Measures real recovery
time from the price tape for stocks AND crypto, side by side. Emits
STOCK_RECOVERY_ANALYSIS.json.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Dict, List
from .paper_sim import _is_crypto
from .atomic_io import write_json_atomic

DEPTHS = [3, 5, 7, 10]
def _now(): return datetime.now().astimezone().isoformat()
def _dt(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None

def _recovery_hours(ser: List, depth_pct: float):
    """Find drops of >=depth% from a running peak; hours until price returns to that peak."""
    times, censored = [], 0
    n = len(ser)
    if n < 5: return times, censored
    peak = ser[0][1]; in_dd = False; dd_peak = peak; dd_i = 0
    for i in range(1, n):
        t, p = ser[i]
        if not in_dd:
            if p > peak: peak = p
            if p <= peak * (1 - depth_pct / 100.0):
                in_dd = True; dd_peak = peak; dd_i = i
        else:
            if p >= dd_peak:
                hrs = (ser[i][0] - ser[dd_i][0]).total_seconds() / 3600.0
                times.append(hrs); in_dd = False; peak = p
    if in_dd: censored += 1
    return times, censored

def build_stock_recovery(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    try: d = json.loads((out / "price_samples.json").read_text()).get("samples", {})
    except Exception as e: return {"error": str(e)}
    series = {sym: [(_dt(t), p) for t, p in rows if p and p > 0 and _dt(t)] for sym, rows in d.items()}
    books = {}
    for label, is_cry in (("stock", False), ("crypto", True)):
        names = [s for s in series if _is_crypto(s) == is_cry and len(series[s]) >= 20]
        per_depth = {}
        for depth in DEPTHS:
            all_t, cens, names_hit = [], 0, 0
            for sym in names:
                ts, c = _recovery_hours(series[sym], depth)
                if ts or c: names_hit += 1
                all_t += ts; cens += c
            recovered = len(all_t)
            per_depth[f"{depth}pct"] = {
                "events_recovered": recovered, "events_still_underwater": cens,
                "recovery_rate_pct": round(recovered / (recovered + cens) * 100, 1) if (recovered + cens) else None,
                "median_hours_to_recover": round(median(all_t), 1) if all_t else None,
                "median_days_to_recover": round(median(all_t) / 24, 2) if all_t else None,
            }
        books[label] = {"names_analyzed": len(names), "by_drawdown_depth": per_depth}
    s = books.get("stock", {}).get("by_drawdown_depth", {})
    c = books.get("crypto", {}).get("by_drawdown_depth", {})
    def med(b, k): return (b.get(k) or {}).get("median_hours_to_recover")
    payload = {"generated_at": _now(),
               "window_days": round((max((max(t for t, _ in v) for v in series.values() if v)) -
                                     min((min(t for t, _ in v) for v in series.values() if v))).total_seconds() / 86400, 1) if series else 0,
               "books": books,
               "headline": (f"After a 5% drop: stocks median recovery "
                            f"{med(s,'5pct')}h vs crypto {med(c,'5pct')}h"
                            if med(s, "5pct") or med(c, "5pct") else
                            "not enough recovered drawdowns in the window yet"),
               "censoring_note": ("Price history is only ~5 days, so slow recoveries (especially deep "
                                  "stock drawdowns) are 'still underwater' = censored. Recovery RATE matters "
                                  "as much as median time: a low stock recovery rate means stocks are NOT "
                                  "reverting on our exit clock, which would mean stock exits need longer holds."),
               "note": "Measurement only. No exit rules changed — this is the evidence to decide them."}
    try: write_json_atomic(out / "STOCK_RECOVERY_ANALYSIS.json", payload)
    except Exception: pass
    return payload

if __name__ == "__main__":
    import sys
    p = build_stock_recovery(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("HEADLINE:", p.get("headline"))
