"""
silmaril.execution.sector_recovery — STOCK SECTOR RECOVERY (2.5.3). Measurement.

Groups closed STOCK trades by sector to see whether mean-reversion recovery differs by
sector (e.g. tech dips revert, energy dips don't). Needs a sector map (sector_map.json,
ticker->sector) which a production run fetches from FMP. Until that cache exists this
reports "awaiting sector data" rather than guessing. Emits SECTOR_RECOVERY.json.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from ._trade_helpers import closed_trades
from .atomic_io import write_json_atomic

def _now(): return datetime.now().astimezone().isoformat()

def build_sector_recovery(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    try: sector_map = json.loads((out / "sector_map.json").read_text())
    except Exception: sector_map = {}
    if isinstance(sector_map, dict) and "map" in sector_map:
        sector_map = sector_map["map"]
    stock = [t for t in closed_trades(out) if t["book"] == "stock"]
    if not sector_map:
        payload = {"generated_at": _now(), "status": "awaiting_sector_data",
                   "stock_trades_available": len(stock),
                   "what": "Recovery by sector — needs sector_map.json (ticker->sector).",
                   "why": "Would show if stock MR works in some sectors but not others.",
                   "action": ("Run the production sector fetch (FMP) once to cache sector tags for the "
                              "stock universe; this engine then activates automatically."),
                   "note": "Engine is wired and ready; it just needs the sector cache to exist."}
        try: write_json_atomic(out / "SECTOR_RECOVERY.json", payload)
        except Exception: pass
        return payload
    by: Dict[str, list] = {}
    for t in stock:
        sec = sector_map.get(t["sym"]) or sector_map.get(t["sym"].replace("-USD", "")) or "Unknown"
        by.setdefault(sec, []).append(t["realized_pct"])
    def stats(rs):
        wins = sum(1 for r in rs if r > 0)
        return {"trades": len(rs), "win_pct": round(wins / len(rs) * 100, 1),
                "expectancy_pct": round(sum(rs) / len(rs), 2)}
    sectors = {s: stats(rs) for s, rs in by.items() if rs}
    ranked = sorted(sectors.items(), key=lambda kv: kv[1]["expectancy_pct"], reverse=True)
    payload = {"generated_at": _now(), "status": "active",
               "by_sector": dict(ranked),
               "best_sector": ranked[0][0] if ranked else None,
               "worst_sector": ranked[-1][0] if ranked else None,
               "what": "Stock mean-reversion recovery grouped by sector.",
               "why": "Reveals whether the weak stock edge is uniform or sector-specific.",
               "action": "If some sectors are positive, the stock book could whitelist those sectors.",
               "note": "Sector tags from cached sector_map.json (FMP)."}
    try: write_json_atomic(out / "SECTOR_RECOVERY.json", payload)
    except Exception: pass
    return payload
