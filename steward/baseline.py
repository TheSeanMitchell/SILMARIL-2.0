"""steward.baseline — the design check, labeled as exactly that.

On first run (and on demand) this replays the registered rules over the ~2 years of
warmup history the price fetch pulls down, using the same choose(), the same t+1
fills and the same both-sides fees as the live books.

WHAT IT IS NOT: evidence. The rules were chosen from published literature rather
than fit to this tape, so it is close to out-of-sample — but the operator will read
it before the forward window finishes, and a number you saw before the experiment
ended is context, never proof. It is labeled IN_DESIGN_CHECK everywhere it appears,
and no pass mark reads from it. Cash earns nothing here (conservative against the
strategy). The forward books are the experiment; this is the sanity floor under it.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Dict, List

from .book import universe_of
from .config import BASELINE_FILE, REGISTERED, round_trip
from .signals import choose, momentum_score
from .util import month_of, now_iso, write_json_atomic


def _series(store: Dict, sym: str) -> Dict[str, float]:
    return {d: px for d, px in store.get(sym, [])}


def run_book(name: str, store: Dict) -> Dict:
    syms = universe_of(name)
    slots = REGISTERED["books"][name]["slots"]
    px = {s: _series(store, s) for s in syms}
    rows = {s: store.get(s, []) for s in syms}
    dates = sorted(set().union(*[set(px[s]) for s in syms])) if syms else []
    if not dates:
        return {"skipped": "no history"}

    # start where every symbol can produce a score (126-bar warmup)
    start_i = None
    for i, d in enumerate(dates):
        if all(momentum_score(rows[s], d) is not None for s in syms):
            start_i = i
            break
    if start_i is None or start_i >= len(dates) - 22:
        return {"skipped": "history shorter than the 126-bar lookback"}

    cash = REGISTERED["start_cash"]
    pos: Dict[str, Dict] = {}
    pending: List[Dict] = []
    last_month = None
    bench = None                                 # fills at first bar after start
    peak, max_dd, trades = 0.0, 0.0, 0
    killed = None
    equity_curve = []
    # carry-forward marks: on a date where a symbol has no bar (weekends in a mixed
    # crypto/equity calendar), it is marked at its LAST KNOWN close — never at a
    # later one. The first draft fell back to the end-of-series price, which is
    # lookahead in the marker itself; caught by a -51% phantom drawdown on GLD/SLV.
    mark: Dict[str, float] = {}
    bench_syms = list(REGISTERED["books"][name]["bench"])
    for s in set(syms) | set(bench_syms):
        first = _series(store, s)
        for dd in sorted(first):
            if dd >= dates[start_i]:
                break
            mark[s] = first[dd]

    for i in range(start_i, len(dates)):
        d = dates[i]
        for s in set(syms) | set(bench_syms):
            if d in px.get(s, {}):
                mark[s] = px[s][d]
            elif s not in px and d in _series(store, s):
                mark[s] = _series(store, s)[d]
        # fills: first bar strictly after the decision date, per symbol
        still = []
        sells = [o for o in pending if o["side"] == "SELL" and d in px[o["sym"]] and d > o["dec"]]
        buys = [o for o in pending if o["side"] == "BUY" and d in px[o["sym"]] and d > o["dec"]]
        for o in pending:
            if o not in sells and o not in buys:
                still.append(o)
        for o in sells:
            p = pos.pop(o["sym"], None)
            if p:
                cash += p["qty"] * px[o["sym"]][d] * (1 - round_trip(o["sym"]) / 2)
                trades += 1
        n_open_buys = len(buys) + sum(1 for o in still if o["side"] == "BUY")
        for o in buys:
            share = cash / max(1, n_open_buys)
            n_open_buys -= 1
            if share < 100:
                continue
            eff = px[o["sym"]][d] * (1 + round_trip(o["sym"]) / 2)
            pos[o["sym"]] = {"qty": share / eff}
            cash -= share
            trades += 1
        pending = still

        # bench fills at the first bar after the start where EVERY leg has a close —
        # same t+1 spirit, same entry fee
        if bench is None and d > dates[start_i]:
            legs = REGISTERED["books"][name]["bench"]
            leg_px = {s: _series(store, s).get(d) for s in legs}
            if all(v is not None for v in leg_px.values()):
                share = REGISTERED["start_cash"] / len(legs)
                bench = [{"sym": s, "qty": share / (leg_px[s] * (1 + round_trip(s) / 2))}
                         for s in legs]

        # mark at carry-forward closes — a position is worth its last KNOWN price
        eq = cash + sum(p["qty"] * mark.get(s, p.get("entry_px", 0.0))
                        for s, p in pos.items())
        bench_eq_now = (sum(l["qty"] * mark.get(l["sym"], 0.0) for l in bench)
                        if bench else REGISTERED["start_cash"])
        peak = max(peak, eq)
        if peak > 0:
            max_dd = min(max_dd, (eq / peak - 1) * 100)
        equity_curve.append([d, round(eq, 2)])

        # the registered kills, replayed exactly as the live book applies them
        if not killed:
            dd_kill = REGISTERED["kills"]["max_drawdown_pct"][name]
            dd_now = (eq / peak - 1) * 100 if peak > 0 else 0.0
            week52 = (date.fromisoformat(d)
                      - date.fromisoformat(dates[start_i])).days >= 364
            if dd_now <= -dd_kill:
                killed = "day %s: drawdown %.1f%% hit the -%.0f%% kill" % (d, dd_now, dd_kill)
            elif week52 and (eq - bench_eq_now) <= REGISTERED["kills"]["week52_delta_usd"]:
                killed = "day %s: week-52 delta $%.0f hit the $%.0f kill" % (
                    d, eq - bench_eq_now, REGISTERED["kills"]["week52_delta_usd"])
            if killed:
                pending = [o for o in pending if o["side"] == "SELL"]
                for s in pos:
                    if not any(o["sym"] == s and o["side"] == "SELL" for o in pending):
                        pending.append({"side": "SELL", "sym": s, "dec": d})

        # daily gate exit — fast out, slow in
        if not killed and REGISTERED.get("daily_gate_exit"):
            for s in list(pos.keys()):
                if any(o["sym"] == s and o["side"] == "SELL" for o in pending):
                    continue
                sc = momentum_score(rows[s], d)
                if sc is not None and sc <= REGISTERED["abs_gate"]:
                    pending.append({"side": "SELL", "sym": s, "dec": d})

        # monthly decision — entries only happen here
        if not killed and not pending and month_of(d) != last_month:
            scores = {s: momentum_score(rows[s], d) for s in syms}
            if all(v is not None for v in scores.values()):
                target = choose(list(pos.keys()), scores, slots)
                for s in list(pos.keys()):
                    if s not in target:
                        pending.append({"side": "SELL", "sym": s, "dec": d})
                for s in target:
                    if s not in pos:
                        pending.append({"side": "BUY", "sym": s, "dec": d})
                last_month = month_of(d)

    last_d = dates[-1]
    eq = cash + sum(p["qty"] * mark.get(s, 0.0) for s, p in pos.items())
    bench_eq = None
    if bench:
        bench_eq = sum(l["qty"] * mark.get(l["sym"], 0.0) for l in bench)
    return {
        "window": [dates[start_i], last_d],
        "final_equity": round(eq, 2),
        "bench_equity": round(bench_eq, 2) if bench_eq else None,
        "delta_usd": round(eq - bench_eq, 2) if bench_eq else None,
        "max_dd_pct": round(max_dd, 2),
        "round_trips": trades // 2,
        "killed": killed,
        "label": "IN_DESIGN_CHECK",
    }


def run_all(store: Dict, data_dir: Path) -> Dict:
    out = {"generated_at": now_iso(), "label": "IN_DESIGN_CHECK — context, never proof",
           "what": ("the registered rules replayed over the warmup tape with the same "
                    "fills and fees as the live books; the forward window is the "
                    "experiment, this is the sanity floor under it"),
           "books": {name: run_book(name, store) for name in REGISTERED["books"]}}
    write_json_atomic(Path(data_dir) / BASELINE_FILE, out)
    return out
