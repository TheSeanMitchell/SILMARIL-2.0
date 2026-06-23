"""
silmaril.execution.edge_capture_engine — THE PRIMARY KPI (Alpha 2.14).

Per the directive: nothing matters more than Edge Capture. Not win rate, not
Sharpe, not conviction, not agent score, not lifecycle. For every watched ticker
this answers the only question that counts:

    move_available   — the best long move the ticker actually offered (a perfect
                       buy-low-sell-high over the window)
    move_captured    — what our strategies actually realized on it
    capture_percent  — captured / available

It runs over the FRESH universe (ghosts excluded), reads what the paper books
actually captured, and produces:
  • a portfolio capture % (the headline KPI),
  • per-ticker available-vs-captured,
  • the biggest MISSES (big available move, ~0 captured) — the training fuel.

This is instrumentation, not a strategy. It does not trade. It tells you, every
cycle, what fraction of the edge that existed you actually took — so progress is
measured against reality instead of belief.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .paper_sim import load_all_samples, is_tradeable, _is_crypto

LOOKBACK = 130            # ~1 day of ~11-min samples


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _available_move(px: List[float]) -> float:
    """Best buy-low-then-sell-high move over the window (max forward gain from any
    running trough). This is what a perfect long could have captured."""
    w = px[-LOOKBACK:]
    if len(w) < 5:
        return 0.0
    best = 0.0
    trough = w[0]
    for p in w:
        if p < trough:
            trough = p
        if trough > 0:
            best = max(best, p / trough - 1)
    return best


def _captured_by_ticker(out: Path) -> Dict[str, float]:
    """Sum realized return % per ticker across all paper books (what we took)."""
    cap: Dict[str, float] = {}
    for bp in out.glob("paper_book_*.json"):
        try:
            d = json.loads(bp.read_text())
        except Exception:
            continue
        for t in d.get("trades", []):
            if t.get("side") == "SELL" and t.get("pnl") is not None:
                sym = t.get("sym", "")
                # express pnl as a rough % of a 10% book slice ($1000 base)
                cap[sym] = cap.get(sym, 0.0) + (t["pnl"] / 1000.0)
    return cap


def build_edge_capture(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    samples = load_all_samples(out)
    captured = _captured_by_ticker(out)

    rows = []
    tot_avail, tot_capt = 0.0, 0.0
    for tk, raw in samples.items():
        px = [p for _, p in raw if p and p > 0]
        if len(px) < 20 or not is_tradeable(px):
            continue
        avail = _available_move(px)
        if avail < 0.02:                       # ignore names that never moved
            continue
        capt = max(0.0, captured.get(tk, 0.0))
        cap_pct = round(min(capt / avail, 1.0) * 100, 1) if avail > 0 else 0.0
        rows.append({"ticker": tk, "asset": "crypto" if _is_crypto(tk) else "stock",
                     "available_move_pct": round(avail * 100, 1),
                     "captured_move_pct": round(capt * 100, 2),
                     "capture_pct": cap_pct, "traded": tk in captured})
        tot_avail += avail
        tot_capt += capt

    rows.sort(key=lambda r: r["available_move_pct"], reverse=True)
    misses = [r for r in rows if not r["traded"] or r["capture_pct"] < 5][:25]
    traded = [r for r in rows if r["traded"]]

    portfolio_capture = round(tot_capt / tot_avail * 100, 2) if tot_avail > 0 else 0.0
    payload = {
        "generated_at": _now(),
        "PRIMARY_KPI_portfolio_capture_pct": portfolio_capture,
        "total_available_move_pct": round(tot_avail * 100, 0),
        "total_captured_move_pct": round(tot_capt * 100, 1),
        "names_with_real_moves": len(rows),
        "names_traded": len(traded),
        "biggest_misses": misses,
        "top_available_moves": rows[:25],
        "headline": (f"Captured {portfolio_capture}% of the available edge across "
                     f"{len(rows)} moving names ({len(traded)} traded)"),
        "note": ("Edge Capture = what we took / what was there to take. The single "
                 "KPI. Misses (big move, ~0 capture) are the training fuel. "
                 "Captured % is approximate until per-name sizing is fully booked."),
    }
    try:
        (out / "edge_capture_engine.json").write_text(json.dumps(payload, indent=2))
    except Exception:
        pass
    return payload


if __name__ == "__main__":
    import sys
    p = build_edge_capture(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("HEADLINE:", p["headline"])
    print(f"\nPRIMARY KPI — portfolio edge capture: {p['PRIMARY_KPI_portfolio_capture_pct']}%")
    print(f"\nBiggest misses (move available, not captured):")
    for r in p["biggest_misses"][:12]:
        print(f"  {r['ticker']:14s} available {r['available_move_pct']:>6.1f}%  captured {r['capture_pct']:>5.1f}%  {'(not traded)' if not r['traded'] else ''}")
