"""
silmaril.execution.opportunity_journal — OPPORTUNITY LIFECYCLE JOURNAL (2.15 P3).

Every major mover, not just the ones we traded. For each: lifecycle state, price
velocity, peak return, whether we captured it, and WHY (captured / not a candidate
/ rejected / not tradeable). This is the training fuel — the daily record of what
the market offered and what we did about it.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from .paper_sim import load_all_samples, is_tradeable, _is_crypto

def _now(): return datetime.now(timezone.utc).isoformat()

def build_opportunity_journal(out_dir, min_move=0.04) -> Dict[str, Any]:
    out = Path(out_dir); samples = load_all_samples(out)
    try:
        from .lifecycle import classify_state
    except Exception:
        classify_state = lambda px, i: "?"
    # what did we trade (any book)?
    traded = set()
    for bp in out.glob("paper_book_*.json"):
        try:
            for tr in json.loads(bp.read_text()).get("trades", []):
                traded.add(tr.get("sym", ""))
        except Exception: pass
    # 5.1B — the audit's reasons, joined in: "why did we miss X" gets the EXACT rule
    try:
        _audit = (json.loads((out / "OPPORTUNITY_AUDIT.json").read_text()).get("by_ticker") or {})
    except Exception:
        _audit = {}
    # open positions → "capital committed / stuck" is a real reason, not a mystery
    _open, _stuck = {}, []
    for bp in out.glob("paper_book_*.json"):
        try:
            _bk = bp.stem.replace("paper_book_", "")
            for _sym, _po in (json.loads(bp.read_text()).get("positions") or {}).items():
                _open[_sym] = _bk
                if _po.get("stuck"):
                    _stuck.append({"book": _bk, "sym": _sym,
                                   "wager_usd": round(float(_po.get("wager_usd") or 0), 2)})
        except Exception:
            pass
    rows = []
    _seen_base = set()
    for tk, raw in samples.items():
        # 5.1B sanity — same law as edge_capture: canonical, one listing per base,
        # fresh print ≤24h, |peak| ≤ 50%/window. The TON +23598% ghosts die here too.
        if "-" in tk and _is_crypto(tk):
            _b = tk.split("-")[0].replace("USDT", "")   # canonical-crypto dedupe (RADUSD twins die here)
            if _b in _seen_base:
                continue
        else:
            _b = tk   # metals (GLD/XAU), energy (WTI/BRENT), stocks (AAPL): dash-less real movers, all welcome
        try:
            _lt = next(str(t) for t, _pp in reversed(raw) if _pp and "T00:00:00" not in str(t))
            _ah = (datetime.now().astimezone()
                   - datetime.fromisoformat(_lt.replace("Z", "+00:00")).astimezone()).total_seconds() / 3600.0
        except Exception:
            _ah = 999
        if _ah > 24:
            continue
        px = [p for _, p in raw if p and p > 0]
        if len(px) < 30: continue
        fresh = is_tradeable(px)
        # peak available move over the series (perfect long)
        trough = px[0]; peak = 0.0
        for p in px:
            if p < trough: trough = p
            if trough > 0: peak = max(peak, p / trough - 1)
        if peak < min_move: continue
        if peak > 0.50: continue        # integrity-suspect spike, not pursuable edge
        _seen_base.add(_b)
        vel = px[-1] / px[-4] - 1 if len(px) >= 4 and px[-4] > 0 else 0.0
        st = classify_state(px, len(px) - 1)
        _ar = _audit.get(tk) or {}
        if tk in _open:
            why = f"CAPITAL COMMITTED — open position in the {_open[tk]} book (rode the move, not yet banked)"
        elif not fresh:
            why = "not tradeable (stale/ghost — can't fill)"
        elif tk in traded:
            why = "captured / attempted"
        elif _ar.get("reason"):
            why = f"{_ar.get('decision','')}: {_ar['reason']}"   # the audit's EXACT rule
        else:
            why = "not a candidate (no oversold entry triggered — dip-buyer is blind to pure strength; TREND_RS is the roadmapped answer)"
        rows.append({"ticker": tk, "asset": "crypto" if _is_crypto(tk) else "stock",
                     "state": st, "peak_available_pct": round(peak * 100, 1),
                     "price_velocity_pct": round(vel * 100, 2),
                     "tradeable": fresh, "captured": tk in traded, "why": why})
    rows.sort(key=lambda r: r["peak_available_pct"], reverse=True)
    missed = [r for r in rows if not r["captured"]]
    payload = {"generated_at": _now(), "movers_logged": len(rows),
               "captured": sum(1 for r in rows if r["captured"]),
               "missed": len(missed),
               "pct_of_movers_missed": round(len(missed) / len(rows) * 100, 1) if rows else 0,
               "journal": rows[:60],
               "stuck_positions": sorted(_stuck, key=lambda r: -r["wager_usd"])[:10],
               "pair_with": "DECISION_TRACE.json — this journal says WHY we missed; the trace says WHY each taken trade lived and died",
               "note": "Every mover >=4%, traded or not. 'why' is the missed-opportunity taxonomy. Training fuel."}
    try: (out / "opportunity_journal.json").write_text(json.dumps(payload, indent=2))
    except Exception: pass
    return payload

if __name__ == "__main__":
    import sys; print(json.dumps(build_opportunity_journal(sys.argv[1] if len(sys.argv) > 1 else "docs/data"))[:300])
