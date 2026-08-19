"""steward.book — five paper books, one discipline.

Every hard lesson from the audited system is structural here, not aspirational:

  * BOTH-SIDES FEES from the first line ever run: entry pays rt/2, exit pays rt/2.
    scripts/test_steward.py proves a flat round trip costs the full declared cost.
  * NO LOOKAHEAD by construction: an order carries the bar its signal saw, and can
    only fill at a close from a bar strictly after it. There is no code path that
    fills at the signal bar.
  * THE BENCHMARK IS A BOOK: each book's buy-and-hold twin is seeded with the same
    $10k, pays the same entry fee, fills on the same t+1 rule, and is marked at the
    same closes. Delta-vs-hold is a subtraction between two honestly-kept accounts,
    not an estimate.
  * KILLS ARE PRE-REGISTERED and checked by code every run. A killed book liquidates
    and stays cash until a human re-registers. There is no quiet restart.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import prices as P
from .config import EQUITY_FILE, REGISTERED, round_trip
from .signals import choose, momentum_score
from .util import ledger_append, month_of, now_iso, read_json, write_json_atomic


# ── state scaffolding ─────────────────────────────────────────────────────────────

def fresh_book(name: str) -> Dict:
    cfg = REGISTERED["books"][name]
    start = REGISTERED["start_cash"]
    return {
        "cash": start, "positions": {}, "pending": [],
        "peak": start, "status": "ACTIVE", "kill_reason": None,
        "last_rebalance_month": None, "last_accrual": None,
        "bench": {"filled": False, "signal_bar": None, "cash": start,
                  "legs": [{"sym": s, "qty": 0.0} for s in cfg["bench"]]},
    }


def universe_of(name: str) -> List[str]:
    if name == "rotator":
        out: List[str] = []
        for syms in REGISTERED["universe"].values():
            out.extend(syms)
        return out
    return list(REGISTERED["universe"][name])


# ── fills: the only door a trade can pass through ─────────────────────────────────

def _fill_pending(bk: Dict, name: str, store: Dict, data_dir: Path) -> None:
    """SELLs first (cash arrives), then BUYs (cash is shared). Every fill is at the
    close of the first bar strictly after the order's signal bar — t+1, always."""
    still: List[Dict] = []
    fills_sell, fills_buy = [], []
    for od in bk["pending"]:
        bar = P.first_bar_after(store, od["sym"], od["signal_bar"])
        if bar is None:
            still.append(od)                       # no newer bar yet — order rests
            continue
        (fills_sell if od["side"] == "SELL" else fills_buy).append((od, bar))

    for od, bar in fills_sell:
        pos = bk["positions"].pop(od["sym"], None)
        if not pos:
            continue
        rt = round_trip(od["sym"])
        eff = bar[1] * (1.0 - rt / 2.0)            # exit pays its half
        proceeds = pos["qty"] * eff
        pnl = proceeds - pos["qty"] * pos["entry_eff"]
        bk["cash"] += proceeds
        ledger_append(data_dir, name, "SELL",
                      {"sym": od["sym"], "fill_bar": bar[0], "px": bar[1],
                       "eff": round(eff, 8), "pnl_usd": round(pnl, 2),
                       "signal_bar": od["signal_bar"], "reason": od.get("reason", "")})

    n_unfilled_buys = len(fills_buy) + sum(1 for od in still if od["side"] == "BUY")
    for od, bar in fills_buy:
        share = bk["cash"] / max(1, n_unfilled_buys)
        n_unfilled_buys -= 1
        if share < 100.0:                          # a seat too thin to matter stays cash
            ledger_append(data_dir, name, "BUY_SKIPPED",
                          {"sym": od["sym"], "why": "share below $100"})
            continue
        rt = round_trip(od["sym"])
        eff = bar[1] * (1.0 + rt / 2.0)            # entry pays its half — day one law
        qty = share / eff
        bk["cash"] -= share
        bk["positions"][od["sym"]] = {"qty": qty, "entry_eff": eff,
                                      "raw_px": bar[1], "filled": bar[0]}
        ledger_append(data_dir, name, "BUY",
                      {"sym": od["sym"], "fill_bar": bar[0], "px": bar[1],
                       "eff": round(eff, 8), "usd": round(share, 2),
                       "signal_bar": od["signal_bar"], "reason": od.get("reason", "")})
    bk["pending"] = still


def _fill_bench(bk: Dict, name: str, store: Dict, data_dir: Path) -> None:
    """The hold twin buys once, on the same t+1 rule, paying the same entry fee.
    Each leg gets an equal share of the seed and fills as its own bar arrives."""
    b = bk["bench"]
    if b["filled"] or not b["signal_bar"]:
        return
    share = REGISTERED["start_cash"] / len(b["legs"])
    done = True
    for leg in b["legs"]:
        if leg["qty"] > 0:
            continue
        bar = P.first_bar_after(store, leg["sym"], b["signal_bar"])
        if bar is None:
            done = False
            continue
        eff = bar[1] * (1.0 + round_trip(leg["sym"]) / 2.0)
        leg["qty"] = share / eff
        b["cash"] -= share
        ledger_append(data_dir, name, "BENCH_BUY",
                      {"sym": leg["sym"], "fill_bar": bar[0], "px": bar[1],
                       "usd": round(share, 2)})
    if done:
        b["filled"] = True


# ── marks, accrual, equity ────────────────────────────────────────────────────────

def _accrue_cash(bk: Dict) -> None:
    """Idle cash earns the registered APY, day-counted between runs."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    last = bk.get("last_accrual")
    bk["last_accrual"] = today
    if not last or last >= today:
        return
    d0 = datetime.strptime(last, "%Y-%m-%d")
    d1 = datetime.strptime(today, "%Y-%m-%d")
    days = (d1 - d0).days
    if days > 0 and bk["cash"] > 0:
        bk["cash"] *= (1.0 + REGISTERED["cash_apy"]) ** (days / 365.0)


def equity(bk: Dict, store: Dict) -> float:
    held = 0.0
    for sym, pos in bk["positions"].items():
        lb = P.latest_bar(store, sym)
        held += pos["qty"] * (lb[1] if lb else pos["entry_eff"])
    return bk["cash"] + held


def bench_equity(bk: Dict, store: Dict) -> float:
    b = bk["bench"]
    v = b["cash"]
    for leg in b["legs"]:
        if leg["qty"] > 0:
            lb = P.latest_bar(store, leg["sym"])
            if lb:
                v += leg["qty"] * lb[1]
    return v


# ── kills: registered, coded, no discretion ───────────────────────────────────────

def _check_kills(bk: Dict, name: str, store: Dict, data_dir: Path,
                 epoch: Optional[str]) -> None:
    if bk["status"] == "KILLED":
        return
    eq = equity(bk, store)
    bk["peak"] = max(bk.get("peak", eq), eq)
    kills = REGISTERED["kills"]

    reason = None
    dd = (eq / bk["peak"] - 1.0) * 100.0 if bk["peak"] > 0 else 0.0
    dd_kill = kills["max_drawdown_pct"][name]
    if dd <= -dd_kill:
        reason = "drawdown %.1f%% breached this book's registered -%.0f%% kill" % (
            dd, dd_kill)
    elif epoch:
        weeks = (datetime.now(timezone.utc)
                 - datetime.fromisoformat(epoch)).days / 7.0
        delta = eq - bench_equity(bk, store)
        if weeks >= 52 and delta <= kills["week52_delta_usd"]:
            reason = "week-%d delta vs hold $%.0f breached the registered $%.0f kill" % (
                weeks, delta, kills["week52_delta_usd"])

    if reason:
        bk["status"] = "KILLED"
        bk["kill_reason"] = reason
        bk["pending"] = [od for od in bk["pending"] if od["side"] == "SELL"]
        for sym in bk["positions"]:
            lb = P.latest_bar(store, sym)
            bk["pending"].append({"side": "SELL", "sym": sym,
                                  "signal_bar": lb[0] if lb else "1970-01-01",
                                  "reason": "KILL LIQUIDATION"})
        ledger_append(data_dir, name, "KILLED", {"reason": reason})


# ── the daily exit check: fast out, slow in ───────────────────────────────────────

def _daily_exits(bk: Dict, name: str, store: Dict, data_dir: Path) -> None:
    """Entries wait for the month; exits do not. Any run where a HELD asset's
    blended score falls through the absolute gate queues its sell. Sized on the
    warmup tape, where a monthly-only exit sat through half of a 50% silver crash
    waiting for the calendar's permission to act."""
    if bk["status"] == "KILLED" or not REGISTERED.get("daily_gate_exit"):
        return
    pending_sells = {o["sym"] for o in bk["pending"] if o["side"] == "SELL"}
    for sym in list(bk["positions"].keys()):
        if sym in pending_sells:
            continue
        lb = P.latest_bar(store, sym)
        if not lb:
            continue
        score = momentum_score(P.closes(store, sym), lb[0])
        if score is not None and score <= REGISTERED["abs_gate"]:
            bk["pending"].append({"side": "SELL", "sym": sym, "signal_bar": lb[0],
                                  "reason": "daily gate exit — trend fell through "
                                            "the floor (%.4f <= %.4f)"
                                            % (score, REGISTERED["abs_gate"])})
            ledger_append(data_dir, name, "GATE_EXIT",
                          {"sym": sym, "score": round(score, 4), "bar": lb[0]})


# ── the monthly decision ──────────────────────────────────────────────────────────

def _maybe_rebalance(bk: Dict, name: str, store: Dict, data_dir: Path,
                     today: Optional[str] = None) -> None:
    if bk["status"] != "ACTIVE" or bk["pending"]:
        return
    syms = universe_of(name)
    stale_max = REGISTERED["kills"]["stale_data_days"]
    newest = None
    for s in syms:
        st = P.staleness_days(store, s, today=today)
        if st is None or st > stale_max:
            ledger_append(data_dir, name, "HALTED",
                          {"why": "%s data stale (%s days) — no new positions on a "
                                  "silent tape" % (s, st)})
            return
        lb = P.latest_bar(store, s)
        newest = max(newest or lb[0], lb[0])
    if month_of(newest) == bk["last_rebalance_month"]:
        return

    scores = {s: momentum_score(P.closes(store, s), P.latest_bar(store, s)[0])
              for s in syms}
    if any(v is None for v in scores.values()):
        ledger_append(data_dir, name, "WAITING",
                      {"why": "history shorter than the 126-bar lookback — no score, "
                              "no trade"})
        return
    target = choose(list(bk["positions"].keys()), scores,
                    REGISTERED["books"][name]["slots"])
    held = set(bk["positions"].keys())
    sells = [s for s in held if s not in target]
    buys = [s for s in target if s not in held]
    for s in sells:
        bk["pending"].append({"side": "SELL", "sym": s,
                              "signal_bar": P.latest_bar(store, s)[0],
                              "reason": "monthly rebalance — lost its seat"})
    for s in buys:
        bk["pending"].append({"side": "BUY", "sym": s,
                              "signal_bar": P.latest_bar(store, s)[0],
                              "reason": "monthly rebalance — won a seat"})
    bk["last_rebalance_month"] = month_of(newest)
    ledger_append(data_dir, name, "REBALANCE",
                  {"month": bk["last_rebalance_month"],
                   "scores": {k: round(v, 4) for k, v in scores.items()},
                   "target": target, "sells": sells, "buys": buys,
                   "note": "cash" if not target else ""})


# ── equity history (for the report's weekly t-test) ───────────────────────────────

def _log_equity(books: Dict, store: Dict, data_dir: Path) -> None:
    path = Path(data_dir) / EQUITY_FILE
    hist = read_json(path, {})
    for name, bk in books.items():
        newest = None
        for s in universe_of(name):
            lb = P.latest_bar(store, s)
            if lb:
                newest = max(newest or lb[0], lb[0])
        if not newest:
            continue
        rows = hist.setdefault(name, [])
        if rows and rows[-1][0] == newest:
            rows[-1] = [newest, round(equity(bk, store), 2),
                        round(bench_equity(bk, store), 2)]
        else:
            rows.append([newest, round(equity(bk, store), 2),
                         round(bench_equity(bk, store), 2)])
    write_json_atomic(path, hist)


# ── the daily cycle ───────────────────────────────────────────────────────────────

def run_cycle(state: Dict, store: Dict, data_dir: Path) -> Dict:
    """One daily pass over all five books. Order is fixed and load-bearing:
    fills first (yesterday's decisions land), then marks and kills (on what is now
    true), then this month's decision if due, then the equity log."""
    if not state.get("epoch"):
        state["epoch"] = now_iso()
        for name, bk in state["books"].items():
            newest = None
            for s in universe_of(name):
                lb = P.latest_bar(store, s)
                if lb:
                    newest = max(newest or lb[0], lb[0])
            bk["bench"]["signal_bar"] = newest
        ledger_append(data_dir, "*", "EPOCH",
                      {"registration_hash": state.get("registration_hash"),
                       "note": "the clock starts; wipes are not a feature of this system"})

    for name, bk in state["books"].items():
        _fill_pending(bk, name, store, data_dir)
        _fill_bench(bk, name, store, data_dir)
        _accrue_cash(bk)
        _check_kills(bk, name, store, data_dir, state.get("epoch"))
        _daily_exits(bk, name, store, data_dir)
        _maybe_rebalance(bk, name, store, data_dir)
    _log_equity(state["books"], store, data_dir)
    return state
