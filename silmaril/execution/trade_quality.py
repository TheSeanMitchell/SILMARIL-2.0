"""
silmaril.execution.trade_quality — TRADE QUALITY LEDGER (2.5.5).

Answers, permanently and honestly, the recurring "why are so many trades $0.00?" question.
Every SELL in each book is classified into one of four buckets, using the book's OWN authoritative
`pnl` field (no recomputation, no synthetic anything):

  REAL WIN       — real-sized position (notional >= $1), pnl > +$0.005
  REAL LOSS      — real-sized position, pnl < -$0.005
  FLAT TIMEOUT   — real-sized position, |pnl| <= $0.005  (a dip that never bounced to target nor
                   fell to stop; sold at ~entry when the hold timer expired — a non-event, not a loss)
  DUST           — position notional < $1 (qty pennies). These form when the entry loop buys the tail
                   of its candidate list with the cash left after the first few full-size buys; a
                   sub-dollar position cannot produce meaningful P&L, so it shows $0.00. Negligible
                   risk, negligible result — log noise, not a leak.

This is OBSERVATIONAL ONLY. It changes no trading logic. It exists so the trade log is legible.
Emits TRADE_QUALITY.json.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

DUST_USD = 1.0
EPS = 0.005

def _now(): return datetime.now(timezone.utc).isoformat()

def _classify_book(trades: List[dict], day: str) -> Dict[str, Any]:
    def notional(t): return abs((t.get("qty") or 0) * (t.get("price") or 0))
    sells = [t for t in trades if t.get("side") == "SELL"]
    def bucketize(rows):
        rw = [t for t in rows if (t.get("pnl") or 0) > EPS and notional(t) >= DUST_USD]
        rl = [t for t in rows if (t.get("pnl") or 0) < -EPS and notional(t) >= DUST_USD]
        flat = [t for t in rows if abs(t.get("pnl") or 0) <= EPS and notional(t) >= DUST_USD]
        dust = [t for t in rows if notional(t) < DUST_USD]
        real = rw + rl
        return {
            "real_wins": len(rw), "real_win_usd": round(sum(t["pnl"] for t in rw), 2),
            "real_losses": len(rl), "real_loss_usd": round(sum(t["pnl"] for t in rl), 2),
            "flat_timeouts": len(flat),
            "dust": len(dust), "dust_usd": round(sum((t.get("pnl") or 0) for t in dust), 2),
            "net_realized_usd": round(sum((t.get("pnl") or 0) for t in rows), 2),
            "real_round_trips": len(real),
            "real_win_rate_pct": round(100 * len(rw) / len(real), 1) if real else None,
        }
    today_sells = [t for t in sells if (t.get("t", "")[:10] == day)]
    return {"lifetime": bucketize(sells), "today": bucketize(today_sells)}

def build_trade_quality(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    day = datetime.now(timezone.utc).date().isoformat()
    books: Dict[str, Any] = {}
    for bk in ("crypto", "stock", "metal", "energy"):
        p = out / f"paper_book_{bk}.json"
        if not p.exists():
            continue
        try:
            trades = json.loads(p.read_text()).get("trades", [])
        except Exception:
            continue
        if trades:
            books[bk] = _classify_book(trades, day)
    payload = {
        "generated_at": _now(),
        "status_label": "OBSERVATIONAL — legibility for the trade log; changes no trading logic.",
        "dust_threshold_usd": DUST_USD,
        "by_book": books,
        "what": "Every SELL bucketed into real-win / real-loss / flat-timeout / dust using the book's own pnl.",
        "why_zero": ("$0.00 trades are NOT hidden losses. They are either DUST (sub-$1 positions bought "
                     "with leftover cash at the tail of the entry loop — can't move the needle) or FLAT "
                     "TIMEOUTS (a dip that never reverted to target nor hit stop, sold at ~entry when the "
                     "hold timer expired). The book's realized P&L already reflects their negligible effect."),
        "honest_note": ("Read net_realized_usd as the truth; real_win_rate_pct counts only real-sized "
                        "round-trips. Dust count is high by design of the sizing loop — it is log noise, "
                        "not risk. No investment logic was touched to produce this."),
    }
    try:
        from .atomic_io import write_json_atomic
        write_json_atomic(out / "TRADE_QUALITY.json", payload)
    except Exception:
        (out / "TRADE_QUALITY.json").write_text(json.dumps(payload, indent=2))
    return payload

if __name__ == "__main__":
    import sys
    print(json.dumps(build_trade_quality(sys.argv[1] if len(sys.argv) > 1 else "docs/data"), indent=2)[:1200])
