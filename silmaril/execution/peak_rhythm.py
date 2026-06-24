"""
silmaril.execution.peak_rhythm — PEAK RHYTHM / BOUNCE TIMING (2.5.4, measurement).

Learns the TIME BETWEEN peaks (and between troughs) for each tracked symbol, so the system
can estimate WHEN the next bounce/peak is likely — the timing backbone of mean-reversion.
For BTC etc. it answers "it fell and will bounce a few times; here's the typical gap between
those bounces, so this is probably near the next peak." Pure measurement on price history —
no behavior change (safe during the 2.5.5 learning pause). Emits PEAK_RHYTHM.json.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import median, mean
from typing import Any, Dict, List
from .atomic_io import write_json_atomic
from .paper_sim import asset_class

def _now(): return datetime.now(timezone.utc).isoformat()
def _dt(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None

def _extrema(prices: List[float], times: List[Any], win: int = 5):
    """Local maxima (peaks) and minima (troughs): a point at least as extreme as `win`
    neighbours each side."""
    peaks, troughs = [], []
    n = len(prices)
    for i in range(win, n - win):
        seg = prices[i - win:i + win + 1]
        if prices[i] == max(seg) and prices[i] > prices[i - win] and prices[i] > prices[i + win]:
            peaks.append((times[i], prices[i]))
        elif prices[i] == min(seg) and prices[i] < prices[i - win] and prices[i] < prices[i + win]:
            troughs.append((times[i], prices[i]))
    return peaks, troughs

def _gaps_min(points):
    ts = [_dt(t) for t, _ in points if _dt(t)]
    return [round((ts[i] - ts[i - 1]).total_seconds() / 60.0, 1) for i in range(1, len(ts))]

def _analyze(prices, times):
    if len(prices) < 20:
        return None
    peaks, troughs = _extrema(prices, times)
    pg, tg = _gaps_min(peaks), _gaps_min(troughs)
    last_peak_t = _dt(peaks[-1][0]) if peaks else None
    med_peak_gap = median(pg) if pg else None
    next_peak_eta = None
    if last_peak_t and med_peak_gap:
        next_peak_eta = (last_peak_t + timedelta(minutes=med_peak_gap)).isoformat()
    # crude trend: last price vs mean of last 20
    recent = prices[-20:]
    trend = "up" if prices[-1] > mean(recent) else "down"
    return {
        "n_points": len(prices),
        "peaks_found": len(peaks), "troughs_found": len(troughs),
        "median_minutes_between_peaks": med_peak_gap,
        "avg_minutes_between_peaks": round(mean(pg), 1) if pg else None,
        "median_minutes_between_troughs": median(tg) if tg else None,
        "last_peak_at": peaks[-1][0] if peaks else None,
        "last_peak_price": round(peaks[-1][1], 6) if peaks else None,
        "predicted_next_peak_at": next_peak_eta,
        "last_trough_at": troughs[-1][0] if troughs else None,
        "current_trend": trend,
        "typical_peak_amplitude_pct": (round(mean([(p / t - 1) * 100 for (_, p), (_, t)
                                       in zip(peaks, troughs)][:10]), 2)
                                       if peaks and troughs else None),
    }

def build_peak_rhythm(out_dir, focus: List[str] = None) -> Dict[str, Any]:
    out = Path(out_dir)
    try: samples = json.loads((out / "price_samples.json").read_text()).get("samples", {})
    except Exception: samples = {}
    # focus set: open positions + majors + (fallback) most-sampled crypto
    focus_syms = set(focus or [])
    try:
        L = json.loads((out / "paper_sim_live.json").read_text())
        for bk in ("crypto", "stock"):
            for p in (L.get(bk, {}) or {}).get("open_positions", []) or []:
                if isinstance(p, dict) and p.get("sym"): focus_syms.add(p["sym"])
    except Exception:
        pass
    for m in ("BTC-USD", "ETH-USD", "SOL-USD", "XAU-USD", "XAG-USD"):
        if m in samples: focus_syms.add(m)
    if len(focus_syms) < 8:
        ranked = sorted(samples.items(), key=lambda kv: len(kv[1]), reverse=True)
        for s, _ in ranked[:12]:
            if asset_class(s) == "crypto": focus_syms.add(s)

    results = {}
    for sym in focus_syms:
        rows = samples.get(sym) or []
        prices = [p for _, p in rows if p and p > 0]
        times = [t for t, p in rows if p and p > 0]
        a = _analyze(prices, times)
        if a: results[sym] = a
    payload = {
        "generated_at": _now(), "tracked": len(results), "by_symbol": results,
        "what": "Typical time between price peaks/troughs per symbol, and the predicted next peak.",
        "why": ("Mean-reversion is about timing the bounce. Knowing the usual gap between peaks "
                "lets us flag 'this is probably near the next bounce peak.'"),
        "action": ("Feeds the chart's prediction overlay. Measurement only during the 2.5.5 "
                   "learning pause — it informs, it does not auto-trade."),
        "note": "Peaks = local maxima over a 5-sample window on ~10-12min cadence (~1h smoothing).",
    }
    try: write_json_atomic(out / "PEAK_RHYTHM.json", payload)
    except Exception: pass
    return payload
