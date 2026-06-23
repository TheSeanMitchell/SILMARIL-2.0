"""
silmaril.execution.edge_capture_breakdown — EDGE CAPTURE BREAKDOWN (2.15 P6).

Edge Capture exists; this asks WHERE capture happens. Breaks realized capture by
strategy (which book), by asset class, and by lifecycle state at entry — so you
can see the highest-ROI sources instead of one blended number.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from .paper_sim import _is_crypto

def _now(): return datetime.now(timezone.utc).isoformat()

def build_edge_capture_breakdown(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    by_strategy: Dict[str, Dict[str, float]] = {}
    by_asset: Dict[str, Dict[str, float]] = {"crypto": {"realized": 0.0, "trades": 0},
                                             "stock": {"realized": 0.0, "trades": 0}}
    for bp in out.glob("paper_book_*.json"):
        strat = bp.stem.replace("paper_book_", "")
        try: d = json.loads(bp.read_text())
        except Exception: continue
        s = by_strategy.setdefault(strat, {"realized": 0.0, "trades": 0, "wins": 0})
        for tr in d.get("trades", []):
            if tr.get("side") == "SELL" and tr.get("pnl") is not None:
                pnl = tr["pnl"]; sym = tr.get("sym", "")
                s["realized"] += pnl; s["trades"] += 1; s["wins"] += 1 if pnl > 0 else 0
                ac = "crypto" if _is_crypto(sym) else "stock"
                by_asset[ac]["realized"] += pnl; by_asset[ac]["trades"] += 1
    for s in by_strategy.values():
        s["realized"] = round(s["realized"], 2)
        s["win_pct"] = round(s["wins"] / s["trades"] * 100, 1) if s["trades"] else None
    for a in by_asset.values(): a["realized"] = round(a["realized"], 2)
    ranked = sorted(by_strategy.items(), key=lambda kv: kv[1]["realized"], reverse=True)
    payload = {"generated_at": _now(),
               "by_strategy": dict(ranked),
               "by_asset_class": by_asset,
               "best_source": ranked[0][0] if ranked else None,
               "note": "Realized P&L attributed by strategy book and asset class. Where capture actually happens. (Agent/sector/authority/regime breakdowns activate as those tags reach the trade records.)"}
    try: (out / "edge_capture_breakdown.json").write_text(json.dumps(payload, indent=2))
    except Exception: pass
    return payload

if __name__ == "__main__":
    import sys; print(json.dumps(build_edge_capture_breakdown(sys.argv[1] if len(sys.argv) > 1 else "docs/data"))[:240])
