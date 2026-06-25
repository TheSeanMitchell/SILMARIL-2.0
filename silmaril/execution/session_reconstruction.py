"""
silmaril.execution.session_reconstruction — TODAY'S SESSION BLACK BOX (2.5.5).

Reconstructs the current trading session (default: since 1 PM Vegas = 20:00 UTC) for every book,
from REAL fills only — entry/exit price, qty, dollar P&L, and timestamps straight out of the
account books. NO synthetic data: exit reasons are reclassified deterministically by comparing the
real exit price to the session champion's real target/stop, and champion stability is read from the
real promotion log. Fixes the "only last 30 trades have reasons" limit — every trade in the window
gets a reconstructed reason. Emits SESSION_TODAY.json + a session fingerprint for recreation.
"""
from __future__ import annotations
import json, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict, deque
from typing import Any, Dict, List
from .atomic_io import write_json_atomic

def _now(): return datetime.now(timezone.utc)
def _dt(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None
def _load(out, n, d=None):
    try: return json.loads((out / n).read_text())
    except Exception: return d if d is not None else {}

def _ts_params(name: str):
    """target%/stop% from a champion name like MR_d3_t3_s2 -> (3.0, 2.0)."""
    t = re.search(r"_t(\d+)", name or ""); s = re.search(r"_s(\d+)", name or "")
    return (float(t.group(1)) if t else None, float(s.group(1)) if s else None)

def _session_start(now: datetime) -> datetime:
    """1 PM Vegas (PDT = UTC-7) = 20:00 UTC. Rolls to yesterday if we're before it."""
    start = now.replace(hour=20, minute=0, second=0, microsecond=0)
    if now < start:
        start -= timedelta(days=1)
    return start

def _pair_book(trades: List[dict], tgt_pct, stop_pct, start: datetime):
    """FIFO-pair BUY->SELL PER SYMBOL; return round-trips that EXITED in the window.
    The book's own `pnl` on the SELL is authoritative for dollars + win/loss; entry is matched
    for hold-time and reason only."""
    lots: Dict[str, deque] = defaultdict(deque)
    out = []
    for tr in sorted(trades, key=lambda x: x.get("t", "")):
        sym = tr.get("sym"); side = (tr.get("side") or "").upper()
        if side == "BUY":
            lots[sym].append(tr)
        elif side == "SELL" and lots[sym]:
            buy = lots[sym].popleft()
            xt = _dt(tr.get("t"))
            if not xt or xt < start:
                continue
            entry = buy.get("price"); exitp = tr.get("price")
            pnl = tr.get("pnl")                       # REAL dollar P&L from the sim
            rp = ((exitp / entry - 1) * 100) if (entry and exitp) else None
            # win/loss is decided by the REAL pnl sign, never by a recomputed price
            if pnl is None:
                outcome = "flat"
            elif pnl > 0.005:
                outcome = "win"
            elif pnl < -0.005:
                outcome = "loss"
            else:
                outcome = "flat"
            # exit reason: honest reconstruction from real price vs champion target/stop
            if outcome == "flat":
                reason = "TIMEOUT_FLAT"
            elif rp is not None and tgt_pct and rp >= tgt_pct * 0.97:
                reason = "TARGET_HIT"
            elif rp is not None and stop_pct and rp <= -stop_pct * 0.97:
                reason = "STOP_HIT"
            elif outcome == "win":
                reason = "TIMEOUT_GAIN"
            else:
                reason = "TIMEOUT_LOSS"
            et = _dt(buy.get("t"))
            hold = round((xt - et).total_seconds() / 60) if (et and xt) else None
            out.append({
                "sym": sym, "entry": entry, "exit": exitp, "qty": tr.get("qty"),
                "pnl_usd": round(pnl, 2) if pnl is not None else None,
                "realized_pct": round(rp, 3) if rp is not None else None,
                "entry_t": buy.get("t"), "exit_t": tr.get("t"),
                "hold_min": hold, "exit_reason": reason, "outcome": outcome,
            })
    return out

def build_session_reconstruction(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    now = _now(); start = _session_start(now)
    gov = _load(out, "CHAMPION_GOVERNANCE.json")
    champ = (gov.get("declared_champion") or {}).get("strategy")
    tgt, stop = _ts_params(champ)
    proms = gov.get("recent_promotions") or gov.get("promotion_history") or []
    rotated = [p for p in proms if _dt(p.get("at")) and _dt(p.get("at")) >= start]

    books_out: Dict[str, Any] = {}
    for book in ("crypto", "stock", "metal", "energy"):
        bk = _load(out, f"paper_book_{book}.json")
        rts = _pair_book(bk.get("trades", []), tgt, stop, start)
        if not rts and book in ("metal", "energy"):
            books_out[book] = {"round_trips": 0, "note": "idle this session"}
            continue
        wins = [t for t in rts if t["outcome"] == "win"]
        losses = [t for t in rts if t["outcome"] == "loss"]
        flats = [t for t in rts if t["outcome"] == "flat"]
        bypnl = defaultdict(float); bycnt = defaultdict(int)
        for t in rts:
            bypnl[t["sym"]] += (t["pnl_usd"] or 0); bycnt[t["sym"]] += 1
        reasons = defaultdict(int)
        for t in rts: reasons[t["exit_reason"]] += 1
        total = round(sum(t["pnl_usd"] or 0 for t in rts), 2)
        top = sorted(bypnl.items(), key=lambda x: -x[1])
        concentration = (round(top[0][1] / total * 100, 1) if (top and total > 0) else None)
        books_out[book] = {
            "round_trips": len(rts), "wins": len(wins), "losses": len(losses), "flat": len(flats),
            "win_rate_pct": round(len(wins) / len(rts) * 100, 1) if rts else None,
            "realized_usd": total,
            "exit_reasons": dict(reasons),
            "top_symbols": [{"sym": s, "usd": round(v, 2), "trips": bycnt[s]} for s, v in top[:8]],
            "top_symbol_share_pct": concentration,
            "trades": sorted(rts, key=lambda x: x["exit_t"] or ""),
        }

    payload = {
        "generated_at": now.isoformat(),
        "session_start_utc": start.isoformat(),
        "session_label": "since 1 PM Vegas (20:00 UTC)",
        "champion_during_session": champ,
        "champion_rotated_during_session": bool(rotated),
        "rotations_in_window": rotated,
        "fingerprint": {                       # what to preserve to recreate this session
            "champion": champ, "target_pct": tgt, "stop_pct": stop,
            "captured_at": now.isoformat(),
            "crypto_realized_usd": (books_out.get("crypto") or {}).get("realized_usd"),
            "crypto_win_rate_pct": (books_out.get("crypto") or {}).get("win_rate_pct"),
        },
        "by_book": books_out,
        "status_label": "OBSERVATIONAL ONLY — reconstructs what happened; changes nothing.",
        "what": "A black-box recorder of the current session: every trade, why it ended, who the champion was.",
        "why": ("To answer 'why did crypto work today' with real evidence and preserve the config so it "
                "can be recreated — not extrapolated, not synthetic."),
        "honest_note": ("Exit reasons reconstructed by comparing REAL exit prices to the session "
                        "champion's target/stop; dollar P&L and timestamps are the real fills. Every "
                        "trade in the window is included (no 30-trade cap). If the champion's biggest "
                        "symbol share is high, that is concentration risk shown honestly, not hidden."),
    }
    try: write_json_atomic(out / "SESSION_TODAY.json", payload)
    except Exception: pass
    return payload
