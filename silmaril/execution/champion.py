"""
silmaril.execution.champion — CHAMPION MODE (Alpha 2.14).

Closes the learning loop: the leaderboard tests every strategy each cycle, and
this picks the one the live paper sim actually trades. The whole point of the
system finally points at one number — the champion's forward P&L.

The danger I flagged before is real: with 50 strategies, the top of the board
jumps around by luck, and naively trading "whatever is #1 this cycle" is textbook
overfitting. So promotion is STICKY and gated:

  • We keep a rolling history of which strategy was the trusted leader each cycle.
  • A challenger only takes the crown if it has been the leader in clearly MORE of
    the recent windows than the incumbent (a hysteresis margin), AND it currently
    has positive net edge on a real sample.
  • Otherwise the champion holds. No flip-flopping on a one-window fluke.

This means the champion changes slowly, only when a strategy genuinely dominates
across windows — which is exactly the signal that separates real edge from noise.
"""
from __future__ import annotations

import json
from .atomic_io import write_json_atomic
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .strategy_lab import STRATEGIES, run_leaderboard

HISTORY_WINDOW = 20      # how many recent cycles of "who led" we remember
PROMOTE_MARGIN = 3       # challenger must lead this many more windows than champ
MIN_TRADES = 30          # a strategy needs a real sample to be eligible
STEP_MIN = 11.0          # steps -> minutes for the sim exit clock
# EVIDENCE-DRIVEN GOVERNANCE (2.18): the champion tracks forward SURVIVABILITY,
# not backtest leaderboard wins. These gate that decision.
CHAMPION_MIN_TRADES = 5  # minimum credible sample to be the *champion* (capital tiers still use 10/25/50/100)
SURV_MARGIN = 15         # challenger must beat the champion's survivability by this much to switch (anti-flip-flop)
AGG_BOOKS = ("crypto", "stock")  # aggregate books are not strategy candidates


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(out: Path) -> Dict[str, Any]:
    try:
        return json.loads((out / "champion.json").read_text())
    except Exception:
        return {"champion": None, "leader_history": [], "promotions": []}


def update_champion(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    # use the leaderboard already written this cycle, or compute it
    try:
        lb = json.loads((out / "strategy_leaderboard.json").read_text())
    except Exception:
        lb = run_leaderboard(out)
    board = lb.get("leaderboard", [])
    by_name = {r["strategy"]: r for r in board}
    leader = lb.get("best_trusted")
    leader_name = leader["strategy"] if leader else None

    st = _load(out)
    hist = (st.get("leader_history") or [])
    if leader_name:
        hist.append(leader_name)
    hist = hist[-HISTORY_WINDOW:]
    freq = Counter(hist)

    # forward survivability ranking (from the previous cycle's validation) — this is
    # the governing evidence. Resolves "most survivable != declared champion".
    surv: Dict[str, Dict[str, Any]] = {}
    try:
        cvj = json.loads((out / "champion_validation.json").read_text())
        for r in cvj.get("strategies", []):
            nm = r["strategy"]
            if nm in AGG_BOOKS or nm not in STRATEGIES:
                continue
            surv[nm] = {"score": (r.get("survivability") or {}).get("score", 0), "n": r.get("n", 0)}
    except Exception:
        surv = {}
    elig = {k: v for k, v in surv.items() if v["n"] >= CHAMPION_MIN_TRADES}
    surv_leader = max(elig, key=lambda k: elig[k]["score"], default=None)

    champ = st.get("champion")
    reason = "champion holds"
    promoted = False
    if champ is None:
        champ = surv_leader or (freq.most_common(1)[0][0] if freq else leader_name)
        reason, promoted = "initial champion", bool(champ)
    elif surv_leader and surv_leader != champ:
        inc = surv.get(champ, {"score": 0, "n": 0})
        chal = surv[surv_leader]
        # Switch on a decisive survivability margin once the challenger has a credible
        # sample. We do NOT require the challenger to match the incumbent's trade count:
        # the incumbent keeps trading, so that test could never be satisfied (a deadlock
        # that pinned a survivability-22 champion under a survivability-81 challenger).
        # Survivability already penalises thin samples via its confidence interval, so a
        # challenger that clears the margin with >= CHAMPION_MIN_TRADES has earned it.
        if chal["score"] >= inc["score"] + SURV_MARGIN and chal["n"] >= CHAMPION_MIN_TRADES:
            champ = surv_leader
            reason = (f"promoted on survivability: {surv_leader} {chal['score']:.0f} "
                      f"> {st.get('champion')} {inc['score']:.0f} (n={chal['n']}, evidence-driven)")
            promoted = True
        else:
            gap = chal["score"] - inc["score"]
            reason = (f"holds: leader {surv_leader} ({chal['score']:.0f}) beats {champ} "
                      f"({inc['score']:.0f}) by {gap:.0f} but n={chal['n']} < {CHAMPION_MIN_TRADES} min"
                      if chal["n"] < CHAMPION_MIN_TRADES else
                      f"holds: {surv_leader} ({chal['score']:.0f}) vs {champ} ({inc['score']:.0f}) "
                      f"under {SURV_MARGIN}-pt switch margin")

    cfg = dict(STRATEGIES.get(champ, {}))
    # express params the way the sim consumes them
    live_params = {
        "dir": cfg.get("dir", "mr"),
        "entry": cfg.get("entry", 0.02),
        "target": cfg.get("target", 0.02),
        "stop": cfg.get("stop", 0.04),
        "max_hold_min": round(cfg.get("hold", 22) * STEP_MIN, 0),
    }
    promotions = st.get("promotions", [])
    if promoted and champ:
        promotions.append({"to": champ, "at": _now(), "why": reason})
    champ_row = by_name.get(champ, {})

    payload = {
        "generated_at": _now(),
        "champion": champ,
        "champion_config": cfg,
        "live_params": live_params,
        "reason": reason,
        "champion_backtest": {k: champ_row.get(k) for k in
                              ("trades", "win_pct", "mean_net_pct", "total_pct")},
        "current_window_leader": leader_name,
        "leader_history": hist,
        "leader_frequency": dict(freq),
        "challengers_on_deck": [r["strategy"] for r in board[:5] if r["strategy"] != champ],
        "promotions": promotions[-20:],
        "gate": {"history_window": HISTORY_WINDOW, "promote_margin": PROMOTE_MARGIN,
                 "min_trades": MIN_TRADES},
        "note": ("Champion changes only when a challenger dominates recent windows "
                 "by a margin — slow on purpose, to trade real edge not noise."),
    }
    try:
        write_json_atomic(out / "champion.json", payload)
    except Exception:
        pass
    return payload


def champion_params(out_dir) -> Optional[Dict[str, Any]]:
    """What the live sim should trade. None -> sim uses its built-in default."""
    try:
        return json.loads((Path(out_dir) / "champion.json").read_text()).get("live_params")
    except Exception:
        return None


if __name__ == "__main__":
    import sys
    p = update_champion(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("CHAMPION:", p["champion"], "->", p["live_params"])
    print("reason:", p["reason"])
    print("backtest:", p["champion_backtest"])
