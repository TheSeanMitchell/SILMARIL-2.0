"""
silmaril.execution.edge_capture — Measurement Spine #2.

THE NORTH-STAR NUMBER. For every name, compare:
    AVAILABLE MOVE  — how much the name moved (from the sample/price history)
    CAPTURED MOVE   — how much of it we actually banked (from trade_forensics)
    EDGE CAPTURE %  — captured ÷ available

The reviewer's exact table:
    INTC  +10.5% available  +0% captured   0% edge
    XRP   +4.2%  available  +3.6% captured  86% edge

This turns "are we any good?" from a theory into a number. A name we held
through a +10% run but only banked +2% on = 20% edge capture = we left 80% on
the table. A name we never touched that ran +10% = 0% capture = a miss (also
fed to the Missed Opportunity Journal).

Writes docs/data/edge_capture.json.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

VERSION = "edge-capture-1.0"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def _dump(path: Path, obj):
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, separators=(",", ":"), allow_nan=False)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _norm(t: str) -> str:
    return str(t).upper().replace("/", "").replace("-", "")


def _f(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


def _available_move_pct(samples_rows, window_hours=24):
    """Available move = the best peak-to-current run the name offered over the
    window. We use (max price in window - min price BEFORE that max) / min, i.e.
    the largest favorable swing a trader could have caught. Falls back to
    first→last if the structure is flat."""
    if not samples_rows or len(samples_rows) < 2:
        return None
    prices = [(_f(r[1])) for r in samples_rows if _f(r[1]) > 0]
    if len(prices) < 2:
        return None
    # largest up-move: track running min, find max gain above it
    run_min = prices[0]
    best = 0.0
    for p in prices:
        if p < run_min:
            run_min = p
        if run_min > 0:
            gain = (p - run_min) / run_min * 100.0
            if gain > best:
                best = gain
    return round(best, 3)


def build_edge_capture(out_dir, top_n_chain: int = 60) -> Dict[str, Any]:
    """Compute available vs captured move and edge-capture % per name."""
    out = Path(out_dir)
    samples = (_load(out / "price_samples.json", {}) or {}).get("samples") or {}
    forensics = _load(out / "trade_forensics.json", {}) or {}
    chain = (_load(out / "momentum_chain.json", {}) or {}).get("chains") or {}

    # BROKER REACHABILITY (Dash 2.1, operator request). Names on the learned/
    # seeded Alpaca 422 blocklist are UNREACHABLE no matter how good our logic
    # is. So edge capture is reported two ways: across the FULL universe
    # (broker-capped — what the account actually achieves) and across only the
    # TRADEABLE universe (the true measure of our entry/exit logic — the number
    # to drive toward ~100% before migration).
    try:
        from .tradability import load_blocklist
        _untradeable = load_blocklist(out)
    except Exception:
        _untradeable = set()

    # captured: sum realized + unrealized % we got per symbol, weighted by the
    # trades. We use realized_pct from closed trades, plus open unrealized_pct.
    captured = {}        # norm symbol -> {"captured_pct": x, "realized_usd": y}
    for acct in (forensics.get("accounts") or {}).values():
        for c in acct.get("closed_trades", []):
            s = _norm(c["symbol"])
            d = captured.setdefault(s, {"captured_pct": 0.0, "realized_usd": 0.0,
                                        "trades": 0, "open_pct": 0.0})
            d["captured_pct"] += _f(c.get("realized_pct"))
            d["realized_usd"] += _f(c.get("realized_usd"))
            d["trades"] += 1
        for o in acct.get("open_positions", []):
            s = _norm(o["symbol"])
            d = captured.setdefault(s, {"captured_pct": 0.0, "realized_usd": 0.0,
                                        "trades": 0, "open_pct": 0.0})
            d["open_pct"] += _f(o.get("unrealized_pct"))

    rows = []
    # universe to score: everything with samples (so we see misses too)
    for tk, srows in samples.items():
        s = _norm(tk)
        avail = _available_move_pct(srows)
        if avail is None:
            continue
        cap = captured.get(s)
        held = cap is not None
        captured_pct = (cap["captured_pct"] + cap["open_pct"]) if cap else 0.0
        edge = None
        if avail > 0.5:   # only meaningful when there was a real move to catch
            edge = round(max(0.0, captured_pct) / avail * 100.0, 1)
        rows.append({
            "ticker": tk,
            "available_pct": avail,
            "captured_pct": round(captured_pct, 3),
            "edge_capture_pct": edge,
            "held": held,
            "realized_usd": round(cap["realized_usd"], 2) if cap else 0.0,
            "crypto": s.endswith("USD") and len(s) > 4,
            "tradeable": s not in _untradeable,
        })

    # the headline table: biggest available moves and how much we caught
    rows.sort(key=lambda r: r["available_pct"], reverse=True)
    top_movers = rows[:30]

    # missed runners: big available move, NOT held (edge 0)
    missed = [r for r in rows if not r["held"] and r["available_pct"] >= 3.0][:25]

    # aggregate edge capture across names we actually held with a real move
    held_with_move = [r for r in rows if r["held"] and r["available_pct"] >= 1.0
                      and r["edge_capture_pct"] is not None]
    avg_edge = (round(sum(r["edge_capture_pct"] for r in held_with_move)
                      / len(held_with_move), 1) if held_with_move else None)

    # CEILING-AWARE EDGE (operator request). Two honest numbers:
    #  • alpaca_reachable_pct — of the total big-mover opportunity, how much is
    #    even REACHABLE on Alpaca (the rest is locked behind migration).
    #  • reachable_edge_capture_pct — of that REACHABLE opportunity, what % did
    #    we actually bank. This counts tradeable names we MISSED as 0, so it is
    #    the true number to drive toward 100% before migration (the held-only
    #    avg hides the tradeable runners we never caught).
    _movers = [r for r in rows if r["available_pct"] >= 3.0]
    _tradeable_movers = [r for r in _movers if r.get("tradeable")]
    _avail_all = sum(r["available_pct"] for r in _movers)
    _avail_reach = sum(r["available_pct"] for r in _tradeable_movers)
    _cap_reach = sum(max(0.0, r["captured_pct"]) for r in _tradeable_movers)
    alpaca_reachable_pct = (round(_avail_reach / _avail_all * 100.0, 1)
                            if _avail_all > 0 else None)
    reachable_edge = (round(_cap_reach / _avail_reach * 100.0, 1)
                      if _avail_reach > 0 else None)
    blocked_by_broker = sum(1 for r in _movers if not r.get("tradeable"))

    payload = {
        "version": VERSION,
        "generated_at": _now(),
        "summary": {
            "avg_edge_capture_pct": avg_edge,
            "reachable_edge_capture_pct": reachable_edge,
            "alpaca_reachable_pct": alpaca_reachable_pct,
            "names_blocked_by_broker": blocked_by_broker,
            "names_held_with_move": len(held_with_move),
            "missed_runners": len(missed),
            "total_available_universe": len(rows),
        },
        "top_movers": top_movers,
        "missed_runners": missed,
        "note": ("Available = the largest favorable swing the name offered over "
                 "the sample window. Captured = what we actually banked "
                 "(realized + open). Edge = captured/available. 0% on a big "
                 "available move = we missed it or exited at a loss. This is the "
                 "single number to drive up over time."),
    }
    _dump(out / "edge_capture.json", payload)
    return payload


if __name__ == "__main__":  # pragma: no cover
    import sys
    p = build_edge_capture(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/data"))
    print(json.dumps(p["summary"], indent=2))
