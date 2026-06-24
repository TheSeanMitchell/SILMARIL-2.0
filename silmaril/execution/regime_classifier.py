"""
silmaril.execution.regime_classifier — REGIME (TREND) CLASSIFICATION PER BOOK (2.5.4).

Classifies the CURRENT regime — UPTREND / SIDEWAYS / DOWNTREND (with strength) — for each
valuable class (crypto, stock, metal, energy) from real price data, every daily run. This is
the parameter the held-stocks problem exposed: buying a high bounce target into a downtrend is
greedy. Exposed as a champion-style parameter per book so it shows in the registry and can later
gate the bounce-target aggression (downtrend → safe target; uptrend → aggressive).

Per-book regime is the median short-horizon trend across that book's fresh symbols. The
classification METHOD becoming a rotating champion (best window) is data-gated until accuracy
history exists — noted honestly. Emits REGIME_CLASSIFIER.json.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List
from .atomic_io import write_json_atomic
from .paper_sim import asset_class

def _now(): return datetime.now(timezone.utc).isoformat()

def _trend_pct(prices: List[float]) -> float:
    if len(prices) < 6: return 0.0
    third = max(2, len(prices) // 3)
    ea = sum(prices[:third]) / third
    la = sum(prices[-third:]) / third
    return (la / ea - 1) * 100 if ea else 0.0

def _label(slope: float):
    if slope > 1.5: return ("UPTREND", "up")
    if slope < -1.5: return ("DOWNTREND", "down")
    return ("SIDEWAYS", "flat")

def build_regime_classifier(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    try: samples = json.loads((out / "price_samples.json").read_text()).get("samples", {})
    except Exception: samples = {}
    WINDOW = 36   # ~last 6h of 10-12min samples
    by_book: Dict[str, Any] = {}
    for book in ("crypto", "stock", "metal", "energy"):
        slopes = []
        for sym, rows in samples.items():
            if asset_class(sym) != book: continue
            px = [p for _, p in rows[-WINDOW:] if p and p > 0]
            if len(px) >= 6:
                slopes.append(_trend_pct(px))
        if not slopes:
            by_book[book] = {"regime": "NO DATA", "dir": "flat", "median_slope_pct": None,
                             "symbols": 0, "advice": "awaiting feed"}
            continue
        med = round(median(slopes), 2)
        lbl, d = _label(med)
        up = sum(1 for s in slopes if s > 1.5); dn = sum(1 for s in slopes if s < -1.5)
        by_book[book] = {
            "regime": lbl, "dir": d, "median_slope_pct": med, "symbols": len(slopes),
            "pct_up": round(up / len(slopes) * 100), "pct_down": round(dn / len(slopes) * 100),
            "advice": ("downtrend → favor the SAFE/accuracy bounce target; high targets rarely fill"
                       if d == "down" else
                       "uptrend → the aggressive bounce target can run" if d == "up" else
                       "sideways → mean-reversion plays cleanest"),
        }
    payload = {
        "generated_at": _now(), "window_samples": WINDOW, "by_book": by_book,
        "what": "Current trend regime (up/sideways/down) for each valuable class, every daily run.",
        "why": ("The held-stocks loss risk came from buying a high bounce target into a downtrend. "
                "Regime must be an explicit parameter so target aggression can match it."),
        "action": ("Surfaced in the parameter registry. Method-as-champion (which window classifies "
                   "best) is DATA-GATED until accuracy history exists; the classification itself runs now."),
        "note": "Per-book regime = median 6h trend across that book's fresh symbols.",
    }
    try: write_json_atomic(out / "REGIME_CLASSIFIER.json", payload)
    except Exception: pass
    return payload
