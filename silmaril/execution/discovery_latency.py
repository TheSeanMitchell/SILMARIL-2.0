"""
silmaril.execution.discovery_latency — DISCOVERY LATENCY ENGINE (2.15 Priority 1).

Are we late? For every closed trade, measure timing against the price path:
bottom_time -> entry (how late after the trough we bought), entry -> peak ->
exit (did we sell before or after the peak, and by how much). Authority headline
detection time is stamped in the ledger. Stores timing so speed is measurable.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List
from .paper_sim import load_all_samples

def _now(): return datetime.now(timezone.utc).isoformat()
def _ser(s, sym): return [(datetime.fromisoformat(t), p) for t, p in s.get(sym, []) if p and p > 0]

def build_discovery_latency(out_dir) -> Dict[str, Any]:
    out = Path(out_dir); samples = load_all_samples(out)
    rows = []
    for bp in out.glob("paper_book_*.json"):
        try: d = json.loads(bp.read_text())
        except Exception: continue
        opens = {}
        for tr in d.get("trades", []):
            sym = tr.get("sym", "")
            if tr.get("side") == "BUY": opens.setdefault(sym, []).append(tr)
            elif tr.get("side") == "SELL" and opens.get(sym):
                b = opens[sym].pop(0)
                try:
                    et, xt = datetime.fromisoformat(b["t"]), datetime.fromisoformat(tr["t"])
                    ent = float(b["price"])
                except Exception: continue
                ser = _ser(samples, sym)
                if not ser: continue
                # bottom in the 6h before entry
                from datetime import timedelta
                pre = [(t, p) for t, p in ser if et - timedelta(hours=6) <= t <= et]
                bottom_t, bottom_p = min(pre, key=lambda x: x[1]) if pre else (et, ent)
                # peak between entry and exit
                seg = [(t, p) for t, p in ser if et <= t <= xt]
                peak_t, peak_p = max(seg, key=lambda x: x[1]) if seg else (xt, ent)
                rows.append({"ticker": sym,
                             "entry_lag_after_bottom_min": round((et - bottom_t).total_seconds() / 60, 0),
                             "peak_to_exit_min": round((xt - peak_t).total_seconds() / 60, 0),
                             "ran_after_entry_pct": round((peak_p / ent - 1) * 100, 2)})
    avg_lag = round(mean([r["entry_lag_after_bottom_min"] for r in rows]), 0) if rows else None
    payload = {"generated_at": _now(), "trades_timed": len(rows),
               "avg_entry_lag_after_bottom_min": avg_lag,
               "detail": rows[:25],
               "headline": (f"{len(rows)} trades timed · avg entry {avg_lag}min after the bottom"
                            if rows else "no closed trades yet — timing populates as the sim exits"),
               "note": "Entry lag after bottom = how late we bought. Full headline->detect->candidate latency needs pipeline timestamps (authority ledger already stamps headline time)."}
    try: (out / "discovery_latency.json").write_text(json.dumps(payload, indent=2))
    except Exception: pass
    return payload

if __name__ == "__main__":
    import sys; print(json.dumps(build_discovery_latency(sys.argv[1] if len(sys.argv) > 1 else "docs/data"))[:240])
