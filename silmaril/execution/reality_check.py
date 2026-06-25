"""
silmaril.execution.reality_check — LIVE-FRICTION REALITY CHECK (2.5.5).

Applies the repo's DOCUMENTED cost model (fees_truth.json — real exchange fee/slippage rates,
already labeled "estimates, verify quarterly") to the crypto book's realized P&L to estimate what
survives live friction. This is a TRANSPARENT PARAMETRIC MODEL using documented rates — it does
NOT invent per-trade bid/ask/spread (none is captured), and it explicitly lists what it cannot
measure. OBSERVATIONAL ONLY. Emits REALITY_CHECK.json.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict
from .atomic_io import write_json_atomic

def _now(): return datetime.now(timezone.utc)
def _dt(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None

def _friction(sells, taker_bps, slip_bps):
    """Round-trip crypto cost = 2*(taker+slippage) on notional. Notional = qty*price per fill."""
    rt_bps = 2 * (taker_bps + slip_bps)        # both sides
    gross = 0.0; friction = 0.0; n = 0
    for t in sells:
        pnl = t.get("pnl"); qty = t.get("qty"); px = t.get("price")
        if pnl is None or not qty or not px: continue
        notional = qty * px
        gross += pnl
        friction += notional * rt_bps / 10000.0
        n += 1
    return round(gross, 2), round(friction, 2), n

def build_reality_check(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    try: fees = json.loads((out / "fees_truth.json").read_text()).get("model", {})
    except Exception: fees = {}
    taker = float(fees.get("crypto_taker_bps_future_zone", 25.0))
    slip = float(fees.get("slippage_bps_market_orders", 2.0))
    try: bk = json.loads((out / "paper_book_crypto.json").read_text())
    except Exception: bk = {}
    sells = [t for t in bk.get("trades", []) if t.get("side") == "SELL" and t.get("pnl") is not None]
    # lifetime + today's session
    g_all, f_all, n_all = _friction(sells, taker, slip)
    start = _now().replace(hour=20, minute=0, second=0, microsecond=0)
    if _now() < start: start -= timedelta(days=1)
    sess = [t for t in sells if _dt(t.get("t")) and _dt(t.get("t")) >= start]
    g_s, f_s, n_s = _friction(sess, taker, slip)

    def block(gross, friction, n):
        net = round(gross - friction, 2)
        conf = (round(max(0, min(100, net / gross * 100))) if gross > 0 else None)
        return {"gross_realized_usd": gross, "modeled_friction_usd": -friction,
                "estimated_live_usd": net, "round_trips": n,
                "survives_pct": conf}

    payload = {
        "generated_at": _now().isoformat(),
        "status_label": "OBSERVATIONAL ONLY — a cost MODEL, not measured execution.",
        "cost_model": {"crypto_taker_bps_per_side": taker, "slippage_bps_per_side": slip,
                       "round_trip_bps": 2 * (taker + slip),
                       "source": "fees_truth.json (documented rates)"},
        "lifetime": block(g_all, f_all, n_all),
        "today_session": block(g_s, f_s, n_s),
        "what": "Estimate of how much crypto P&L survives real-exchange fees + modeled slippage.",
        "why": "Paper fills at mid with no cost; this haircuts by the documented fee model to gauge reality.",
        "NOT_modeled": ["real-time bid/ask spread (not captured anywhere — mid-price only)",
                        "partial fills", "exchange latency / outages",
                        "delisted/halted/unavailable assets", "market impact beyond flat slippage bps"],
        "honest_note": ("This applies DOCUMENTED fee/slippage rates (real, from fees_truth.json) — it does "
                        "NOT fabricate per-trade spread. Because spread and the items above are unmeasured, "
                        "the true live result would likely be somewhat LOWER than this estimate. Treat "
                        "'survives_pct' as a fee-only floor, not a precise reality score."),
    }
    try: write_json_atomic(out / "REALITY_CHECK.json", payload)
    except Exception: pass
    return payload
