"""
silmaril.execution.opportunity_journal — MISSED-MOVER JOURNAL (7.1 sanity rebuild).

THE 2026-07-25 COMPLAINT, verbatim: "Why am I seeing all of this: 99.7% of 399 tradable
movers missed … BRENT +41.8% — not tradeable (stale/ghost — can't fill) … What?"

Three defects, all fixed here:
  1. THE MOVE WAS ALL-TIME, NOT A MOVE. peak was the best trough→peak across the ENTIRE
     stored series (weeks), so BRENT "offered 41.8%" from some long-dead low. The move is
     now measured over the last 48h of LIVE prints only (backfill daily candles excluded
     by the T00:00:00 law), which is the only window a live dip-buyer could have played.
  2. GHOSTS HEADLINED THE LIST. A name whose feed is frozen CANNOT be filled — it is not
     a "missed tradable mover", it is an excluded name. Ghosts and closed-market names no
     longer appear in the journal or the missed%; they are counted in `excluded` with the
     reason, one line, done.
  3. NON-CANONICAL TWINS PARADED (REQUSDT, LMWRUSDT). The dedupe only fired on dashed
     keys. Loading now goes through the one-key law (canon_keys.canonical_samples), so a
     second spelling of the same coin cannot exist to be listed.

Everything else is preserved: the audit's EXACT-rule join, the capital-committed rows,
the stuck-position list. Writes docs/data/opportunity_journal.json. Tripwire: T109.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .paper_sim import _is_crypto, is_tradeable, load_all_samples, asset_class


def _now():
    return datetime.now(timezone.utc).isoformat()


def _live_window(raw: List, hours: float = 48.0) -> List[float]:
    """Live prints only (no backfill candles), inside the window, in time order."""
    cut = datetime.now(timezone.utc).timestamp() - hours * 3600.0
    out = []
    for t, p in (raw or []):
        ts = str(t)
        if not p or float(p) <= 0 or "T00:00:00" in ts:
            continue
        try:
            tt = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
        if tt >= cut:
            out.append(float(p))
    return out


def build_opportunity_journal(out_dir, min_move=0.04) -> Dict[str, Any]:
    out = Path(out_dir)
    samples = load_all_samples(out)   # 7.1: canonical — one spelling per asset, unioned history
    try:
        from .lifecycle import classify_state
    except Exception:
        classify_state = lambda px, i: "?"
    try:
        from .market_calendar import equity_day_status
        _eq_status, _eq_reason = equity_day_status()
    except Exception:
        _eq_status, _eq_reason = "OPEN", ""
    traded = set()
    for bp in out.glob("paper_book_*.json"):
        try:
            for tr in json.loads(bp.read_text()).get("trades", []):
                traded.add(tr.get("sym", ""))
        except Exception:
            pass
    try:
        _audit = (json.loads((out / "OPPORTUNITY_AUDIT.json").read_text()).get("by_ticker") or {})
    except Exception:
        _audit = {}
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

    rows: List[Dict[str, Any]] = []
    excluded = {"stale_ghost": 0, "closed_market": 0, "too_thin": 0, "spike_suspect": 0}
    for tk, raw in samples.items():
        cls = asset_class(tk)
        win = _live_window(raw, 48.0)
        if len(win) < 20:
            # thin live window: either a new name or a quiet/closed feed — never a "missed mover"
            if cls != "crypto" and _eq_status == "CLOSED":
                excluded["closed_market"] += 1
            else:
                excluded["too_thin"] += 1
            continue
        allpx = [p for _, p in raw if p and p > 0]
        fresh = is_tradeable(allpx)
        if not fresh:
            if cls != "crypto" and _eq_status == "CLOSED":
                excluded["closed_market"] += 1
            else:
                excluded["stale_ghost"] += 1
            continue   # a name that cannot fill is EXCLUDED, not "missed"
        # best playable trough→peak inside the live 48h window only
        trough = win[0]; peak = 0.0
        for p in win:
            if p < trough:
                trough = p
            if trough > 0:
                peak = max(peak, p / trough - 1)
        if peak < min_move:
            continue
        if peak > 0.50:
            excluded["spike_suspect"] += 1
            continue
        vel = win[-1] / win[-4] - 1 if len(win) >= 4 and win[-4] > 0 else 0.0
        st = classify_state(win, len(win) - 1)
        _ar = _audit.get(tk) or {}
        if tk in _open:
            why = f"CAPITAL COMMITTED — open position in the {_open[tk]} book (rode the move, not yet banked)"
        elif tk in traded:
            why = "captured / attempted"
        elif _ar.get("reason"):
            why = f"{_ar.get('decision','')}: {_ar['reason']}"
        else:
            why = ("not a candidate (no oversold entry triggered — dip-buyer is blind to pure "
                   "strength; TREND_RS is the roadmapped answer)")
        rows.append({"ticker": tk, "asset": cls, "state": st,
                     "peak_available_pct": round(peak * 100, 1),
                     "window_h": 48,
                     "price_velocity_pct": round(vel * 100, 2),
                     "tradeable": True, "captured": tk in traded, "why": why})
    rows.sort(key=lambda r: r["peak_available_pct"], reverse=True)
    missed = [r for r in rows if not r["captured"]]
    payload = {"generated_at": _now(), "window_h": 48, "movers_logged": len(rows),
               "captured": sum(1 for r in rows if r["captured"]),
               "missed": len(missed),
               "pct_of_movers_missed": round(len(missed) / len(rows) * 100, 1) if rows else 0,
               "journal": rows[:60],
               "excluded": excluded,
               "excluded_note": ("names that COULD NOT be filled are not 'missed movers': "
                                 "stale/ghost feeds, closed markets (%s), thin live windows and "
                                 ">50%%/48h integrity-suspect spikes are counted here, never in "
                                 "the missed%%" % (_eq_reason or "weekend/holiday")),
               "stuck_positions": sorted(_stuck, key=lambda r: -r["wager_usd"])[:10],
               "pair_with": "DECISION_TRACE.json — this journal says WHY we missed; the trace says WHY each taken trade lived and died",
               "note": ("Every FILLABLE mover >=4% over the last 48h of LIVE prints (backfill "
                        "candles excluded), canonical keys only. 'why' is the missed-opportunity "
                        "taxonomy. Training fuel.")}
    try:
        (out / "opportunity_journal.json").write_text(json.dumps(payload, indent=2))
    except Exception:
        pass
    return payload


if __name__ == "__main__":
    import sys
    print(json.dumps(build_opportunity_journal(sys.argv[1] if len(sys.argv) > 1 else "docs/data"))[:300])
