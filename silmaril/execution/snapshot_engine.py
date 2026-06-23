"""
silmaril.execution.snapshot_engine — IMMUTABLE SNAPSHOT ENGINE (Alpha 2.17 S4).

Functionality + ergonomic prep, NOT logic. Every cycle it records a compact row of
the platform's state, and once per day it writes an immutable full baseline. This
costs nothing now and becomes priceless later: it is the trend trail the validation
mission needs (champion survivability and equity over time) and the history the UI
round will visualize. Touches no trading logic.

Repo-health design (deliberate): instead of thousands of per-cycle directories,
  • snapshot_history.jsonl   one compact line per cycle, capped (rolling weeks)
  • snapshots/<date>.json    one immutable full baseline per day (write-once)
"""
from __future__ import annotations
import json, os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

HISTORY_CAP = 5000  # ~weeks of 15-min cycles; keeps the file small and git-friendly

try:
    from .atomic_io import write_json_atomic
except Exception:
    def write_json_atomic(path, obj, indent=2):
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, indent=indent)); os.replace(tmp, p); return True

def _now(): return datetime.now().astimezone()
def _load(out, n):
    try: return json.loads((out / n).read_text())
    except Exception: return {}

def _compact_state(out: Path) -> Dict[str, Any]:
    cv = _load(out, "champion_validation.json")
    gov = _load(out, "CHAMPION_GOVERNANCE.json")
    live = _load(out, "paper_sim_live.json")
    ec = _load(out, "edge_capture_engine.json")
    champ = cv.get("declared_champion")
    row = next((r for r in cv.get("strategies", []) if r["strategy"] == champ), {})
    sv = row.get("survivability", {})
    cb, sb = live.get("crypto", {}), live.get("stock", {})
    return {
        "ts": _now().isoformat(),
        "champion": champ,
        "survivability": sv.get("score"),
        "trade_count": row.get("n"),
        "win_pct": row.get("win_pct"),
        "champion_total_return_pct": row.get("total_return_pct"),
        "governance_aligned": gov.get("aligned"),
        "crypto_equity": cb.get("equity"),
        "crypto_realized_pnl": cb.get("realized_pnl"),
        "crypto_open_positions": cb.get("open_positions"),
        "stock_equity": sb.get("equity"),
        "stock_open_positions": sb.get("open_positions"),
        "combined_equity": live.get("combined_equity"),
        "edge_capture_pct": ec.get("PRIMARY_KPI_portfolio_capture_pct"),
        "arena_top": [r["strategy"] for r in cv.get("strategies", [])[:3]],
    }

def take_snapshot(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    snap = _compact_state(out)

    # 1) append a compact row to the rolling history (capped)
    hist_path = out / "snapshot_history.jsonl"
    try:
        lines = hist_path.read_text().splitlines() if hist_path.exists() else []
    except Exception:
        lines = []
    lines.append(json.dumps(snap, separators=(",", ":")))
    lines = lines[-HISTORY_CAP:]
    try:
        tmp = hist_path.with_suffix(".jsonl.tmp")
        tmp.write_text("\n".join(lines) + "\n"); os.replace(tmp, hist_path)
    except Exception:
        pass

    # 2) immutable daily baseline (write-once per date = that day's first snapshot)
    date = _now().strftime("%Y-%m-%d")
    daily = out / "snapshots" / f"{date}.json"
    if not daily.exists():
        full = {
            "date": date, "captured_at": snap["ts"], "type": "daily_baseline_immutable",
            "compact": snap,
            "champion_validation": _load(out, "champion_validation.json"),
            "governance": _load(out, "CHAMPION_GOVERNANCE.json"),
            "capital_allocation": _load(out, "capital_allocation.json"),
            "positions_live": _load(out, "paper_sim_live.json"),
            "note": "Immutable: written once on the first cycle of the day. Forensic baseline.",
        }
        try: write_json_atomic(daily, full)
        except Exception: pass

    return {"generated_at": snap["ts"], "history_rows": len(lines),
            "daily_baseline": str(daily.name), "latest": snap}

if __name__ == "__main__":
    import sys
    p = take_snapshot(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("history rows:", p["history_rows"], "| daily:", p["daily_baseline"])
    print("latest snapshot:", json.dumps(p["latest"], indent=2))
