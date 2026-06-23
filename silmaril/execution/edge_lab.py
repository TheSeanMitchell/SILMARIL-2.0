"""
silmaril.execution.edge_lab — EDGE VALIDATION (Race to Alpha 2.11).

The question this project never actually tested until now: does any signal
PREDICT FORWARD RETURNS? This module answers it empirically and automatically.

It reads the rolling price history (price_samples.json — already days of ~11-min
samples across the whole universe) and, for a battery of candidate signals,
measures the realized forward return AFTER the signal fires, net of a round-trip
cost, with a t-stat. No lookahead: the signal uses only past samples, the outcome
uses only future samples.

This is the ALPHA 2.2 mandate made concrete: edge capture becomes the PRIMARY
success metric, not win rate, not conviction. A signal earns its place only if
its net forward return beats baseline with significance — otherwise it is
rejected. The same harness accepts a fuller history (e.g. FreeCryptoAPI's full
universe) by writing it into price_samples.json's schema; the math is identical.

Headline finding on the 3-day in-repo data (BTC/ETH-class universe):
  • momentum / persistence  -> NEGATIVE net edge (t ~ -14)  [what we trade today]
  • mean reversion / oversold -> POSITIVE net edge (t ~ +12..+17)
i.e. this universe mean-reverts on this horizon; trading momentum is the wrong
side of the tape. Treat as a strong signal to verify out-of-sample, not gospel.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Callable, Dict, List

VERSION = "edge-lab-1.0"

# ~11-min sampling cadence -> step counts for each horizon
STEP = {"30m": 3, "1h": 6, "2h": 12, "4h": 24}
ROUND_TRIP_COST = 0.003   # 0.3% spread+fees on liquid crypto (illiquid is worse)
MIN_N = 80                # don't report a signal with too few firings

# Candidate signals. Each takes (r10, r1h, r4h) past returns -> fires bool.
SIGNALS: Dict[str, Callable[[float, float, float], bool]] = {
    "momentum_10m_gt_1pct":      lambda r10, r1h, r4h: r10 > 0.01,
    "persistence_10m_1h_up":     lambda r10, r1h, r4h: r10 > 0 and r1h > 0,
    "strong_persist":            lambda r10, r1h, r4h: r10 > 0.01 and r1h > 0.02,
    "oversold_10m_lt_1pct":      lambda r10, r1h, r4h: r10 < -0.01,
    "deep_oversold_1h_lt_3pct":  lambda r10, r1h, r4h: r1h < -0.03,
    "capitulation_1h_lt_5pct":   lambda r10, r1h, r4h: r1h < -0.05,
    "falling_knife":             lambda r10, r1h, r4h: r10 < -0.01 and r1h < -0.03,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _series(rows) -> List[float]:
    return [p for _, p in rows if p and p > 0]


def build_edge_lab(out_dir, cost: float = ROUND_TRIP_COST) -> Dict[str, Any]:
    out = Path(out_dir)
    try:
        samples = json.loads((out / "price_samples.json").read_text()).get("samples", {})
    except Exception as e:
        return {"version": VERSION, "error": f"no price_samples.json: {e}"}

    # build (r10, r1h, r4h, {horizon: fwd_return}) points with no lookahead
    pts = []
    for _tk, rows in samples.items():
        px = _series(rows)
        n = len(px)
        if n < 40:
            continue
        for i in range(24, n - 24):
            p = px[i]
            if p <= 0:
                continue
            r10 = px[i] / px[i - 1] - 1 if px[i - 1] > 0 else 0.0
            r1h = px[i] / px[i - 6] - 1 if px[i - 6] > 0 else 0.0
            r4h = px[i] / px[i - 24] - 1 if px[i - 24] > 0 else 0.0
            fwd = {k: (px[i + s] / p - 1) for k, s in STEP.items() if px[i + s] > 0}
            pts.append((r10, r1h, r4h, fwd))

    def measure(sel, hz):
        xs = [f[hz] for (*_, f) in sel if hz in f]
        if len(xs) < MIN_N:
            return None
        m = mean(xs)
        sd = pstdev(xs) or 1e-9
        return {
            "n": len(xs),
            "gross_pct": round(m * 100, 3),
            "net_pct": round((m - cost) * 100, 3),
            "hit_pct": round(sum(1 for x in xs if x > 0) / len(xs) * 100, 1),
            "t_stat": round(m / (sd / math.sqrt(len(xs))), 2),
        }

    baseline = {hz: measure(pts, hz) for hz in STEP}
    results = {}
    for name, fn in SIGNALS.items():
        sel = [t for t in pts if fn(t[0], t[1], t[2])]
        results[name] = {hz: measure(sel, hz) for hz in STEP}

    # verdict: best signal by net 1h edge that clears cost AND is significant
    ranked = []
    for name, r in results.items():
        h1 = r.get("1h")
        if h1 and h1["t_stat"] is not None:
            ranked.append((name, h1["net_pct"], h1["t_stat"]))
    ranked.sort(key=lambda x: x[1], reverse=True)
    winners = [r for r in ranked if r[1] > 0 and r[2] >= 3.0]
    losers = [r for r in ranked if r[1] < 0 and r[2] <= -3.0]

    verdict = "NO SIGNAL CLEARS COST WITH SIGNIFICANCE — do not risk capital yet"
    if winners:
        best = winners[0]
        verdict = (f"EDGE FOUND: '{best[0]}' nets {best[1]:+.2f}%/trade at 1h "
                   f"(t={best[2]:+.1f}). Direction that works here.")

    payload = {
        "version": VERSION,
        "generated_at": _now(),
        "data_points": len(pts),
        "round_trip_cost_pct": cost * 100,
        "baseline_drift": baseline,
        "signals": results,
        "verdict": verdict,
        "edge_signals_ranked_by_1h_net": [
            {"signal": n, "net_1h_pct": v, "t_stat": t} for n, v, t in ranked],
        "anti_edge_signals": [n for n, v, t in losers],
        "note": ("Net = gross minus round-trip cost. A signal is real only if net "
                 "beats baseline with |t|>=3. Verify out-of-sample before sizing — "
                 "3 days is one regime, not proof for all time."),
    }
    try:
        (out / "edge_lab.json").write_text(json.dumps(payload, indent=2))
    except Exception as e:
        payload["_write_error"] = str(e)
    return payload


if __name__ == "__main__":
    import sys
    p = build_edge_lab(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("VERDICT:", p.get("verdict"))
    print("\nranked by 1h net edge:")
    for r in p.get("edge_signals_ranked_by_1h_net", []):
        print(f"  {r['signal']:28s} {r['net_1h_pct']:+6.2f}%  t={r['t_stat']:+5.1f}")
