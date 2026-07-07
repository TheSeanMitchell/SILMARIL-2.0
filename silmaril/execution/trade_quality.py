"""
TRADE QUALITY ENGINE (4.0 Movement I — Verification; Notes #11) — not WHETHER a trade made money
but HOW WELL it executed: entry vs local low, exit vs local high, %% of the available move
captured. Every closed trade gets a report card, GEKKO included. Deterministic; honest below n=3.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path


def build_trade_quality(out_dir):
    out = Path(out_dir)
    try:
        samples = json.loads((out / "price_samples.json").read_text()).get("samples", {})
    except Exception:
        samples = {}
    now = datetime.now(timezone.utc)
    books = {}
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        try:
            trs = json.loads((out / f"paper_book_{bk}.json").read_text()).get("trades", [])
        except Exception:
            trs = []
        buys, cards = {}, []
        for t in trs:
            if t.get("side") == "BUY":
                buys[t.get("sym")] = t
                continue
            if t.get("side") != "SELL" or t.get("realized_pct") is None:
                continue
            b = buys.get(t.get("sym"))
            if not b:
                continue
            try:
                bt = datetime.fromisoformat(b["t"])
                st = datetime.fromisoformat(t["t"])
            except Exception:
                continue
            w0, w1 = bt - timedelta(hours=1), st + timedelta(hours=3)
            px = []
            for ts, p in samples.get(t["sym"], []):
                if not p or p <= 0 or "T00:00:00" in ts:
                    continue
                try:
                    dt = datetime.fromisoformat(ts)
                except Exception:
                    continue
                if w0 <= dt <= w1:
                    px.append(p)
            if len(px) < 4:
                continue
            lo, hi = min(px), max(px)
            entry = float(b.get("px") or b.get("price") or 0)
            exit_ = float(t.get("px") or t.get("price") or 0)
            if not entry or not exit_ or hi <= lo:
                continue
            cards.append({"sym": t["sym"], "closed": t.get("t", "")[:16],
                          "entry_above_low_pct": round((entry / lo - 1) * 100, 2),
                          "exit_below_high_pct": round((hi / exit_ - 1) * 100, 2),
                          "capture_pct": round((exit_ - entry) / (hi - lo) * 100, 1),
                          "realized_pct": t["realized_pct"]})
        n = len(cards)
        if n < 3:
            books[bk] = {"n": n, "status": "insufficient — needs >=3 closed trades with price context"}
            continue
        books[bk] = {"n": n,
                     "avg_entry_above_low_pct": round(sum(c["entry_above_low_pct"] for c in cards) / n, 2),
                     "avg_exit_below_high_pct": round(sum(c["exit_below_high_pct"] for c in cards) / n, 2),
                     "avg_capture_pct": round(sum(c["capture_pct"] for c in cards) / n, 1),
                     "recent_cards": cards[-25:]}
    payload = {"generated_at": now.isoformat(), "books": books,
               "what": ("Execution report cards: bought how far above the local low, sold how far "
                        "below the local high, and %% of the available move captured. Profit says "
                        "WHETHER; this says HOW WELL — Notes #11 made real.")}
    (out / "TRADE_QUALITY.json").write_text(json.dumps(payload, indent=1))
    return payload
