"""
GRAPH READ — 7.2.0. ONE structure engine. The chart draws it; the sleeves trade on it.

WHY THIS FILE EXISTS, stated without optimism.

The operator's instruction was: *"quadruple down on the internal graphing system, then train
sleeves that READ the graph the same way M FLOOR ARTIST does — take the place of real humans
using real graphs."* Before building that, three things had to be admitted:

1. **My claim that "M FLOOR ARTIST is green in all four books" was FALSE.** It was measured on
   equity, which includes unrealized marks on open positions. On realized fee-paid P&L — the
   doctrine's Law 1, the only score — M is crypto −$12.92, stock −$50.56, metal +$21.11,
   energy +$4.76. **Total −$37.60.** M is the least-bad sleeve in a losing workshop, not a
   winner. Everything below is built on that corrected footing.

2. **`_structure_levels` anchored its 72-hour window to `_now()` instead of to the data.**
   Live that is roughly harmless because now ≈ the last print. For every backtest, warm start,
   graph→decision audit and reconstruction it silently used a window containing few or none of
   the rows it was handed, then fell back to `live[-200:]` without saying so. Measured on
   PENDLE-USD: the same tape truncated 2 days back reported 0 floors at ≥3 tests; truncated 5
   days back reported 3. That is not a market changing, it is a window bug — and it means every
   structure-based verdict this project has produced outside the live path was measured through
   the wrong lens, including my own audits of M.

3. Structure lived inside `strategy_lab_abcd` as private helpers while the chart computed its
   own copy in JavaScript. Two implementations of "where are the floors" cannot stay honest.

So: ONE module, anchored to the data, with an explicit `as_of`, published to disk each cycle so
the chart and the sleeves read *the same object*. If the picture and the decision ever disagree
again, it is a bug with a name rather than a mystery.

WHAT IT COMPUTES, and why each one is here rather than being clever for its own sake:

  levels          floors/ceilings with test counts, AGE, and how recently each was respected —
                  a level tested 6 times two days ago is not the same evidence as one tested 3
                  times in the last hour, and the old code could not tell them apart
  strength        a level's score: tests, recency, and how cleanly price reversed off it
  approach        are we falling INTO a floor or drifting up off it, and how fast — the
                  difference between catching support and catching a knife
  range_pos       where price sits between nearest floor and nearest ceiling (0=floor, 1=ceiling)
  headroom        distance to the next ceiling, in % and in units of the name's own noise —
                  a 1% target under a ceiling 0.4% away is not a trade, however good the ratio
  cadence         peak rhythm, phase, and time to the next expected peak
  trend           multi-window trajectory plus whether peaks and troughs are stepping up
  break_state     INTACT / TESTING / BROKEN for the nearest level — a floor that just gave way
                  is the single most dangerous thing to buy, and nothing measured it before
  verdict         a compact human-readable read: what a trader would say looking at this chart

Nothing here predicts. It describes, in the same terms a person reading the chart would use,
and it does so identically for the picture and for the decision.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .atomic_io import write_json_atomic
except Exception:                                            # pragma: no cover
    def write_json_atomic(path, payload):                    # type: ignore
        Path(path).write_text(json.dumps(payload, indent=2))

LOOKBACK_H = 72.0
MIN_PRINTS = 30


def _ts(x) -> Optional[datetime]:
    try:
        d = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _live(rows: List) -> List[Tuple[datetime, float]]:
    out = []
    for r in (rows or []):
        try:
            if not r or len(r) < 2 or not r[1] or float(r[1]) <= 0:
                continue
            if "T00:00:00" in str(r[0]):
                continue                                     # daily backfill is not the tape
            t = _ts(r[0])
            if t:
                out.append((t, float(r[1])))
        except Exception:
            continue
    out.sort()
    return out


def read_graph(rows: List, lookback_h: float = LOOKBACK_H,
               as_of: datetime = None) -> Dict[str, Any]:
    """The canonical read. `as_of` defaults to THE LAST PRINT — never to wall-clock now.

    That default is the fix for bug (2) above: a structure read must be anchored to the data it
    is handed, so the same tape produces the same answer whether it is read live, in a backtest,
    or in an audit six days later."""
    live = _live(rows)
    out: Dict[str, Any] = {"ok": False, "why": "no tape"}
    if len(live) < MIN_PRINTS:
        out["why"] = "only %d live prints (need %d)" % (len(live), MIN_PRINTS)
        return out

    anchor = as_of or live[-1][0]
    cut = anchor - timedelta(hours=lookback_h)
    win = [(t, p) for t, p in live if cut <= t <= anchor]
    if len(win) < MIN_PRINTS:
        win = [x for x in live if x[0] <= anchor][-240:]
        if len(win) < MIN_PRINTS:
            out["why"] = "not enough prints inside the window"
            return out

    ts = [t for t, _p in win]
    ys = [p for _t, p in win]
    n = len(ys)
    px = ys[-1]

    # the name's own noise — every threshold below is scaled to it, never to a constant
    steps = sorted(abs(ys[i] / ys[i - 1] - 1) for i in range(1, n) if ys[i - 1] > 0)
    sig = steps[len(steps) // 2] if steps else 0.001
    prom = max(sig * 3, 0.002)
    w = max(2, n // 40)

    peaks: List[Tuple[datetime, float]] = []
    troughs: List[Tuple[datetime, float]] = []
    for i in range(w, n - w):
        seg = ys[i - w:i + w + 1]
        if ys[i] == max(seg):
            base = min(ys[max(0, i - w * 3):i + 1])
            if base > 0 and ys[i] / base - 1 >= prom:
                peaks.append((ts[i], ys[i]))
        if ys[i] == min(seg):
            cap = max(ys[max(0, i - w * 3):i + 1])
            if ys[i] > 0 and cap / ys[i] - 1 >= prom:
                troughs.append((ts[i], ys[i]))

    def cluster(pts: List[Tuple[datetime, float]]) -> List[Dict[str, Any]]:
        """Levels with tests, AGE and RECENCY — the thing the old cluster could not express."""
        lv: List[Dict[str, Any]] = []
        tol = max(sig * 2, 0.004)
        for t, p in pts:
            for q in lv:
                if abs(p / q["level"] - 1) <= tol:
                    q["level"] = (q["level"] * q["tested"] + p) / (q["tested"] + 1)
                    q["tested"] += 1
                    q["last_t"] = max(q["last_t"], t)
                    q["first_t"] = min(q["first_t"], t)
                    break
            else:
                lv.append({"level": p, "tested": 1, "first_t": t, "last_t": t})
        span_h = max(1e-6, (anchor - win[0][0]).total_seconds() / 3600.0)
        for q in lv:
            age_h = (anchor - q["last_t"]).total_seconds() / 3600.0
            life_h = max(1e-6, (q["last_t"] - q["first_t"]).total_seconds() / 3600.0)
            q["age_h"] = round(age_h, 2)
            q["span_h"] = round(life_h, 2)
            # STRENGTH: tests matter, but a level respected recently and over a long life
            # matters more. Deliberately simple and inspectable rather than tuned.
            recency = max(0.0, 1.0 - (age_h / span_h if span_h > 0 else 1.0))
            q["strength"] = round(q["tested"] * (0.55 + 0.45 * recency), 2)
            q.pop("first_t", None)
            q["last_t"] = q["last_t"].isoformat()
        return sorted(lv, key=lambda q: -q["strength"])

    floors_all = cluster(troughs)
    ceils_all = cluster(peaks)
    # 7.2.0: the tolerance used to let "nearest resistance" sit BELOW price, which produced
    # band_pos of 209% and negative headroom — nonsense that a sleeve would then reason from.
    # Support must be at or below price; resistance must be genuinely ABOVE it. If price has
    # cleared every known ceiling, say so honestly rather than pointing at one underneath.
    floors = [f for f in floors_all if f["level"] <= px * 1.002]
    ceils = [c for c in ceils_all if c["level"] > px * 1.0005]

    nf = max(floors, key=lambda f: f["level"]) if floors else None    # nearest support below
    nc = min(ceils, key=lambda c: c["level"]) if ceils else None      # nearest resistance above

    # APPROACH — are we falling into support or lifting off it, and how fast?
    k = min(6, max(3, n // 30))
    recent = ys[-k:]
    slope_pct = (recent[-1] / recent[0] - 1) * 100 if recent[0] > 0 else 0.0
    approach = ("FALLING_INTO" if slope_pct < -sig * 100 else
                "LIFTING_OFF" if slope_pct > sig * 100 else "FLAT_AT")

    # BREAK STATE for the nearest floor — the most dangerous thing to misread
    break_state, broke_by = "NONE", None
    if nf:
        below = [p for p in ys[-k:] if p < nf["level"] * 0.997]
        if len(below) >= max(2, k // 2):
            break_state = "BROKEN"
            broke_by = round((min(below) / nf["level"] - 1) * 100, 3)
        elif abs(px / nf["level"] - 1) <= max(sig * 2, 0.004):
            break_state = "TESTING"
        else:
            break_state = "INTACT"

    # CADENCE
    cadence_min = None
    phase = "UNKNOWN"
    next_peak_in_min = None
    if len(peaks) >= 3:
        gaps = sorted((peaks[i][0] - peaks[i - 1][0]).total_seconds() / 60.0
                      for i in range(1, len(peaks)))
        cadence_min = gaps[len(gaps) // 2]
        since = (anchor - peaks[-1][0]).total_seconds() / 60.0
        if cadence_min > 0:
            frac = since / cadence_min
            phase = ("PEAK_DUE" if frac >= 0.85 else
                     "JUST_PEAKED" if frac <= 0.25 else "MID_CYCLE")
            next_peak_in_min = round(cadence_min - since, 1)

    # TREND — trajectory across windows, plus whether the structure itself is stepping up
    def win_pct(hours):
        c = anchor - timedelta(hours=hours)
        seg = [p for t, p in live if c <= t <= anchor]
        return round((seg[-1] / seg[0] - 1) * 100, 3) if len(seg) >= 2 and seg[0] > 0 else None

    traj = {("%dh" % h): win_pct(h) for h in (2, 4, 8, 12, 24, 48, 72)}
    def steps_of(pts):
        if len(pts) < 3:
            return "UNKNOWN"
        a, b = pts[-3][1], pts[-1][1]
        return "RISING" if b > a * 1.002 else "FALLING" if b < a * 0.998 else "FLAT"
    peak_traj, trough_traj = steps_of(peaks), steps_of(troughs)

    hi, lo = max(ys), min(ys)
    range_pos = round((px - lo) / (hi - lo), 3) if hi > lo else 0.5
    band_pos = None
    if nf and nc and nc["level"] > nf["level"]:
        band_pos = round(min(1.0, max(0.0, (px - nf["level"]) / (nc["level"] - nf["level"]))), 3)
    above_all = (nf is not None and nc is None)   # price has cleared every known ceiling

    headroom_pct = round((nc["level"] / px - 1) * 100, 3) if nc else None
    support_pct = round((px / nf["level"] - 1) * 100, 3) if nf else None
    # headroom measured in the name's OWN noise: a 1% target under a ceiling 0.4% away is not a
    # trade however good the ratio looks
    headroom_sigmas = round((headroom_pct / 100.0) / sig, 2) if (headroom_pct and sig > 0) else None

    # the sentence a trader would say out loud looking at this chart
    bits = []
    if nf:
        bits.append("support %.6g (%dx, strength %.1f, %s)"
                    % (nf["level"], nf["tested"], nf["strength"], break_state.lower()))
    if nc:
        bits.append("resistance %.6g (%dx) %.2f%% up" % (nc["level"], nc["tested"], headroom_pct or 0))
    if band_pos is not None:
        bits.append("sitting %.0f%% of the way up the band" % (band_pos * 100))
    bits.append("%s at %.2f%%/%d prints" % (approach.lower().replace("_", " "), slope_pct, k))
    if phase != "UNKNOWN":
        bits.append("cadence %s" % phase.lower().replace("_", " "))
    bits.append("peaks %s, troughs %s" % (peak_traj.lower(), trough_traj.lower()))

    out = {
        "ok": True,
        "as_of": anchor.isoformat(),
        "prints_in_window": n,
        "px": px,
        "sigma_step": round(sig, 6),
        "floors": floors[:6], "ceilings": ceils[:6],
        "nearest_floor": nf, "nearest_ceiling": nc,
        "support_pct": support_pct, "headroom_pct": headroom_pct,
        "headroom_sigmas": headroom_sigmas,
        "range_pos": range_pos, "band_pos": band_pos, "above_all_ceilings": above_all,
        "approach": approach, "approach_slope_pct": round(slope_pct, 3),
        "break_state": break_state, "broke_by_pct": broke_by,
        "cadence_min": (round(cadence_min, 1) if cadence_min else None),
        "cadence_phase": phase, "next_peak_in_min": next_peak_in_min,
        "peaks_n": len(peaks), "troughs_n": len(troughs),
        "peak_trajectory": peak_traj, "trough_trajectory": trough_traj,
        "trajectory": traj,
        "verdict": " · ".join(bits),
    }
    return out


def build_graph_read(out_dir, samples: Dict[str, List] = None,
                     limit: int = 400) -> Dict[str, Any]:
    """Publish GRAPH_READ.json so the chart and the sleeves consume the SAME object.

    Two implementations of 'where are the floors' cannot stay honest — the dashboard computed
    its own in JavaScript while the sleeves computed theirs in Python. This is the single
    source of truth; the chart reads it and falls back to its own maths only when a name is
    absent, and says so when it does."""
    out = Path(out_dir)
    if samples is None:
        try:
            from .canon_keys import canonical_samples
            samples = canonical_samples(out)
        except Exception:
            samples = {}
    truth = {}
    try:
        truth = (json.loads((out / "PRICE_TRUTH.json").read_text()).get("by_symbol") or {})
    except Exception:
        pass

    by: Dict[str, Any] = {}
    ranked = sorted((samples or {}).items(), key=lambda kv: -len(kv[1] or []))
    for sym, rows in ranked[:limit]:
        rec = truth.get(sym)
        if rec is not None and not rec.get("structure_ok", rec.get("tradeable", True)):
            continue                       # a broken feed has no structure worth publishing
        r = read_graph(rows)
        if r.get("ok"):
            by[sym] = r

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "law": ("ONE structure engine. The chart draws this object and the sleeves trade on it. "
                "Anchored to the LAST PRINT, never to wall-clock time, so a backtest and a live "
                "read of the same tape agree."),
        "lookback_h": LOOKBACK_H, "symbols": len(by), "by_symbol": by,
    }
    write_json_atomic(out / "GRAPH_READ.json", payload)
    return payload


# ── the reader every sleeve uses ──────────────────────────────────────────────────────
_CACHE: Dict[str, Any] = {}


def load_reads(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    try:
        st = (out / "GRAPH_READ.json").stat().st_mtime
    except Exception:
        return {}
    if _CACHE.get("mt") == st:
        return _CACHE.get("by") or {}
    try:
        by = json.loads((out / "GRAPH_READ.json").read_text()).get("by_symbol") or {}
    except Exception:
        by = {}
    _CACHE["mt"], _CACHE["by"] = st, by
    return by


if __name__ == "__main__":                                   # pragma: no cover
    import sys
    p = build_graph_read(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("published structure for %d symbols" % p["symbols"])
    for s, r in list(p["by_symbol"].items())[:6]:
        print("  %-11s %s" % (s, r["verdict"]))
