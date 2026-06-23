"""
silmaril.execution.regime_observer — REGIME OBSERVER (2.5.1 proof mode). Measurement.

NOT a regime trader. It classifies the market each moment — trend, volatility,
breadth — into a named regime (Strong Bull … Panic), independently for crypto and
stock (they are different markets). Then it tags every completed trade with the
regime at entry and reports which strategies win or lose in each regime, and which
regimes do the most damage. No strategy changes. Emits REGIME_ANALYSIS.json.
"""
from __future__ import annotations
import json, glob
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median, pstdev
from typing import Any, Dict, List, Optional
from .paper_sim import _is_crypto
from .atomic_io import write_json_atomic

def _now(): return datetime.now().astimezone().isoformat()
def _dt(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None

def _series(out: Path):
    try: d = json.loads((out / "price_samples.json").read_text()).get("samples", {})
    except Exception: return {}
    return {sym: [(_dt(t), p) for t, p in rows if p and p > 0 and _dt(t)] for sym, rows in d.items()}

def _asof(ser, t):
    """last price at or before t."""
    p = None
    for ts, px in ser:
        if ts <= t: p = px
        else: break
    return p

def _market_state(series, names, t: datetime):
    """trend (median 24h return), breadth (% up 24h), vol (median 24h stdev of step returns)."""
    rets, ups, tot, vols = [], 0, 0, []
    t0 = t - timedelta(hours=24)
    for s in names:
        ser = series.get(s, [])
        pt, p0 = _asof(ser, t), _asof(ser, t0)
        if pt and p0:
            rets.append(pt / p0 - 1); tot += 1; ups += 1 if pt > p0 else 0
            win = [px for ts, px in ser if t0 <= ts <= t]
            if len(win) > 3:
                sr = [win[i] / win[i-1] - 1 for i in range(1, len(win)) if win[i-1] > 0]
                if sr: vols.append(pstdev(sr))
    if tot == 0: return None
    trend = median(rets); breadth = ups / tot; vol = median(vols) if vols else 0.0
    return {"trend_24h_pct": round(trend * 100, 2), "breadth_up_pct": round(breadth * 100, 1),
            "vol": round(vol * 100, 3)}

def _label(st, vol_hi: float):
    """name the regime from trend + breadth."""
    if st is None: return "UNKNOWN", "UNKNOWN"
    tr, br = st["trend_24h_pct"], st["breadth_up_pct"]
    if tr >= 3 and br >= 60: m = "STRONG_BULL"
    elif tr >= 1: m = "BULL"
    elif tr <= -3 and br <= 40: m = "PANIC"
    elif tr <= -1: m = "BEAR"
    elif tr < 0: m = "WEAK"
    else: m = "NEUTRAL"
    v = "HIGH_VOL" if st["vol"] >= vol_hi else "LOW_VOL"
    return m, v

def _closed_trades(out: Path):
    trades = []
    for fn in glob.glob(str(out / "paper_book_*.json")):
        strat = Path(fn).stem.replace("paper_book_", "")
        try: tr = json.loads(Path(fn).read_text()).get("trades", [])
        except Exception: continue
        lots = defaultdict(deque)
        for t in tr:
            if t.get("side") == "BUY": lots[t.get("sym")].append((t.get("price"), t.get("t")))
            elif t.get("side") == "SELL" and lots[t.get("sym")]:
                ep, et = lots[t.get("sym")].popleft()
                trades.append({"strategy": strat, "sym": t.get("sym"), "entry_t": et,
                               "ret_pct": round((t.get("price") / ep - 1) * 100, 2) if ep else 0})
    return trades

def build_regime_analysis(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    series = _series(out)
    trades = _closed_trades(out)
    books = {}
    from .paper_sim import asset_class as _ac, BOOKS as _BOOKS
    for book in _BOOKS:
        crypto = (book == "crypto")
        names = [s for s in series if _ac(s) == book and len(series[s]) > 8]
        # vol threshold = median of sampled vols across the window (for HIGH/LOW split)
        all_t = sorted({ts for s in names for ts, _ in series[s]})
        samp = all_t[::max(1, len(all_t) // 40)] if all_t else []
        vols = [v["vol"] for v in (_market_state(series, names, t) for t in samp) if v]
        vol_hi = median(vols) if vols else 0.0
        # current regime
        cur = _market_state(series, names, all_t[-1]) if all_t else None
        cm, cv = _label(cur, vol_hi)
        # tag trades
        buckets = defaultdict(lambda: defaultdict(list))   # regime -> strategy -> [ret]
        regime_all = defaultdict(list)
        tagged = 0
        for tr in trades:
            if _ac(tr["sym"]) != book: continue
            et = _dt(tr["entry_t"])
            if not et: continue
            st = _market_state(series, names, et)
            m, _v = _label(st, vol_hi)
            buckets[m][tr["strategy"]].append(tr["ret_pct"])
            regime_all[m].append(tr["ret_pct"]); tagged += 1
        def stats(rs):
            if not rs: return None
            wins = sum(1 for r in rs if r > 0)
            return {"trades": len(rs), "avg_ret_pct": round(sum(rs)/len(rs), 2),
                    "win_pct": round(wins/len(rs)*100, 1)}
        by_regime = {m: {"overall": stats(regime_all[m]),
                         "by_strategy": {s: stats(rl) for s, rl in sd.items()}}
                     for m, sd in buckets.items()}
        # which regime hurts / helps most
        ranked = sorted(((m, stats(rl)) for m, rl in regime_all.items() if rl),
                        key=lambda x: x[1]["avg_ret_pct"])
        books[book] = {
            "current_regime": {"market": cm, "vol": cv, **(cur or {})},
            "vol_high_threshold_pct": round(vol_hi, 3),
            "trades_tagged": tagged,
            "by_regime": by_regime,
            "most_damaging_regime": ({"regime": ranked[0][0], **ranked[0][1]} if ranked else None),
            "most_profitable_regime": ({"regime": ranked[-1][0], **ranked[-1][1]} if ranked else None),
        }
    payload = {"generated_at": _now(), "books": books,
               "regimes_defined": ["STRONG_BULL", "BULL", "NEUTRAL", "WEAK", "BEAR", "PANIC", "(+HIGH/LOW_VOL)"],
               "method": ("Crypto and stock get INDEPENDENT regimes from their own universe: trend = median "
                          "24h return, breadth = % of names up, vol = median 24h step-return stdev."),
               "note": "Observer only — no regime reactions, no strategy changes. Evidence to decide later."}
    try: write_json_atomic(out / "REGIME_ANALYSIS.json", payload)
    except Exception: pass
    return payload

if __name__ == "__main__":
    import sys
    p = build_regime_analysis(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    for bk, b in p["books"].items():
        print(f"{bk}: now={b['current_regime']['market']}/{b['current_regime']['vol']} "
              f"trend={b['current_regime'].get('trend_24h_pct')}% | tagged {b['trades_tagged']} trades")
        print("   regimes:", {m: v["overall"] for m, v in b["by_regime"].items() if v["overall"]})
