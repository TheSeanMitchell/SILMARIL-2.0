"""
silmaril.execution.execution_leak — EXECUTION LEAK ENGINE (2.15 Priority 2).

Where money disappears between signal and realized P&L. For every CLOSED trade it
pairs entry->exit and asks: how much did the name keep running AFTER we sold
(premature-exit leak), and what fraction of the in-trade move did we actually keep
(capture). Ranks the biggest leaks. Instrumentation, not a strategy.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List
from .paper_sim import load_all_samples

POST_EXIT_WINDOW_H = 6.0   # how long after exit to look for "it kept running"

def _now(): return datetime.now(timezone.utc).isoformat()

def _series(samples, sym):
    return [(datetime.fromisoformat(t), p) for t, p in samples.get(sym, []) if p and p > 0]

def _price_at(ser, when, after=True):
    """closest price at/after (or before) `when`."""
    best = None
    for t, p in ser:
        if after and t >= when: return p
        if not after and t <= when: best = p
    return best

def _peak_between(ser, t0, t1):
    ps = [p for t, p in ser if t0 <= t <= t1]
    return max(ps) if ps else None

def build_execution_leak(out_dir) -> Dict[str, Any]:
    out = Path(out_dir); samples = load_all_samples(out)
    trades = []
    for bp in out.glob("paper_book_*.json"):
        try: d = json.loads(bp.read_text())
        except Exception: continue
        opens = {}
        for tr in d.get("trades", []):
            sym = tr.get("sym", "")
            if tr.get("side") == "BUY":
                opens.setdefault(sym, []).append(tr)
            elif tr.get("side") == "SELL" and opens.get(sym):
                b = opens[sym].pop(0)
                trades.append((sym, b, tr, bp.stem.replace("paper_book_", "")))
    rows = []
    for sym, b, s, book in trades:
        try:
            ent, ext = float(b["price"]), float(s["price"])
            et, xt = datetime.fromisoformat(b["t"]), datetime.fromisoformat(s["t"])
        except Exception: continue
        ser = _series(samples, sym)
        if not ser: continue
        peak_in = _peak_between(ser, et, xt) or max(ent, ext)
        from datetime import timedelta
        peak_post = _peak_between(ser, xt, xt + timedelta(hours=POST_EXIT_WINDOW_H)) or ext
        realized = (ext / ent - 1)
        available_in = (peak_in / ent - 1)
        capture = round(realized / available_in * 100, 1) if available_in > 1e-9 else (100.0 if realized > 0 else 0.0)
        leak_post = round(max(0.0, peak_post / ext - 1) * 100, 2)   # money left after exit
        rows.append({"ticker": sym, "book": book,
                     "entry": round(ent, 6), "exit": round(ext, 6),
                     "realized_pct": round(realized * 100, 2),
                     "available_in_pct": round(available_in * 100, 2),
                     "in_trade_capture_pct": min(capture, 100.0),
                     "premature_exit_leak_pct": leak_post,
                     "peak_after_exit": round(peak_post, 6)})
    rows.sort(key=lambda r: r["premature_exit_leak_pct"], reverse=True)
    avg_cap = round(mean([r["in_trade_capture_pct"] for r in rows]), 1) if rows else None
    avg_leak = round(mean([r["premature_exit_leak_pct"] for r in rows]), 2) if rows else None
    # EXIT EFFICIENCY (aggregate): of the peak gain reached WHILE we held each trade,
    # how much did we actually realize. This is a DIFFERENT question from the primary
    # Edge Capture KPI (which is capture of the total available *market* move), so the
    # two numbers are not supposed to be equal. The per-trade *average* (avg_cap) is
    # distorted by losers (one trade can read -300%) and should be ignored.
    sum_avail = sum(r["available_in_pct"] for r in rows if r["available_in_pct"] > 0)
    sum_real = sum(r["realized_pct"] for r in rows if r["available_in_pct"] > 0)
    exit_eff = round(sum_real / sum_avail * 100, 1) if sum_avail > 0 else None
    payload = {"generated_at": _now(), "closed_trades_analyzed": len(rows),
               "exit_efficiency_pct": exit_eff,
               "avg_per_trade_capture_pct_DISTORTED_IGNORE": avg_cap,
               "avg_premature_exit_leak_pct": avg_leak,
               "biggest_leaks": rows[:25],
               "headline": (f"{len(rows)} closed trades · exit efficiency {exit_eff}% of in-trade peak "
                            f"· avg post-exit leak {avg_leak}%"
                            if rows else "no closed trades yet — populates as the sim exits positions"),
               "reconciliation_note": ("This panel's 'exit efficiency' answers a DIFFERENT question from the "
                            "Edge Capture KPI: efficiency = how much of each trade's in-trade peak we kept; "
                            "the KPI = how much of the total available market move we captured. They are not "
                            "meant to match. The old -35% 'avg capture' was a distorted per-trade average "
                            "(losers produce negative ratios) — it was the bug, now retired."),
               "note": "Leak = how much the name kept running after we sold. High leak = exiting too early."}
    try: (out / "execution_leak.json").write_text(json.dumps(payload, indent=2))
    except Exception: pass
    return payload

if __name__ == "__main__":
    import sys
    p = build_execution_leak(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("HEADLINE:", p["headline"])
    for r in p["biggest_leaks"][:8]:
        print(f"  {r['ticker']:12s} realized {r['realized_pct']:>+6.2f}% · capture {r['in_trade_capture_pct']:>5.1f}% · post-exit leak {r['premature_exit_leak_pct']:>5.2f}%")
