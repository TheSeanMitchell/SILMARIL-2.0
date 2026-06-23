"""
silmaril.execution.lifecycle — ATTENTION LIFECYCLE ENGINE (Alpha 2.13).

One unified state machine instead of separate momentum/persistence/exhaustion
engines. Every ticker gets a state from its own price dynamics:

  BIRTH        flat, just turning up
  ACCELERATION rising and speeding up
  PERSISTENCE  rising steadily
  EXPANSION    rising strongly across every window
  CLIMAX       parabolic and decelerating (a top)
  EXHAUSTION   was up, now rolling over
  DECAY        falling

Built MEASUREMENT FIRST, per the locked gameplan: before a single dollar is wired
to a state, this proves whether the state predicts forward returns. It classifies
every ticker at every point in history (no lookahead — state uses only past bars)
and measures the realized forward return that followed each state, net of cost.

If a state cleanly predicts forward direction (e.g. DECAY → bounce, CLIMAX →
drop), it is a real, tradeable signal and the capital router can use it. If the
forward returns are flat across states, the lifecycle is pretty narrative with no
edge, and we say so rather than wiring it. No state earns capital on its name
alone — only on its forward-return evidence.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional

# windows in samples (~11-min cadence): ~30m / ~2h / ~6h, forward ~1h
W_SHORT, W_MED, W_LONG, W_FWD = 3, 12, 36, 6
COST = 0.003

STATES = ["BIRTH", "ACCELERATION", "PERSISTENCE", "EXPANSION",
          "CLIMAX", "EXHAUSTION", "CAPITULATION", "DECAY", "NEUTRAL"]


def _ret(px: List[float], i: int, k: int) -> Optional[float]:
    if i - k < 0 or px[i - k] <= 0:
        return None
    return px[i] / px[i - k] - 1


def classify_state(px: List[float], i: int) -> str:
    """State at index i from PAST bars only (no lookahead)."""
    rs = _ret(px, i, W_SHORT)
    rm = _ret(px, i, W_MED)
    rl = _ret(px, i, W_LONG)
    if rs is None or rm is None:
        return "NEUTRAL"
    rl = rl if rl is not None else rm
    # acceleration: is the short-window slope speeding up vs the prior bar?
    rs_prev = _ret(px, i - 1, W_SHORT)
    accel = (rs - rs_prev) if rs_prev is not None else 0.0

    # most extreme first
    if rm >= 0.10 and accel < 0:
        return "CLIMAX"                       # parabolic, rolling
    if rm >= 0.02 and rs <= -0.01:
        return "EXHAUSTION"                   # uptrend turning down
    if rm <= -0.05:
        return "CAPITULATION"                 # deep flush — the bounce signal
    if rm <= -0.02:
        return "DECAY"                        # mild pullback
    if rs > 0 and rm >= 0.03 and rl > 0:
        return "EXPANSION"                    # strong sustained up
    if rs >= 0.01 and accel > 0:
        return "ACCELERATION"                 # rising and speeding up
    if rs > 0 and rm > 0:
        return "PERSISTENCE"                  # steady up
    if abs(rl) < 0.01 and rs > 0:
        return "BIRTH"                        # flat base, just turning up
    return "NEUTRAL"


def _stats(xs: List[float]) -> Dict[str, Any]:
    if len(xs) < 30:
        return {"n": len(xs), "fwd_net_pct": None, "hit_pct": None, "t_stat": None}
    m = mean(xs)
    sd = pstdev(xs) or 1e-9
    return {"n": len(xs),
            "fwd_net_pct": round((m - COST) * 100, 3),
            "fwd_gross_pct": round(m * 100, 3),
            "hit_pct": round(sum(1 for x in xs if x > 0) / len(xs) * 100, 1),
            "t_stat": round(m / (sd / math.sqrt(len(xs))), 2)}


def measure_lifecycle(out_dir) -> Dict[str, Any]:
    """Classify every ticker at every point; measure the forward return that
    followed each state. This is the evidence the engine stands or falls on."""
    out = Path(out_dir)
    try:
        from .paper_sim import load_all_samples, is_tradeable
        samples = load_all_samples(out)
    except Exception:
        try:
            samples = json.loads((out / "price_samples.json").read_text()).get("samples", {})
        except Exception as e:
            return {"error": str(e)}
        is_tradeable = lambda p: True  # noqa

    by_state: Dict[str, List[float]] = {s: [] for s in STATES}
    current: Dict[str, str] = {}                 # latest state per ticker (for live)
    for tk, rows in samples.items():
        px = [p for _, p in rows if p and p > 0]
        n = len(px)
        if n < W_LONG + W_FWD + 2:
            continue
        try:
            if not is_tradeable(px):
                continue
        except Exception:
            pass
        for i in range(W_LONG, n - W_FWD):
            st = classify_state(px, i)
            fwd = _ret(px, i + W_FWD, W_FWD)     # return AFTER point i
            if fwd is not None:
                by_state[st].append(fwd)
        current[tk] = classify_state(px, n - 1)

    table = {s: _stats(by_state[s]) for s in STATES}
    # which states are tradeable signals (significant forward edge net of cost)?
    longs = [s for s in STATES if (table[s]["fwd_net_pct"] or 0) > 0
             and (table[s]["t_stat"] or 0) >= 3]
    shorts = [s for s in STATES if (table[s]["fwd_net_pct"] or 0) < 0
              and (table[s]["t_stat"] or 0) <= -3]
    # distribution of current states across the live universe
    dist: Dict[str, int] = {s: 0 for s in STATES}
    for s in current.values():
        dist[s] = dist.get(s, 0) + 1

    verdict = ("lifecycle has NO forward edge — narrative only, do not wire to capital"
               if not longs and not shorts else
               f"PREDICTIVE states — long: {longs or 'none'} | avoid/short: {shorts or 'none'}")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "forward_return_by_state": table,
        "tradeable_long_states": longs,
        "avoid_or_short_states": shorts,
        "current_state_distribution": dist,
        "current_states_sample": dict(list(current.items())[:40]),
        "verdict": verdict,
        "note": ("Forward return = realized ~1h return AFTER the state, net of "
                 "0.3% cost, no lookahead. A state is a real signal only at |t|>=3. "
                 "States with no significant edge are narrative, not tradeable."),
    }
    try:
        (out / "lifecycle.json").write_text(json.dumps(payload, indent=2))
    except Exception:
        pass
    return payload


if __name__ == "__main__":
    import sys
    p = measure_lifecycle(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("VERDICT:", p.get("verdict"))
    print(f"\n{'STATE':14s}{'n':>8}{'fwd_net%':>10}{'hit%':>7}{'t':>7}")
    for s, st in p.get("forward_return_by_state", {}).items():
        if st.get("n", 0) >= 30:
            print(f"{s:14s}{st['n']:>8}{st['fwd_net_pct']:>+9.3f}%{st['hit_pct']:>6.0f}%{st['t_stat']:>+7.1f}")
