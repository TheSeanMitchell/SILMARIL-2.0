"""
silmaril.execution.session_anatomy — TRADE-BY-TRADE ANATOMY OF TODAY'S SESSION (2.5.5).

For every session trade, replays the REAL price path from price_samples to expose, with zero
synthetic data:
  - ENTRY trigger: how deep the dip was at buy time (entry vs the recent pre-entry high),
  - MFE (max favorable excursion): the best price reachable during the hold = the perfect exit,
  - MAE (max adverse excursion): the worst drawdown taken during the hold,
  - CAPTURE EFFICIENCY: what % of the available up-move we actually banked (exit vs MFE),
  - POST-EXIT drift: how much more the price offered right after we sold (did we leave money?),
  - a verdict per trade: CAPTURED_WELL / SOLD_TOO_EARLY / GAVE_BACK / FLAT_TIMEOUT.
Then aggregates: avg dip depth, avg capture, how often we left money, and a MKR-vs-rest split so
today's concentration is dissected, not hidden. OBSERVATIONAL ONLY. Emits SESSION_ANATOMY.json.
"""
from __future__ import annotations
import json
from datetime import timedelta
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, List
from ._trade_helpers import price_series, _dt
from .atomic_io import write_json_atomic

def _load(out, n, d=None):
    try: return json.loads((out / n).read_text())
    except Exception: return d if d is not None else {}

LOOKBACK_MIN = 60     # window before entry to measure the dip from
FORWARD_MIN = 60      # window after exit to measure what was left on the table

def _anatomy(t, ser):
    et, xt = _dt(t["entry_t"]), _dt(t["exit_t"])
    entry, exitp = t.get("entry"), t.get("exit")
    if not (et and xt and entry and exitp and ser):
        return None
    hold = [p for d, p in ser if et <= d <= xt and p > 0]
    before = [p for d, p in ser if et - timedelta(minutes=LOOKBACK_MIN) <= d < et and p > 0]
    after = [p for d, p in ser if xt < d <= xt + timedelta(minutes=FORWARD_MIN) and p > 0]
    mfe = max(hold) if hold else exitp
    mae = min(hold) if hold else entry
    mfe_pct = round((mfe / entry - 1) * 100, 2)
    mae_pct = round((mae / entry - 1) * 100, 2)
    capture = round((exitp - entry) / (mfe - entry) * 100, 1) if mfe > entry else None
    dip_pct = round((entry / max(before) - 1) * 100, 2) if before else None   # how deep the entry dip was
    post_high = max(after) if after else exitp
    left_pct = round((post_high / exitp - 1) * 100, 2) if after else None     # more that was available after exit
    # verdict
    if t.get("outcome") == "flat":
        verdict = "FLAT_TIMEOUT"
    elif left_pct is not None and left_pct > 0.5:
        verdict = "SOLD_TOO_EARLY"      # price kept climbing after we sold
    elif capture is not None and capture < 60:
        verdict = "GAVE_BACK"           # we banked under 60% of the up-move we saw
    else:
        verdict = "CAPTURED_WELL"
    return {**t, "dip_at_entry_pct": dip_pct, "mfe_pct": mfe_pct, "mae_pct": mae_pct,
            "capture_efficiency_pct": capture, "left_on_table_pct": left_pct, "verdict": verdict}

def _agg(rows):
    if not rows:
        return None
    caps = [r["capture_efficiency_pct"] for r in rows if r["capture_efficiency_pct"] is not None]
    dips = [r["dip_at_entry_pct"] for r in rows if r["dip_at_entry_pct"] is not None]
    lefts = [r["left_on_table_pct"] for r in rows if r["left_on_table_pct"] is not None]
    maes = [r["mae_pct"] for r in rows if r["mae_pct"] is not None]
    verdicts: Dict[str, int] = {}
    for r in rows: verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
    return {
        "n": len(rows),
        "avg_dip_at_entry_pct": round(mean(dips), 2) if dips else None,
        "avg_capture_efficiency_pct": round(mean(caps), 1) if caps else None,
        "median_capture_efficiency_pct": round(median(caps), 1) if caps else None,
        "avg_left_on_table_pct": round(mean(lefts), 2) if lefts else None,
        "worst_drawdown_taken_pct": round(min(maes), 2) if maes else None,
        "avg_hold_min": round(mean([r["hold_min"] for r in rows if r.get("hold_min") is not None]), 1) if rows else None,
        "verdicts": verdicts,
    }

def build_session_anatomy(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    sess = _load(out, "SESSION_TODAY.json")
    series = price_series(out)
    crypto = ((sess.get("by_book") or {}).get("crypto") or {}).get("trades") or []
    rows = [a for a in (_anatomy(t, series.get(t["sym"]) or []) for t in crypto) if a]

    # MKR vs the rest — dissect the concentration
    top_sym = None
    tops = ((sess.get("by_book") or {}).get("crypto") or {}).get("top_symbols") or []
    if tops: top_sym = tops[0]["sym"]
    mkr_rows = [r for r in rows if r["sym"] == top_sym]
    rest_rows = [r for r in rows if r["sym"] != top_sym]

    # DIP-DEPTH BUCKETS — the headline lesson of today: what dip depth produced what return
    def bucket_label(d):
        if d is None: return None
        a = abs(d)
        if a < 2: return "0-2% (shallow)"
        if a < 4: return "2-4%"
        if a < 6: return "4-6%"
        return "6%+ (deep)"
    buckets: Dict[str, List] = {}
    for r in rows:
        b = bucket_label(r["dip_at_entry_pct"])
        if b: buckets.setdefault(b, []).append(r)
    dip_buckets = []
    for b in ("0-2% (shallow)", "2-4%", "4-6%", "6%+ (deep)"):
        rs2 = buckets.get(b) or []
        if not rs2: continue
        rets = [r["realized_pct"] for r in rs2 if r["realized_pct"] is not None]
        caps = [r["capture_efficiency_pct"] for r in rs2 if r["capture_efficiency_pct"] is not None]
        wins = sum(1 for r in rs2 if r.get("outcome") == "win")
        dip_buckets.append({
            "dip_band": b, "trades": len(rs2),
            "avg_return_pct": round(mean(rets), 2) if rets else None,
            "win_rate_pct": round(wins / len(rs2) * 100) if rs2 else None,
            "avg_capture_pct": round(mean(caps), 1) if caps else None,
        })

    payload = {
        "generated_at": sess.get("generated_at"),
        "session_label": sess.get("session_label"),
        "status_label": "OBSERVATIONAL ONLY — dissects what happened; changes nothing.",
        "overall": _agg(rows),
        "top_symbol": top_sym,
        "top_symbol_anatomy": _agg(mkr_rows),
        "rest_anatomy": _agg(rest_rows),
        "dip_depth_buckets": dip_buckets,
        "trades": rows,
        "legend": {
            "dip_at_entry_pct": "how far price had fallen from its recent high when we BOUGHT (the MR trigger)",
            "mfe_pct": "max favorable excursion — the best exit price that existed during the hold",
            "mae_pct": "max adverse excursion — the worst drawdown we sat through",
            "capture_efficiency_pct": "% of the available up-move we actually banked (exit vs MFE)",
            "left_on_table_pct": "how much MORE the price offered in the hour after we sold",
            "verdict": "CAPTURED_WELL / SOLD_TOO_EARLY (kept climbing) / GAVE_BACK (<60% captured) / FLAT_TIMEOUT",
        },
        "what": "Trade-by-trade forensic replay of today's session against the real price path.",
        "why": ("To understand obsessively WHY each entry and exit happened and whether we captured the "
                "edge that was actually there — so the good behavior can be recognized and repeated."),
        "honest_note": ("All from real fills + real price_samples (mid-price). MFE/MAE/capture are measured "
                        "against sampled mid prices, so they describe the move that existed, not guaranteed "
                        "fills. No synthetic data; no behavior changed."),
    }
    try: write_json_atomic(out / "SESSION_ANATOMY.json", payload)
    except Exception: pass
    return payload
