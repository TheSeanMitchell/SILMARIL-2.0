"""
silmaril.execution.trade_forensics — Measurement Spine #1.

THE PROBLEM THIS SOLVES: realized_pnl was effectively None. The system knew
signals, buys, sells, headlines — but not PROFIT. A race car with no
speedometer. This reconstructs every trade's full path from the BROKER'S OWN
filled orders (ground truth, not internal guesses):

    signal → entry (fill) → position → exit (fill) → REALIZED $ RESULT

For each ticker it matches buy fills to sell fills (FIFO), computes the actual
dollars made/lost, holding time, and entry/exit prices. Open positions are
marked-to-market against the last sample price. Writes a per-account and
combined ledger to docs/data/trade_forensics.json.

This is the foundation of the spine — Edge Capture and the Missed Opportunity
Journal both build on the realized numbers this produces.
"""
from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

VERSION = "trade-forensics-1.0"

ACCOUNTS = [
    ("LEGACY", "alpaca_paper_state.json", "stocks"),
    ("HARVEST_3", "alpaca_h3_state.json", "crypto"),
    ("HARVEST_5", "alpaca_h5_state.json", "crypto"),
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def _dump(path: Path, obj):
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, separators=(",", ":"), allow_nan=False)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _norm(t: str) -> str:
    return str(t).upper().replace("/", "").replace("-", "")


def _f(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


def _parse_fills(orders: List[Dict[str, Any]]):
    """Pull (ts, symbol, side, qty, price) from filled/partially-filled
    orders, sorted by time. Uses the broker's filled_qty/filled_avg_price."""
    fills = []
    for o in orders:
        status = str(o.get("status") or "")
        if status not in ("filled", "partially_filled"):
            continue
        qty = _f(o.get("filled_qty"))
        px = _f(o.get("filled_avg_price"))
        if qty <= 0 or px <= 0:
            continue
        fills.append({
            "ts": o.get("time") or o.get("submitted_at") or "",
            "symbol": _norm(o.get("symbol")),
            "side": str(o.get("side") or "").lower(),
            "qty": qty,
            "price": px,
        })
    fills.sort(key=lambda x: x["ts"])
    return fills


def _round_trips_for_account(orders, last_prices):
    """FIFO-match buys to sells per symbol → closed round-trips with realized
    $ and % ; remaining open lots marked-to-market against last_prices."""
    fills = _parse_fills(orders)
    lots = defaultdict(deque)   # symbol -> deque of open buy lots
    closed = []
    realized_total = 0.0
    wins = 0
    losses = 0

    for fl in fills:
        sym = fl["symbol"]
        if fl["side"] == "buy":
            lots[sym].append({"qty": fl["qty"], "price": fl["price"],
                              "ts": fl["ts"]})
        elif fl["side"] == "sell":
            remaining = fl["qty"]
            sell_px = fl["price"]
            while remaining > 1e-12 and lots[sym]:
                lot = lots[sym][0]
                take = min(remaining, lot["qty"])
                cost = take * lot["price"]
                proceeds = take * sell_px
                pnl = proceeds - cost
                pct = (pnl / cost * 100.0) if cost > 0 else 0.0
                realized_total += pnl
                if pnl >= 0:
                    wins += 1
                else:
                    losses += 1
                closed.append({
                    "symbol": sym,
                    "qty": round(take, 8),
                    "entry_price": round(lot["price"], 8),
                    "exit_price": round(sell_px, 8),
                    "entry_ts": lot["ts"],
                    "exit_ts": fl["ts"],
                    "realized_usd": round(pnl, 2),
                    "realized_pct": round(pct, 3),
                })
                lot["qty"] -= take
                remaining -= take
                if lot["qty"] <= 1e-12:
                    lots[sym].popleft()
            # if remaining > 0 here, it's a sell with no matching buy
            # (pre-existing position) — ignore for realized math.

    # open lots → unrealized mark-to-market
    open_positions = []
    unrealized_total = 0.0
    for sym, dq in lots.items():
        if not dq:
            continue
        tot_qty = sum(l["qty"] for l in dq)
        if tot_qty <= 1e-12:
            continue
        cost = sum(l["qty"] * l["price"] for l in dq)
        avg_entry = cost / tot_qty if tot_qty > 0 else 0.0
        last = last_prices.get(sym) or last_prices.get(sym + "USD") or avg_entry
        mv = tot_qty * last
        upnl = mv - cost
        unrealized_total += upnl
        open_positions.append({
            "symbol": sym,
            "qty": round(tot_qty, 8),
            "avg_entry": round(avg_entry, 8),
            "last_price": round(last, 8),
            "unrealized_usd": round(upnl, 2),
            "unrealized_pct": round((upnl / cost * 100.0) if cost > 0 else 0.0, 3),
        })

    return {
        "closed_trades": closed,
        "open_positions": open_positions,
        "realized_usd": round(realized_total, 2),
        "unrealized_usd": round(unrealized_total, 2),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / (wins + losses) * 100.0, 1) if (wins + losses) else None,
    }


def build_trade_forensics(out_dir, last_prices: Optional[Dict[str, float]] = None
                          ) -> Dict[str, Any]:
    """Reconstruct realized + unrealized P&L per account from broker fills."""
    out = Path(out_dir)
    # last sample prices for marking open positions
    if last_prices is None:
        samples = (_load(out / "price_samples.json", {}) or {}).get("samples") or {}
        last_prices = {}
        for tk, rows in samples.items():
            if rows:
                last_prices[_norm(tk)] = _f(rows[-1][1])

    per_account = {}
    combined_realized = 0.0
    combined_unrealized = 0.0
    combined_wins = 0
    combined_losses = 0
    all_closed = []

    for acct_id, fn, klass in ACCOUNTS:
        st = _load(out / fn, {})
        orders = st.get("orders") or []
        rt = _round_trips_for_account(orders, last_prices)
        eq = _f((st.get("account") or {}).get("equity"), 10000.0)
        rt["account"] = acct_id
        rt["class"] = klass
        rt["equity"] = round(eq, 2)
        rt["realized_pct_of_principal"] = round(rt["realized_usd"] / 10000.0 * 100.0, 3)
        per_account[acct_id] = rt
        combined_realized += rt["realized_usd"]
        combined_unrealized += rt["unrealized_usd"]
        combined_wins += rt["wins"]
        combined_losses += rt["losses"]
        for c in rt["closed_trades"]:
            c2 = dict(c); c2["account"] = acct_id
            all_closed.append(c2)

    # biggest winners / losers across everything (the leak finder)
    all_closed.sort(key=lambda c: c["realized_usd"])
    biggest_losers = all_closed[:10]
    biggest_winners = list(reversed(all_closed[-10:]))

    payload = {
        "version": VERSION,
        "generated_at": _now(),
        "combined": {
            "realized_usd": round(combined_realized, 2),
            "unrealized_usd": round(combined_unrealized, 2),
            "total_pnl_usd": round(combined_realized + combined_unrealized, 2),
            "wins": combined_wins,
            "losses": combined_losses,
            "win_rate": round(combined_wins / (combined_wins + combined_losses) * 100.0, 1)
                        if (combined_wins + combined_losses) else None,
            "closed_trade_count": len(all_closed),
        },
        "accounts": per_account,
        "biggest_winners": biggest_winners,
        "biggest_losers": biggest_losers,
        "note": ("Realized P&L reconstructed from the BROKER'S filled orders "
                 "(FIFO match of buys→sells). This is the speedometer: actual "
                 "dollars made/lost per trade, not signal win-rate. Win-rate "
                 "here counts realized round-trips, not directional calls — so "
                 "'high win-rate but negative realized' shows up as small wins "
                 "+ big losers in biggest_losers."),
    }
    _dump(out / "trade_forensics.json", payload)
    return payload


if __name__ == "__main__":  # pragma: no cover
    import sys
    p = build_trade_forensics(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/data"))
    print(json.dumps(p["combined"], indent=2))
