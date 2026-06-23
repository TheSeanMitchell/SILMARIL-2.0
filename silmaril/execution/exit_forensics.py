"""
silmaril.execution.exit_forensics — EXIT FORENSICS (2.5.1 P2). Measurement, not alpha.

For every closed trade, looks at what the price did AFTER we exited: best, worst, and
final return at +1/+3/+5/+10/+20 days. Answers the one question that matters about
exits — did we sell winners too early (execution failure) or was the thesis just
wrong (price kept falling)? Emits EXIT_FORENSICS.json, split by book and strategy.
"""
from __future__ import annotations
import json, glob
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List
from .paper_sim import _is_crypto
from .atomic_io import write_json_atomic

WINDOWS_D = [1, 3, 5, 10, 20]
def _now(): return datetime.now().astimezone().isoformat()
def _dt(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None

def _closed_trades(out: Path) -> List[Dict[str, Any]]:
    trades = []
    for fn in glob.glob(str(out / "paper_book_*.json")):
        strat = Path(fn).stem.replace("paper_book_", "")
        if strat in ("crypto", "stock"):  # live books; arena books carry the strategy name
            pass
        try: tr = json.loads(Path(fn).read_text()).get("trades", [])
        except Exception: continue
        lots = defaultdict(deque)
        for t in tr:
            side, sym, px, ts = t.get("side"), t.get("sym"), t.get("price"), t.get("t")
            if side == "BUY": lots[sym].append((px, ts))
            elif side == "SELL" and lots[sym]:
                ep, et = lots[sym].popleft()
                trades.append({"strategy": strat, "sym": sym, "entry": ep, "exit": px,
                               "exit_t": ts, "realized_pct": round((px / ep - 1) * 100, 2) if ep else 0})
    return trades

def _series(out: Path):
    try: d = json.loads((out / "price_samples.json").read_text()).get("samples", {})
    except Exception: return {}
    return {sym: [(_dt(t), p) for t, p in rows if p and p > 0 and _dt(t)] for sym, rows in d.items()}

def _agg(rs: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not rs: return {}
    losers = [r for r in rs if r["realized_pct"] < 0]
    exec_fail = [r for r in losers if r["post_exit_leak_pct"] > 1.0]   # lost, but bounced after we sold
    return {"closed_trades": len(rs),
            "avg_post_exit_leak_pct": round(mean([r["post_exit_leak_pct"] for r in rs]), 2),
            "avg_saved_loss_pct": round(mean([r["post_exit_saved_pct"] for r in rs]), 2),
            "avg_exit_quality": round(mean([r["exit_quality"] for r in rs]), 2),
            "losers": len(losers), "execution_failures": len(exec_fail),
            "thesis_failures": len(losers) - len(exec_fail),
            "verdict": (f"{len(exec_fail)}/{len(losers)} losing trades bounced after exit "
                        f"(sold too early); {len(losers) - len(exec_fail)} kept falling (thesis wrong)"
                        if losers else "no losing trades to attribute yet")}

def build_exit_forensics(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    trades, series = _closed_trades(out), _series(out)
    rows = []
    for tr in trades:
        ser = series.get(tr["sym"]); xt = _dt(tr["exit_t"]); xp = tr["exit"]
        if not ser or not xt or not xp: continue
        after = [(t, p) for t, p in ser if t >= xt]
        if len(after) < 2: continue
        best = max(p for _, p in after); worst = min(p for _, p in after)
        leak = round((best / xp - 1) * 100, 2)             # ran up after we sold
        saved = round((xp / worst - 1) * 100, 2) if worst > 0 else 0.0  # fell after we sold
        finals = {}
        for lbl, hrs in [("1h", 1), ("4h", 4)] + [(f"{d}d", d * 24) for d in WINDOWS_D]:
            tgt = xt + timedelta(hours=hrs)
            pts = [p for t, p in after if t <= tgt]
            finals[lbl] = round((pts[-1] / xp - 1) * 100, 2) if (len(pts) > 1 and after[-1][0] >= tgt) else None
        lk = max(0.0, leak)
        # exit classification per the directive
        if tr["realized_pct"] < -1.0 and lk < 1.0:
            klass = "LATE_EXIT"          # held into a loss that didn't bounce — exit too late
        elif lk >= 4.0:
            klass = "CATASTROPHIC_EXIT"  # sold way too early, huge run-up after
        elif lk >= 1.0:
            klass = "EARLY_EXIT"         # sold too soon, left money
        else:
            klass = "GOOD_EXIT"          # little/no run-up after — sold well
        rows.append({**tr, "book": "crypto" if _is_crypto(tr["sym"]) else "stock",
                     "post_exit_leak_pct": lk, "post_exit_saved_pct": max(0.0, saved),
                     "exit_quality": round(max(0.0, saved) - lk, 2),
                     "exit_class": klass, "window_finals_pct": finals})
    def _classes(rs):
        from collections import Counter
        c = Counter(r["exit_class"] for r in rs)
        return {k: c.get(k, 0) for k in ("GOOD_EXIT", "EARLY_EXIT", "LATE_EXIT", "CATASTROPHIC_EXIT")}
    payload = {"generated_at": _now(), "overall": _agg(rows),
               "exit_class_counts": _classes(rows),
               "exit_class_by_book": {bk: _classes([r for r in rows if r["book"] == bk]) for bk in ("crypto", "stock")},
               "by_book": {bk: _agg([r for r in rows if r["book"] == bk]) for bk in ("crypto", "stock")},
               "by_strategy": {s: _agg([r for r in rows if r["strategy"] == s])
                               for s in sorted(set(r["strategy"] for r in rows))},
               "worst_offenders": [{"ticker": r["sym"], "strategy": r["strategy"], "book": r["book"],
                                    "realized_pct": r["realized_pct"], "leak_pct": r["post_exit_leak_pct"],
                                    "exit_class": r["exit_class"]}
                                   for r in sorted(rows, key=lambda r: r["post_exit_leak_pct"], reverse=True)[:12]],
               "windows_note": "+1h/+4h added; +10/+20d stay null until history is that long (~5 days now).",
               "note": "Leak = ran up after we sold (too early). GOOD<1% leak, EARLY 1-4%, CATASTROPHIC>=4%, LATE = held into a non-bouncing loss."}
    try: write_json_atomic(out / "EXIT_FORENSICS.json", payload)
    except Exception: pass
    return payload

if __name__ == "__main__":
    import sys
    p = build_exit_forensics(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("OVERALL:", p["overall"])
    for bk, a in p["by_book"].items(): print(f"  {bk}: {a.get('verdict','-')}")
