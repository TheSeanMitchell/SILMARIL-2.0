"""
silmaril.execution.compounding_projection — COMPOUNDING PROJECTION (2.5.4).

Projects what the current champion would grow $10k into if its observed per-trade edge and
trade frequency held, compounded over 1d/3d/1w/2w/3w/4w/3mo/1yr — compared against passively
holding BTC over the same span. This is a PROJECTION assuming the edge persists (it may not);
it is labeled as such, not a promise. Emits COMPOUNDING_PROJECTION.json.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from ._trade_helpers import closed_trades, _dt
from .atomic_io import write_json_atomic

def _now(): return datetime.now(timezone.utc).isoformat()
HORIZONS = [("1d", 1), ("3d", 3), ("1w", 7), ("2w", 14), ("3w", 21), ("4w", 28), ("3mo", 90), ("1y", 365)]
BASE = 10000.0

def build_compounding_projection(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    # champion strategy only — compounding ONE book's capital, not every arena book combined
    try:
        champ = (json.loads((out / "CHAMPION_GOVERNANCE.json").read_text())
                 .get("declared_champion", {}) or {}).get("strategy")
    except Exception:
        champ = None
    allt = [t for t in closed_trades(out) if t["book"] == "crypto"]
    trades = [t for t in allt if champ and t["strategy"] == champ] or allt
    if not trades:
        payload = {"generated_at": _now(), "status": "no_trades_yet",
                   "note": "Need closed crypto trades to project compounding."}
        try: write_json_atomic(out / "COMPOUNDING_PROJECTION.json", payload)
        except Exception: pass
        return payload
    rets = [t["realized_pct"] for t in trades]
    expectancy = sum(rets) / len(rets)
    ts = sorted([_dt(t["exit_t"]) for t in trades if _dt(t["exit_t"])])
    span_days = max(1.0, (ts[-1] - ts[0]).total_seconds() / 86400) if len(ts) > 1 else 1.0
    trades_per_day = min(3.0, len(trades) / span_days)      # cap at a sane ceiling for $10k/few positions
    daily_factor = (1 + expectancy / 100.0) ** trades_per_day
    daily_pct = (daily_factor - 1) * 100

    # passive BTC over same span (per-day)
    btc_daily_pct = None
    try:
        ps = json.loads((out / "price_samples.json").read_text()).get("samples", {})
        b = [p for _, p in ps.get("BTC-USD", []) if p and p > 0]
        if len(b) > 2:
            tot = (b[-1] / b[0] - 1) * 100
            btc_daily_pct = ((1 + tot / 100) ** (1 / span_days) - 1) * 100
    except Exception:
        pass

    proj = {}
    for label, days in HORIZONS:
        val = BASE * (daily_factor ** days)
        row = {"champion_value": round(val, 2), "champion_return_pct": round((val / BASE - 1) * 100, 1),
               "credible": days <= 14}     # beyond ~4 weeks naive compounding is not believable
        if btc_daily_pct is not None:
            bv = BASE * ((1 + btc_daily_pct / 100) ** days)
            row["passive_btc_value"] = round(bv, 2)
            row["passive_btc_return_pct"] = round((bv / BASE - 1) * 100, 1)
        proj[label] = row

    payload = {
        "generated_at": _now(), "status": "active", "baseline": BASE,
        "per_trade_expectancy_pct": round(expectancy, 3),
        "trades_per_day": round(trades_per_day, 2),
        "daily_compounded_pct": round(daily_pct, 3),
        "observed_span_days": round(span_days, 1), "trades_observed": len(trades),
        "projections": proj,
        "passive_btc_daily_pct": round(btc_daily_pct, 3) if btc_daily_pct is not None else None,
        "what": "If the champion's observed edge + trade pace held, what $10k becomes over time.",
        "why": "Turns per-trade edge into the number that matters: compounded growth vs just holding BTC.",
        "honest_warning": ("PROJECTION, NOT A PROMISE. It assumes the current edge and frequency persist "
                           "unchanged — they very likely will not over weeks/months. Tiny per-trade noise "
                           "compounds into wild long-horizon numbers; treat 3mo/1y as illustrative only. "
                           f"Based on just {len(trades)} trades over {round(span_days,1)} days."),
    }
    try: write_json_atomic(out / "COMPOUNDING_PROJECTION.json", payload)
    except Exception: pass
    return payload
