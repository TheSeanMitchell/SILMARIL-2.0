"""strategy_lab_abcd.py — 5.1 FINAL: the A/B/C/D discipline lab.

The operator's scientific approach: keep the current forever-ride engine as the
LIVE book (A, the control) and race disciplined variations against it in
isolated paper sleeves. They share the SAME entry signals and universe every
cycle; they differ ONLY in position management. Judged Δ-vs-HODL and realized
$/day — never win rate. The winner earns promotion to live; nothing is assumed.

  A — FOREVER RIDE  cap 10, fixed target, ride to hit/stop         (the control = current behavior)
  B — CAP ONLY      cap 5, same fixed target                       (does concentration alone help?)
  C — FULL DISCIPLINE cap 5, 72h recycle (accept ~-0.3% to free    (concentrate + recycle + let
                      capital) + let winners ride on fast-green      winners run)
  D — SNIPER        cap 2-3, confidence-gated entries only, ride    (mean-reversion sniper on the
                      hard, recycle ruthlessly                       full prediction stack)

Each sleeve is a self-contained $10k book persisted in STRATEGY_LAB.json
(append-safe, survives wipes if preserved). This module runs AFTER the live
sim each cycle, reusing the live marks + candidate signals so it costs almost
nothing and mirrors reality exactly.

HONEST: these are measurement sleeves. They never touch real books, never fund
the Master, never enter championship. Their only job is to answer, forward,
which discipline compounds — with a pre-registered kill criterion each.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .atomic_io import write_json_atomic

STORE = "STRATEGY_LAB.json"
START = 10000.0
MIN_COST = 0.004

SLEEVES = {
    "A": {"name": "FOREVER RIDE", "cap": 10, "recycle_h": None, "ride_winners": False,
          "conf_gate": 0.0, "desc": "the control — current live behavior: hold up to 10, fixed target, ride to hit/stop"},
    "B": {"name": "CAP ONLY", "cap": 5, "recycle_h": None, "ride_winners": False,
          "conf_gate": 0.0, "desc": "concentration alone: hold 5 best, bigger slices, same fixed target"},
    "C": {"name": "FULL DISCIPLINE", "cap": 5, "recycle_h": 72, "ride_winners": True,
          "conf_gate": 0.0, "desc": "concentrate + recycle dead capital (accept ~-0.3% at 72h) + let winners ride on fast-green"},
    "D": {"name": "SNIPER", "cap": 3, "recycle_h": 48, "ride_winners": True,
          "conf_gate": 0.45, "desc": "2-3 max, confidence-gated entries only, ride hard, recycle ruthlessly — the full-prediction-stack sniper"},
}


def _now():
    return datetime.now(timezone.utc)


def _parse(t) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _fresh_book() -> Dict[str, Any]:
    return {"cash": START, "positions": {}, "realized_pnl": 0.0, "trades": [],
            "peak_equity": START, "max_dd_pct": 0.0}


def _load_state(out: Path) -> Dict[str, Any]:
    try:
        st = json.loads((out / STORE).read_text())
        if "sleeves" in st:
            return st
    except Exception:
        pass
    return {"sleeves": {k: _fresh_book() for k in SLEEVES}, "created_at": _now().isoformat()}


def _equity(bk: Dict[str, Any], marks: Dict[str, float]) -> float:
    held = sum(p["qty"] * marks.get(s, p["entry"]) for s, p in bk["positions"].items())
    return bk["cash"] + held


def _sell(bk: Dict[str, Any], sym: str, price: float, why: str):
    pos = bk["positions"].get(sym)
    if not pos or price <= 0:
        return
    eff = price * (1 - pos.get("cost", MIN_COST) / 2.0)
    proceeds = pos["qty"] * eff
    pnl = proceeds - pos["qty"] * pos["entry"]
    bk["cash"] += proceeds
    bk["realized_pnl"] += pnl
    bk["trades"].append({"side": "SELL", "sym": sym, "why": why,
                         "pnl": round(pnl, 2),
                         "realized_pct": round((eff / pos["entry"] - 1) * 100, 3) if pos["entry"] > 0 else 0,
                         "t": _now().isoformat()})
    del bk["positions"][sym]


def _run_sleeve(key: str, cfg: Dict[str, Any], bk: Dict[str, Any],
                marks: Dict[str, tuple], candidates: List[tuple],
                conf_map: Dict[str, float], fastgreen: set, fastred_books: set,
                cost_of) -> None:
    """One cycle for one sleeve. marks: {sym:(px, h1)}. candidates: [(sym,px,h1,cv)]."""
    now = _now()

    # ── EXITS ──────────────────────────────────────────────────────────
    for sym in list(bk["positions"].keys()):
        pos = bk["positions"][sym]
        mk = marks.get(sym)
        if not mk:
            continue
        cur = mk[0]
        chg = cur / pos["entry"] - 1 if pos["entry"] > 0 else 0
        cost = pos.get("cost", MIN_COST)
        tgt = pos.get("target", 0.05)
        stop = pos.get("stop", 0.06)
        try:
            hold_h = (now - _parse(pos["t"])).total_seconds() / 3600.0
        except Exception:
            hold_h = 0.0

        # let winners ride: if flagged and price is above target AND still fast-green, hold
        riding = cfg["ride_winners"] and (sym in fastgreen) and chg >= tgt
        if chg >= tgt and not riding:
            _sell(bk, sym, cur, "TARGET"); continue
        if chg <= -stop:
            _sell(bk, sym, cur, "STOP"); continue
        if riding and chg <= tgt * 0.5:            # trail: gave back half the gain → bank it
            _sell(bk, sym, cur, "RIDE_TRAIL"); continue
        # recycle dead capital: past the window and roughly flat → free it (accept tiny loss)
        if cfg["recycle_h"] and hold_h >= cfg["recycle_h"] and -0.01 <= chg <= 0.01:
            _sell(bk, sym, cur, "RECYCLE_FLAT"); continue

    # ── ENTRIES (fill remaining slots with the best candidates) ─────────
    cap = cfg["cap"]
    open_n = len(bk["positions"])
    if open_n < cap:
        # rank candidates: sniper uses confidence, others use dip depth (cv)
        pool = [c for c in candidates if c[0] not in bk["positions"]]
        if cfg["conf_gate"] > 0:
            pool = [c for c in pool if conf_map.get(c[0], 0.0) >= cfg["conf_gate"]]
            pool.sort(key=lambda c: -conf_map.get(c[0], 0.0))
        else:
            pool.sort(key=lambda c: (c[2] or 0))   # deepest dip first
        for sym, px, h1, cv in pool[: cap - open_n]:
            if px <= 0:
                continue
            cost = cost_of(px)
            budget = bk["cash"] / max(1, cap - open_n)   # spread remaining cash over open slots
            budget = min(budget, bk["cash"] * 0.95)
            if budget < 50:
                break
            qty = budget / px
            bk["cash"] -= budget
            bk["positions"][sym] = {"qty": qty, "entry": px, "cost": cost,
                                    "target": 0.05, "stop": 0.06, "t": now.isoformat(),
                                    "conf": round(conf_map.get(sym, 0.0), 3)}
            bk["trades"].append({"side": "BUY", "sym": sym, "wager_usd": round(budget, 2),
                                 "conf": round(conf_map.get(sym, 0.0), 3), "t": now.isoformat()})

    # ── bookkeeping: equity, drawdown ──────────────────────────────────
    eq = _equity(bk, {s: m[0] for s, m in marks.items()})
    bk["peak_equity"] = max(bk.get("peak_equity", START), eq)
    dd = (eq / bk["peak_equity"] - 1) * 100 if bk["peak_equity"] else 0
    bk["max_dd_pct"] = min(bk.get("max_dd_pct", 0.0), round(dd, 2))


def build_strategy_lab(out_dir, marks_raw=None, candidates=None) -> Dict[str, Any]:
    """Run all four sleeves one cycle. If marks/candidates aren't passed, read them
    from the live sim's store so the lab can also run standalone."""
    out = Path(out_dir)
    st = _load_state(out)

    # marks + candidates: prefer what the live sim just computed
    marks: Dict[str, tuple] = {}
    cands: List[tuple] = []
    try:
        live = json.loads((out / "paper_sim_live.json").read_text())
        for bkname in ("crypto",):     # lab races on the crypto universe (the Cat-1 proving ground)
            b = live.get(bkname) or {}
            for pos in b.get("positions", []):
                if pos.get("mark") and pos.get("sym"):
                    marks[pos["sym"]] = (pos["mark"], 0)
            dt = b.get("decision_trace_live") or []
            for d in dt:
                sym = d.get("sym")
                if sym and marks.get(sym):
                    cands.append((sym, marks[sym][0], (d.get("dip_pct") or 0) / 100.0, d.get("conviction") or 0))
    except Exception:
        pass

    # confidence + fast-green from their stores
    conf_map: Dict[str, float] = {}
    fastgreen: set = set()
    try:
        ce = json.loads((out / "CONFIDENCE_ENGINE.json").read_text()).get("by_symbol", {})
        conf_map = {s: (v.get("confidence") or 0.0) for s, v in ce.items()}
    except Exception:
        pass
    try:
        mtf = json.loads((out / "MTF_REGIME.json").read_text()).get("symbols", {})
        fastgreen = {s for s, v in mtf.items() if v.get("fast_green")}
    except Exception:
        pass

    def cost_of(px):
        return 0.004 if px >= 1 else 0.006

    for key, cfg in SLEEVES.items():
        _run_sleeve(key, cfg, st["sleeves"][key], marks, cands, conf_map, fastgreen, set(), cost_of)

    # ── scorecard ───────────────────────────────────────────────────────
    hodl = None
    try:
        hodl = (json.loads((out / "BENCH_BOOKS.json").read_text()).get("books", {})
                .get("BENCH_HODL", {}).get("return_pct"))
    except Exception:
        pass
    m0 = {s: m[0] for s, m in marks.items()}
    board = []
    for key, cfg in SLEEVES.items():
        bk = st["sleeves"][key]
        eq = _equity(bk, m0)
        ret = (eq / START - 1) * 100
        closed = [t for t in bk["trades"] if t["side"] == "SELL"]
        wins = sum(1 for t in closed if t["pnl"] > 0)
        board.append({
            "sleeve": key, "name": cfg["name"], "cap": cfg["cap"],
            "equity": round(eq, 2), "return_pct": round(ret, 3),
            "realized_pnl": round(bk["realized_pnl"], 2),
            "delta_vs_hodl": round(ret - float(hodl), 3) if hodl is not None else None,
            "open": len(bk["positions"]), "closed": len(closed),
            "win_rate": round(wins / len(closed) * 100, 1) if closed else None,
            "max_dd_pct": bk.get("max_dd_pct", 0.0),
            "desc": cfg["desc"],
            "kill_criterion": "after 40 closed trades, if delta_vs_hodl < sleeve A's, this variation is disproven for now",
        })
    board.sort(key=lambda r: (r["delta_vs_hodl"] if r["delta_vs_hodl"] is not None else r["return_pct"]), reverse=True)

    st["generated_at"] = _now().isoformat()
    st["scoreboard"] = board
    st["what"] = ("A/B/C/D discipline lab — four isolated $10k sleeves on the crypto universe, same entry "
                  "signals, differing ONLY in position management. A=current behavior (control). Judged "
                  "Δ-vs-HODL and realized compounding, NOT win rate. The winner earns promotion to live.")
    st["how_to_read"] = ("Each sleeve holds a different max # of positions and exits differently. Watch "
                         "delta_vs_hodl over ~40 closed trades: the discipline that compounds fastest wins. "
                         "Never funds the Master; pure measurement.")
    write_json_atomic(out / STORE, st)
    lead = board[0] if board else {}
    return {"summary": f"strategy lab: A {board[0]['return_pct'] if board else 0}%… leader "
                       f"{lead.get('sleeve','-')} ({lead.get('name','-')}) {lead.get('return_pct','-')}%"}
