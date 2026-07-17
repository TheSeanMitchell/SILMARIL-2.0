"""silmaril.execution.geometry — 7.0 THE GEOMETRY GATE (the law of winnable trades).

The finding that reframed the project: the median fitted strategy demanded an 87.4%
win rate JUST TO BREAK EVEN, because a hard stop floor overrode every quiet name's
measured pulse. The operator's own words: "if the math demands 87% but the name
wins 53%, don't trade it at all."

This module makes that sentence executable, for every name, every cycle:

    p_star  = (stop + cost) / (target + stop)      # win rate REQUIRED to break even
    p_floor = Wilson 95% lower bound of the name's own book record,
              pooled with its CLUSTER PRIOR (class × vol-tercile) when thin —
              so a name with n=0 inherits its behavioral family and SAYS SO.

    verdict:
      TRADEABLE                 p_floor > p_star + margin  (the door is unlocked)
      UNTRADEABLE:geometry      honest stop > ratio × target (no geometry can win)
      UNTRADEABLE:evidence      p_floor exists and sits below the bar
      STAND-DOWN                not enough evidence anywhere — observe, don't guess

Law 21 (new constitution): no floor may silently DISTORT a measured value.
Overrides must ABSTAIN, not widen. The heatshield keeps its true job — refusing
noise-stopped trades — by refusing the TRADE, never by faking the stop.

Emits GEOMETRY.json. Consumed by paper_sim (entry gate), the lab's G sleeve,
and the Master. KILL: geometry.mode:"off".
"""
from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .atomic_io import write_json_atomic


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load(out: Path, name: str, default=None):
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return default if default is not None else {}


def wilson_lo(k: int, n: int, z: float = 1.96) -> Optional[float]:
    if n <= 0:
        return None
    ph = k / n
    den = 1 + z * z / n
    return max(0.0, (ph + z * z / (2 * n)
                     - z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))) / den)


def p_star(target: float, stop: float, cost: float) -> Optional[float]:
    if target is None or stop is None or (target + stop) <= 0:
        return None
    return (stop + cost) / (target + stop)


def build_geometry(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    cat = _load(out, "PARAM_CATALOG.json")
    kb = cat.get("geometry") or {}
    ratio = float(kb.get("max_stop_ratio", 1.5))
    margin = float(kb.get("evidence_margin", 0.03))
    min_n = int(kb.get("min_evidence_n", 8))

    fp = _load(out, "FINGERPRINTS.json")
    cards = {c.get("sym"): c for c in (fp.get("cards") or [])}
    conf = (_load(out, "CONFIDENCE_CARDS.json").get("cards") or {})

    # per-name book record (all books, this epoch)
    rec: Dict[str, List[int]] = {}
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        for t in (_load(out, f"paper_book_{bk}.json").get("trades") or []):
            if t.get("side") != "SELL":
                continue
            w = 1 if float(t.get("pnl") or 0) > 0 else 0
            a = rec.setdefault(t.get("sym"), [0, 0])
            a[0] += w
            a[1] += 1

    # CLUSTER PRIORS v1: class × vol-tercile → pooled bounce_reliability as the prior
    # win propensity for a limit-at-bounce MR exit (an evidence-weighted prior, stated).
    by_cluster: Dict[str, List[float]] = {}
    vols: Dict[str, float] = {}
    for sym, c in cards.items():
        f = c.get("fp") or {}
        v = f.get("typical_dip")
        if v:
            vols[sym] = float(v)
    terc = sorted(vols.values())
    t1 = terc[len(terc) // 3] if terc else 0.004
    t2 = terc[2 * len(terc) // 3] if terc else 0.01

    def cluster_of(sym: str, klass: str) -> str:
        v = vols.get(sym)
        b = "v1" if (v or 0) <= t1 else ("v2" if (v or 0) <= t2 else "v3")
        return f"{klass}:{b}"

    for sym, c in cards.items():
        f = c.get("fp") or {}
        br = f.get("bounce_reliability")
        kl = (conf.get(sym) or {}).get("class") or ("crypto" if sym.endswith("-USD") else "stock")
        if br is not None:
            by_cluster.setdefault(cluster_of(sym, kl), []).append(float(br))
    prior = {k: (statistics.median(v), len(v)) for k, v in by_cluster.items() if v}

    rows: Dict[str, Any] = {}
    counts = {"TRADEABLE": 0, "UNTRADEABLE:geometry": 0, "UNTRADEABLE:evidence": 0, "STAND-DOWN": 0}
    for sym, c in cards.items():
        fit = c.get("fit") or {}
        f = c.get("fp") or {}
        tgt = fit.get("target")
        vol_stop = (f.get("typical_dip") or 0) * 3.0 or None   # the honest, un-floored stop
        cost = float(fit.get("cost") or 0.004)
        kl = (conf.get(sym) or {}).get("class") or ("crypto" if sym.endswith("-USD") else "stock")
        k_, n_ = rec.get(sym, [0, 0])
        own_lo = wilson_lo(k_, n_)
        cl = cluster_of(sym, kl)
        pr, pn = prior.get(cl, (None, 0))
        # shrinkage: w = n/(n+k). thin names inherit their family and SAY SO.
        if n_ >= min_n and own_lo is not None:
            p_floor, ev_src = own_lo, f"own(n={n_})"
        elif pr is not None:
            w = n_ / (n_ + 8.0)
            p_floor = (w * (own_lo or pr)) + (1 - w) * pr * 0.9   # prior haircut 10%
            ev_src = f"cluster {cl}(n={pn})·w={w:.2f}"
        else:
            p_floor, ev_src = None, "none"
        if tgt and vol_stop:
            geo_ok = vol_stop <= tgt * ratio
            stop_used = min(vol_stop, tgt * ratio)
            ps = p_star(tgt, stop_used, cost)
        else:
            geo_ok, stop_used, ps = False, None, None
        if not tgt or not vol_stop:
            verdict = "STAND-DOWN"
        elif not geo_ok and (p_floor is None or p_floor < (p_star(tgt, vol_stop, cost) or 1) + margin):
            verdict = "UNTRADEABLE:geometry"
        elif p_floor is None:
            verdict = "STAND-DOWN"
        elif p_floor < (ps or 1) + margin:
            verdict = "UNTRADEABLE:evidence"
        else:
            verdict = "TRADEABLE"
        counts[verdict] += 1
        rows[sym] = {"class": kl, "target_pct": round((tgt or 0) * 100, 3),
                     "stop_vol_pct": round((vol_stop or 0) * 100, 3),
                     "stop_used_pct": round((stop_used or 0) * 100, 3) if stop_used else None,
                     "p_star_pct": round(ps * 100, 1) if ps else None,
                     "p_floor_pct": round(p_floor * 100, 1) if p_floor is not None else None,
                     "evidence": ev_src, "cluster": cl, "verdict": verdict}
    best = sorted((r for r in rows.items() if r[1]["verdict"] == "TRADEABLE"),
                  key=lambda x: (x[1]["p_floor_pct"] or 0) - (x[1]["p_star_pct"] or 100),
                  reverse=True)[:12]
    payload = {"generated_at": _now(), "knob": {"max_stop_ratio": ratio,
               "evidence_margin": margin, "min_evidence_n": min_n},
               "counts": counts, "n": len(rows),
               "clusters": {k: {"prior_bounce_rel": round(v[0], 3), "n": v[1]}
                            for k, v in prior.items()},
               "most_winnable": [{"sym": s, **{k: r[k] for k in
                                 ("p_star_pct", "p_floor_pct", "evidence", "verdict")}}
                                 for s, r in best],
               "by_symbol": rows,
               "what": ("THE LAW OF WINNABLE TRADES: p* = (stop+cost)/(target+stop) vs the "
                        "Wilson floor of proven wins (own record ∪ cluster prior, shrunk and "
                        "stated). If the math demands more than the evidence has ever "
                        "delivered, the trade does not happen — Law 21: abstain, never distort.")}
    write_json_atomic(out / "GEOMETRY.json", payload)
    return {"summary": f"geometry: {counts['TRADEABLE']} tradeable · "
                       f"{counts['UNTRADEABLE:geometry']} geo-locked · "
                       f"{counts['UNTRADEABLE:evidence']} evidence-short · "
                       f"{counts['STAND-DOWN']} stand-down"}
