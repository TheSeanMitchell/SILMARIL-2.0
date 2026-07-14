"""strategy_lab_abcd.py — 5.11 WRAP: the per-industry A–F discipline race.

v2 changes (operator directives, 2026-07-13):
  · EVERY industry gets its own full lab (crypto · stock · metal · energy) —
    same sleeves, own universe, own scoreboard. Sleeve state keys are
    "book:K"; legacy crypto-only keys ("A".."D") migrate automatically.
  · NEW SLEEVE E — ADAPTIVE STRIKER: normally a 2-slot D-style sniper, but when
    the industry surges (MTF fast-green OR a top card printing >=+3%/h) it OPENS
    +2 STRIKE SLOTS and buys the strongest movers, riding with a trail. The
    "never miss the +7% energy day" law, tested scientifically before it ever
    touches live capital.
  · NEW SLEEVE F — CASH HARVESTER: same disciplined sniper, but every realized
    profit is VAULTED as non-spendable. Working capital never exceeds the $10k
    base — the operator's honesty experiment: "if we have no capital left over
    we really don't have any profits." The vault IS the profit; the equity line
    can't flatter itself with recycled winnings.

Judged per industry on Δ-vs-HODL (crypto) / raw compounding, never win rate.
Kill (Law 15): after 40 closed trades in a sleeve, trailing that industry's A
sleeve = disproven for now. Sleeves never touch live books, never fund the
Master. Pure measurement.
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
BOOKS = ("crypto", "stock", "metal", "energy")

SLEEVES = {
    "A": {"name": "FOREVER RIDE", "cap": 10, "recycle_h": None, "ride_winners": False,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False,
          "desc": "the control — current live behavior: hold up to 10, fixed target, ride to hit/stop"},
    "B": {"name": "CAP ONLY", "cap": 5, "recycle_h": None, "ride_winners": False,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False,
          "desc": "concentration alone: hold 5 best, bigger slices, same fixed target"},
    "C": {"name": "FULL DISCIPLINE", "cap": 5, "recycle_h": 72, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False,
          "desc": "concentrate + recycle dead capital (~-0.3% at 72h) + let winners ride on fast-green"},
    "D": {"name": "SNIPER", "cap": 3, "recycle_h": 48, "ride_winners": True,
          "conf_gate": 0.45, "strike_extra": 0, "vault": False,
          "desc": "2-3 max, confidence-gated entries only, ride hard, recycle ruthlessly"},
    "E": {"name": "ADAPTIVE STRIKER", "cap": 2, "recycle_h": 36, "ride_winners": True,
          "conf_gate": 0.45, "strike_extra": 2, "vault": False,
          "desc": ("sniper base (2 slots) that OPENS +2 STRIKE SLOTS on an industry surge "
                   "(fast-green / +3%/h movers) and rides the strongest movers with a trail — "
                   "the never-miss-the-big-day law")},
    "F": {"name": "CASH HARVESTER", "cap": 3, "recycle_h": 48, "ride_winners": True,
          "conf_gate": 0.45, "strike_extra": 0, "vault": True,
          "desc": ("sniper discipline, but every realized profit is VAULTED (non-spendable); "
                   "working capital never exceeds the $10k base — profits are only profits when "
                   "they leave the table")},
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
            "peak_equity": START, "max_dd_pct": 0.0, "vault_usd": 0.0}


def _load_state(out: Path) -> Dict[str, Any]:
    st = None
    try:
        st = json.loads((out / STORE).read_text())
    except Exception:
        pass
    if not st or "sleeves" not in st:
        st = {"sleeves": {}, "created_at": _now().isoformat()}
    for k in list(st["sleeves"].keys()):
        if ":" not in k:
            st["sleeves"][f"crypto:{k}"] = st["sleeves"].pop(k)
    for bk in BOOKS:
        for sk in SLEEVES:
            st["sleeves"].setdefault(f"{bk}:{sk}", _fresh_book())
            st["sleeves"][f"{bk}:{sk}"].setdefault("vault_usd", 0.0)
    return st


def _equity(bk: Dict[str, Any], marks: Dict[str, float]) -> float:
    held = sum(p["qty"] * marks.get(s, p["entry"]) for s, p in bk["positions"].items())
    return bk["cash"] + held


def _sell(bk: Dict[str, Any], sym: str, price: float, why: str, vault: bool):
    pos = bk["positions"].get(sym)
    if not pos or price <= 0:
        return
    eff = price * (1 - pos.get("cost", MIN_COST) / 2.0)
    proceeds = pos["qty"] * eff
    pnl = proceeds - pos["qty"] * pos["entry"]
    bk["cash"] += proceeds
    bk["realized_pnl"] += pnl
    if vault and pnl > 0:
        bk["cash"] -= pnl
        bk["vault_usd"] = round(bk.get("vault_usd", 0.0) + pnl, 2)
    bk["trades"].append({"side": "SELL", "sym": sym, "why": why,
                         "pnl": round(pnl, 2),
                         "realized_pct": round((eff / pos["entry"] - 1) * 100, 3) if pos["entry"] > 0 else 0,
                         "style": pos.get("style", "MR"),
                         "t": _now().isoformat()})
    del bk["positions"][sym]


def _run_sleeve(cfg: Dict[str, Any], bk: Dict[str, Any],
                marks: Dict[str, float], candidates: List[tuple],
                conf_map: Dict[str, float], fastgreen: set,
                surge: bool, strike_pool: List[tuple], cost_of) -> None:
    now = _now()
    vault = bool(cfg.get("vault"))

    for sym in list(bk["positions"].keys()):
        pos = bk["positions"][sym]
        cur = marks.get(sym)
        if not cur:
            continue
        chg = cur / pos["entry"] - 1 if pos["entry"] > 0 else 0
        tgt = pos.get("target", 0.05)
        stop = pos.get("stop", 0.06)
        try:
            hold_h = (now - _parse(pos["t"])).total_seconds() / 3600.0
        except Exception:
            hold_h = 0.0
        striking = pos.get("style") == "STRIKE"
        riding = (cfg["ride_winners"] and (sym in fastgreen) and chg >= tgt) or \
                 (striking and chg >= tgt and surge)
        if chg >= tgt and not riding:
            _sell(bk, sym, cur, "TARGET", vault); continue
        if chg <= -stop:
            _sell(bk, sym, cur, "STOP", vault); continue
        if riding:
            hw = max(pos.get("hw", chg), chg)
            pos["hw"] = hw
            if chg <= hw * 0.6:
                _sell(bk, sym, cur, "RIDE_TRAIL", vault); continue
        if cfg["recycle_h"] and hold_h >= cfg["recycle_h"] and -0.01 <= chg <= 0.01:
            _sell(bk, sym, cur, "RECYCLE_FLAT", vault); continue

    def _avail() -> float:
        return bk["cash"]

    if cfg.get("strike_extra") and surge:
        strikes_open = sum(1 for p in bk["positions"].values() if p.get("style") == "STRIKE")
        room = cfg["strike_extra"] - strikes_open
        for sym, px, mom in strike_pool:
            if room <= 0:
                break
            if sym in bk["positions"] or not px or px <= 0:
                continue
            budget = min(_avail() * 0.30, _avail() - 25)
            if budget < 50:
                break
            qty = budget / px
            bk["cash"] -= budget
            bk["positions"][sym] = {"qty": qty, "entry": px, "cost": cost_of(px),
                                    "target": 0.04, "stop": 0.05, "style": "STRIKE",
                                    "t": now.isoformat(), "conf": round(conf_map.get(sym, 0.0), 3)}
            bk["trades"].append({"side": "BUY", "sym": sym, "style": "STRIKE",
                                 "wager_usd": round(budget, 2), "mom_h1": mom,
                                 "t": now.isoformat()})
            room -= 1

    cap = cfg["cap"]
    open_mr = sum(1 for p in bk["positions"].values() if p.get("style") != "STRIKE")
    if open_mr < cap:
        pool = [c for c in candidates if c[0] not in bk["positions"]]
        if cfg["conf_gate"] > 0:
            pool = [c for c in pool if conf_map.get(c[0], 0.0) >= cfg["conf_gate"]]
            pool.sort(key=lambda c: -conf_map.get(c[0], 0.0))
        else:
            pool.sort(key=lambda c: (c[2] or 0))
        for sym, px, h1, cv in pool[: cap - open_mr]:
            if not px or px <= 0:
                continue
            budget = _avail() / max(1, cap - open_mr)
            budget = min(budget, _avail() * 0.95)
            if budget < 50:
                break
            qty = budget / px
            bk["cash"] -= budget
            bk["positions"][sym] = {"qty": qty, "entry": px, "cost": cost_of(px),
                                    "target": 0.05, "stop": 0.06, "style": "MR",
                                    "t": now.isoformat(), "conf": round(conf_map.get(sym, 0.0), 3)}
            bk["trades"].append({"side": "BUY", "sym": sym, "style": "MR",
                                 "wager_usd": round(budget, 2),
                                 "conf": round(conf_map.get(sym, 0.0), 3), "t": now.isoformat()})

    eq = _equity(bk, marks) + bk.get("vault_usd", 0.0)
    bk["peak_equity"] = max(bk.get("peak_equity", START), eq)
    dd = (eq / bk["peak_equity"] - 1) * 100 if bk["peak_equity"] else 0
    bk["max_dd_pct"] = min(bk.get("max_dd_pct", 0.0), round(dd, 2))


def build_strategy_lab(out_dir, marks_raw=None, candidates=None) -> Dict[str, Any]:
    out = Path(out_dir)
    st = _load_state(out)

    live = {}
    try:
        live = json.loads((out / "paper_sim_live.json").read_text())
    except Exception:
        pass
    cards = {}
    try:
        cards = json.loads((out / "CONFIDENCE_CARDS.json").read_text()).get("cards") or {}
    except Exception:
        pass
    conf_map = {s: (c.get("confidence") or 0.0) for s, c in cards.items()}
    mtf_books, mtf_syms = {}, {}
    try:
        _m = json.loads((out / "MTF_REGIME.json").read_text())
        mtf_books = _m.get("books") or {}
        mtf_syms = _m.get("symbols") or {}
    except Exception:
        pass
    fastgreen = {s for s, v in mtf_syms.items() if v.get("fast_green")}

    def cost_of(px):
        return 0.004 if px >= 1 else 0.006

    hodl = None
    try:
        hodl = (json.loads((out / "BENCH_BOOKS.json").read_text()).get("books", {})
                .get("BENCH_HODL", {}).get("return_pct"))
    except Exception:
        pass

    by_industry: Dict[str, List[Dict[str, Any]]] = {}
    for book in BOOKS:
        b = live.get(book) or {}
        marks: Dict[str, float] = {}
        cands: List[tuple] = []
        for pos in b.get("positions", []) or []:
            if pos.get("mark") and pos.get("sym"):
                marks[pos["sym"]] = pos["mark"]
        for d in b.get("decision_trace_live") or []:
            sym = d.get("sym")
            if not sym:
                continue
            px = marks.get(sym) or (cards.get(sym) or {}).get("last_px")
            if px:
                marks.setdefault(sym, px)
                cands.append((sym, px, (d.get("dip_pct") or 0) / 100.0, d.get("conviction") or 0))
        pool = []
        for sym, c in cards.items():
            if c.get("class") != book or not c.get("last_px"):
                continue
            mom = ((c.get("momentum") or {}).get("h1"))
            if mom is not None and mom >= 3.0:
                pool.append((sym, c["last_px"], round(float(mom), 2)))
                marks.setdefault(sym, c["last_px"])
        pool.sort(key=lambda x: -x[2])
        surge = bool((mtf_books.get(book) or {}).get("fast_green")) or bool(pool)
        strike_pool = pool[:4]

        rows = []
        for sk, cfg in SLEEVES.items():
            bk = st["sleeves"][f"{book}:{sk}"]
            _run_sleeve(cfg, bk, marks, cands, conf_map, fastgreen, surge, strike_pool, cost_of)
            eq = _equity(bk, marks) + bk.get("vault_usd", 0.0)
            ret = (eq / START - 1) * 100
            closed = [t for t in bk["trades"] if t["side"] == "SELL"]
            wins = sum(1 for t in closed if t["pnl"] > 0)
            rows.append({
                "sleeve": sk, "name": cfg["name"], "cap": cfg["cap"],
                "equity": round(eq, 2), "return_pct": round(ret, 3),
                "realized_pnl": round(bk["realized_pnl"], 2),
                "vault_usd": round(bk.get("vault_usd", 0.0), 2),
                "delta_vs_hodl": (round(ret - float(hodl), 3)
                                  if (hodl is not None and book == "crypto") else None),
                "open": len(bk["positions"]), "closed": len(closed),
                "win_rate": round(wins / len(closed) * 100, 1) if closed else None,
                "max_dd_pct": bk.get("max_dd_pct", 0.0),
                "desc": cfg["desc"],
            })
        rows.sort(key=lambda r: -(r["delta_vs_hodl"] if r["delta_vs_hodl"] is not None
                                  else r["return_pct"]))
        by_industry[book] = rows

    st["generated_at"] = _now().isoformat()
    st["by_industry"] = by_industry
    st["scoreboard"] = by_industry.get("crypto", [])
    st["what"] = ("per-industry A–F discipline race: same entries per industry, differing ONLY in "
                  "position management. A = the control (current live behavior). E = ADAPTIVE "
                  "STRIKER (opens strike slots on a surge — the never-miss-the-big-day test). "
                  "F = CASH HARVESTER (profits vaulted; $10k working base — profits are only "
                  "profits when they leave the table). Judged on compounding, never win rate; "
                  "kill after 40 closed if trailing that industry's A.")
    write_json_atomic(out / STORE, st)
    _lead = {bk: (rows[0]["sleeve"] if rows else "-") for bk, rows in by_industry.items()}
    return {"summary": f"strategy lab v2: leaders {_lead} · 24 sleeves across 4 industries"}
