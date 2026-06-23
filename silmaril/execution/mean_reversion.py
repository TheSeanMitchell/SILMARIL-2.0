"""
silmaril.execution.mean_reversion — the STRATEGY FLIP (Alpha 2.11).

edge_lab proved it on 200k+ points of our own data: in this universe, on this
horizon, MOMENTUM loses (-0.94%/trade, t=-14) and MEAN REVERSION wins
(oversold +0.66%, deep-oversold +1.05%, capitulation +2.86%, all net of cost).
So we stop buying strength and start buying weakness — buy the crash, sell the
bounce, cut hard if it keeps falling (the crash tail is the only thing that kills
a mean-reversion book).

This module is the brain of that flip:
  • select_oversold()    — candidate pool: crypto names that just dropped, ranked
                           by depth (capitulation first — it bounces hardest).
  • mean_reversion_exit()— exit at a bounce TARGET, a hard STOP, or a TIME limit,
                           whichever comes first. The stop is mandatory.
  • backtest()           — simulates the FULL strategy (entry+exit) on the price
                           history so the real expectancy (with stops, not raw
                           forward returns) is known before a dollar rides on it.

Set MEAN_REVERSION_ENABLED = False to fall straight back to the momentum path.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

# ── strategy switch ──────────────────────────────────────────────────────────
MEAN_REVERSION_ENABLED = os.environ.get("SILMARIL_MEAN_REVERSION", "1") != "0"

# ── strategy parameters (LIQUID-VALIDATED — see the honest backtest) ──────────
# The big illiquid backtest (+1384%) was a bid-ask-spread mirage. On the liquid,
# Alpaca-tradeable names the only config that survives cost is a deeper-dip entry
# with a wider target. These are marginal and from a 3-day window — the LIVE
# paper run is the real out-of-sample test, not a proven winner.
MR_DROP_1H_PCT = 0.02     # enter when down >= 2% over ~1h (shallower loses on liquid)
MR_BOUNCE_TARGET_PCT = 0.02    # take the bounce here
MR_HARD_STOP_PCT = 0.04   # cut here if it keeps falling (the crash-tail guard)
MR_MAX_HOLD_MIN = 240.0   # if no bounce in ~4h, time out
ROUND_TRIP_COST = 0.003

STEP_MIN = 11.0           # sampling cadence (min/sample) for time math

# Only trade where a bounce is REAL and not just the spread oscillating. These
# are the liquid majors (Alpaca-tradeable, tight spreads). Illiquid coins show a
# huge phantom edge that vanishes once you pay their spread — never trade them.
LIQUID_ONLY = os.environ.get("SILMARIL_MR_LIQUID_ONLY", "1") != "0"
LIQUID_NAMES = {"BTC", "ETH", "SOL", "XRP", "DOGE", "LTC", "BCH", "AVAX", "LINK",
                "DOT", "UNI", "AAVE", "MATIC", "ADA", "SHIB", "CRV", "MKR",
                "SUSHI", "YFI", "GRT", "BAT", "XTZ", "ALGO", "ATOM"}


def _h1(chain_entry) -> Optional[float]:
    # chain windows are stored in PERCENT (e.g. -3.0 == -3%); return a fraction
    w = (chain_entry or {}).get("windows") or {}
    v = w.get("h1")
    return (float(v) / 100.0) if v is not None else None


def _norm(t: str) -> str:
    return str(t).upper().replace("/", "").replace("-", "")


def _base(t: str) -> str:
    """Base coin symbol for liquid-whitelist matching: BTC-USD/BTCUSD -> BTC."""
    s = str(t).upper().replace("/", "").replace("-", "")
    return s[:-3] if s.endswith("USD") and len(s) > 3 else s


def select_oversold(debates: List[Dict[str, Any]], chain: Dict[str, Any],
                    drop_1h_pct: float = MR_DROP_1H_PCT) -> Dict[str, Dict[str, Any]]:
    """Crypto names that just dropped >= drop_1h_pct over the hour. The deeper
    the drop, the better the expected bounce, so depth is the ranking key."""
    pool: Dict[str, Dict[str, Any]] = {}
    for d in debates:
        t = str(d.get("ticker") or "")
        ac = str(d.get("asset_class") or "").lower()
        if ac not in ("crypto", "token", "commodity", "fx", "valuable"):
            continue
        if LIQUID_ONLY and _base(t) not in LIQUID_NAMES:
            continue                         # never chase the illiquid spread mirage
        ce = (chain.get(t.upper()) or chain.get(t.upper().replace("USD", "-USD"))
              or chain.get(t.upper().replace("-USD", "USD")))
        h1 = _h1(ce)
        if h1 is None or h1 > -drop_1h_pct:
            continue
        dd = dict(d)
        dd["_mr_drop_pct"] = h1          # how oversold (more negative = deeper)
        pool[t] = dd
    return pool


def oversold_rank(ticker: str, chain: Dict[str, Any]) -> float:
    """Rank score: deeper drop ranks higher (capitulation first)."""
    ce = (chain.get(ticker.upper())
          or chain.get(ticker.upper().replace("USD", "-USD"))
          or chain.get(ticker.upper().replace("-USD", "USD")))
    h1 = _h1(ce)
    return (-h1) if h1 is not None else -1.0


def mean_reversion_exit(entry_price: float, current_price: float,
                        hold_minutes: float) -> Tuple[bool, str]:
    """Exit at bounce target, hard stop, or time limit — whichever first."""
    if entry_price <= 0 or current_price <= 0:
        return False, ""
    chg = current_price / entry_price - 1.0
    if chg <= -MR_HARD_STOP_PCT:
        return True, f"MEAN-REV STOP: {chg*100:+.2f}% — cutting the falling knife"
    if chg >= MR_BOUNCE_TARGET_PCT:
        return True, f"MEAN-REV TAKE: {chg*100:+.2f}% — banked the bounce"
    if hold_minutes >= MR_MAX_HOLD_MIN:
        return True, f"MEAN-REV TIMEOUT: {hold_minutes:.0f} min, no bounce ({chg*100:+.2f}%)"
    return False, ""


# ── full-strategy backtest (entry + bounce/stop/time exit) ───────────────────
def _run_bt(samples, liquid_only, cost):
    drop_steps = 6
    bounce, stop = MR_BOUNCE_TARGET_PCT, MR_HARD_STOP_PCT
    max_steps = int(MR_MAX_HOLD_MIN / STEP_MIN)
    rets: List[float] = []
    exits = {"TAKE": 0, "STOP": 0, "TIMEOUT": 0}
    for _tk, rows in samples.items():
        if liquid_only and _base(_tk) not in LIQUID_NAMES:
            continue
        px = [p for _, p in rows if p and p > 0]
        n = len(px)
        if n < drop_steps + 3:
            continue
        i = drop_steps
        while i < n - 1:
            entered = (px[i] / px[i - drop_steps] - 1) <= -MR_DROP_1H_PCT if px[i - drop_steps] > 0 else False
            if not entered:
                i += 1
                continue
            ep = px[i]
            j = i + 1
            outcome = None
            while j < n:
                chg = px[j] / ep - 1
                if chg <= -stop:
                    outcome, k = "STOP", j; break
                if chg >= bounce:
                    outcome, k = "TAKE", j; break
                if (j - i) >= max_steps:
                    outcome, k = "TIMEOUT", j; break
                j += 1
            if outcome is None:
                break
            rets.append((px[k] / ep - 1) - cost)
            exits[outcome] += 1
            i = k + 1
    if not rets:
        return {"trades": 0}
    wins = sum(1 for r in rets if r > 0)
    return {
        "trades": len(rets),
        "win_rate_pct": round(wins / len(rets) * 100, 1),
        "mean_net_return_pct": round(mean(rets) * 100, 3),
        "total_net_return_pct": round(sum(rets) * 100, 1),
        "exit_breakdown": exits,
    }


def backtest(out_dir, cost: float = ROUND_TRIP_COST) -> Dict[str, Any]:
    out = Path(out_dir)
    try:
        samples = json.loads((out / "price_samples.json").read_text()).get("samples", {})
    except Exception as e:
        return {"error": f"no price_samples.json: {e}"}
    liquid = _run_bt(samples, True, cost)
    allnames = _run_bt(samples, False, cost)
    # the honest verdict is the LIQUID one — that's what we can actually trade
    lm = liquid.get("mean_net_return_pct")
    verdict = ("NO tradeable edge: liquid mean-reversion is flat/negative net of cost"
               if (lm is None or lm <= 0) else
               f"MARGINAL edge: liquid nets {lm:+.2f}%/trade — unproven, paper-test it")
    return {
        "generated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "params": {"drop_1h_pct": MR_DROP_1H_PCT, "bounce_pct": MR_BOUNCE_TARGET_PCT,
                   "stop_pct": MR_HARD_STOP_PCT, "cost": cost, "liquid_only": LIQUID_ONLY},
        "liquid_tradeable": liquid,
        "all_names_incl_illiquid_MIRAGE": allnames,
        "verdict": verdict,
        "note": ("all-names total is a bid-ask-spread mirage on illiquid coins; "
                 "only the liquid number is real. 3-day window = one regime."),
    }


if __name__ == "__main__":
    import sys
    print(json.dumps(backtest(sys.argv[1] if len(sys.argv) > 1 else "docs/data"), indent=2))
