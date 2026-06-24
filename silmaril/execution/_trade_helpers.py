"""Shared closed-trade extraction for 2.5.3 audit engines."""
from __future__ import annotations
import json, glob, re
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from .paper_sim import asset_class

def _dt(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None

def ts_from_name(name: str):
    """MR_d3_t3_s4 -> (target_pct, stop_pct). Returns (None,None) if unparseable."""
    t = re.search(r"_t(\d+)", name or ""); s = re.search(r"_s(\d+)", name or "")
    return (int(t.group(1)) if t else None, int(s.group(1)) if s else None)

def closed_trades(out: Path) -> List[Dict[str, Any]]:
    """FIFO-paired BUY->SELL with entry/exit time+price, book, and the strategy's
    target/stop parsed from its name."""
    rows = []
    for fn in glob.glob(str(out / "paper_book_*.json")):
        strat = Path(fn).stem.replace("paper_book_", "")
        tpct, spct = ts_from_name(strat)
        try: tr = json.loads(Path(fn).read_text()).get("trades", [])
        except Exception: continue
        lots = defaultdict(deque)
        for t in tr:
            side, sym, px, ts = t.get("side"), t.get("sym"), t.get("price"), t.get("t")
            if side == "BUY": lots[sym].append((px, ts))
            elif side == "SELL" and lots[sym]:
                ep, et = lots[sym].popleft()
                rows.append({"strategy": strat, "sym": sym, "book": asset_class(sym),
                             "entry": ep, "exit": px, "entry_t": et, "exit_t": ts,
                             "target_pct": tpct, "stop_pct": spct,
                             "realized_pct": round((px / ep - 1) * 100, 2) if ep else 0.0})
    return rows

def price_series(out: Path):
    try: d = json.loads((out / "price_samples.json").read_text()).get("samples", {})
    except Exception: return {}
    return {sym: [(_dt(t), p) for t, p in rows if p and p > 0 and _dt(t)] for sym, rows in d.items()}
