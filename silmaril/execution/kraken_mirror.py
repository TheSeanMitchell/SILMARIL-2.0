"""
silmaril.execution.kraken_mirror — KRAKEN MIRROR (2.5.5).

The operator's vision: run our internal crypto orders against a live venue (Kraken) and see whether
our paper results survive real-market friction. This is the honest, account-free, synthetic-free
version of that idea.

It takes today's REAL internal round-trips (from paper_book_crypto.json) and re-prices each one using
the REAL live Kraken bid/ask spread captured in KRAKEN_SPREAD.json. On a live venue a marketable
round-trip pays the spread: you buy near the ask and sell near the bid, so the round-trip gives back
≈ (spread fraction) × notional versus our frictionless internal mid-fill. The mirror subtracts that
real spread from each internal trade's P&L and reports what the SAME trades would have netted on
Kraken — plus a survival %.

This is the measured Reality Audit: not a fee MODEL, but the actual spread Kraken was quoting. It is
OBSERVATIONAL — it changes no trading logic and submits no orders. Symbols Kraken wasn't quoting fall
back to the median quoted spread (clearly flagged). Emits KRAKEN_MIRROR.json.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

def _now(): return datetime.now(timezone.utc).isoformat()

def build_kraken_mirror(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    # real Kraken spreads
    spreads: Dict[str, float] = {}
    median_bps = None
    try:
        k = json.loads((out / "KRAKEN_SPREAD.json").read_text())
        median_bps = k.get("median_spread_bps")
        for sym, r in (k.get("by_symbol") or {}).items():
            if r.get("spread_bps") is not None:
                spreads[sym] = float(r["spread_bps"])
    except Exception:
        pass

    if not spreads:
        payload = {"generated_at": _now(), "status_label": "OBSERVATIONAL",
                   "available": False,
                   "note": ("Waiting for live Kraken quotes — KRAKEN_SPREAD.json not populated yet. The "
                            "Kraken pull runs on the hourly cycle; once it has quoted symbols, this mirror "
                            "re-prices our trades against real spreads.")}
        try:
            from .atomic_io import write_json_atomic
            write_json_atomic(out / "KRAKEN_MIRROR.json", payload)
        except Exception:
            (out / "KRAKEN_MIRROR.json").write_text(json.dumps(payload, indent=2))
        return payload

    # today's real round-trips
    day = datetime.now(timezone.utc).date().isoformat()
    try:
        trades = json.loads((out / "paper_book_crypto.json").read_text()).get("trades", [])
    except Exception:
        trades = []
    sells = [t for t in trades if t.get("side") == "SELL" and t.get("t", "")[:10] == day
             and abs((t.get("qty") or 0) * (t.get("price") or 0)) >= 1.0]   # ignore dust

    med = float(median_bps) if median_bps else (sum(spreads.values()) / len(spreads))
    rows: List[dict] = []
    internal_net = 0.0
    kraken_net = 0.0
    friction_total = 0.0
    proxy_count = 0
    for t in sells:
        sym = t.get("sym")
        notional = abs((t.get("qty") or 0) * (t.get("price") or 0))
        ipnl = float(t.get("pnl") or 0)
        bps = spreads.get(sym)
        is_proxy = bps is None
        if is_proxy:
            bps = med
            proxy_count += 1
        friction = notional * (bps / 10000.0)          # cost of crossing the real spread once (round-trip)
        kpnl = ipnl - friction
        internal_net += ipnl
        kraken_net += kpnl
        friction_total += friction
        rows.append({"sym": sym, "notional": round(notional, 2), "internal_pnl": round(ipnl, 2),
                     "kraken_spread_bps": round(bps, 2), "spread_cost": round(friction, 2),
                     "kraken_pnl": round(kpnl, 2), "spread_is_proxy": is_proxy})

    survival = (kraken_net / internal_net * 100) if internal_net else None
    payload = {
        "generated_at": _now(),
        "status_label": "OBSERVATIONAL — re-prices our real trades on live Kraken spread; no orders sent.",
        "available": True,
        "day": day,
        "kraken_symbols_quoted": len(spreads),
        "kraken_median_spread_bps": round(med, 2),
        "round_trips_mirrored": len(rows),
        "proxied_symbols": proxy_count,
        "internal_net_today": round(internal_net, 2),
        "kraken_spread_cost_today": round(friction_total, 2),
        "kraken_net_today": round(kraken_net, 2),
        "survival_pct": round(survival, 1) if survival is not None else None,
        "by_trade": sorted(rows, key=lambda r: r["kraken_pnl"]),
        "what": "Our same internal round-trips, charged the REAL Kraken bid/ask spread they'd cross live.",
        "why": "Answers 'do our results survive a live venue?' with measured spread, not a model.",
        "honest_note": ("Spread is the dominant live cost here, but not the only one — real fills can also "
                        "see slippage on size and partial fills in thin books; this mirror captures the "
                        "spread component, which is the biggest and the one we can now measure. Proxied "
                        "symbols (not quoted by Kraken this snapshot) use the median spread. Dust trades "
                        "excluded. Going forward, a live order would also need a Kraken futures-demo "
                        "account + keys; this gets the validation without that risk."),
    }
    try:
        from .atomic_io import write_json_atomic
        write_json_atomic(out / "KRAKEN_MIRROR.json", payload)
    except Exception:
        (out / "KRAKEN_MIRROR.json").write_text(json.dumps(payload, indent=2))
    return payload

if __name__ == "__main__":
    import sys
    print(json.dumps(build_kraken_mirror(sys.argv[1] if len(sys.argv) > 1 else "docs/data"), indent=2)[:1500])
