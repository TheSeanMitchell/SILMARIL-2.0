"""
REGIME CLASSIFIER — 3.0, rebuilt for ACCURACY and TRANSPARENCY.

THE BUG THIS FIXES: the old version sliced rows[-36:] WITHOUT removing daily-backfill candles
("T00:00:00"). So the "last 6h" window was actually polluted with a year of midnight closes — Bitcoin
down 42% on the year forced crypto to read DOWNTREND even on a strongly green day. Every downstream gate
inherited that lie.

NOW: only true intraday prints feed the read. Each book gets a MULTI-TIMEFRAME picture (1h / 6h / 24h)
plus breadth (% of names up) and volatility, and the headline regime is the intraday trend. Every number
is written out so the operator sees EXACTLY why a book is red/yellow/green — no hidden constants.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List
from .atomic_io import write_json_atomic
from .paper_sim import asset_class

UP, DN = 1.0, -1.0

def _now(): return datetime.now(timezone.utc).isoformat()

def _intraday(rows):
    return [(t, p) for t, p in rows if p and p > 0 and "T00:00:00" not in t]

def _ok_ts(t, cut):
    try:
        return datetime.fromisoformat(t).timestamp() >= cut
    except Exception:
        return False

def _slope_window(rows, nowt, hours):
    cut = nowt.timestamp() - hours * 3600
    px = [p for t, p in rows if _ok_ts(t, cut)]
    if len(px) < (3 if hours <= 1 else 4):
        return None
    q = max(2, len(px) // 4)
    a = sum(px[:q]) / q
    b = sum(px[-q:]) / q
    return round((b / a - 1) * 100, 3) if a else None

def _vol(rows, nowt, hours=6):
    cut = nowt.timestamp() - hours * 3600
    px = [p for t, p in rows if _ok_ts(t, cut)]
    if len(px) < 5:
        return None
    rets = [abs(px[i] / px[i - 1] - 1) for i in range(1, len(px)) if px[i - 1] > 0]
    return round(sum(rets) / len(rets) * 100, 3) if rets else None

def _label(slope):
    if slope is None:
        return ("NO DATA", "flat")
    if slope > UP:
        return ("UPTREND", "up")
    if slope < DN:
        return ("DOWNTREND", "down")
    return ("SIDEWAYS", "flat")

def _advice(regime):
    return {
        "UPTREND":   "uptrend -> bounces run; aggressive targets can pay; hard gate open",
        "DOWNTREND": "downtrend -> favor safety; hard-gated books block new entries and log the A/B",
        "SIDEWAYS":  "range -> classic mean-reversion; buy dips, take the base target",
        "NO DATA":   "not enough fresh intraday data yet - warming up",
    }.get(regime, "")

def build_regime_classifier(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    try:
        samples = json.loads((out / "price_samples.json").read_text()).get("samples", {})
    except Exception:
        samples = {}
    nowt = datetime.now(timezone.utc)
    by_book: Dict[str, Any] = {}
    for book in ("crypto", "stock", "metal", "energy"):
        rows_by_sym = {s: _intraday(r) for s, r in samples.items() if asset_class(s) == book}
        s1, s6, s24, vols, fresh = [], [], [], [], 0
        for s, r in rows_by_sym.items():
            if len(r) < 4:
                continue
            fresh += 1
            for arr, hrs in ((s1, 1), (s6, 6), (s24, 24)):
                v = _slope_window(r, nowt, hrs)
                if v is not None:
                    arr.append(v)
            v = _vol(r, nowt)
            if v is not None:
                vols.append(v)
        if not s6 and not s1:
            by_book[book] = {"regime": "NO DATA", "dir": "flat", "fresh_symbols": fresh,
                             "slope_1h_pct": None, "slope_6h_pct": None, "slope_24h_pct": None,
                             "median_slope_pct": None,
                             "why": "no fresh intraday prints yet - warming up", "advice": _advice("NO DATA")}
            continue
        m1 = round(median(s1), 3) if s1 else None
        m6 = round(median(s6), 3) if s6 else None
        m24 = round(median(s24), 3) if s24 else None
        head = m6 if m6 is not None else m1
        regime, d = _label(head)
        base = s6 or s1
        up = sum(1 for x in base if x > UP)
        dn = sum(1 for x in base if x < DN)
        n = len(base)
        # MOVERS context — the median can look flat while the top decile rips. Show both so a green day
        # never reads as "broken": headline stays median (honest breadth), but movers_24h_pct surfaces the
        # names the operator is actually eyeballing.
        import statistics as _st
        s24_sorted = sorted(s24) if s24 else []
        movers = round(s24_sorted[int(len(s24_sorted) * 0.9)], 3) if len(s24_sorted) >= 3 else None
        pct_up_24 = round(sum(1 for x in s24 if x > 0) / len(s24) * 100) if s24 else 0
        by_book[book] = {
            "regime": regime, "dir": d,
            "slope_1h_pct": m1, "slope_6h_pct": m6, "slope_24h_pct": m24,
            "movers_24h_pct": movers, "breadth_up_24h_pct": pct_up_24,
            "median_slope_pct": head,
            "breadth_up_pct": round(up / n * 100) if n else 0,
            "breadth_down_pct": round(dn / n * 100) if n else 0,
            "avg_volatility_pct": round(median(vols), 3) if vols else None,
            "fresh_symbols": fresh,
            "shift_watch": ("FAST 1h diverges from 6h - regime may be turning"
                            if (m1 is not None and m6 is not None and (m1 > UP) != (m6 > UP)) else "stable"),
            "why": "24h median %+.2f%% (top movers +%.1f%%) . %d%% of names up on the day . 6h %+.2f%% . 1h %+.2f%%" % (
                (m24 if m24 is not None else 0.0), (movers if movers is not None else 0.0), pct_up_24,
                (m6 if m6 is not None else 0.0), (m1 if m1 is not None else 0.0)) if False else "6h intraday median %+.2f%% . 1h %+.2f%% . breadth %d%% up / %d%% down" % (
                (m6 if m6 is not None else 0.0), (m1 if m1 is not None else 0.0),
                round(up / n * 100) if n else 0, round(dn / n * 100) if n else 0),
            "advice": _advice(regime),
        }
    payload = {"generated_at": _now(), "method": "intraday-only multi-timeframe (1h/6h/24h) + breadth",
               "thresholds": {"up_pct": UP, "down_pct": DN}, "by_book": by_book,
               "what": ("Live regime per book from INTRADAY prints only (daily-backfill candles excluded - the "
                        "bug that made green days read DOWNTREND). Headline = 6h trend; 1h = fast shift trigger; "
                        "breadth = %% of names trending. Every number shown so the read is auditable.")}
    try:
        write_json_atomic(out / "REGIME_CLASSIFIER.json", payload)
    except Exception:
        (out / "REGIME_CLASSIFIER.json").write_text(json.dumps(payload, indent=1))
    return payload
