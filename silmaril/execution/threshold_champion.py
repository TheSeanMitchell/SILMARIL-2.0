"""
silmaril.execution.threshold_champion — DROP × BOUNCE-BACK CHAMPION (2.5.4).

Tests EVERY drop trigger from 1.0%..5.0% against EVERY bounce-back (take-profit) target from
1.0%..5.0% over real crypto price history. For each (drop, bounce) pair it measures how often
the bounce target was actually reached (accuracy/probability), the average captured move, and
the expectancy. It then elects:
  - champion DROP threshold,
  - champion BOUNCE-BACK threshold,
  - and the champion COMBO (the drop+bounce pair with the best expectancy).
Runs every cycle, leaderboard-style, exactly like the strategy champion. Measurement only —
recommends; does not flip live params during the learning pause. Emits THRESHOLD_CHAMPION.json.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List
from ._trade_helpers import price_series
from .paper_sim import asset_class
from .atomic_io import write_json_atomic

def _now(): return datetime.now(timezone.utc).isoformat()
DROPS = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
BOUNCES = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
LOOKBACK = 6     # samples to measure the drop over (~1h on 10-12min cadence)
HORIZON = 18     # samples to allow the bounce (~3h)
MIN_SIGNALS = 15

def _signals_for_drop(px: List[float], drop_pct: float):
    """Indices where price fell >= drop_pct over LOOKBACK (an oversold entry)."""
    out = []
    for i in range(LOOKBACK, len(px) - HORIZON):
        if (px[i] / px[i - LOOKBACK] - 1) * 100 <= -drop_pct:
            out.append(i)
    return out

def build_threshold_champion(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    series = price_series(out)
    names = sorted([s for s in series if asset_class(s) == "crypto" and len(series[s]) > LOOKBACK + HORIZON],
                   key=lambda s: len(series[s]), reverse=True)[:45]
    # precompute entries per drop (shared across bounce targets)
    seqs = {s: [p for _, p in series[s]] for s in names}
    entries = {d: [] for d in DROPS}
    for s in names:
        px = seqs[s]
        for d in DROPS:
            for i in _signals_for_drop(px, d):
                fwd = px[i:i + HORIZON]
                best = (max(fwd) / px[i] - 1) * 100
                end = (fwd[-1] / px[i] - 1) * 100
                entries[d].append((best, end))
    # grid: for each (drop, bounce) measure accuracy + expectancy
    grid = []
    for d in DROPS:
        rows = entries[d]
        for b in BOUNCES:
            if not rows:
                continue
            outcomes = [b if best >= b else end for best, end in rows]  # sell at target else hold-to-horizon
            hits = sum(1 for best, _ in rows if best >= b)
            grid.append({"drop": d, "bounce": b, "signals": len(rows),
                         "hit_rate_pct": round(hits / len(rows) * 100, 1),
                         "avg_captured_pct": round(mean(outcomes), 3),
                         "expectancy_pct": round(mean(outcomes), 3)})
    eligible = [g for g in grid if g["signals"] >= MIN_SIGNALS]
    combo = max(eligible, key=lambda g: g["expectancy_pct"]) if eligible else None
    # marginal champions
    def best_drop():
        agg = {}
        for g in eligible:
            agg.setdefault(g["drop"], []).append(g["expectancy_pct"])
        if not agg: return None
        return max(agg.items(), key=lambda kv: mean(kv[1]))[0]
    def best_bounce():
        agg = {}
        for g in eligible:
            agg.setdefault(g["bounce"], []).append(g["expectancy_pct"])
        if not agg: return None
        return max(agg.items(), key=lambda kv: mean(kv[1]))[0]
    # accuracy-optimal (highest hit-rate combo with decent sample) — the "safe" champion
    safe = max(eligible, key=lambda g: g["hit_rate_pct"]) if eligible else None
    payload = {
        "generated_at": _now(),
        "drops_tested": DROPS, "bounces_tested": BOUNCES,
        "champion_drop_pct": best_drop(), "champion_bounce_pct": best_bounce(),
        "champion_combo": ({"drop": combo["drop"], "bounce": combo["bounce"],
                            "expectancy_pct": combo["expectancy_pct"],
                            "hit_rate_pct": combo["hit_rate_pct"], "signals": combo["signals"]} if combo else None),
        "accuracy_champion_combo": ({"drop": safe["drop"], "bounce": safe["bounce"],
                                     "hit_rate_pct": safe["hit_rate_pct"],
                                     "expectancy_pct": safe["expectancy_pct"]} if safe else None),
        "current_live": {"drop_pct": 3.0, "bounce_pct": 3.0},
        "grid": sorted(grid, key=lambda g: g["expectancy_pct"], reverse=True)[:30],
        "what": "Every drop trigger 1-5% x every bounce-back target 1-5%, on real crypto history.",
        "why": ("Settles the entry+exit thresholds with evidence, and elects a champion drop, a "
                "champion bounce-back, and the best combo — like the strategy champion."),
        "action": ("Champion the combo per book once un-paused. The accuracy champion = highest "
                   "hit-rate (safer, good for downtrends); the expectancy champion = best return "
                   "(more aggressive, good for uptrends)."),
        "note": ("Hit_rate = % of oversold entries that reached the bounce target within ~3h. "
                 "Expectancy = avg outcome selling at target, else holding to horizon. Crypto only "
                 "until other books have history. Recommends; does not change live params."),
    }
    try: write_json_atomic(out / "THRESHOLD_CHAMPION.json", payload)
    except Exception: pass
    return payload
