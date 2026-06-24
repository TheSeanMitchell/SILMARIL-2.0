"""
silmaril.execution.time_of_day — STRATEGY TIME ATTRIBUTION (2.5.3). Measurement.

Win rate, expectancy and edge by time-of-day window for each strategy and book, so we
can see which hours produce winners vs noise. Measures only — does NOT enforce windows.
Emits TIME_OF_DAY.json.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from ._trade_helpers import closed_trades, _dt
from .atomic_io import write_json_atomic

def _now(): return datetime.now().astimezone().isoformat()

def _window(et_hour, et_min):
    m = et_hour * 60 + et_min
    if m < 570: return "PREMARKET"        # before 9:30
    if m < 600: return "OPEN"             # 9:30-10:00
    if m < 720: return "MORNING"          # 10:00-12:00
    if m < 840: return "MIDDAY"           # 12:00-14:00
    if m < 960: return "POWER_HOUR"       # 14:00-16:00
    return "AFTER_HOURS"

def build_time_of_day(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    trades = closed_trades(out)
    from datetime import timezone
    def to_et(dt):
        # entry_t is ISO with offset; convert to US/Eastern-ish via fixed -4 (EDT, June)
        try: return dt.astimezone(timezone.utc).astimezone(timezone(__import__("datetime").timedelta(hours=-4)))
        except Exception: return None
    buckets = {}
    for tr in trades:
        et = _dt(tr["entry_t"]); 
        if not et: continue
        e = to_et(et)
        if not e: continue
        w = _window(e.hour, e.minute)
        buckets.setdefault(tr["book"], {}).setdefault(w, []).append(tr["realized_pct"])
    def stats(rs):
        if not rs: return None
        wins = sum(1 for r in rs if r > 0)
        return {"trades": len(rs), "win_pct": round(wins / len(rs) * 100, 1),
                "expectancy_pct": round(sum(rs) / len(rs), 2),
                "best": round(max(rs), 2), "worst": round(min(rs), 2)}
    WINS = ["PREMARKET", "OPEN", "MORNING", "MIDDAY", "POWER_HOUR", "AFTER_HOURS"]
    by_book = {}
    for bk, wd in buckets.items():
        by_book[bk] = {w: stats(wd.get(w, [])) for w in WINS if wd.get(w)}
    # best window per book
    best = {}
    for bk, wd in by_book.items():
        scored = [(w, s["expectancy_pct"]) for w, s in wd.items() if s]
        if scored: best[bk] = max(scored, key=lambda x: x[1])[0]
    payload = {"generated_at": _now(), "by_book": by_book, "best_window_by_book": best,
               "windows": WINS,
               "what": "Trade win rate & expectancy by hour-of-day window (crypto/stock separate).",
               "why": "Some hours are noise, some are edge. Shows where the edge actually lives.",
               "action": "Measurement only — not enforced. Evidence for later session-gating.",
               "note": "Windows in US/Eastern. Crypto trades 24/7 so it fills all windows; stock only RTH."}
    try: write_json_atomic(out / "TIME_OF_DAY.json", payload)
    except Exception: pass
    return payload
