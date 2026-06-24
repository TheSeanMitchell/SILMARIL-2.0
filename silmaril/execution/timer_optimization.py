"""
silmaril.execution.timer_optimization — TIMER / EDGE-CAPTURE SIMULATION (2.5.4).

The decision trace shows almost every trade ends on TIMEOUT, not target/stop. This engine
asks the real question: would a different hold-timer (or NO timer) have captured more edge?

For each closed trade it replays the actual forward price path and re-exits under a grid of
candidate timeouts {30m … 12h, none}, taking the earliest of target-hit / stop-hit / timeout.
It then aggregates per quadrant to find the timer that maximises realized edge, and diagnoses
WHY edge leaked: sold too early (price hit target after we bailed), sold too late (gave back a
better price we already had), or thesis slow/wrong (never recovered).

Measurement + simulation only — it recommends, it does not change live behavior (safe during
the 2.5.5 learning pause). Per-book (crypto/stock/metal/energy), localized. Emits
TIMER_OPTIMIZATION.json.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List
from ._trade_helpers import closed_trades, price_series, _dt
from .atomic_io import write_json_atomic

def _now(): return datetime.now().astimezone().isoformat()
CANDIDATES = [30, 60, 120, 180, 240, 360, 480, 600, 720, None]   # minutes; None = no timer
HORIZON_H = 24                                                   # how far forward we look

def _path(series, sym, start, hours):
    ser = series.get(sym) or []
    end = start + timedelta(hours=hours)
    return [(t, p) for t, p in ser if start <= t <= end]

def _simulate_exit(path, entry, tgt, stp, timeout_min):
    """Replay path; return realized% under this timeout (earliest of target/stop/timeout)."""
    if not path or not entry:
        return None
    t0 = path[0][0]
    deadline = (t0 + timedelta(minutes=timeout_min)) if timeout_min else None
    last_p = path[-1][1]
    for t, p in path:
        if tgt and p >= tgt:
            return round((tgt / entry - 1) * 100, 3)        # took profit
        if stp and p <= stp:
            return round((stp / entry - 1) * 100, 3)        # stopped out
        if deadline and t >= deadline:
            return round((p / entry - 1) * 100, 3)          # timed out at market
    return round((last_p / entry - 1) * 100, 3)             # ran out of data / no timer

def _diagnose(path, entry, exit_px, exit_t, tgt):
    """Classify the edge leak for the ACTUAL exit."""
    if not path or not entry:
        return "unknown"
    xt = _dt(exit_t)
    before = [(t, p) for t, p in path if xt and t <= xt]
    after = [(t, p) for t, p in path if xt and t > xt]
    peak_before = max((p for _, p in before), default=exit_px)
    hit_target_after = tgt and any(p >= tgt for _, p in after)
    if hit_target_after:
        return "sold_too_early"          # target came later, we bailed
    if peak_before > exit_px * 1.004:
        return "sold_too_late"           # we held past a better price
    if tgt and peak_before < tgt:
        return "thesis_slow"             # never reached target in window
    return "captured_ok"

def build_timer_optimization(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    trades, series = closed_trades(out), price_series(out)
    rows = []
    for tr in trades:
        if not tr["entry"] or not tr["target_pct"]:
            continue
        et = _dt(tr["entry_t"])
        if not et:
            continue
        path = _path(series, tr["sym"], et, HORIZON_H)
        if len(path) < 3:
            continue
        tgt = tr["entry"] * (1 + tr["target_pct"] / 100)
        stp = tr["entry"] * (1 - (tr["stop_pct"] or 99) / 100)
        sims = {}
        for T in CANDIDATES:
            r = _simulate_exit(path, tr["entry"], tgt, stp, T)
            if r is not None:
                sims[str(T) if T else "none"] = r
        rows.append({"sym": tr["sym"], "book": tr["book"], "strategy": tr["strategy"],
                     "actual_realized_pct": tr["realized_pct"],
                     "leak": _diagnose(path, tr["entry"], tr["exit"], tr["exit_t"], tgt),
                     "sims": sims})

    def agg(book_rows):
        if not book_rows:
            return None
        by_T = {}
        for key in [str(c) if c else "none" for c in CANDIDATES]:
            vals = [r["sims"][key] for r in book_rows if key in r["sims"]]
            if vals:
                by_T[key] = {"avg_realized_pct": round(mean(vals), 3),
                             "total_realized_pct": round(sum(vals), 2),
                             "win_pct": round(sum(1 for v in vals if v > 0) / len(vals) * 100, 1),
                             "n": len(vals)}
        best = max(by_T.items(), key=lambda kv: kv[1]["avg_realized_pct"]) if by_T else None
        # current behaviour ~= shortest timeout that still beats nothing; compare to actual
        actual_avg = round(mean([r["actual_realized_pct"] for r in book_rows]), 3)
        leaks = {}
        for r in book_rows:
            leaks[r["leak"]] = leaks.get(r["leak"], 0) + 1
        return {"trades": len(book_rows), "actual_avg_realized_pct": actual_avg,
                "by_timeout": by_T,
                "optimal_timeout_min": (None if best and best[0] == "none" else (int(best[0]) if best else None)),
                "optimal_avg_realized_pct": best[1]["avg_realized_pct"] if best else None,
                "improvement_vs_actual_pct": (round(best[1]["avg_realized_pct"] - actual_avg, 3) if best else None),
                "leak_breakdown": leaks}

    books = {b: agg([r for r in rows if r["book"] == b]) for b in ("crypto", "stock", "metal", "energy")}
    books = {b: v for b, v in books.items() if v}
    # headline recommendation per book
    recs = {}
    for b, v in books.items():
        t = v["optimal_timeout_min"]
        recs[b] = ("REMOVE timer (hold to target/stop)" if t is None
                   else f"set timer ≈ {t} min") + f" → +{v['improvement_vs_actual_pct']}%/trade vs today"
    payload = {
        "generated_at": _now(), "candidates_min": [c if c else "none" for c in CANDIDATES],
        "by_book": books, "recommendation_by_book": recs,
        "what": "Replays each closed trade under many hold-timers to find the one that captures the most edge.",
        "why": ("Trades keep ending on TIMEOUT, not target. This proves whether a longer/shorter/no "
                "timer would have captured more, per quadrant."),
        "action": ("Champion the best timer per book like any other parameter. Leak breakdown says WHY: "
                   "sold_too_early = raise/RemoveTimer; sold_too_late = tighten exit; thesis_slow = entry/regime."),
        "note": ("Simulation over real forward price paths (24h horizon). Recommends only — does not change "
                 "live timers during the learning pause. Each quadrant evaluated independently."),
    }
    try: write_json_atomic(out / "TIMER_OPTIMIZATION.json", payload)
    except Exception: pass
    return payload
