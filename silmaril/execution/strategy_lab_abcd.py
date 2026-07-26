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
# 7.1.4: last real print time per symbol, so an exit taken across a sampling outage can say
# so. SHIB-USD's -6.342% STOP on 2026-07-26 crossed a 2h52m hole in the tape; the fill was
# honest but nobody was watching, and evidence nobody watched should not weigh the same.
_LASTPRINT: Dict[str, Any] = {}

# 7.1.4 THE ONE FRESH PRICE LAW. The forensics of the "$242.19 / +11.533% TARGET" fill:
# PNUT-USD was bought at ~0.0397 and sold at 0.0443. The tape's only prints near 0.0397 are
# from the PREVIOUS morning; at the moment of the buy the freshest print was 0.0448. So the
# ENTRY was priced from a stale/derived number while the EXIT was priced from the live tape —
# two different prices for one position, which fabricates P&L out of nothing. Worse, that
# fabricated win went straight into LAB_OUTCOMES.jsonl as 1 of only 5 pieces of evidence the
# maturity gate and sleeve promotion had to learn from.
#
# The law, in three parts, so the class cannot recur whichever store leaks next:
#   1. Only the TAPE may price a fill. Derived stores (confidence cards, traces, rosters) may
#      RANK and SUGGEST; they may never set an entry or exit price.
#   2. No fill on a stale print. If the freshest print for a name is older than the window,
#      there is no fill — the position simply stays armed, exactly as a real venue would leave
#      a resting order unfilled.
#   3. Every fill stamps the age of the print it used, so a future leak is visible in the
#      record instead of hiding inside a plausible number.
# The limit-fill cap in _sell is the backstop: even if a stale price ever slips through again,
# a take-profit cannot fill above its limit, so a windfall is impossible by construction.
MAX_PX_AGE_MIN = 45.0


def _px_age_min(sym: str) -> Optional[float]:
    """Minutes since this name last actually printed, or None when unknown."""
    try:
        t = _LASTPRINT.get(sym)
        if not t:
            return None
        return max(0.0, (_now() - t).total_seconds() / 60.0)
    except Exception:
        return None


def _px_is_fresh(sym: str) -> bool:
    """A fill may only happen on a print we can still call current. Unknown age is NOT fresh —
    with money on the line, "we don't know how old this is" must mean no."""
    a = _px_age_min(sym)
    return a is not None and a <= MAX_PX_AGE_MIN


def _sell(bk: Dict[str, Any], sym: str, price: float, why: str, vault: bool,
          intended: float = None, gap_h: float = None):
    """7.1.4 THE LIMIT-FILL LAW — the fix for the "$242.19 / +11.533% TARGET" trade.

    THE INCIDENT (2026-07-26 06:52): sleeve E held PNUT-USD with a STRIKE target of +4%.
    Price rose past the target between cycles and the exit booked at the SAMPLED mark —
    +11.533%, a $242 windfall on a $2,100 wager. Then it went straight into
    LAB_OUTCOMES.jsonl, where it was 1 of only 5 pieces of evidence the maturity gate and
    sleeve promotion had to learn from. A single unreal fill was 20% of the system's
    knowledge. That is exactly the corruption the operator kept sensing.

    THE LAW — how real execution actually works, and the asymmetry is the whole point:
      * A take-profit is a LIMIT order. It CANNOT fill above its limit. Ever. So a TARGET
        exit fills at the target price, never at a mark above it. Windfalls are impossible
        by construction, not by luck.
      * A stop is a MARKET order. It CAN fill worse than the trigger. So a STOP exit fills
        at the WORSE of the stop price and the mark — slippage is real and must be worn.
      * A trailing/discretionary exit fills at the mark; that is what it is.
    Every capped fill is stamped so the record shows what was given up, and any fill made
    across a sampling gap is stamped too, so learning can discount what it could not see.
    This is also the honesty bar for live handoff: paper fills a live venue would refuse
    are not evidence."""
    pos = bk["positions"].get(sym)
    if not pos or price <= 0:
        return
    fill_px, capped, forgone = price, False, 0.0
    if intended is not None and intended > 0:
        if why == "TARGET" and price > intended:          # a limit cannot overfill
            forgone = (price / intended - 1) * 100.0
            fill_px, capped = intended, True
        elif why == "STOP" and price > intended:          # never better than the trigger
            fill_px, capped = intended, True
    eff = fill_px * (1 - pos.get("cost", MIN_COST) / 2.0)
    proceeds = pos["qty"] * eff
    pnl = proceeds - pos["qty"] * pos["entry"]
    bk["cash"] += proceeds
    bk["realized_pnl"] += pnl
    if vault and pnl > 0:
        bk["cash"] -= pnl
        bk["vault_usd"] = round(bk.get("vault_usd", 0.0) + pnl, 2)
    _rec = {"side": "SELL", "sym": sym, "why": why, "simulated": True,
            "pnl": round(pnl, 2),
            "realized_pct": round((eff / pos["entry"] - 1) * 100, 3) if pos["entry"] > 0 else 0,
            "style": pos.get("style", "MR"),
            "entry": pos.get("entry"), "exit": round(fill_px, 12),
            "mark_seen": round(price, 12),
            "opened_t": pos.get("t"),
            "t": _now().isoformat()}
    if capped:
        _rec["fill_capped"] = True
        _rec["limit_px"] = round(intended, 12)
        if forgone > 0.001:
            _rec["forgone_pct"] = round(forgone, 3)
            _rec["why_capped"] = ("a take-profit limit cannot fill above its limit — the mark ran "
                                  "%.2f%% past it between cycles and that excess is not ours" % forgone)
    if gap_h and gap_h > 0.75:
        _rec["gap_fill_h"] = round(gap_h, 2)
        _rec["why_gap"] = ("the tape had no print for %.1fh before this exit — the fill is honest "
                           "but unobserved, so it should carry less weight than a watched one" % gap_h)
    bk["trades"].append(_rec)
    try:  # ONE-UNIVERSE RIVER: resolved workshop outcome → shared evidence ledger
        if _RIVER.get("out"):
            with open(Path(_RIVER["out"]) / "LAB_OUTCOMES.jsonl", "a") as _rf:
                _rf.write(json.dumps({
                    "t": _now().isoformat(), "sym": sym,
                    "book": _RIVER.get("book"), "sleeve": _RIVER.get("sleeve"),
                    "why": why, "pnl": round(pnl, 2),
                    "net_pct": round((eff / pos["entry"] - 1) * 100, 3) if pos["entry"] > 0 else 0,
                    "win": pnl > 0, "style": pos.get("style", "MR"),
                    "fill_capped": bool(capped), "gap_fill_h": (round(gap_h, 2) if gap_h else None),
                    "source": "strategy_lab"}) + "\n")
    except Exception:
        pass
    del bk["positions"][sym]


# ── 7.1.5 THE PER-SYMBOL CALENDAR ──────────────────────────────────────────────────────
# 7.1.4 gated by BOOK and got it wrong in both directions. The metal book holds XAU, XAG,
# XPT, XPD, XCU — SPOT metals, not ETFs — and spot metal never closed on weekends the way an
# equity does; blocking the whole book on a Saturday silenced instruments that were trading
# fine. Meanwhile the stock book holds real equities that must respect the NYSE session.
# One calendar per BOOK cannot be right for both, so the calendar is now per SYMBOL.
#
# Operator note, 2026-07-26: CME's 1-Ounce Gold future moved to 24/7 on this date, and a 24/7
# 10-Barrel WTI contract is scheduled for 2026-08-30. Our metal/energy books trade the SPOT
# series, which already price around the clock on weekdays; gold now prices on weekends too.
# The table below encodes that, with the WTI date pre-registered so it flips itself.
SPOT_24_7 = {"XAU"}                                   # CME 1oz gold: 24/7 from 2026-07-26
SPOT_24_5 = {"XAG", "XPT", "XPD", "XCU",              # spot metals: Sun 22:00 → Fri 21:00 UTC
             "BRENT", "WTI", "NATGAS", "GASOIL"}      # energy spot/futures: same window
WTI_24_7_FROM = datetime(2026, 8, 30, tzinfo=timezone.utc)
_US_ETF = {"GLD", "IAU", "SLV", "GDX", "SIVR", "PPLT", "PALL", "CPER",
           "USO", "USL", "USOI", "UNG", "BNO", "UGA", "SPY", "QQQ"}


# ── 7.1.5 THE RAILS THE SLEEVES NEVER GOT ─────────────────────────────────────────────
# The audit that produced this release: the BOOKS carry a re-entry cooldown (4 references), a
# trajectory veto (11 references) and a market calendar, accumulated over six releases of hard
# lessons. The SLEEVES carried NONE of them. Grep score before this change —
#   cooldown: books 3, sleeves 0 · re-entry: books 4, sleeves 0 · trajectory: books 11, sleeves 0
# and the workshop's results read exactly like a book with no rails would:
#
#   G GEOMETRY SNIPER — 4 closed, 0% win, every one a STOP. And the ledger shows why:
#       SELL XTZ-USD  STOP 08:47:54   ->  BUY XTZ-USD 08:47:54   (the same second)
#       SELL TURBO    STOP 12:18:42   ->  BUY TURBO   12:18:42   (the same second)
#       SELL XMR-USD  STOP 17:31:23   ->  BUY XMR-USD 17:31:23   (the same second)
#     It stopped out and instantly re-bought the identical falling name, over and over. That is
#     not a bad strategy; that is a strategy with no cooldown, feeding itself into a knife.
#
#   H PATIENT REVERT — 2 closed, 0% win, both STOPs, both on names in confirmed downtrends
#     (XTZ: peaks FALLING, -1.6% 1D / -2.2% 2D / -2.2% 3D; TURBO likewise). Mean reversion wants
#     oversold-in-a-RANGE. Bought in free-fall it is just early.
#
# Two rails, both mirroring what the books already do, both knob-gated with a kill switch.
REENTRY_COOLDOWN_MIN = 180.0        # matches the books' 180-minute re-entry cooldown
STOPPED_COOLDOWN_MIN = 360.0        # a name that stopped us out earns a longer timeout


def _cooldown_ok(bk: Dict[str, Any], sym: str) -> tuple:
    """(may_enter, why_not). A name we just exited is not a fresh idea — least of all one that
    just stopped us out. This single rail is what breaks G's stop→rebuy loop."""
    try:
        last, was_stop = None, False
        for t in reversed(bk.get("trades") or []):
            if t.get("side") == "SELL" and t.get("sym") == sym:
                last = _parse(t.get("t"))
                was_stop = str(t.get("why") or "").upper() == "STOP"
                break
        if not last:
            return True, None
        mins = (_now() - last).total_seconds() / 60.0
        bar = STOPPED_COOLDOWN_MIN if was_stop else REENTRY_COOLDOWN_MIN
        if mins < bar:
            return False, ("cooldown — %s %s us %.0fm ago; a name we just exited is not a fresh "
                           "idea for another %.0fm" % (sym, "stopped" if was_stop else "closed",
                                                       mins, bar - mins))
    except Exception:
        pass
    return True, None


def _peaks_falling(rows: List) -> Optional[bool]:
    """Is this name making LOWER highs? The graph brain's most basic read, finally consulted by
    a decision instead of only drawn. None when there is not enough structure to judge."""
    try:
        live = [(t, float(p)) for t, p in (rows or [])
                if p and float(p) > 0 and "T00:00:00" not in str(t)]
        if len(live) < 30:
            return None
        ys = [p for _t, p in live][-400:]
        n = len(ys)
        rets = sorted(abs(ys[i] / ys[i - 1] - 1) for i in range(1, n) if ys[i - 1] > 0)
        sig = rets[len(rets) // 2] if rets else 0.001
        prom, w = max(sig * 3, 0.002), max(2, n // 40)
        peaks = []
        for i in range(w, n - w):
            if ys[i] == max(ys[i - w:i + w + 1]):
                base = min(ys[max(0, i - w * 3):i + 1])
                if base > 0 and ys[i] / base - 1 >= prom:
                    peaks.append(ys[i])
        if len(peaks) < 3:
            return None
        lp = peaks[-3:]
        return lp[-1] < lp[0] * 0.998
    except Exception:
        return None


def _trajectory_ok(sym: str, rows: List, cfg: Dict[str, Any]) -> tuple:
    """(may_enter, why_not). Mean reversion wants oversold-in-a-range, never free-fall. If the
    name is down across EVERY window AND its peaks are stepping down, this is not a dip — it is
    a decline, and buying it is what cost H both of its trades.

    This is the first time the graph's own read gates a decision rather than decorating one. It
    is deliberately a VETO, not a signal: a veto can only prevent a trade the system was already
    about to take, so it cannot manufacture a new class of loss. Its effect is logged for the
    graph→decision audit to grade."""
    if not cfg.get("respect_trajectory", True):
        return True, None
    try:
        from .paper_sim import _traj_win as _tw
        wins = []
        for h in (4, 12, 24):
            pct, basis = _tw([(str(t), float(p)) for t, p in (rows or []) if p], h)
            if pct is not None:
                wins.append(pct)
        if len(wins) >= 2 and all(w < -0.005 for w in wins):
            if _peaks_falling(rows) is True:
                return False, ("trajectory veto — %s is down across every window (%s) and its "
                               "peaks are stepping down. That is a decline, not a dip; mean "
                               "reversion wants oversold-in-a-range."
                               % (sym, ", ".join("%.2f%%" % (w * 100) for w in wins)))
    except Exception:
        pass
    return True, None


def _market_open_for_symbol(sym: str, book: str = None) -> bool:
    """May we OPEN a position in this instrument right now?

    Conservative by construction: anything unrecognised falls through to the equity session,
    because a missed entry costs nothing and a fill against a frozen weekend print corrupts the
    record — which is exactly what the Sunday IRM trade did."""
    s = (sym or "").upper()
    t = _now().astimezone(timezone.utc)
    wd, mins = t.weekday(), t.hour * 60 + t.minute

    if book in ("crypto", "aggressive") or s.endswith("-USD") or s.endswith("USDT"):
        return True                                    # crypto never closes
    if s in SPOT_24_7 or (s == "WTI" and t >= WTI_24_7_FROM):
        return True                                    # 24/7 spot (gold today, WTI from Aug 30)
    if s in SPOT_24_5:
        # the global 24/5 window: closes Fri 21:00 UTC, reopens Sun 22:00 UTC
        if wd == 5:
            return False
        if wd == 4 and mins >= 21 * 60:
            return False
        if wd == 6 and mins < 22 * 60:
            return False
        return True
    if s in _US_ETF or book in ("stock", "metal", "energy"):
        if wd >= 5:
            return False
        return (13 * 60 + 30) <= mins <= (20 * 60)     # NYSE regular session, UTC
    return False


def _market_open_for(book: str) -> bool:
    """Book-level convenience kept for callers that ask 'is anything in this book open?'.
    A book is open if ANY of its instruments is — the per-symbol gate does the real work."""
    if book in (None, "crypto", "aggressive"):
        return True
    probe = {"metal": ("XAU", "XAG", "GLD"), "energy": ("BRENT", "WTI", "USO"),
             "stock": ("SPY",)}.get(book, ("SPY",))
    return any(_market_open_for_symbol(x, book) for x in probe)


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
        if not _px_is_fresh(sym):
            pos["stale_px"] = True            # armed, not filled — never exit on fiction
            continue
        pos.pop("stale_px", None)
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
        _gap_h = None
        try:
            _lt = _LASTPRINT.get(sym)
            if _lt:
                _gap_h = max(0.0, (now - _lt).total_seconds() / 3600.0)
        except Exception:
            _gap_h = None
        if chg >= tgt and not riding:
            _sell(bk, sym, cur, "TARGET", vault,
                  intended=pos["entry"] * (1.0 + tgt), gap_h=_gap_h); continue
        if chg <= -stop:
            _sell(bk, sym, cur, "STOP", vault,
                  intended=pos["entry"] * (1.0 - stop), gap_h=_gap_h); continue
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
            # THE ONE FRESH PRICE LAW: the STRIKE pool is ranked from confidence cards, but it
            # may not be PRICED from them. Re-price from the tape and refuse a stale fill.
            _tp = marks.get(sym)
            if not _tp or _tp <= 0 or not _px_is_fresh(sym):
                continue
            if not _market_open_for_symbol(sym, _book7):
                continue
            _ok, _why = _cooldown_ok(bk, sym)
            if not _ok:
                _vetoes.append({"sym": sym, "sleeve": cfg.get("sleeve"), "why": _why})
                continue
            _ok, _why = _trajectory_ok(sym, tape.get(sym), cfg)
            if not _ok:
                _vetoes.append({"sym": sym, "sleeve": cfg.get("sleeve"), "why": _why})
                continue
            px = _tp
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
                                 "entry": px, "px_age_min": round(_px_age_min(sym) or 0.0, 1),
                                 "target_pct": 4.0, "stop_pct": 5.0,
                                 "t": now.isoformat()})
            room -= 1

    # ── 7.1.4 THE MARKET CALENDAR LAW ────────────────────────────────────────────────
    # THE INCIDENT: on Sunday 2026-07-26 sleeve E opened IRM at $128.31 with "entry -> now"
    # both reading $128.31 — because the price was Friday's close and NYSE has been shut for
    # two days. The funded books have carried a market-closed gate for releases; the SLEEVES
    # never had one, so the whole workshop could trade equities, metals and energy all
    # weekend against frozen prices. Those fills are pure fiction: a live broker would have
    # queued the order to Monday's open and filled somewhere else entirely. Crypto is 24/7
    # and unaffected. This gate blocks ENTRIES only — exits and marks continue, exactly as a
    # real desk manages a position through a closed session.
    _book7 = bk.get("_book7")
    _vetoes = bk.setdefault("_vetoes7", [])
    tape = bk.get("_tape7") or {}
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
            _tp = marks.get(sym)
            if not _tp or _tp <= 0 or not _px_is_fresh(sym):
                continue                      # tape-priced, fresh-only (see THE ONE FRESH PRICE LAW)
            if not _market_open_for_symbol(sym, _book7):
                continue
            _ok, _why = _cooldown_ok(bk, sym)
            if not _ok:
                _vetoes.append({"sym": sym, "sleeve": cfg.get("sleeve"), "why": _why})
                continue
            _ok, _why = _trajectory_ok(sym, tape.get(sym), cfg)
            if not _ok:
                _vetoes.append({"sym": sym, "sleeve": cfg.get("sleeve"), "why": _why})
                continue
            px = _tp
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
                                 "wager_usd": round(budget, 2), "entry": px,
                                 "px_age_min": round(_px_age_min(sym) or 0.0, 1),
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
    # 7.1.4: remember when each name last actually printed, so an exit taken across a hole in
    # the tape can be stamped as unobserved (see _sell's gap_h).
    try:
        _LASTPRINT.clear()
        for _s7, _rw7 in (_tape7 or {}).items():
            for _r7 in reversed(_rw7 or []):
                if _r7 and len(_r7) >= 2 and _r7[1] and float(_r7[1]) > 0 and "T00:00:00" not in str(_r7[0]):
                    _dt7 = _parse(_r7[0])
                    if _dt7:
                        _LASTPRINT[_s7] = _dt7
                    break
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
        # 7.1.4: EVERY name in this book's candidate stream is priced from the TAPE, up front.
        # Previously marks were seeded from book positions and held-sleeve names only, and any
        # other candidate fell back to a derived store's last_px — the stale-entry vector.
        for _sy4, _rw4 in (_tape7 or {}).items():
            for _t4, _p4 in reversed(_rw4 or []):
                try:
                    if _p4 and float(_p4) > 0 and "T00:00:00" not in str(_t4):
                        marks[_sy4] = float(_p4)
                        marks_all[_sy4] = float(_p4)
                        break
                except Exception:
                    break
        for pos in b.get("positions", []) or []:
            if pos.get("mark") and pos.get("sym") and pos["sym"] not in marks:
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
                    # 7.1.4: a daily-backfill candle is not a live mark (backfill-poisoning law)
                    if _p9 and float(_p9) > 0 and "T00:00:00" not in str(_t9):
                        marks[_sym9] = float(_p9)
                        marks_all[_sym9] = float(_p9)
                        break
        for d in b.get("decision_trace_live") or []:
            sym = d.get("sym")
            if not sym:
                continue
            # THE ONE FRESH PRICE LAW: price from the TAPE only. The card's last_px may be
            # hours old on a fast pass, and pairing a stale entry with a live exit is exactly
            # how the PNUT windfall was manufactured. A name with no tape mark is not a
            # candidate at all — it is a name we cannot honestly price.
            px = marks.get(sym)
            if px:
                cands.append((sym, px, (d.get("dip_pct") or 0) / 100.0, d.get("conviction") or 0))
        pool = []
        for sym, c in cards.items():
            if c.get("class") != book or not c.get("last_px"):
                continue
            mom = ((c.get("momentum") or {}).get("h1"))
            if mom is not None and mom >= 3.0:
                # ranked by the card, PRICED by the tape (or skipped entirely)
                _tpx = marks.get(sym)
                if _tpx and _tpx > 0:
                    pool.append((sym, _tpx, round(float(mom), 2)))
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
            bk["_book7"] = book
            bk["_tape7"] = _tape7
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
    # ── 7.1.5: publish WHY each sleeve stayed out. "Quiet by correct design" and "actually
    # broken" look identical from the outside unless the vetoes are written down, and the
    # operator has had to guess between them for weeks. Now the workshop states its reasons.
    try:
        _vall, _counts = [], {}
        for _k, _b in (st.get("sleeves") or {}).items():
            for _v in (_b.pop("_vetoes7", None) or []):
                _v = dict(_v); _v["book"] = _k.split(":")[0]
                _vall.append(_v)
                _kind = ("cooldown" if "cooldown" in (_v.get("why") or "")
                         else "trajectory" if "trajectory veto" in (_v.get("why") or "") else "other")
                _counts[_kind] = _counts.get(_kind, 0) + 1
            _b.pop("_tape7", None); _b.pop("_book7", None)
        write_json_atomic(out / "SLEEVE_VETOES.json", {
            "generated_at": _now().isoformat(),
            "what": ("every entry a sleeve DECLINED this cycle and the exact rail that stopped it. "
                     "A workshop that is quiet because its rails are working looks identical to a "
                     "broken one until it says so."),
            "counts": _counts, "total": len(_vall), "vetoes": _vall[:300],
            "rails": {"reentry_cooldown_min": REENTRY_COOLDOWN_MIN,
                      "stopped_cooldown_min": STOPPED_COOLDOWN_MIN,
                      "trajectory_veto": "down across every window AND peaks stepping down"},
        })
    except Exception:
        pass
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
                if _r.get("excluded"):
                    continue          # 7.1.4: quarantined fabricated fills are not evidence
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
