"""
silmaril.execution.master_log — MASTER TRADE LOG (2.5.5).

One flat, chronological record of EVERY trade across all four books, newest first, so the operator
can page back through the entire history (100 at a time in the UI) and see each trade's win/loss and
exact timestamp. Pure read of the book files — OBSERVATIONAL, no logic touched. Emits MASTER_LOG.json.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

def _now(): return datetime.now(timezone.utc).isoformat()

def build_master_log(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    rows: List[dict] = []
    for bk in ("crypto", "stock", "metal", "energy"):
        p = out / f"paper_book_{bk}.json"
        if not p.exists():
            continue
        try:
            trades = json.loads(p.read_text()).get("trades", [])
        except Exception:
            continue
        for t in trades:
            ts = t.get("t") or ""
            pnl = t.get("pnl")
            rows.append({
                "book": bk,
                "ts": ts,
                "date": ts[:10],
                "time": (ts[11:19] if len(ts) >= 19 else ""),
                "side": t.get("side"),
                "sym": t.get("sym"),
                "qty": t.get("qty"),
                "price": t.get("price"),
                "pnl": pnl,                              # None for BUYs
                "result": ("win" if (pnl is not None and pnl > 0.005)
                           else "loss" if (pnl is not None and pnl < -0.005)
                           else "flat" if pnl is not None else None),
            })
    # newest first
    rows.sort(key=lambda r: r["ts"], reverse=True)
    sells = [r for r in rows if r["side"] == "SELL" and r["pnl"] is not None]
    wins = [r for r in sells if r["result"] == "win"]
    losses = [r for r in sells if r["result"] == "loss"]
    payload = {
        "generated_at": _now(),
        "status_label": "OBSERVATIONAL — complete trade history; changes nothing.",
        "total_trades": len(rows),
        "total_round_trips": len(sells),
        "lifetime_wins": len(wins),
        "lifetime_losses": len(losses),
        "lifetime_win_rate_pct": round(100 * len(wins) / len(sells), 1) if sells else None,
        "page_size": 100,
        "trades": rows,                                 # full history, newest first
        "what": "Every trade ever made, across all four books, newest first. Page back through all of it.",
    }
    try:
        from .atomic_io import write_json_atomic
        write_json_atomic(out / "MASTER_LOG.json", payload)
    except Exception:
        (out / "MASTER_LOG.json").write_text(json.dumps(payload, indent=2))
    return payload

if __name__ == "__main__":
    import sys
    d = build_master_log(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(f"total_trades={d['total_trades']} round_trips={d['total_round_trips']} win_rate={d['lifetime_win_rate_pct']}%")
