"""
silmaril.execution.chart_intel — 7.0.6 THE GRAPH BRAIN.

The operator's complaint, verbatim: "when as a human we look at the graphs, we can see peaks, we can
see if the peaks are in an upward trajectory, downward trajectory, the time between each peak, if the
last peak was more or less... we see all of the things a professional trader would notice. We need the
system to be doing the same."

They were right that the data was already there and right that nothing was using it. The receipt: on
2026-07-24 the crypto/stock books bought MRVL while it was down 8.66% over 24h and 6.99% over 72h. The
trajectory veto HAD both numbers and waved the trade through anyway, because its "floor" test was
"were the last 3 prints non-decreasing?" — a condition satisfied 72% of the time on MRVL's own tape.
It was a coin flip wearing the costume of a safety gate. AMAT (-4.39%/24h) died the same way.

This module replaces guesswork with structure, computed from our own tape:

  PEAKS & TROUGHS   fractal swing detection with a prominence filter, so noise is not a peak
  STRUCTURE         Dow's rule: higher highs + higher lows = UPTREND; lower highs + lower lows =
                    DOWNTREND; anything else = RANGE. This is the operator's RUNE observation
                    ("the peaks at Jul 19 and Jul 21 rose, then Jul 22 and Jul 24 collapsed")
                    expressed as code.
  FLOORS & CEILINGS support/resistance from CLUSTERED troughs and peaks, with a test count — a level
                    touched four times is real; a level touched once is a coincidence.
  BASING            has price actually stopped making new lows? (the honest version of "is there a
                    floor") — the most recent trough must not be the lowest, and price must sit a
                    real, volatility-scaled distance above it.
  WINDOWS           trajectory across 2h/4h/8h/12h/1d/2d/3d/1w — the exact ladder the operator listed.
  CADENCE           median minutes between peaks, and the implied ETA of the next one.
  CROSS-SOURCE      the same symbol priced from every feed we hold; disagreement is surfaced, never
                    averaged away.

Everything here is measured from real prints. Nothing is synthesised, nothing is assumed, and where
the tape is too thin to support a conclusion the field comes back None and the verdict says so.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .atomic_io import write_json_atomic

STORE = "CHART_INTEL.json"

# every price file we hold — used both as the price source and as the cross-source check
SOURCE_FILES = ("price_samples.json", "ccxt_samples.json",
                "metals_samples.json", "energy_samples.json")

WINDOWS_H = (2, 4, 8, 12, 24, 48, 72, 168)
WINDOW_LABEL = {2: "2h", 4: "4h", 8: "8h", 12: "12h", 24: "1d", 48: "2d", 72: "3d", 168: "1w"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ts(t) -> Optional[float]:
    try:
        d = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
    except Exception:
        return None


def _clean(rows, drop_backfill: bool = True) -> List[Tuple[float, float]]:
    """(epoch, price), sorted, positive prices only. Daily backfill candles are dropped by default:
    a 00:00:00 stamp is a daily close, not an intraday print, and mixing them fabricates moves."""
    out = []
    for t, p in (rows or []):
        if not p or float(p) <= 0:
            continue
        if drop_backfill and "T00:00:00" in str(t):
            continue
        e = _ts(t)
        if e is not None:
            out.append((e, float(p)))
    out.sort()
    return out


def window_move(pts: List[Tuple[float, float]], hours: float) -> Optional[float]:
    """Fractional move across the window, measured from the earliest print inside it."""
    if len(pts) < 4:
        return None
    now = pts[-1][0]
    cut = now - hours * 3600.0
    inside = [p for e, p in pts if e >= cut]
    if len(inside) < 3:
        return None
    first, last = inside[0], inside[-1]
    return (last / first - 1.0) if first > 0 else None


def swings(pts: List[Tuple[float, float]], k: int = 5,
           min_prom: float = 0.004) -> Tuple[List[dict], List[dict]]:
    """Fractal swing detection. px[i] is a peak when it is the maximum of the window [i-k, i+k] and
    stands at least `min_prom` above the lower of the two troughs bracketing it. The prominence
    filter is what separates a real turning point from tick noise — without it every wiggle in a
    600-print series registers as structure, which is how a free-falling stock came to look
    'supported'."""
    if len(pts) < (2 * k + 3):
        return [], []
    peaks, troughs = [], []
    for i in range(k, len(pts) - k):
        w = [p for _e, p in pts[i - k:i + k + 1]]
        px = pts[i][1]
        if max(w) == min(w):
            continue                      # dead flat window — no structure to read
        # NOTE: an earlier cut required the extreme to be UNIQUE in its window (w.count(px)==1).
        # That silently disabled swing detection on any tape that repeats a price — which is most
        # of them, and nearly all of a quiet ETF's session. A turning point that prints its high
        # twice is still a turning point. We now take the FIRST index achieving the extreme.
        if px == max(w):
            peaks.append({"i": i, "t": pts[i][0], "px": px})
        elif px == min(w):
            troughs.append({"i": i, "t": pts[i][0], "px": px})
    # Ties and plateaus produce clusters of adjacent detections; keep one turning point per swing.
    def _dedupe(marks, keep_max):
        out = []
        for m in marks:
            if out and (m["i"] - out[-1]["i"]) <= k:
                if (m["px"] > out[-1]["px"]) if keep_max else (m["px"] < out[-1]["px"]):
                    out[-1] = m
            else:
                out.append(m)
        return out
    peaks, troughs = _dedupe(peaks, True), _dedupe(troughs, False)

    # prominence filter: a peak must clear its neighbouring troughs by min_prom
    def _prominent(marks, others, is_peak):
        keep = []
        for m in marks:
            near = [o["px"] for o in others if abs(o["i"] - m["i"]) <= 3 * k]
            if not near:
                keep.append(m)
                continue
            base = max(near) if is_peak else min(near)
            if base <= 0:
                continue
            rel = (m["px"] / base - 1.0) if is_peak else (base / m["px"] - 1.0)
            if rel >= min_prom:
                keep.append(m)
        return keep
    return _prominent(peaks, troughs, True), _prominent(troughs, peaks, False)


def _direction(marks: List[dict], n: int = 3) -> Dict[str, Any]:
    """Are the last n swing points rising, falling, or flat? This is the operator's own eye test:
    'the last peak was more or less, and how much more or less'."""
    if len(marks) < 2:
        return {"direction": None, "n": len(marks), "change_pct": None}
    last = marks[-n:] if len(marks) >= n else marks
    a, b = last[0]["px"], last[-1]["px"]
    if a <= 0:
        return {"direction": None, "n": len(last), "change_pct": None}
    chg = (b / a - 1.0)
    d = "RISING" if chg > 0.004 else "FALLING" if chg < -0.004 else "FLAT"
    return {"direction": d, "n": len(last), "change_pct": round(chg * 100, 3),
            "levels": [round(m["px"], 8) for m in last]}


def _levels(marks: List[dict], tol: float = 0.006) -> List[dict]:
    """Cluster swing points into price levels. A level tested repeatedly is structure; a level
    touched once is an accident. Returned strongest-first."""
    if not marks:
        return []
    pxs = sorted(m["px"] for m in marks)
    clusters: List[List[float]] = [[pxs[0]]]
    for p in pxs[1:]:
        if clusters[-1][-1] > 0 and abs(p / clusters[-1][-1] - 1.0) <= tol:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    out = [{"level": round(statistics.median(c), 8), "tested": len(c)} for c in clusters]
    out.sort(key=lambda d: (-d["tested"], -d["level"]))
    return out


def analyze(sym: str, rows, cost: Optional[float] = None) -> Dict[str, Any]:
    """Everything the graph knows about one symbol, from its own prints."""
    pts = _clean(rows)
    n = len(pts)
    base: Dict[str, Any] = {"sym": sym, "prints": n, "generated_at": _now()}
    if n < 20:
        base.update({"verdict": {"buyable": None,
                                 "why": f"tape too thin to read structure ({n} intraday prints)"},
                     "structure": None})
        return base

    last = pts[-1][1]
    span_h = (pts[-1][0] - pts[0][0]) / 3600.0
    rets = [abs(pts[i][1] / pts[i - 1][1] - 1.0) for i in range(1, n) if pts[i - 1][1] > 0]
    rets = [r for r in rets if r > 0]
    sigma = statistics.median(rets) if rets else 0.0

    pk, tr = swings(pts, k=5, min_prom=max(0.004, (cost or 0.0) * 2))
    pk_dir, tr_dir = _direction(pk), _direction(tr)

    # Dow structure: it takes BOTH sequences agreeing to call a trend.
    structure, struct_why = "RANGE", "peaks and troughs disagree — no clean trend"
    if pk_dir["direction"] == "RISING" and tr_dir["direction"] == "RISING":
        structure, struct_why = "UPTREND", "higher highs and higher lows"
    elif pk_dir["direction"] == "FALLING" and tr_dir["direction"] == "FALLING":
        structure, struct_why = "DOWNTREND", "lower highs and lower lows"
    elif pk_dir["direction"] == "FALLING" and tr_dir["direction"] in ("FLAT", None):
        structure, struct_why = "DISTRIBUTION", "lower highs against a flat floor"
    elif pk_dir["direction"] in ("FLAT", None) and tr_dir["direction"] == "RISING":
        structure, struct_why = "ACCUMULATION", "higher lows against a flat ceiling"

    floors, ceilings = _levels(tr), _levels(pk)
    floor = floors[0] if floors else None
    ceiling = ceilings[0] if ceilings else None

    # BASING — the honest replacement for "3 rising prints". Two conditions, both structural:
    #   1. the most recent trough is NOT the lowest of the recent troughs (it stopped making lows)
    #   2. price sits a real, volatility-scaled distance above that trough (it actually lifted)
    based, base_why = False, "no basing evidence"
    if len(tr) >= 2:
        recent = tr[-4:]
        lows = [t["px"] for t in recent]
        newest = recent[-1]["px"]
        if newest > min(lows) * (1 + max(0.002, sigma)):
            lift = (last / newest - 1.0) if newest > 0 else 0.0
            if lift >= max(0.002, sigma * 2):
                based, base_why = True, (f"stopped making lows and lifted {lift*100:.2f}% "
                                         f"off the last trough")
            else:
                base_why = f"higher low printed but price has only lifted {lift*100:.2f}% off it"
        else:
            base_why = "most recent trough is still the lowest — price is still making new lows"

    wins = {}
    for h in WINDOWS_H:
        m = window_move(pts, h)
        wins[WINDOW_LABEL[h]] = None if m is None else round(m * 100, 3)
    down_windows = [k for k, v in wins.items() if v is not None and v < 0]
    up_windows = [k for k, v in wins.items() if v is not None and v > 0]

    cadence_min, next_eta_min = None, None
    if len(pk) >= 3:
        gaps = [(pk[i]["t"] - pk[i - 1]["t"]) / 60.0 for i in range(1, len(pk))]
        gaps = [g for g in gaps if g > 0]
        if gaps:
            cadence_min = round(statistics.median(gaps), 1)
            since = (pts[-1][0] - pk[-1]["t"]) / 60.0
            next_eta_min = round(cadence_min - since, 1)

    rng_lo = floor["level"] if floor else min(p for _e, p in pts)
    rng_hi = ceiling["level"] if ceiling else max(p for _e, p in pts)
    pos_in_range = None
    if rng_hi > rng_lo:
        pos_in_range = round(max(0.0, min(1.0, (last - rng_lo) / (rng_hi - rng_lo))), 3)

    # THE VERDICT the entry gate consumes. A dip inside an uptrend is the trade the whole system is
    # built to take. A dip inside a downtrend is a falling knife, and no amount of oversold-ness
    # makes it one — that is the MRVL/AMAT/RUNE lesson, encoded.
    buyable, why = True, "structure permits a dip entry"
    if structure == "DOWNTREND" and not based:
        buyable = False
        why = (f"DOWNTREND ({struct_why}) with no basing — {base_why}. "
               f"down in {len(down_windows)} of {len([v for v in wins.values() if v is not None])} "
               f"windows. A falling knife is not a dip.")
    # NOTE — 7.0.6a, and this is a correction of my own overreach. Two further rules once lived
    # here: block DISTRIBUTION, and block anything "down across 6+ timeframes". Both were removed
    # after a POINT-IN-TIME backtest (tape truncated to each entry moment, no look-ahead) over the
    # 2026-07-23 session showed they destroyed profit rather than protecting it:
    #
    #     actual day                   +173.76
    #     with those extra rules       +141.21   (blocked MKR +73.67 and MANTA +33.33)
    #     structure-only (this build)  +248.21   (blocked ZEC -74.45 and nothing else)
    #
    # A RANGE name sitting at its floor is the mean-reversion trade this entire platform exists to
    # take; "down in many windows" is what a dip LOOKS like and is not evidence against it. Only
    # the indefensible shape is refused now: lower highs AND lower lows AND still printing new
    # lows. Everything else is left to the strategy, which is where that judgment belongs.

    base.update({
        "last": round(last, 8), "span_h": round(span_h, 1), "sigma_pct": round(sigma * 100, 4),
        "windows": wins, "down_windows": down_windows, "up_windows": up_windows,
        "peaks": [{"t": datetime.fromtimestamp(m["t"], timezone.utc).isoformat(),
                   "px": round(m["px"], 8)} for m in pk[-8:]],
        "troughs": [{"t": datetime.fromtimestamp(m["t"], timezone.utc).isoformat(),
                     "px": round(m["px"], 8)} for m in tr[-8:]],
        "peak_trajectory": pk_dir, "trough_trajectory": tr_dir,
        "structure": structure, "structure_why": struct_why,
        "floor": floor, "ceiling": ceiling,
        "floors": floors[:4], "ceilings": ceilings[:4],
        "distance_to_floor_pct": (round((last / floor["level"] - 1) * 100, 3)
                                  if floor and floor["level"] > 0 else None),
        "distance_to_ceiling_pct": (round((ceiling["level"] / last - 1) * 100, 3)
                                    if ceiling and last > 0 else None),
        "position_in_range": pos_in_range,
        "based": based, "basing_why": base_why,
        "cadence_min": cadence_min, "next_peak_eta_min": next_eta_min,
        "verdict": {"buyable": buyable, "why": why},
    })
    return base


def cross_source(sym: str, out: Path) -> Dict[str, Any]:
    """The same name priced from every feed we hold. Disagreement is REPORTED, never averaged —
    the operator asked to know when sources differ, not to have the difference hidden."""
    seen = {}
    for fn in SOURCE_FILES:
        try:
            s = json.loads((out / fn).read_text()).get("samples", {})
        except Exception:
            continue
        rows = _clean(s.get(sym))
        if rows:
            seen[fn.replace("_samples.json", "").replace(".json", "")] = {
                "last": round(rows[-1][1], 8), "prints": len(rows),
                "age_min": round((datetime.now(timezone.utc).timestamp() - rows[-1][0]) / 60.0, 1)}
    if len(seen) < 2:
        return {"sources": seen, "agree": None,
                "note": "only one feed carries this name — no cross-check possible"}
    prices = [v["last"] for v in seen.values()]
    spread = (max(prices) / min(prices) - 1.0) if min(prices) > 0 else None
    return {"sources": seen, "spread_pct": round((spread or 0) * 100, 4),
            "agree": bool(spread is not None and spread <= 0.005),
            "note": ("sources agree within 0.5%" if spread is not None and spread <= 0.005
                     else "SOURCES DISAGREE — treat this name's price as suspect")}


def build_chart_intel(out_dir, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    """Analyse every name the books can actually act on, and publish the whole picture."""
    out = Path(out_dir)
    samples: Dict[str, Any] = {}
    for fn in SOURCE_FILES:
        try:
            samples.update(json.loads((out / fn).read_text()).get("samples", {}))
        except Exception:
            continue
    try:
        live = json.loads((out / "paper_sim_live.json").read_text())
    except Exception:
        live = {}

    # focus: everything currently held, everything in a live funnel, plus the broad tape
    focus = set(symbols or [])
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        b = live.get(bk) or {}
        for p in (b.get("positions") or []):
            if p.get("sym"):
                focus.add(p["sym"])
        for d in (b.get("decision_trace_live") or []):
            if d.get("sym"):
                focus.add(d["sym"])
    if not focus:
        focus = set(list(samples.keys())[:400])

    by_symbol, n_block = {}, 0
    for sym in sorted(focus):
        rows = samples.get(sym)
        if not rows:
            continue
        a = analyze(sym, rows)
        if a.get("verdict", {}).get("buyable") is False:
            n_block += 1
        by_symbol[sym] = a

    payload = {
        "generated_at": _now(),
        "symbols_analysed": len(by_symbol),
        "would_block": n_block,
        "by_symbol": by_symbol,
        "what": ("THE GRAPH BRAIN: every metric a professional trader reads off a chart, computed "
                 "from our own prints — swing peaks and troughs, Dow structure (higher highs + "
                 "higher lows), clustered floors and ceilings with test counts, basing evidence, "
                 "trajectory across 2h/4h/8h/12h/1d/2d/3d/1w, peak cadence and next-peak ETA. The "
                 "entry gate consumes verdict.buyable, so what the chart shows and what the engine "
                 "does can no longer disagree."),
        "receipt": ("Built after the 2026-07-24 MRVL loss: the book bought a name down 8.66%/24h "
                    "and 6.99%/72h because the old floor test ('were the last 3 prints "
                    "non-decreasing?') passes 72% of the time on that very tape. Structure replaces "
                    "coin-flips."),
    }
    try:
        write_json_atomic(out / STORE, payload)
    except Exception:
        pass
    return payload


def verdict_for(out_dir, sym: str) -> Dict[str, Any]:
    """What the gate asks: may this name be bought right now, and why not."""
    try:
        d = json.loads((Path(out_dir) / STORE).read_text()).get("by_symbol", {})
        return (d.get(sym) or {}).get("verdict") or {}
    except Exception:
        return {}


if __name__ == "__main__":
    import sys
    p = build_chart_intel(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(f"analysed {p['symbols_analysed']} · would block {p['would_block']}")
    for s, a in list(p["by_symbol"].items())[:12]:
        v = a.get("verdict", {})
        print(f"  {s:12} {str(a.get('structure')):13} based={str(a.get('based')):5} "
              f"buyable={str(v.get('buyable')):5} {str(v.get('why'))[:70]}")
