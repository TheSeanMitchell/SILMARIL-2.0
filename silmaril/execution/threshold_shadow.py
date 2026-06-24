"""
silmaril.execution.threshold_shadow — DROP-THRESHOLD SHADOW SIM (2.5.3). Measurement.

Answers '2.9% vs 3.0% vs 3.1%?' with data instead of opinion. For each candidate drop
threshold, scans the crypto universe for oversold events and measures the forward
mean-reversion outcome. Emits THRESHOLD_SHADOW.json. Does NOT change the live threshold.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict
from ._trade_helpers import price_series
from .paper_sim import asset_class
from .atomic_io import write_json_atomic

def _now(): return datetime.now().astimezone().isoformat()
THRESHOLDS = [2.7, 2.8, 2.9, 3.0, 3.1, 3.2]
LOOKBACK = 6     # samples to measure the drop over (~1h)
FORWARD = 12     # samples to measure recovery (~2h)

def build_threshold_shadow(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    series = price_series(out)
    names = [s for s in series if asset_class(s) == "crypto" and len(series[s]) > LOOKBACK + FORWARD]
    results = {}
    for thr in THRESHOLDS:
        events, rets = 0, []
        for s in names:
            px = [p for _, p in series[s]]
            for i in range(LOOKBACK, len(px) - FORWARD):
                drop = (px[i] / px[i - LOOKBACK] - 1) * 100
                if drop <= -thr:
                    fwd = (max(px[i:i + FORWARD]) / px[i] - 1) * 100  # best recovery in window
                    rets.append(fwd); events += 1
        results[f"{thr}pct"] = {
            "setups": events,
            "avg_forward_best_pct": round(mean(rets), 2) if rets else None,
            "pct_recovered_1pct": round(sum(1 for r in rets if r >= 1) / len(rets) * 100, 1) if rets else None,
        }
    # pick the threshold with the best expectancy*frequency balance
    scored = [(t, d["setups"], d["avg_forward_best_pct"]) for t, d in results.items() if d["avg_forward_best_pct"]]
    best = max(scored, key=lambda x: (x[2] or 0)) if scored else None
    payload = {"generated_at": _now(), "by_threshold": results,
               "current_live_threshold_pct": 3.0,
               "best_by_recovery": best[0] if best else None,
               "what": "Each candidate drop trigger, its setup count and forward recovery, on the crypto tape.",
               "why": "Settles 2.9 vs 3.0 vs 3.1 with evidence, not a guess.",
               "action": "Tighter threshold = more setups but possibly weaker each; this shows the tradeoff.",
               "note": "Shadow only. Live threshold unchanged at 3.0%."}
    try: write_json_atomic(out / "THRESHOLD_SHADOW.json", payload)
    except Exception: pass
    return payload
