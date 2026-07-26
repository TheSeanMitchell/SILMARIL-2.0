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
    # ── 7.0 THE STOP-LOSS LABORATORY — two stop philosophies, racing in the open ──
    "G": {"name": "GEOMETRY SNIPER", "cap": 4, "recycle_h": 48, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False, "geometry": True,
          "desc": ("7.0: trades ONLY names the Geometry Gate marks TRADEABLE; stop is CAPPED at "
                   "1.5× target (p* ≤ ~60% by construction). The 'winnable-math-only' thesis, "
                   "as its own clickable portfolio — watch it, debug it, judge it")},
    # ── 7.0.5 THE EXPANSION BENCH (operator: "create a new sleeve specially made for [metals], then
    # apply that sleeve to the rest of the industries just to see if it performs ... a scalable format
    # for expanding sleeves"). Every sleeve is exactly two things: a CANDIDATE FILTER (which names it
    # will look at) and a DISCIPLINE (how it holds them). Adding a sleeve is one dict entry plus, if
    # it needs a new filter, one clause in the filter block below. They run on ALL FOUR books
    # automatically, so a metals idea is tested against crypto/stock/energy for free.
    "I": {"name": "VOLATILITY HUNTER", "cap": 4, "recycle_h": 72, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False, "min_edge_ratio": 3.0,
          "desc": ("7.0.5 THE METAL ANSWER: only names whose OWN reachable move is >=3x their "
                   "round-trip cost. Gold fails this (it travels 0.22% against a 0.11% round trip, "
                   "so fees eat half the move and the geometry demands an 80% win rate); silver and "
                   "the miners pass. Instead of forcing a quiet book to trade, this sleeve simply "
                   "refuses names whose arithmetic cannot pay — and takes the ones that can")},
    "J": {"name": "TREND RIDER", "cap": 4, "recycle_h": 96, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False, "trend_only": True,
          "desc": ("7.0.5 PLAY IT LIKE A NORMAL TRADER: not a mean-reversion gimmick — buy the "
                   "PULLBACK inside a confirmed uptrend (24h AND 72h trajectory positive) and ride "
                   "the winner instead of selling into a fixed target. The dip is the entry, the "
                   "trend is the thesis. If trend-following beats revert on any book, this proves it")},
    "K": {"name": "POSITION TRADER", "cap": 2, "recycle_h": 336, "ride_winners": True,
          "conf_gate": 0.55, "strike_extra": 0, "vault": False, "patient": True,
          "desc": ("7.0.5 LOW-TURNOVER, LONG-HORIZON: two names maximum, highest conviction only, "
                   "held up to 14 DAYS. Every round trip costs 0.2-0.4%, so churn is the quiet "
                   "killer; this sleeve pays that toll as few times as possible and lets time do "
                   "the work. The control against every fast strategy in the bench")},
    "H": {"name": "PATIENT REVERT", "cap": 3, "recycle_h": 168, "ride_winners": False,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False, "patient": True,
          "desc": ("7.0: the operator's time-edge thesis — ONLY names with proven revert evidence "
                   "(bounce-reliability ≥0.75 or evidence floor ≥65%), WIDE vol-native stop "
                   "uncapped, hold up to 7 DAYS for the revert WE KNOW comes. If patience is the "
                   "edge, this sleeve proves it; if it isn't, this sleeve pays the tuition")},
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
    # ── 5.3 CLEAN ROOM (M4): the lab honors the wipe like every other STATE store.
    # F4 receipt: created 07-12, wiped 07-14, sleeve trades from 07-12 → void.
    try:
        _wm = json.loads((out / "WIPE_MARKER.json").read_text()).get("wiped_at")
    except Exception:
        _wm = None
    if _wm and str(st.get("created_at", "")) < str(_wm):
        st = {"sleeves": {}, "created_at": _now().isoformat()}
    st["wipe_epoch"] = _wm
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


# ── 7.0 ONE-UNIVERSE RIVER (operator directive): the workshop feeds the books. ──
# Every sleeve close appends a resolved outcome to LAB_OUTCOMES.jsonl; the real books'
# maturity gate COUNTS these, so what the sleeves learn matures names for production.
# The sleeves already trade the books' own candidate stream (decision_trace_live) —
# this closes the return river: candidates flow down, resolved evidence flows back up.
_RIVER = {"out": None, "sleeve": None, "book": None}


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
    bk["trades"].append({"side": "SELL", "sym": sym, "why": why, "simulated": True,
                         "pnl": round(pnl, 2),
                         "realized_pct": round((eff / pos["entry"] - 1) * 100, 3) if pos["entry"] > 0 else 0,
                         "style": pos.get("style", "MR"),
                         "t": _now().isoformat()})
    try:  # ONE-UNIVERSE RIVER: resolved workshop outcome → shared evidence ledger
        if _RIVER.get("out"):
            with open(Path(_RIVER["out"]) / "LAB_OUTCOMES.jsonl", "a") as _rf:
                _rf.write(json.dumps({
                    "t": _now().isoformat(), "sym": sym,
                    "book": _RIVER.get("book"), "sleeve": _RIVER.get("sleeve"),
                    "why": why, "pnl": round(pnl, 2),
                    "net_pct": round((eff / pos["entry"] - 1) * 100, 3) if pos["entry"] > 0 else 0,
                    "win": pnl > 0, "style": pos.get("style", "MR"),
                    "source": "strategy_lab"}) + "\n")
    except Exception:
        pass
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
            bk["trades"].append({"side": "BUY", "sym": sym, "style": "STRIKE", "simulated": True,
                                 "regime": bk.get("_regime7"),
                                 "wager_usd": round(budget, 2), "mom_h1": mom,
                                 "t": now.isoformat()})
            room -= 1

    cap = cfg["cap"]
    open_mr = sum(1 for p in bk["positions"].values() if p.get("style") != "STRIKE")
    if open_mr < cap:
        pool = [c for c in candidates if c[0] not in bk["positions"]]
        if cfg["conf_gate"] > 0:
            # 5.3 Law 18 — PERCENTILE GATE. The 0.45 absolute gate starved D/E/F forever
            # (card scale maxes ~0.39). The sniper now demands the TOP DECILE of THIS
            # cycle's live industry pool (min pool 20); small pools stand the gate down.
            _vals = sorted(v for v in conf_map.values() if v is not None)
            if len(_vals) >= 20:
                _cut = _vals[max(0, int(len(_vals) * 0.90))]
                pool = [c for c in pool if conf_map.get(c[0], 0.0) >= _cut]
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
            # ── 7.0 STOP-LOSS LAB: the sleeve's stop philosophy BINDS at entry ──
            tgt, stp = 0.05, 0.06
            _g7 = (bk.get("_geo7") or {}).get(sym) or {}
            if cfg.get("geometry") and _g7.get("target_pct"):
                tgt = float(_g7["target_pct"]) / 100.0
                stp = min(float(_g7.get("stop_used_pct") or (_g7["target_pct"] * 1.5)) / 100.0,
                          tgt * 1.5)                       # capped: p* ≤ ~60% by construction
            elif cfg.get("patient") and _g7:
                tgt = max(0.02, float(_g7.get("target_pct") or 3.0) / 100.0)
                stp = max(float(_g7.get("stop_vol_pct") or 6.0) / 100.0, tgt * 1.2)  # WIDE, on purpose
            bk["positions"][sym] = {"qty": qty, "entry": px, "cost": cost_of(px),
                                    "target": tgt, "stop": stp, "style": "MR",
                                    "t": now.isoformat(), "conf": round(conf_map.get(sym, 0.0), 3)}
            bk["trades"].append({"side": "BUY", "sym": sym, "style": "MR", "simulated": True,
                                 "regime": bk.get("_regime7"),
                                 "target_pct": round(tgt * 100, 2), "stop_pct": round(stp * 100, 2),
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

    _geo = {}
    try:
        _geo = (json.loads((out / "GEOMETRY.json").read_text()).get("by_symbol") or {})
    except Exception:
        _geo = {}
    marks_all: Dict[str, float] = {}
    # 7.0.8: every price series we hold, so any sleeve position can be marked to the live tape.
    # 7.1 ONE-KEY LAW: load through the canonical union so a position keyed one spelling can
    # never miss a tape stored under another (the DOGE-USD/DOGEUSDT class of freeze).
    _tape7: Dict[str, Any] = {}
    try:
        from .canon_keys import canonical_samples as _cs71
        _tape7 = _cs71(out)
    except Exception:
        for _fn7 in ("price_samples.json", "ccxt_samples.json",
                     "metals_samples.json", "energy_samples.json"):
            try:
                _tape7.update(json.loads((out / _fn7).read_text()).get("samples", {}))
            except Exception:
                pass
    _regimes = (live.get("regimes") or {}) if isinstance(live, dict) else {}
    # ── 7.0.5 EXPANSION-BENCH INPUTS — measured on our own tape, never assumed. ──────────────
    # _reach[sym]  = how far this name actually travels over a day (feeds VOLATILITY HUNTER)
    # _cost7[sym]  = its real round-trip cost from the venue-routed fee model
    # _trend[sym]  = multi-window trajectory; >0 means 24h AND 72h are up (feeds TREND RIDER)
    _reach, _trend, _cost7 = {}, {}, {}
    try:
        from .paper_sim import _reachable_move as _rm7, _traj_win as _tw7, round_trip_cost as _rtc7
        # 7.1 ONE-KEY LAW: measure reach/trend/cost on the SAME canonical union the sleeves
        # trade (was a second raw merge that skipped ccxt and kept duplicate spellings).
        _samp = _tape7
        for _s7, _rows7 in _samp.items():
            try:
                _r = _rm7(_rows7, 24)
                if _r:
                    _reach[_s7] = _r
                _p24, _ = _tw7(_rows7, 24)
                _p72, _ = _tw7(_rows7, 72)
                _trend[_s7] = 1 if (_p24 is not None and _p72 is not None
                                    and _p24 > 0 and _p72 > 0) else 0
            except Exception:
                continue
    except Exception:
        pass

    def _cost_for_sym(sym, book):
        """Real round-trip cost for THIS name on the venue that would fill it."""
        if sym in _cost7:
            return _cost7[sym]
        try:
            from .paper_sim import round_trip_cost as _rtc
            _px = [p for _t, p in (_samp.get(sym) or []) if p and p > 0]
            _cost7[sym] = _rtc(_px, book) if _px else None
        except Exception:
            _cost7[sym] = None
        return _cost7[sym]
    by_industry: Dict[str, List[Dict[str, Any]]] = {}
    for book in BOOKS:
        b = live.get(book) or {}
        marks: Dict[str, float] = {}
        cands: List[tuple] = []
        for pos in b.get("positions", []) or []:
            if pos.get("mark") and pos.get("sym"):
                marks[pos["sym"]] = pos["mark"]
                marks_all[pos["sym"]] = pos["mark"]
        # ── 7.0.9 THE FROZEN WORKSHOP — the worst bug in this audit. ─────────────────────────────
        # `marks` was built ONLY from names the funded books currently hold. On the 2026-07-25 tree
        # the books held exactly one name (LTCUSDT) while the sleeves held 41 — so 41 of 41 sleeve
        # positions had NO MARK. A sleeve cannot hit a target it cannot see and cannot hit a stop it
        # cannot see, so every one of those positions was frozen: never sold, never graded, never
        # returned to the river as evidence. STRK-USD sat at +28.25% unrealised because the
        # simulator was blind to the price, not because it chose to hold.
        #
        # The workshop is the bottom of the pyramid. With it frozen, nothing matured, nothing was
        # promoted, and the whole learning chain stalled. Marks now come from the PRICE TAPE for
        # every name a sleeve holds, which is the same tape the books trade on.
        for _sk9, _sb9 in (st.get("sleeves") or {}).items():
            if not _sk9.startswith(book + ":"):
                continue
            for _sym9 in (_sb9.get("positions") or {}):
                if _sym9 in marks:
                    continue
                for _t9, _p9 in reversed(_tape7.get(_sym9) or []):
                    if _p9 and float(_p9) > 0:
                        marks[_sym9] = float(_p9)
                        marks_all[_sym9] = float(_p9)
                        break
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
            _cands_sk = cands
            if cfg.get("min_edge_ratio"):
                # 7.0.5 VOLATILITY HUNTER: keep only names whose own reachable move clears their own
                # round-trip cost by the required multiple. This is the honest reply to "why won't
                # gold trade" — it will, the day its move is worth its fees, and not before.
                _mer = float(cfg["min_edge_ratio"])
                _keep = []
                for c in cands:
                    _sym = c[0]
                    _rm = _reach.get(_sym)
                    _cst = _cost_for_sym(_sym, book)
                    if _rm and _cst and _cst > 0 and (_rm / _cst) >= _mer:
                        _keep.append(c)
                _cands_sk = _keep
            elif cfg.get("trend_only"):
                # 7.0.5 TREND RIDER: a dip is only an entry if the larger trajectory is UP. Buying
                # the pullback inside an uptrend is what a normal trader does; buying every dip is
                # what a gimmick does.
                _cands_sk = [c for c in cands if (_trend.get(c[0]) or 0) > 0]
            elif cfg.get("geometry"):
                _cands_sk = [c for c in cands
                             if (_geo.get(c[0]) or {}).get("verdict") == "TRADEABLE"]
            elif cfg.get("patient"):
                _cands_sk = [c for c in cands
                             if (((cards.get(c[0]) or {}).get("bounce_reliability") or 0) >= 0.75
                                 or ((_geo.get(c[0]) or {}).get("p_floor_pct") or 0) >= 65)]
            bk["_geo7"] = {c[0]: _geo.get(c[0]) for c in _cands_sk} if (cfg.get("geometry") or cfg.get("patient")) else None
            bk["_regime7"] = _regimes.get(book)
            _RIVER.update({"out": str(out), "sleeve": sk, "book": book})
            _run_sleeve(cfg, bk, marks, _cands_sk, conf_map, fastgreen, surge, strike_pool, cost_of)
            _RIVER.update({"out": None})
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
                # 5.3 HARVEST VIEW (M5, arithmetic approximation, labeled): what this sleeve
                # would hold if every realized win had been vaulted instead of rolled.
                "harvest_view": {
                    "reserve_usd": round(sum(max(0.0, t["pnl"]) for t in closed), 2),
                    "working_usd": round(eq - sum(max(0.0, t["pnl"]) for t in closed), 2),
                    "total_usd": round(eq, 2),
                    "note": "same trades, profits pocketed — approximation, not a resim"},
                "trades_since_wipe": len(bk["trades"]),
                "desc": cfg["desc"],
            })
        rows.sort(key=lambda r: -(r["delta_vs_hodl"] if r["delta_vs_hodl"] is not None
                                  else r["return_pct"]))
        by_industry[book] = rows

    st["generated_at"] = _now().isoformat()
    # ── 7.0.6 SLEEVE MARKS (the "bar sits at zero in the middle" bug). Sleeve positions carried
    # entry but never a MARK, so the UI's position bar fell back to mark=entry — which lands the
    # marker at exactly 50% of the stop..target range for every open trade, forever. Stamping the
    # live mark (and the sleeve's own target/stop) makes the bar show where price actually sits.
    try:
        for _sk7, _sb7 in (st.get("sleeves") or {}).items():
            _bk7 = _sk7.split(":")[0] if ":" in _sk7 else "crypto"
            _cfg7 = SLEEVES.get(_sk7.split(":")[-1]) or {}
            for _sym7, _p7 in (_sb7.get("positions") or {}).items():
                # 7.0.8 THE ACTUAL FIX. 7.0.6 sourced marks only from LIVE BOOK positions — but a
                # sleeve holds names the books do not (ENA, WAVES, RUNE, BNB, BAL...). So marks_all
                # was empty for 118 of 118 sleeve positions and every bar still read "entry -> entry
                # +0.00%". Marks now come from the PRICE TAPE, which prices every name we hold.
                _mk7 = marks_all.get(_sym7)
                if not _mk7:
                    _rows7 = _tape7.get(_sym7) or []
                    for _t7, _px7 in reversed(_rows7):
                        if _px7 and float(_px7) > 0:
                            _mk7 = float(_px7)
                            break
                if _mk7:
                    _p7["mark"] = round(float(_mk7), 8)
                    if _p7.get("entry"):
                        _p7["upl_pct"] = round((float(_mk7) / float(_p7["entry"]) - 1) * 100, 3)
                _p7.setdefault("target", _p7.get("target"))
                _p7.setdefault("stop", _p7.get("stop"))
    except Exception:
        pass
    st["by_industry"] = by_industry
    # 7.0.2 PYRAMID: publish each sleeve's DISCIPLINE so sleeve_promotion can hand the
    # winner's playbook up to its industry book. Read-only export — sleeve behaviour is
    # never altered by this, only made legible upstairs (operator: "only want the best of
    # them selected for use, do not alter their behavior").
    st["sleeves_def"] = {k: {kk: vv for kk, vv in v.items() if kk != "desc"}
                         for k, v in SLEEVES.items()}
    st["scoreboard"] = by_industry.get("crypto", [])
    st["what"] = ("per-industry A–F discipline race: same entries per industry, differing ONLY in "
                  "position management. A = the control (current live behavior). E = ADAPTIVE "
                  "STRIKER (opens strike slots on a surge — the never-miss-the-big-day test). "
                  "F = CASH HARVESTER (profits vaulted; $10k working base — profits are only "
                  "profits when they leave the table). Judged on compounding, never win rate; "
                  "kill after 40 closed if trailing that industry's A.")
    write_json_atomic(out / STORE, st)
    # ── 7.0 ONE-UNIVERSE: publish the river summary + the CHAMPION SLEEVE spotlight ──
    try:
        _per, _tot, _24 = {}, 0, 0
        _cut = (_now() - __import__("datetime").timedelta(hours=24)).isoformat()
        _lp = out / "LAB_OUTCOMES.jsonl"
        if _lp.exists():
            for _ln in _lp.read_text().splitlines()[-5000:]:
                try:
                    _r = json.loads(_ln)
                except Exception:
                    continue
                _tot += 1
                if str(_r.get("t", "")) >= _cut:
                    _24 += 1
                _e = _per.setdefault(_r.get("sym"), {"n": 0, "wins": 0})
                _e["n"] += 1
                _e["wins"] += 1 if _r.get("win") else 0
        _spot, _sbook = None, None
        for _bk2, _rows2 in by_industry.items():
            for _r2 in _rows2:
                if (_r2.get("closed") or 0) >= 3 and _r2.get("delta_vs_hodl") is not None:
                    if _spot is None or _r2["delta_vs_hodl"] > _spot["delta_vs_hodl"]:
                        _spot, _sbook = dict(_r2), _bk2
        if _spot is None:   # pre-null-data fallback: best return with >=1 close
            for _bk2, _rows2 in by_industry.items():
                for _r2 in _rows2:
                    if (_r2.get("closed") or 0) >= 1:
                        if _spot is None or _r2["return_pct"] > _spot["return_pct"]:
                            _spot, _sbook = dict(_r2), _bk2
        if _spot is not None:
            _spot["book"] = _sbook
        write_json_atomic(out / "LAB_EVIDENCE.json", {
            "generated_at": _now().isoformat(),
            "resolved_total": _tot, "resolved_24h": _24,
            "per_symbol": {k: v for k, v in sorted(_per.items(), key=lambda kv: -kv[1]["n"])[:200]},
            "spotlight": _spot,
            "what": ("ONE UNIVERSE: sleeves trade the books' own candidates; every sleeve close lands "
                     "here as a resolved outcome that COUNTS toward the real books' maturity gate. "
                     "spotlight = best sleeve by delta-vs-HODL (>=3 closes; Law 10), the leader to cheer.")})
    except Exception:
        pass
    _lead = {bk: (rows[0]["sleeve"] if rows else "-") for bk, rows in by_industry.items()}
    return {"summary": f"strategy lab v2: leaders {_lead} · 24 sleeves across 4 industries"}
