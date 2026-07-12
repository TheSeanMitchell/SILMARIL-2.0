"""mtf_regime.py — 5.1B: MULTI-TIMEFRAME regime ladder, per BOOK and per VALUABLE.

The operator's crash-day mandate, given a sensor: slopes at 15m · 30m · 1h · 2h ·
3h · 6h · 12h · 24h · 2d · 3d · 7d · 30d, per book (median of its liquid names)
and per symbol (top fingerprint-depth names). Each timeframe is a GREEN/RED vote;
confluence stacks the votes with weights that favor the actionable middle
(1h–6h) so a coin can be strong while its industry is weak — and so a fast red
streak (15m+30m+1h all red) flags a shift BEFORE the 24h line admits it.

Consumers: paper_sim (regime-flip harvest · entry throttle · symbol-override ·
conviction sizing), conductor_report_card (crash-avoidance grading), the UI
LIVE REGIME ladder. Store: MTF_REGIME.json, every cycle.

Formula (printed here so nothing is a black box):
  slope(tf) = last/first − 1 over the tf window (last real prints only)
  green(tf) = slope ≥ +0.05% for tf<2h, ≥ +0.10% otherwise (noise floor)
  red(tf)   = slope ≤ −0.05% / −0.10% (same floors)
  confluence = Σ w(tf)·sign, w = {15m:.5,30m:.75,1h:1,2h:1,3h:1,6h:1,
               12h:.75,24h:.75,2d:.5,3d:.5,7d:.25,30d:.25}  → range ≈ −8.5..+8.5
  fast_red  = 15m,30m,1h all red   ·   fast_green = 15m,30m,1h all green
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .atomic_io import write_json_atomic
from .paper_sim import load_all_samples, asset_class

STORE = "MTF_REGIME.json"
TFS_MIN = [15, 30, 60, 120, 180, 360, 720, 1440, 2880, 4320, 10080, 43200]
TF_LABEL = {15: "15m", 30: "30m", 60: "1h", 120: "2h", 180: "3h", 360: "6h",
            720: "12h", 1440: "24h", 2880: "2d", 4320: "3d", 10080: "7d", 43200: "30d"}
W = {15: .5, 30: .75, 60: 1, 120: 1, 180: 1, 360: 1, 720: .75, 1440: .75,
     2880: .5, 4320: .5, 10080: .25, 43200: .25}
SYM_CAPS = {"crypto": 40, "stock": 30, "metal": 12, "energy": 12}


def _now():
    return datetime.now(timezone.utc)


def _parse(t) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _slopes(rows: List) -> Dict[int, Optional[float]]:
    """rows = [(iso, price)]; intraday prints only (backfill T00:00:00 excluded)."""
    now = _now()
    pts: List[Tuple[float, float]] = []
    for t, p in rows[-3200:]:
        if not p or "T00:00:00" in str(t):
            continue
        dt = _parse(t)
        if dt is None:
            continue
        pts.append(((now - dt).total_seconds() / 60.0, float(p)))
    if len(pts) < 3:
        return {tf: None for tf in TFS_MIN}
    pts.sort(key=lambda x: x[0])            # age ascending; pts[0] is freshest
    last = pts[0][1]
    out: Dict[int, Optional[float]] = {}
    for tf in TFS_MIN:
        # SPARSE-SAMPLING SAFE (selftest T11 caught the flaw): with ~10-min pulse
        # spacing a raw "oldest point inside the window" rule leaves short TFs with
        # a single point → slope 0 → fast_red could NEVER trip. Anchor instead on
        # the point whose age is CLOSEST to tf inside a 0.5×–1.6× band, so a 15m
        # slope is measured against a genuinely ~15-minute-old print.
        # pts[1:]: the baseline must be strictly OLDER than the freshest print,
        # or a lone in-band fresh point measures itself (slope 0 forever).
        band = [(age, price) for age, price in pts[1:] if tf * 0.5 <= age <= tf * 1.6]
        if band:
            first = min(band, key=lambda ap: abs(ap[0] - tf))[1]
            out[tf] = last / first - 1.0
        else:
            out[tf] = None
    return out


def _vote(slope: Optional[float], tf: int) -> int:
    if slope is None:
        return 0
    floor = 0.0005 if tf < 120 else 0.001
    return 1 if slope >= floor else (-1 if slope <= -floor else 0)


def _row(slopes: Dict[int, Optional[float]]) -> Dict[str, Any]:
    votes = {tf: _vote(s, tf) for tf, s in slopes.items()}
    conf = round(sum(W[tf] * v for tf, v in votes.items()), 2)
    greens = sum(1 for v in votes.values() if v > 0)
    reds = sum(1 for v in votes.values() if v < 0)
    return {
        "tf": {TF_LABEL[tf]: (None if slopes[tf] is None else round(slopes[tf] * 100, 3))
               for tf in TFS_MIN},
        "votes": {TF_LABEL[tf]: votes[tf] for tf in TFS_MIN},
        "greens": greens, "reds": reds, "confluence": conf,
        "fast_red": all(votes[tf] < 0 for tf in (15, 30, 60)),
        "fast_green": all(votes[tf] > 0 for tf in (15, 30, 60)),
    }


def build_mtf_regime(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    samples = load_all_samples(out)
    by_cls: Dict[str, List[Tuple[str, list]]] = {}
    for sym, rows in samples.items():
        cls = asset_class(sym)
        if cls == "crypto" and "-" not in sym:
            continue          # canonical-crypto law only; GLD/XAU/WTI/AAPL are dash-less and MUST pass
        by_cls.setdefault(cls, []).append((sym, rows))

    books: Dict[str, Any] = {}
    symbols: Dict[str, Any] = {}
    for cls, lst in by_cls.items():
        lst.sort(key=lambda x: len(x[1]), reverse=True)
        top = lst[: SYM_CAPS.get(cls, 12)]
        sym_rows = []
        for sym, rows in top:
            r = _row(_slopes(rows))
            r["class"] = cls
            symbols[sym] = r
            sym_rows.append(r)
        if sym_rows:
            med: Dict[int, Optional[float]] = {}
            for tf in TFS_MIN:
                vals = sorted(v["tf"][TF_LABEL[tf]] for v in sym_rows
                              if v["tf"][TF_LABEL[tf]] is not None)
                med[tf] = (vals[len(vals) // 2] / 100.0) if vals else None
            bk = _row(med)
            bk["n_symbols"] = len(sym_rows)
            bk["leaders"] = sorted(((s, symbols[s]["confluence"]) for s, _ in top),
                                   key=lambda x: -x[1])[:5]
            books[cls] = bk

    payload = {
        "generated_at": _now().isoformat(),
        "what": ("multi-timeframe regime ladder 15m→30d, per book (median of its deepest names) "
                 "and per valuable. GREEN/RED votes stack into a weighted confluence score; "
                 "fast_red (15m·30m·1h all red) is the early-shift tripwire the July-11 crash asked for."),
        "formula": {"weights": {TF_LABEL[k]: v for k, v in W.items()},
                    "noise_floor_pct": {"<2h": 0.05, ">=2h": 0.10},
                    "confluence_range": "≈ −8.5 (all red) .. +8.5 (all green)"},
        "books": books,
        "symbols": symbols,
    }
    write_json_atomic(out / STORE, payload)
    fr = [b for b, v in books.items() if v.get("fast_red")]
    return {"summary": f"MTF ladder: {len(books)} books · {len(symbols)} valuables · "
                       f"fast_red: {', '.join(fr) or 'none'}"}
