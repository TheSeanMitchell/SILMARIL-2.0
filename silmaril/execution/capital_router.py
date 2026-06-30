"""
silmaril.execution.capital_router — CONVERT EDGE INTO DEPLOYED CAPITAL (2.12).

The 2.12 mission in one module: the leaderboard stops being informational and
becomes ACTIONABLE. Capital is split across the top strategies weighted by their
edge — the champion gets the most, losers get zero — and it migrates every cycle
as the board changes. Plus the three things the audit demanded never be null:
per-trade edge capture, hold-time, and churn.

What it produces each cycle (capital_allocation.json):
  • ALLOCATION — how the $10k crypto book is split across the top strategies, and
    how that shifted from last cycle (winners gain, losers lose).
  • LIVE SUB-BOOKS — each top strategy actually trades its slice (real prices,
    simulated fills, honest fees). Capital is deployed, not just recommended.
  • ATTRIBUTION (never null) — held_edge_capture_pct, median_hold_minutes,
    share_churned_under_30min, and per-trade ENTRY/EXIT reason + edge captured +
    edge missed.
  • DEPLOYMENT AUDIT — deployed $ vs idle $, and WHY any cash is idle. No idle
    capital without an explanation.
  • PROOF — champion-weighted vs equal-weighted portfolio return, so you can see
    whether concentrating on the champion actually helps (honest either way).

Still paper, still real prices. Capital allocation is now wired to measured edge —
the bridge from "we found the best strategy" to "we put money behind it."
"""
from __future__ import annotations

import json
from .atomic_io import write_json_atomic
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

from .paper_sim import (PaperBook, load_all_samples, is_tradeable, round_trip_cost,
                        _is_crypto, _marks_from_samples, MAX_NAMES, PER_NAME_FRAC,
                        HEATSHIELD, HEATSHIELD_FLOOR, TIMEOUT_EXIT)
from .strategy_lab import STRATEGIES

TOP_K = 3
TOTAL = 10000.0
CHURN_MIN = 30.0
MIN_TRADES = 30
STEP_MIN = 11.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _params(name: str) -> Dict[str, Any]:
    c = STRATEGIES.get(name, {})
    return {"dir": c.get("dir", "mr"), "entry": c.get("entry", 0.02),
            "target": c.get("target", 0.02), "stop": c.get("stop", 0.04),
            "max_hold_min": c.get("hold", 22) * STEP_MIN}


# ── allocation: champion-weighted, positive edge only ────────────────────────
def compute_allocation(board: List[Dict[str, Any]], top_k: int = TOP_K) -> Dict[str, float]:
    elig = [r for r in board if r.get("trades", 0) >= MIN_TRADES
            and r.get("mean_net_pct", 0) > 0][:top_k]
    if not elig:
        return {}
    tot = sum(r["mean_net_pct"] for r in elig)
    return {r["strategy"]: round(r["mean_net_pct"] / tot, 4) for r in elig}


# ── backtest one strategy WITH per-trade attribution (no nulls) ──────────────
def _bt_attrib(fresh: Dict[str, List[float]], cfg: Dict[str, Any],
               costs: Dict[str, float]) -> Dict[str, Any]:
    d, tgt, stop_, hold_steps = cfg["entry"], cfg["target"], cfg["stop"], int(cfg["max_hold_min"] / STEP_MIN)
    mr = cfg["dir"] == "mr"
    trades = []
    for tk, px in fresh.items():
        n = len(px); c = costs[tk]; i = 6
        while i < n - 1:
            if px[i - 6] <= 0:
                i += 1; continue
            move = px[i] / px[i - 6] - 1
            if not ((move <= -d) if mr else (move >= d)):
                i += 1; continue
            ep = px[i]; j = i + 1; oc = None; mfe = ep
            while j < n:
                mfe = max(mfe, px[j])
                ch = px[j] / ep - 1
                if ch <= -stop_: oc, k = "STOP", j; break
                if ch >= tgt: oc, k = "TAKE", j; break
                if TIMEOUT_EXIT and (j - i) >= hold_steps: oc, k = "TIMEOUT", j; break
                j += 1
            if oc is None: break
            realized = px[k] / ep - 1 - c
            best = mfe / ep - 1                       # max favorable move
            cap = (max(0.0, (px[k] / ep - 1)) / best) if best > 1e-9 else (1.0 if realized > 0 else 0.0)
            trades.append({
                "ticker": tk,
                "entry_reason": f"{'oversold' if mr else 'strength'} {move*100:+.1f}% / 1h",
                "exit_reason": oc,
                "edge_capture_pct": round(min(cap, 1.0) * 100, 1),
                "missed_edge_pct": round(max(0.0, best - max(0.0, px[k] / ep - 1)) * 100, 2),
                "hold_min": round((k - i) * STEP_MIN, 0),
                "net_pct": round(realized * 100, 3),
            })
            i = k + 1
    if not trades:
        return {"trades": 0, "held_edge_capture_pct": 0.0, "median_hold_minutes": 0.0,
                "share_churned_under_30min": 0.0, "mean_net_pct": 0.0, "samples": []}
    holds = [t["hold_min"] for t in trades]
    return {
        "trades": len(trades),
        "held_edge_capture_pct": round(sum(t["edge_capture_pct"] for t in trades) / len(trades), 1),
        "median_hold_minutes": round(median(holds), 0),
        "share_churned_under_30min": round(sum(1 for h in holds if h < CHURN_MIN) / len(holds) * 100, 1),
        "win_rate_pct": round(sum(1 for t in trades if t["net_pct"] > 0) / len(trades) * 100, 1),
        "mean_net_pct": round(sum(t["net_pct"] for t in trades) / len(trades), 3),
        "samples": trades[-8:],
    }


# ── live: deploy each top strategy's slice as its own sub-book ────────────────
def _run_strategy_book(out: Path, name: str, capital: float, p: Dict[str, Any],
                       marks: Dict[str, tuple], samples: Dict[str, List]) -> Dict[str, Any]:
    book = PaperBook.load(out / f"paper_book_{name}.json", capital)
    now = datetime.now(timezone.utc)
    cmarks = {s: v for s, v in marks.items() if _is_crypto(s)}
    mk = {s: v[0] for s, v in cmarks.items()}

    def px_of(s): return [x for _, x in samples.get(s, []) if x and x > 0]
    def fresh_ok(s):
        pp = px_of(s); return len(pp) > 20 and is_tradeable(pp)

    # exits
    for s in list(book.positions.keys()):
        pos = book.positions[s]; cur = cmarks.get(s, (pos["entry"], 0))[0]
        chg = cur / pos["entry"] - 1 if pos["entry"] > 0 else 0
        try:
            hold = (now - datetime.fromisoformat(pos["t"])).total_seconds() / 60.0
        except Exception:
            hold = 0.0
        eff_stop = max(p["stop"], HEATSHIELD_FLOOR) if HEATSHIELD else p["stop"]
        timed_out = TIMEOUT_EXIT and hold >= p["max_hold_min"]
        if chg <= -eff_stop or chg >= p["target"] or timed_out:
            book.sell(s, cur, now.isoformat())
    # entries
    mr = p["dir"] == "mr"
    cands = [(s, lp, h1) for s, (lp, h1) in cmarks.items()
             if ((h1 <= -p["entry"]) if mr else (h1 >= p["entry"]))
             and s not in book.positions and fresh_ok(s)]
    cands.sort(key=lambda x: x[2], reverse=not mr)
    for s, lp, h1 in cands[:MAX_NAMES]:
        budget = min(book.equity(mk) * PER_NAME_FRAC, book.cash * 0.95)
        if budget > 1:
            book.buy(s, budget, lp, round_trip_cost(px_of(s)), now.isoformat())
    book.save(out / f"paper_book_{name}.json")
    eq = book.equity(mk)
    return {"equity": round(eq, 2), "cash": round(book.cash, 2),
            "open_positions": len(book.positions),
            "deployed": round(eq - book.cash, 2),
            "realized_pnl": round(book.realized_pnl, 2)}


def route(out_dir, total: float = TOTAL) -> Dict[str, Any]:
    out = Path(out_dir)
    try:
        lb = json.loads((out / "strategy_leaderboard.json").read_text())
    except Exception:
        from .strategy_lab import run_leaderboard
        lb = run_leaderboard(out)
    board = lb.get("leaderboard", [])
    alloc = compute_allocation(board)

    samples = load_all_samples(out)
    marks = _marks_from_samples(samples)
    fresh = {tk: px for tk, px in
             ((k, [p for t, p in v if p and p > 0 and "T00:00:00" not in t]) for k, v in samples.items())
             if _is_crypto(tk) and len(px) > 20 and is_tradeable(px)}
    costs = {tk: round_trip_cost(px) for tk, px in fresh.items()}

    # previous allocation (to show migration)
    try:
        prev = json.loads((out / "capital_allocation.json").read_text()).get("allocation", {})
    except Exception:
        prev = {}

    # deploy + attribute each funded strategy
    books, attrib, deployed_total, idle_total = {}, {}, 0.0, 0.0
    for name, w in alloc.items():
        cap = total * w
        p = _params(name)
        books[name] = {"weight_pct": round(w * 100, 1), "allocated": round(cap, 2),
                       "prev_weight_pct": round(prev.get(name, 0) * 100, 1),
                       **_run_strategy_book(out, name, cap, p, marks, samples)}
        attrib[name] = _bt_attrib(fresh, STRATEGIES.get(name, {}) | p, costs)
        deployed_total += books[name]["deployed"]
        idle_total += books[name]["cash"]

    # deployment audit — why is anything idle?
    oversold_now = sum(1 for s, (lp, h1) in marks.items()
                       if _is_crypto(s) and h1 <= -0.02 and s in fresh)
    audit = {
        "deployed_dollars": round(deployed_total, 2),
        "idle_dollars": round(idle_total, 2),
        "deployment_efficiency_pct": round(deployed_total / total * 100, 1) if total else 0,
        "funded_strategies": len(alloc),
        "oversold_names_available_now": oversold_now,
        "idle_reason": (
            "no funded strategy (no positive-edge strategy with a real sample)" if not alloc
            else "no oversold names meet entry right now — capital waits for a setup"
            if oversold_now == 0 else
            "partially deployed; remaining cash is per-name sizing headroom"),
    }

    # proof: champion-weighted vs equal-weighted top-K (does concentration help?)
    topk = [r["strategy"] for r in board if r.get("trades", 0) >= MIN_TRADES][:TOP_K]
    def port(weights):
        return round(sum(weights.get(n, 0) * (attrib.get(n, {}).get("mean_net_pct", 0))
                         for n in topk), 3)
    eq_w = {n: 1 / len(topk) for n in topk} if topk else {}
    proof = {
        "champion_weighted_edge_per_trade_pct": port(alloc),
        "equal_weighted_edge_per_trade_pct": port(eq_w),
        "concentrating_on_champion_helps": port(alloc) >= port(eq_w),
    }

    # blended no-null attribution across funded strategies (weighted)
    blended = {"held_edge_capture_pct": 0.0, "median_hold_minutes": 0.0,
               "share_churned_under_30min": 0.0, "total_trades": 0}
    if alloc:
        for name, w in alloc.items():
            a = attrib[name]
            blended["held_edge_capture_pct"] += w * a["held_edge_capture_pct"]
            blended["median_hold_minutes"] += w * a["median_hold_minutes"]
            blended["share_churned_under_30min"] += w * a["share_churned_under_30min"]
            blended["total_trades"] += a["trades"]
        for k in ("held_edge_capture_pct", "median_hold_minutes", "share_churned_under_30min"):
            blended[k] = round(blended[k], 1)

    payload = {
        "generated_at": _now(),
        "total_capital": total,
        "allocation": alloc,
        "books": books,
        "attribution_no_nulls": blended,
        "attribution_by_strategy": attrib,
        "deployment_audit": audit,
        "allocation_proof": proof,
        "note": ("Capital is split across the top strategies by edge and migrates "
                 "each cycle (winners gain, losers drop to 0). All attribution is "
                 "computed from real sim trades — never null. Paper, real prices."),
    }
    try:
        write_json_atomic(out / "capital_allocation.json", payload)
    except Exception:
        pass
    return payload


if __name__ == "__main__":
    import sys
    p = route(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("ALLOCATION:", json.dumps(p["allocation"]))
    print("ATTRIBUTION (no nulls):", json.dumps(p["attribution_no_nulls"]))
    print("DEPLOYMENT AUDIT:", json.dumps(p["deployment_audit"]))
    print("PROOF:", json.dumps(p["allocation_proof"]))
