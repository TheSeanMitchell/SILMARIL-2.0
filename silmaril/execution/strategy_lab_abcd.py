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
from datetime import datetime, timedelta, timezone
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
    # ══ 7.1.8 THE RATIO BENCH ═══════════════════════════════════════════════════════════
    # Three sleeves built on ONE finding, which is arithmetic rather than prediction:
    #
    #     required win rate = stop / (target + stop)
    #
    # Every existing sleeve inherits a BLANKET 6% stop from the fingerprint default, while its
    # target is measured per name. H PATIENT REVERT aims ~0.78% against that 6% stop, so it
    # needs 6/6.78 = 88.5% just to break even. It delivers 88.6% — the highest win rate in the
    # whole workshop — and still loses money, because it was set an impossible bar. That is not
    # a broken sleeve; it is a broken ratio, and the ratio is the one number nobody measured.
    #
    # These three attack it from three different directions. All of them size the STOP from
    # evidence instead of a constant, all of them refuse a shape whose arithmetic cannot pay,
    # and all of them are knob-gated. They do not promise edge — they promise that when they
    # win, winning is worth something, and that they never take a trade the maths forbids.
    "L": {"name": "TOLLBOOTH", "cap": 5, "recycle_h": 24, "ride_winners": False,
          "conf_gate": 0.0, "strike_extra": 0, "vault": True,
          "measured_stop": True, "min_rr": 1.6, "wr_margin": 0.08, "max_hold_h": 18,
          "desc": ("7.1.8 RATIO BENCH #1 — the arithmetic-first sleeve. Stop is MEASURED from the "
                   "name's own adverse excursion (how far it actually goes against you before the "
                   "bounce arrives), never the 6% default. Requires target/stop >= 1.6, which caps "
                   "the required win rate at ~38%, and additionally demands the name's measured "
                   "bounce reliability beat that requirement by 8 points. Small, frequent, vaulted: "
                   "it collects a modest toll many times with the maths on its side, instead of "
                   "winning 9 times out of 10 for nothing. If H's problem is the ratio, L is the "
                   "control that proves it")},
    "M": {"name": "FLOOR ARTIST", "cap": 4, "recycle_h": 48, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False,
          "structure_entry": True, "floor_tests": 3, "floor_prox_pct": 1.5,
          "measured_stop": True, "stop_below_floor_pct": 0.6, "target_at_ceiling": True,
          "desc": ("7.1.8 RATIO BENCH #2 — the first sleeve whose ENTRY is chosen by the graph. "
                   "Buys only within 0.8% of a floor the tape has TESTED at least 3 times, places "
                   "its stop just 0.6% BELOW that floor (the level's natural invalidation point, "
                   "which is what makes the stop tight and honest rather than arbitrary), and takes "
                   "profit at the nearest ceiling above. Reward and risk are both read off real "
                   "structure, so the ratio is a property of the setup instead of a guess. This is "
                   "the answer to 'make the graph drive decisions' — if floors and ceilings carry "
                   "information, this sleeve converts it into money or proves it does not")},
    "N": {"name": "CEILING SWEEP", "cap": 4, "recycle_h": 36, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": True,
          "measured_stop": True, "min_rr": 1.3, "sweep_at_ceiling": True,
          "sweep_stall_cycles": 2, "sweep_min_net_pct": 0.35, "max_hold_h": 30,
          "desc": ("7.1.8 RATIO BENCH #3 — the operator's own idea, implemented: 'is there a way to "
                   "sweep profits when they don't hit their GOAL, but it would be profitable to take "
                   "the new ceiling as it is established?' Yes. This sleeve exits on STRUCTURE, not "
                   "on a fixed number: when price reaches a ceiling the tape has tested at least "
                   "twice AND the last two cycles failed to make a new high, it takes the money — "
                   "provided the fill clears fees with real margin. It also sweeps a profitable "
                   "position whose cadence says its peak has already passed. Never sweeps a loss: "
                   "the stop still owns the downside")},
    # ══ 7.1.9 THE ROTATION BENCH ════════════════════════════════════════════════════════
    # The operator's real question is no longer "does a sleeve work" — M FLOOR ARTIST is green
    # in all four books and B CAP ONLY leads metal and energy. It is: **how do we know WHICH
    # sleeve will win BEFORE it trades, instead of finding out afterwards?** These three attack
    # that directly. They are experiments in SELECTION, not new entry gimmicks.
    "O": {"name": "REGIME SWITCHER", "cap": 4, "recycle_h": 48, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False,
          "measured_stop": True, "min_rr": 1.3, "regime_adaptive": True,
          "desc": ("7.1.9 ROTATION #1 — one sleeve, three personalities, chosen by the REGIME the "
                   "book is actually in. SIDEWAYS: mean-revert (buy the dip, take the ceiling). "
                   "UPTREND: buy the pullback and trail (never sell into strength). DOWNTREND: "
                   "refuse to open at all and sit in cash. Every existing sleeve runs one fixed "
                   "personality in every weather; this one asks what weather it is first. If the "
                   "regime classifier has any predictive value, O converts it into money — and if "
                   "it does not, O will underperform its own components and prove that too")},
    "P": {"name": "SURVIVOR" , "cap": 3, "recycle_h": 36, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": True,
          "measured_stop": True, "min_rr": 1.5, "survivor_only": True, "survivor_min_n": 4,
          "desc": ("7.1.9 ROTATION #2 — the meta-sleeve. It has NO opinion about markets. Each "
                   "cycle it copies whichever sleeve in ITS OWN book currently has the best "
                   "delta-vs-null over at least 4 closed trades, and re-elects every cycle. This "
                   "is the rotation system as a testable hypothesis: if past sleeve performance "
                   "predicts future sleeve performance, P beats the average sleeve; if leadership "
                   "is noise, P lands mid-pack and tells us rotation is a fantasy. Either answer "
                   "is worth more than guessing — it is the experiment that decides whether the "
                   "MASTER should rotate at all")},
    "Q": {"name": "COMPOUNDER", "cap": 2, "recycle_h": 24, "ride_winners": True,
          "conf_gate": 0.50, "strike_extra": 0, "vault": False,
          "measured_stop": True, "min_rr": 2.0, "compound": True, "max_hold_h": 12,
          "desc": ("7.1.9 ROTATION #3 — the food-on-the-table sleeve, built for turnover rather "
                   "than size. Two slots, 2:1 minimum ratio, 12-hour maximum hold, and profits are "
                   "REINVESTED rather than vaulted so position size grows with the book. The "
                   "arithmetic it is chasing: 0.5% per trade at 2 trades a day compounds to ~+45% "
                   "a quarter, while one 6% winner a month does not. Small, fast, strict — and it "
                   "will fail loudly if fees or slippage eat a target that thin, which is exactly "
                   "the thing we need to know before any of this touches real money")},
    # ══ 7.2.0 THE READER BENCH — sleeves that read the chart the way a person does ══════
    # Built on GRAPH_READ.json, the single structure object the CHART DRAWS AND THE SLEEVES
    # TRADE ON. Not a second opinion computed in parallel — literally the same numbers, so a
    # disagreement between the picture and the decision is now a bug with a name.
    #
    # Each of these is a specific human reading, written down. They are deliberately narrow:
    # a rule you can argue with is worth more than a score you cannot inspect.
    "R": {"name": "SUPPORT READER", "cap": 4, "recycle_h": 48, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False,
          "graph_entry": "support", "min_strength": 2.5, "max_band_pos": 0.30,
          "min_headroom_sigmas": 3.0, "min_rr": 1.5, "stop_below_floor_pct": 0.5,
          "desc": ("7.2.0 M FLOOR ARTIST 2.0 — everything M does, plus the four things M was "
                   "blind to. (1) LEVEL STRENGTH: a floor tested 6x two days ago is weaker "
                   "evidence than one tested 3x in the last hour, and M could not tell them "
                   "apart. (2) BREAK STATE: M would happily buy a floor that had just given "
                   "way; R refuses anything BROKEN and prefers TESTING or INTACT. (3) HEADROOM "
                   "IN THE NAME'S OWN NOISE: a 1% target under a ceiling 0.4% away is not a "
                   "trade however good the ratio looks, so R demands 3 sigma of clear air. "
                   "(4) BAND POSITION: buy in the bottom third between floor and ceiling, not "
                   "merely 'near a floor'. This is the sleeve M should have been")},
    "S": {"name": "BOUNCE READER", "cap": 3, "recycle_h": 36, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False,
          "graph_entry": "bounce", "min_strength": 2.0, "max_band_pos": 0.35,
          "min_headroom_sigmas": 2.5, "min_rr": 1.4, "stop_below_floor_pct": 0.6,
          "desc": ("7.2.0 THE PATIENT HAND — the difference between catching support and "
                   "catching a knife, which is a question of TIMING, not of level. R will buy "
                   "while price is still falling into a floor; S waits for the tape to actually "
                   "turn (approach = LIFTING_OFF or FLAT_AT off an intact level) and for the "
                   "trough sequence to stop stepping down. It will take fewer trades and enter "
                   "later and worse on price. If patience is worth more than price, S beats R; "
                   "if it is not, S proves that, and the pair is the experiment")},
    "T": {"name": "CEILING READER", "cap": 3, "recycle_h": 24, "ride_winners": False,
          "conf_gate": 0.0, "strike_extra": 0, "vault": True,
          "graph_entry": "support", "min_strength": 2.0, "max_band_pos": 0.40,
          "min_headroom_sigmas": 2.0, "min_rr": 1.3, "stop_below_floor_pct": 0.6,
          "exit_at_ceiling": True, "ceiling_prox_pct": 0.35,
          "desc": ("7.2.0 THE FULL HUMAN LOOP — buy low against structure AND sell into the "
                   "ceiling, rather than at an arbitrary percentage. T exits when price reaches "
                   "the resistance the chart actually shows, or when a new ceiling forms "
                   "underneath the old one (the tape telling you the run is over). This is the "
                   "operator's own description: 'buying low, and getting excited and when "
                   "realizing the ceiling is hitting, selling.' Vaulted, so what it takes off "
                   "the table stays off it")},
    "H": {"name": "PATIENT REVERT", "cap": 3, "recycle_h": 168, "ride_winners": False,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False, "patient": True,
          "desc": ("7.0: the operator's time-edge thesis — ONLY names with proven revert evidence "
                   "(bounce-reliability ≥0.75 or evidence floor ≥65%), WIDE vol-native stop "
                   "uncapped, hold up to 7 DAYS for the revert WE KNOW comes. If patience is the "
                   "edge, this sleeve proves it; if it isn't, this sleeve pays the tuition")},
    # == 7.3 THE EVIDENCE BENCH (U-Z) =============================================
    # Six sleeves designed FROM this project's own audited trades (2,403 closes,
    # re-scored at the REAL venue fee model: 0.068% equity / 0.325% crypto). Each
    # encodes exactly ONE measured effect, with the numbers named in its desc.
    #
    # THE MINING DEBT, STATED UP FRONT: these were designed on the same tape that
    # produced the evidence. So Law 15 is UPGRADED for them - disproven if trailing
    # this book's A sleeve after 40 closes, and NEVER called proven without
    # delta-vs-null > 0 AND per-trade t >= 3.0 on FORWARD closes only.
    "U": {"name": "PATIENCE FLOOR", "cap": 4, "recycle_h": 96, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False, "min_hold_h": 24,
          "desc": ("7.3 EVIDENCE - the hold-time curve. Holds under 2h averaged -0.45%/trade "
                   "(t=-5.29, n=605): pure noise-stopouts. 12-24h averaged +0.40% (t=+2.78) "
                   "and 24-48h +0.57% (t=+2.54). U has one law: before hour 24 NOTHING but "
                   "the hard stop may close the position. The market is not allowed to shake "
                   "it out with noise it would have recovered from by lunch")},
    "V": {"name": "WIDE STOP EARLY HARVEST", "cap": 4, "recycle_h": 72, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False,
          "measured_stop": True, "min_rr": 1.2, "wide_stop_mult": 2.0,
          "giveback_frac": 0.15, "giveback_arm_pct": 1.0,
          "desc": ("7.3 EVIDENCE - the exit asymmetry, inverted. 880 STOP exits averaged "
                   "-2.01% while 745 give-back exits banked +1.82%: the book gave its losers "
                   "twice the rope it gave its winners. V doubles the measured stop distance "
                   "(hit rarely, and only when genuinely wrong) and harvests winners at a "
                   "tight 15% give-back instead of waiting for a distant target")},
    "W": {"name": "HIGH GROUND", "cap": 4, "recycle_h": 48, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False,
          "trend_only": True, "min_band_pos": 0.60,
          "desc": ("7.3 EVIDENCE - the honestly-graded graph audit. Entries in the TOP third "
                   "of the range with trend UP were the only green bucket; buying the LOW "
                   "third (the dip) won 35.7% and lost -0.96%/trade. Every reader sleeve "
                   "R/S/T buys the dip and they are the four largest losses in the workshop. "
                   "W buys STRENGTH: top 40% of the 48h range, confirmed uptrend, never the "
                   "falling knife")},
    "X": {"name": "QUIET TAPE", "cap": 4, "recycle_h": 72, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False, "news_fade_veto": 0.5,
          "desc": ("7.3 EVIDENCE - the newsfade finding (in-sample t=-2.51 over n=582, "
                   "overlapping windows, so it carries the mining debt and must replicate). "
                   "A net-bullish headline day preceded WEAK 3-5 day returns: by the time the "
                   "wire is excited the move has been sold. X refuses any name the crowd "
                   "bought today - silence is the entry condition")},
    "Y": {"name": "INSIDER TAILWIND", "cap": 3, "recycle_h": 120, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False, "insider_gate": 1.0,
          "desc": ("7.3 EXTERNAL EVIDENCE (weakest of the six, and labelled so): only names "
                   "with recent Form 4 insider filing activity, scored by this project's own "
                   "EDGAR fetcher. NOTE the scorer counts FILINGS, not parsed transaction "
                   "codes - a pass here justifies building the real XML parser, nothing more. "
                   "Trades will be rare and live almost entirely in the stock book; that "
                   "scarcity is the design, not a defect")},
    "Z": {"name": "REGIME GATE", "cap": 5, "recycle_h": 48, "ride_winners": True,
          "conf_gate": 0.0, "strike_extra": 0, "vault": False, "regime_gate": "UPTREND",
          "desc": ("7.3 EVIDENCE - the rotation law as a sleeve, which is the operator's "
                   "original wish finally measured. Entries taken while the book's regime "
                   "read UP averaged +0.66%/trade; SIDEWAYS -0.29%; DOWN -0.98% (honest "
                   "entry-time grading, n=2,292). Z trades ONLY while this book's regime "
                   "reads UPTREND. Everything else is cash, and cash is a position")},
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


# ── 7.1.8 THE RATIO BENCH MACHINERY ───────────────────────────────────────────────────
# Everything below exists to replace ONE constant with evidence: the 6% blanket stop that set
# an 88.5% break-even bar on H and made the whole workshop's arithmetic unwinnable.


def _measured_stop(rows: List, dip: float, target: float,
                   floor_pct: float = 0.004, cap_pct: float = 0.10) -> Optional[float]:
    """How far does this name ACTUALLY go against you after a dip entry, before it either
    bounces to target or keeps falling? Measured from its own tape as the 75th percentile of
    adverse excursion — wide enough to survive normal noise, tight enough that the ratio can pay.

    This is the number that was never measured. Everything used 6%."""
    try:
        live = [(str(t), float(p)) for t, p in (rows or [])
                if p and float(p) > 0 and "T00:00:00" not in str(t)]
        if len(live) < 60:
            return None
        px = [p for _t, p in live]
        n = len(px)
        excursions = []
        i = 6
        while i < n - 2:
            ref = max(px[max(0, i - 6):i + 1])
            if ref <= 0 or (px[i] / ref - 1.0) > -dip:
                i += 1
                continue
            entry = px[i]
            worst = 0.0
            j = i + 1
            while j < n:
                ch = px[j] / entry - 1.0
                if ch <= -cap_pct:                 # ran away; this entry's excursion is the cap
                    worst = cap_pct
                    break
                worst = max(worst, -min(0.0, ch))
                if ch >= target:                   # resolved upward — record what it cost to hold
                    break
                j += 1
            excursions.append(worst)
            i = j + 1 if j > i else i + 1
        # 7.1.9: 8 excursions was too strict on a 12-day tape — it blocked L and N from EVERY
        # trade in all four books ("not enough dip history to MEASURE a stop"), while M FLOOR
        # ARTIST, which reads structure instead, traded and went green in all four. 5 is still a
        # real sample and lets the bench run; it tightens itself as history accumulates.
        if len(excursions) < 5:
            return None
        excursions.sort()
        p75 = excursions[int(len(excursions) * 0.75)]
        return max(floor_pct, min(cap_pct, p75 * 1.15))     # small buffer past the 75th percentile
    except Exception:
        return None


def _structure_levels(rows: List, lookback_h: float = 72.0) -> Dict[str, Any]:
    """Floors and ceilings with their test counts, plus the last price — the same swing maths the
    chart draws, so what a sleeve trades on is exactly what the operator sees."""
    out = {"floors": [], "ceilings": [], "px": None}
    try:
        live = [(_parse(t), float(p)) for t, p in (rows or [])
                if p and float(p) > 0 and "T00:00:00" not in str(t)]
        live = [(t, p) for t, p in live if t]
        if len(live) < 30:
            return out
        cut = _now() - timedelta(hours=lookback_h)
        win = [(t, p) for t, p in live if t >= cut] or live[-200:]
        ys = [p for _t, p in win]
        out["px"] = ys[-1]
        n = len(ys)
        rets = sorted(abs(ys[i] / ys[i - 1] - 1) for i in range(1, n) if ys[i - 1] > 0)
        sig = rets[len(rets) // 2] if rets else 0.001
        prom, w = max(sig * 3, 0.002), max(2, n // 40)
        peaks, troughs = [], []
        for i in range(w, n - w):
            seg = ys[i - w:i + w + 1]
            if ys[i] == max(seg):
                base = min(ys[max(0, i - w * 3):i + 1])
                if base > 0 and ys[i] / base - 1 >= prom:
                    peaks.append(ys[i])
            if ys[i] == min(seg):
                cap = max(ys[max(0, i - w * 3):i + 1])
                if ys[i] > 0 and cap / ys[i] - 1 >= prom:
                    troughs.append(ys[i])

        def cluster(pts):
            lv, tol = [], max(sig * 2, 0.004)
            for px in pts:
                for q in lv:
                    if abs(px / q["level"] - 1) <= tol:
                        q["level"] = (q["level"] * q["tested"] + px) / (q["tested"] + 1)
                        q["tested"] += 1
                        break
                else:
                    lv.append({"level": px, "tested": 1})
            return sorted(lv, key=lambda q: -q["tested"])

        out["floors"] = cluster(troughs)
        out["ceilings"] = cluster(peaks)
    except Exception as _e:
        # 7.1.8: a bare `except: pass` here hid a missing timedelta import for a whole release —
        # the helper returned "no structure" for every name and looked like a market condition.
        # Never silent again.
        try:
            print("  _structure_levels(%s): %s" % (rows and "rows" or "empty", _e))
        except Exception:
            pass
    return out


def _own_universe(cfg: Dict[str, Any], book: str, marks: Dict[str, float],
                  out: Any, cost_of, held: set = None) -> List[tuple]:
    """7.2.1 THE FUNNEL THAT STARVED THE WORKSHOP.

    Every sleeve — all twenty of them — was fed candidates from exactly one place:
    `decision_trace_live`, the FUNDED BOOK's mean-reversion dip scan. Measured on the
    operator's 2026-08-01 15:00 tree, that list contained **ZERO rows** for crypto. Not "no
    good candidates" — no candidates at all. So the entire workshop sat idle, and seven
    sleeves (L, N, O, Q, R, S, T) had never taken a single trade since being added.

    That is not selectivity, it is starvation, and the design error is mine. A SUPPORT READER
    does not want the names that dipped 0.5% this cycle; it wants the names sitting on a strong
    tested floor with clear air above. At the moment the pool read zero, R could have traded 5
    names, T could have traded 7, out of 130 with published structure. They never saw them.

    So a sleeve with its OWN entry thesis now scans its OWN universe: every name in this book
    with published structure, a fresh tape-priced mark, and a feed graded OK. It still passes
    every rail afterwards — cooldown, trajectory, calendar, price truth, and its own gate. The
    mean-reversion sleeves are untouched and keep using the dip funnel, because for them the
    dip IS the thesis."""
    try:
        from .graph_read import load_reads
        reads = load_reads(out) or {}
    except Exception:
        return []
    if not reads:
        return []
    from .paper_sim import asset_class
    out_rows = []
    held = held or set()
    for sym, r in reads.items():
        try:
            if sym in held:
                # 7.2.2 SECOND LEAK, same origin. bk["positions"] is keyed by SYMBOL, so
                # buying a name we already hold OVERWRITES the existing position and its
                # capital simply disappears. The mean-reversion path filtered held names out
                # of its pool; the universe scanner I added in 7.2.1 did not. crypto:R bought
                # BONK and KSM twice and lost $5,000 of a $10,000 book that way — on top of
                # the cap-guard leak, in the same release.
                continue
            if asset_class(sym) != book:
                continue
            px = marks.get(sym)
            if not px or px <= 0 or not _px_is_fresh(sym):
                continue
            if not r.get("ok"):
                continue
            # rank by how deep in its own band the name is sitting — a structure sleeve's
            # natural ordering, the way dip depth is a mean-reversion sleeve's
            bp = r.get("band_pos")
            out_rows.append((sym, px, (bp if bp is not None else 1.0), r.get("headroom_sigmas") or 0.0))
        except Exception:
            continue
    out_rows.sort(key=lambda x: (x[2], -x[3]))       # lowest in band first, most headroom first
    return [(s, px, 0.0, hs) for s, px, _bp, hs in out_rows]


def _resting_fill(rows: List, entry: float, level_chg: float, since_iso: str,
                  cur: float) -> tuple:
    """7.2.2 THE RESTING ORDER — the difference between a real exit and a glance.

    Every exit in this engine was evaluated ONLY at the moment a cycle happened to look. A real
    stop or limit does not work that way: it SITS IN THE BOOK and fills when price crosses it.
    Measured across 44 governor exits on the operator's tape, that gap cost **0.360% per exit**,
    and in the worst case a "BREAKEVEN_LOCK" — an order whose entire purpose is to exit at
    break-even — booked **-3.64%** on ONDO-USD because the cycle next looked after price had
    already fallen through. Labelling that a break-even lock was not honest.

    So: walk the tape between the last cycle and now. If price CROSSED the resting level, fill
    at the level. If it GAPPED straight past it, fill at the first print beyond — the worse of
    the two, because a gap is real and slippage is worn, never gifted. Returns
    (fill_chg, crossed) where crossed says whether a resting order would have triggered at all."""
    try:
        seg = []
        for r in (rows or []):
            if not r or len(r) < 2 or not r[1]:
                continue
            t = str(r[0])
            if "T00:00:00" in t or (since_iso and t <= since_iso):
                continue
            seg.append(float(r[1]))
        if not seg:
            return None, False
        # A resting order only triggers on a DOWNWARD CROSS. It must have been above the level
        # first — otherwise the entry print itself "crosses" it and every position exits at once.
        above = False
        prev = None
        for p in seg:
            ch = p / entry - 1.0
            if ch > level_chg:
                above = True
                prev = ch
                continue
            if above:
                # crossed on this step: a resting order fills AT its level when price passes
                # smoothly through, or at this print if the move gapped straight past it. Take
                # the worse of the two — slippage is worn, never gifted.
                return min(level_chg, ch), True
            prev = ch
        return None, False
    except Exception:
        return None, False


def _graph_shape(cfg: Dict[str, Any], sym: str, out: Any) -> tuple:
    """(ok, target, stop, why_not) for the READER BENCH — the entry a person would take.

    Reads GRAPH_READ.json, the SAME object the chart draws. Both legs come off real structure:
    the target is the ceiling the chart shows, the stop sits under the floor the chart shows.
    Every refusal names the specific thing on the chart that stopped it, so the operator can
    look at the picture and check the verdict by eye."""
    try:
        from .graph_read import load_reads
        r = (load_reads(out) or {}).get(sym)
    except Exception:
        r = None
    if not r or not r.get("ok"):
        return False, None, None, "no published structure for this name yet"

    nf, nc = r.get("nearest_floor"), r.get("nearest_ceiling")
    if not nf:
        return False, None, None, "no support below price on the chart"
    if not nc:
        return False, None, None, "no resistance above price — nothing to sell into"

    # (1) the floor must be STRONG — tests weighted by how recently it was respected
    need_str = float(cfg.get("min_strength", 2.0))
    if float(nf.get("strength") or 0) < need_str:
        return False, None, None, ("support %.6g is weak (%dx, strength %.1f, last touched %.1fh "
                                   "ago; needs %.1f)" % (nf["level"], nf["tested"], nf["strength"],
                                                         nf.get("age_h") or 0, need_str))
    # (2) it must not have just given way — the single most dangerous thing to buy
    if r.get("break_state") == "BROKEN":
        return False, None, None, ("support %.6g has BROKEN (price %.2f%% through it) — a floor "
                                   "that just failed is not support"
                                   % (nf["level"], r.get("broke_by_pct") or 0))
    # (3) we must be LOW in the band, not merely near a level
    bp = r.get("band_pos")
    if bp is None:
        return False, None, None, "cannot locate price between floor and ceiling"
    if bp > float(cfg.get("max_band_pos", 0.30)):
        return False, None, None, ("price sits %.0f%% of the way up the band; this sleeve buys "
                                   "the bottom %.0f%%" % (bp * 100, float(cfg.get("max_band_pos", 0.30)) * 100))
    # (4) clear air to the ceiling, measured in the name's OWN noise
    hs = r.get("headroom_sigmas")
    need_hs = float(cfg.get("min_headroom_sigmas", 2.5))
    if hs is None or hs < need_hs:
        return False, None, None, ("only %.1f sigma of clear air to resistance %.6g (needs %.1f) "
                                   "— the target is inside the noise"
                                   % (hs or 0.0, nc["level"], need_hs))
    # (5) S BOUNCE READER additionally waits for the turn — timing, not level
    if cfg.get("graph_entry") == "bounce":
        if r.get("approach") == "FALLING_INTO":
            return False, None, None, ("still falling into support at %.2f%%/print — waiting for "
                                       "the tape to turn rather than catching the knife"
                                       % (r.get("approach_slope_pct") or 0))
        if r.get("trough_trajectory") == "FALLING":
            return False, None, None, "troughs are still stepping down — the base has not formed"

    px = float(r["px"])
    stop_px = nf["level"] * (1.0 - float(cfg.get("stop_below_floor_pct", 0.5)) / 100.0)
    stop = max(0.003, (px - stop_px) / px)
    tgt = (nc["level"] / px) - 1.0
    rr = tgt / max(stop, 1e-9)
    if rr < float(cfg.get("min_rr", 1.4)):
        return False, None, None, ("chart pays %.2f:1 (%.2f%% up to %.6g, %.2f%% down to under "
                                   "%.6g) — below the %.2f:1 this sleeve requires"
                                   % (rr, tgt * 100, nc["level"], stop * 100, nf["level"],
                                      float(cfg.get("min_rr", 1.4))))
    return True, tgt, stop, None


def _ceiling_exit(cfg: Dict[str, Any], sym: str, out: Any, chg: float, cost: float) -> tuple:
    """T CEILING READER's exit: sell into the resistance the chart shows, or when a NEW ceiling
    forms below the old one — the tape's way of saying the run is finished. Never sells a loss."""
    if not cfg.get("exit_at_ceiling"):
        return False, None
    if chg <= cost:
        return False, None
    try:
        from .graph_read import load_reads
        r = (load_reads(out) or {}).get(sym)
    except Exception:
        r = None
    if not r or not r.get("ok"):
        return False, None
    hp = r.get("headroom_pct")
    if hp is not None and hp <= float(cfg.get("ceiling_prox_pct", 0.35)):
        nc = r.get("nearest_ceiling") or {}
        return True, ("reached resistance %.6g (%dx tested, %.2f%% headroom left) — selling into "
                      "the ceiling the chart shows rather than a number we invented"
                      % (nc.get("level") or 0, nc.get("tested") or 0, hp))
    if r.get("peak_trajectory") == "FALLING" and r.get("cadence_phase") == "JUST_PEAKED":
        return True, ("peaks are stepping down and the cycle has just turned — banking +%.2f%% "
                      "rather than waiting for a high that is not coming" % (chg * 100))
    return False, None


def _ratio_shape(cfg: Dict[str, Any], sym: str, rows: List, dip: float, tgt: float,
                 stp: float, cost: float, bounce_rel: Optional[float]) -> tuple:
    """(ok, target, stop, why_not). The gate that decides whether a ratio-bench sleeve may take
    this name at all, and with what shape. Returns the ORIGINAL shape untouched for every sleeve
    that is not on the bench, so nothing existing changes behaviour."""
    if not (cfg.get("measured_stop") or cfg.get("structure_entry")):
        return True, tgt, stp, None

    # ── M FLOOR ARTIST: both legs read off real structure ────────────────────────────
    if cfg.get("structure_entry"):
        S = _structure_levels(rows)
        px = S.get("px")
        if not px:
            return False, tgt, stp, "no structure yet (needs ~30 prints)"
        need = int(cfg.get("floor_tests", 3))
        prox = float(cfg.get("floor_prox_pct", 0.8)) / 100.0
        # A floor is SUPPORT: it must sit at or below the current price, and the price must be
        # close enough above it that we are buying AT the level rather than halfway to the next
        # one. A level above the price is broken support, not a floor — accepting those produced
        # negative risk distances and nonsense ratios on the first live read.
        floors = [f for f in S["floors"]
                  if f["tested"] >= need and f["level"] <= px <= f["level"] * (1 + prox)]
        if not floors:
            return False, tgt, stp, ("no floor tested >=%dx sitting within %.1f%% under price"
                                     % (need, prox * 100))
        fl = max(floors, key=lambda f: f["level"])          # the nearest supporting floor
        stop_px = fl["level"] * (1 - float(cfg.get("stop_below_floor_pct", 0.6)) / 100.0)
        new_stop = max(0.003, (px - stop_px) / px)
        ceils = [c for c in S["ceilings"] if c["level"] > px * 1.004 and c["tested"] >= 2]
        if cfg.get("target_at_ceiling") and ceils:
            cl = min(ceils, key=lambda c: c["level"])
            new_tgt = (cl["level"] / px) - 1.0
        else:
            new_tgt = tgt
        rr = new_tgt / max(new_stop, 1e-9)
        if rr < float(cfg.get("min_rr", 1.3)):
            return False, tgt, stp, ("floor setup pays %.2f:1, below the %.2f:1 this sleeve requires"
                                     % (rr, float(cfg.get("min_rr", 1.3))))
        return True, new_tgt, new_stop, None

    # ── L TOLLBOOTH / N CEILING SWEEP: measured stop, then the ratio must clear ─────
    ms = _measured_stop(rows, dip, tgt)
    if ms is None:
        return False, tgt, stp, "not enough dip history to MEASURE a stop (needs 5 completed excursions)"
    new_stop = ms
    rr = tgt / max(new_stop, 1e-9)
    min_rr = float(cfg.get("min_rr", 1.3))
    if rr < min_rr:
        return False, tgt, new_stop, ("measured stop %.2f%% against a %.2f%% target pays only "
                                      "%.2f:1, below the %.2f:1 this sleeve requires"
                                      % (new_stop * 100, tgt * 100, rr, min_rr))
    req_wr = (new_stop + cost) / max(tgt + new_stop, 1e-9)
    margin = float(cfg.get("wr_margin", 0.0))
    if margin > 0:
        if bounce_rel is None:
            return False, tgt, new_stop, "no measured bounce reliability to compare against the required win rate"
        if bounce_rel < req_wr + margin:
            return False, tgt, new_stop, ("shape needs %.1f%% wins, name delivers %.1f%% — short of "
                                          "the %.0f-point margin this sleeve demands"
                                          % (req_wr * 100, bounce_rel * 100, margin * 100))
    return True, tgt, new_stop, None


def _ceiling_sweep(cfg: Dict[str, Any], pos: Dict[str, Any], rows: List, chg: float,
                   cost: float) -> tuple:
    """(should_sweep, why). N CEILING SWEEP's exit: take a real profit at an established ceiling
    that has stopped making new highs, rather than holding for a number that may never come.
    Never sweeps a loss — the stop still owns the downside."""
    if not cfg.get("sweep_at_ceiling"):
        return False, None
    min_net = float(cfg.get("sweep_min_net_pct", 0.35)) / 100.0
    if chg <= (cost + min_net):
        return False, None                                   # not profitable enough to be worth it
    S = _structure_levels(rows)
    px = S.get("px")
    if not px:
        return False, None
    ceils = [c for c in S["ceilings"] if c["tested"] >= 2]
    if not ceils:
        return False, None
    near = min(ceils, key=lambda c: abs(c["level"] - px))
    at_ceiling = abs(px / near["level"] - 1) <= 0.004
    if not at_ceiling:
        return False, None
    # and it must have STOPPED climbing: the last N cycles made no new high
    k = int(cfg.get("sweep_stall_cycles", 2)) + 1
    live = [float(p) for t, p in (rows or [])
            if p and float(p) > 0 and "T00:00:00" not in str(t)][-k:]
    if len(live) < k or max(live[:-1]) < px:
        return False, None                                   # still making highs — let it run
    return True, ("swept at a ceiling tested %dx with no new high for %d cycles — +%.2f%% banked "
                  "rather than held for a target that may not come"
                  % (near["tested"], k - 1, chg * 100))


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


def _book_null_pct(tape: Dict[str, Any], syms: List[str], since_iso: str) -> Optional[float]:
    """7.4 THE MISSING NULL. Equal-weight buy-and-hold of THIS book's own tradeable
    names, from `since_iso` to now, on the same tape the sleeves trade.

    WHY THIS EXISTS: delta_vs_hodl was hard-gated to `book == "crypto"`, so stock,
    metal and energy printed a DASH where the only number that matters should be.
    A sleeve showing "+7.895%" with no comparison is not information: SPY returned
    +1.5% and QQQ +2.3% over the same window, and without that on the card nobody
    can tell a real sleeve from a rising tide. Crypto was measured against a 50/50
    BTC-ETH hold and was honestly shown to be LOSING to it by 8.4 points; the other
    three books were never measured at all.

    Fees are deliberately NOT charged here: a null is what you get for doing nothing,
    and doing nothing costs nothing. That makes this the harder, honest bar."""
    rets = []
    for sym in syms:
        rows = (tape or {}).get(sym) or []
        first = last = None
        for t, p in rows:
            if not p or p <= 0:
                continue
            if first is None and str(t) >= str(since_iso):
                first = p
            if str(t) >= str(since_iso):
                last = p
        if first and last and first > 0:
            rets.append((last / first - 1.0) * 100.0)
    if len(rets) < 2:
        return None
    return sum(rets) / len(rets)


def _uz_entry_gates(cfg: Dict[str, Any], sym: str, bk: Dict[str, Any],
                    rows: List) -> tuple:
    """7.3 THE EVIDENCE BENCH entry gates (U-Z). Returns (may_enter, why_not).
    Every veto is a measured effect, and every veto is written to SLEEVE_VETOES."""
    # Z REGIME GATE - entries only while this book's regime reads UPTREND
    _rg = cfg.get("regime_gate")
    if _rg and str(bk.get("_regime7") or "").upper() != str(_rg).upper():
        return False, ("regime gate - book reads %s, entries only in %s (measured: UP-regime "
                       "entries +0.66%%/trade vs DOWN -0.98%%)"
                       % (bk.get("_regime7"), _rg))
    # W HIGH GROUND - top of the 48h range only; the dip was the losing bucket
    _mbp = cfg.get("min_band_pos")
    if _mbp:
        try:
            _cut = _now() - timedelta(hours=48)
            _px48 = []
            for _t, _p in (rows or []):
                if not _p or _p <= 0:
                    continue
                _pt = _parse(_t)
                if _pt and _pt >= _cut:
                    _px48.append(_p)
            if len(_px48) < 12:
                return False, "high ground - not enough 48h tape to place the range"
            _lo, _hi = min(_px48), max(_px48)
            _pos = (_px48[-1] - _lo) / (_hi - _lo) if _hi > _lo else 0.5
            if _pos < float(_mbp):
                return False, ("high ground - sitting at %.0f%% of the 48h range, need "
                               ">= %.0f%% (only top-third entries graded green)"
                               % (_pos * 100, float(_mbp) * 100))
        except Exception:
            return False, "high ground - range unreadable; no entry on a blind read"
    # X QUIET TAPE - refuse names the crowd bought today (newsfade, in-sample t=-2.51)
    _nfv = cfg.get("news_fade_veto")
    if _nfv is not None:
        _sent = (bk.get("_news7") or {}).get(str(sym).upper())
        if _sent is not None and _sent >= float(_nfv):
            return False, ("quiet tape - net-bullish headlines today (sentiment %.2f >= "
                           "%.2f); the crowd already bought this one" % (_sent, float(_nfv)))
    # Y INSIDER TAILWIND - Form 4 activity required; EDGAR calls budgeted per cycle
    _ig = cfg.get("insider_gate")
    if _ig is not None:
        if int(bk.get("_f4_calls", 0)) >= 25:
            return False, "insider gate - EDGAR scan budget (25 names) spent this cycle"
        bk["_f4_calls"] = int(bk.get("_f4_calls", 0)) + 1
        try:
            from ..ingestion.form4 import get_insider_buy_score
            _sc = float(get_insider_buy_score(str(sym).split("-")[0]) or 0.0)
        except Exception:
            _sc = 0.0
        if _sc < float(_ig):
            return False, ("insider gate - filing-activity score %.1f < %.1f; no insider "
                           "buying, no trade" % (_sc, float(_ig)))
    return True, ""


def _run_sleeve(cfg: Dict[str, Any], bk: Dict[str, Any],
                marks: Dict[str, float], candidates: List[tuple],
                conf_map: Dict[str, float], fastgreen: set,
                surge: bool, strike_pool: List[tuple], cost_of) -> None:
    # 7.1.6: these are read by BOTH the strike block and the mean-reversion block, and the
    # strike block runs first — defining them lower down raised UnboundLocalError on the
    # very first live cycle. Hoisted so every entry path sees them.
    _book7 = bk.get("_book7")
    _vetoes = bk.setdefault("_vetoes7", [])
    tape = bk.get("_tape7") or {}
    # ── 7.1.9 ROTATION BENCH: two sleeves decide WHAT to be before deciding what to buy ──
    if cfg.get("regime_adaptive"):
        # O REGIME SWITCHER — one sleeve, three personalities, picked by the weather.
        _rg = str(bk.get("_regime7") or "").upper()
        cfg = dict(cfg)
        if "DOWN" in _rg:
            _vetoes.append({"sym": "*", "sleeve": cfg.get("_letter"),
                            "why": "regime switcher — book is DOWNTREND; sitting in cash by design"})
            return
        if "UP" in _rg:
            cfg["ride_winners"] = True
            cfg["giveback_frac"] = 0.35          # let a trend breathe
        else:
            cfg["ride_winners"] = False          # sideways: take the ceiling, do not dream
            cfg["giveback_frac"] = 0.20
    if cfg.get("survivor_only"):
        # P SURVIVOR — copy whichever sleeve in THIS book currently leads on real closes.
        _lead, _best = None, None
        for _k, _b in (bk.get("_peers7") or {}).items():
            if _k == cfg.get("_letter"):
                continue
            if int(_b.get("closed") or 0) < int(cfg.get("survivor_min_n", 4)):
                continue
            _d = _b.get("delta_vs_hodl")
            if _d is None:
                continue
            if _best is None or _d > _best:
                _lead, _best = _k, _d
        if not _lead:
            _vetoes.append({"sym": "*", "sleeve": cfg.get("_letter"),
                            "why": ("survivor — no peer sleeve has %d closed trades yet; waiting "
                                    "rather than guessing" % int(cfg.get("survivor_min_n", 4)))})
            return
        _src = dict(SLEEVES.get(_lead) or {})
        _src.update({"_letter": cfg.get("_letter"), "cap": cfg.get("cap"),
                     "vault": cfg.get("vault"), "measured_stop": True,
                     "min_rr": cfg.get("min_rr"), "recycle_h": cfg.get("recycle_h")})
        cfg = _src
        bk["_following7"] = "%s (Δnull %+.3f%%)" % (_lead, _best)
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
        # 7.3 U PATIENCE FLOOR: holds under 2h averaged -0.45%/trade (t=-5.29, n=605)
        # because ordinary noise tripped exits that would have recovered. Before the
        # floor, ONLY the hard stop may act - no trail, no give-back, no recycle.
        _minh = cfg.get("min_hold_h")
        if _minh and hold_h < float(_minh) and chg > -stop:
            continue
        # ── 7.1.6 THE TRAIL, NOT THE FLAG ────────────────────────────────────────────────
        # The operator's STRK-USD trade, in full: bought at 0.030977, ran to 0.035183 (+13.6%),
        # and exited at the +4% limit for $2.00 with "forgone 9.209%". Two separate faults, and
        # the honest one first — the CAP was right: a take-profit is a limit order and cannot
        # fill above its limit. But this sleeve is ADAPTIVE STRIKER, whose entire stated purpose
        # is "the never-miss-the-big-day law", and it missed the big day.
        #
        # Why: the ride test asked "is this name hot RIGHT NOW?" (`sym in fastgreen`, a flag
        # computed from the last hour, plus an industry `surge` flag). STRK's run happened
        # overnight; by the 07:28 check the hour was cool, so `riding` was False and the hard
        # target fired. A sleeve that exists to catch big days should ask "is this POSITION
        # winning?", not "is the tape excited this minute".
        #
        # It now trails: once a position clears its target it stops being a target trade and
        # becomes a trailing one — we record the best gain seen and exit only when the move
        # gives back `trail_giveback`. Downside is unchanged (the stop still binds), the limit
        # law is unchanged (a trail exit is a MARKET order and takes the mark), and the
        # give-back is knob-gated.
        # ── 7.1.9 THE GIVE-BACK GOVERNOR ──────────────────────────────────────────────
        # The audit that produced this: across 186 closed sleeve trades, the MEDIAN trade gave
        # back 2.90% from its own peak, 638% was left on the table in total, and 124 trades gave
        # back more than 2%. Worst of all, THIRTEEN positions that were up more than 2% closed
        # NEGATIVE — REZ +3.69% → -3.61%, AAVE +2.82% → -6.56%, CSGP +4.12% → -1.06%.
        # Breakdown by exit reason:
        #     STOP          n=94  got -4.51%  had been +0.34%   gave back 4.84%
        #     RECYCLE_FLAT  n=52  got -0.03%  had been +2.33%   gave back 2.36%
        #     RIDE_TRAIL    n=22  got +4.22%  had been +6.42%   gave back 2.20%
        #     TARGET        n=18  got +3.78%  had been +4.48%   gave back 0.69%
        # The trail only existed for `ride_winners` sleeves and only ARMED above target. A
        # position that ran +3% and rolled over had nothing watching it — it rode all the way
        # back down to the stop. That is the operator's exact complaint: "letting ceiling hit and
        # then letting profits erode and then losing our value when we could have cashed out."
        #
        # THE LAW: once a position has been meaningfully green it may never go red. Every sleeve
        # tracks its high-water mark. Two rails, both knob-gated:
        #   1. BREAK-EVEN LOCK — after +1.2% the stop moves to entry+costs. A winner cannot
        #      become a loser. This alone would have saved all 13 of those trades.
        #   2. GIVE-BACK CAP — surrender at most 40% of the best gain seen, once past +1.2%.
        # Neither invents an exit the market did not offer; both simply stop donating gains back.
        _hw = max(float(pos.get("peak_chg") or 0.0), chg)
        pos["peak_chg"] = _hw
        _prev_seen = pos.get("_last_seen")
        pos["_last_seen"] = now.isoformat()
        # Parameters FITTED on the operator's own 186 closed trades, not guessed. The sweep:
        #     arm 1.2% give 40%  ->  -32.4 pts (my first guess: rescued 31 trades but strangled
        #                            the winners — more winners, worse total. Honest and wrong.)
        #     arm 2.0% give 25%  ->  +28.2 pts, 82 winners vs 69   <-- selected
        #     arm 3.0% give 25%  ->   +2.5 pts
        #     break-even lock alone at 2.0% -> +7.8 pts
        # Arming at 2% instead of 1.2% is the whole difference: below 2% the noise band eats the
        # trade before the move has declared itself.
        # ── 7.2.3 THE ARM MUST SCALE WITH THE TARGET ──────────────────────────────────
        # A flat 2.0% arm meant a position with a 1% target was NEVER protected: it could not
        # reach the arm before its own goal. That is exactly the RECYCLE_FLAT bleed the August
        # audit found — 84 closed trades that averaged **+1.96% peak** and exited at **-0.11%**,
        # every one of them peaking just under the global arm and then recycled flat.
        # Re-swept across 378 real closed trades, arming at 40% of the position's OWN target
        # (capped at 2.0%, so a big target still arms sensibly) gives:
        #     flat 2.0% arm        -275.4%   168 winners   <- what shipped in 7.1.9
        #     arm = target x0.40   -138.1%   211 winners   <- +137.3 pts, +43 winners
        # Same trades, same give-back fraction; only the arm changed.
        _tgt_ref = float(pos.get("target") or cfg.get("target") or 0.05)
        _arm_cap = float(cfg.get("giveback_arm_pct", 2.0)) / 100.0
        _arm = min(_arm_cap, max(0.004, _tgt_ref * float(cfg.get("giveback_arm_frac", 0.40))))
        _give = float(cfg.get("giveback_frac", 0.25))
        if cfg.get("giveback_governor", True) and _hw >= _arm:
            _cost = pos.get("cost", MIN_COST)
            if chg <= _cost:                                   # BREAK-EVEN LOCK
                # 7.2.2: fill where a RESTING order would have, not where we happened to look
                _fc, _cr = _resting_fill(tape.get(sym), pos["entry"], _cost,
                                         str(_prev_seen or pos.get("t") or ""), cur)
                _px_fill = pos["entry"] * (1.0 + _fc) if _cr and _fc is not None else cur
                _sell(bk, sym, _px_fill, "BREAKEVEN_LOCK", vault, gap_h=None)
                _vetoes.append({"sym": sym, "sleeve": cfg.get("_letter"),
                                "why": ("break-even lock — was +%.2f%%, protecting the trade rather "
                                        "than letting a winner become a loser" % (_hw * 100))})
                continue
            if chg <= _hw * (1.0 - _give):                     # GIVE-BACK CAP
                _lvl = _hw * (1.0 - _give)
                _fc, _cr = _resting_fill(tape.get(sym), pos["entry"], _lvl,
                                         str(_prev_seen or pos.get("t") or ""), cur)
                _px_fill = pos["entry"] * (1.0 + _fc) if _cr and _fc is not None else cur
                _sell(bk, sym, _px_fill, "GIVEBACK_CAP", vault, gap_h=None)
                _vetoes.append({"sym": sym, "sleeve": cfg.get("_letter"),
                                "why": ("give-back cap — peaked +%.2f%%, banked +%.2f%% rather than "
                                        "surrendering more than %.0f%% of the run"
                                        % (_hw * 100, chg * 100, _give * 100))})
                continue
        _trail_give = float(cfg.get("trail_giveback", 0.25))
        riding = False
        if cfg["ride_winners"] and chg >= tgt:
            _best = _hw
            # give back a quarter of the run (never more than the run itself) before letting go
            riding = chg >= _best * (1.0 - _trail_give)
            if not riding:
                _sell(bk, sym, cur, "RIDE_TRAIL", vault, gap_h=None)
                continue
        _gap_h = None
        try:
            _lt = _LASTPRINT.get(sym)
            if _lt:
                _gap_h = max(0.0, (now - _lt).total_seconds() / 3600.0)
        except Exception:
            _gap_h = None
        # 7.1.8 N CEILING SWEEP: take a real profit at an established ceiling that has stopped
        # making new highs, instead of holding for a number that may never arrive.
        _ce, _cewhy = _ceiling_exit(cfg, sym, bk.get("_out7"), chg, pos.get("cost", MIN_COST))
        if _ce:
            _sell(bk, sym, cur, "CEILING_READ", vault, gap_h=_gap_h)
            _vetoes.append({"sym": sym, "sleeve": cfg.get("_letter"), "why": _cewhy})
            continue
        _sw, _swwhy = _ceiling_sweep(cfg, pos, tape.get(sym), chg, pos.get("cost", MIN_COST))
        if _sw:
            _sell(bk, sym, cur, "CEILING_SWEEP", vault, gap_h=_gap_h)
            _vetoes.append({"sym": sym, "sleeve": cfg.get("_letter"), "why": _swwhy})
            continue
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
                _vetoes.append({"sym": sym, "sleeve": cfg.get("_letter") or cfg.get("name"), "why": _why})
                continue
            _ok, _why = _trajectory_ok(sym, tape.get(sym), cfg)
            if not _ok:
                _vetoes.append({"sym": sym, "sleeve": cfg.get("_letter") or cfg.get("name"), "why": _why})
                continue
            px = _tp
            # 7.1.6 STRIKE SIZING. The STRK win was +3.688% on a $54.32 wager — two dollars —
            # because the mean-reversion slots had already spent the sleeve down to pocket
            # change ($3,621 + $3,440 of a $10k book) and the strike slots took what was left.
            # A sleeve whose job is to catch the big day cannot be funded with crumbs: when it
            # is right, being right has to matter. STRIKE now draws against a reserved slice of
            # STARTING capital, not against whatever the other slots failed to spend.
            _start = float(bk.get("start_equity") or 10000.0)
            _reserve = _start * float(cfg.get("strike_reserve_frac", 0.15))
            budget = max(0.0, min(_reserve, _avail() - 25))
            if budget < _start * 0.02:                 # too thin to be worth the slot
                continue
            if budget < 50:
                break
            # 7.2.7 BOTH SIDES, REAL VENUE: the entry pays its half of the round trip
            # at the cost the venue would really charge, exactly as paper_sim.buy does.
            _c7 = cost_of(px, sym, _book7)
            _eff7 = px * (1.0 + _c7 / 2.0)
            qty = budget / _eff7
            bk["cash"] -= budget
            bk["positions"][sym] = {"qty": qty, "entry": _eff7, "raw_entry": px, "cost": _c7,
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
        # 7.2.1: sleeves with their own entry thesis scan their own universe instead of
        # inheriting the mean-reversion dip funnel that starved them to zero. ALWAYS, not only
        # when the funnel is empty — for a structure sleeve the dip list is simply the wrong
        # question, whether or not it happens to have rows in it today.
        _scan = cap - open_mr
        if cfg.get("graph_entry"):
            pool = _own_universe(cfg, _book7, marks, bk.get("_out7"), cost_of,
                                 held=set(bk["positions"].keys()))
            # These gates are severe by design — measured on the operator's tape, R passed 5
            # names out of 130 and S passed 1. Slicing to `cap` before the gate runs would
            # therefore find nothing almost every cycle, which is exactly how a sleeve looks
            # "broken" while being merely mis-fed. Scan deep, then let the gate be the filter.
            _scan = max(cap * 30, 120)
        for sym, px, h1, cv in pool[:_scan]:
            if not px or px <= 0:
                continue
            _tp = marks.get(sym)
            if not _tp or _tp <= 0 or not _px_is_fresh(sym):
                continue                      # tape-priced, fresh-only (see THE ONE FRESH PRICE LAW)
            if not _market_open_for_symbol(sym, _book7):
                continue
            _ok, _why = _cooldown_ok(bk, sym)
            if not _ok:
                _vetoes.append({"sym": sym, "sleeve": cfg.get("_letter") or cfg.get("name"), "why": _why})
                continue
            _ok, _why = _trajectory_ok(sym, tape.get(sym), cfg)
            if not _ok:
                _vetoes.append({"sym": sym, "sleeve": cfg.get("_letter") or cfg.get("name"), "why": _why})
                continue
            # 7.3 THE EVIDENCE BENCH: U-Z gates, each one a measured effect
            _ok, _why = _uz_entry_gates(cfg, sym, bk, tape.get(sym))
            if not _ok:
                _vetoes.append({"sym": sym, "sleeve": cfg.get("_letter") or cfg.get("name"),
                                "why": _why})
                continue
            px = _tp
            # ── 7.2.2 THE CAPITAL LEAK I INTRODUCED IN 7.2.1 ────────────────────────────
            # 7.2.1 let thesis sleeves scan deep (120+ names) and added a cap guard to stop
            # once full — but the guard sat AFTER `bk["cash"] -= budget` and simply `break`ed.
            # Every cycle the sleeve deducted a budget for a position it then never created.
            # crypto:R ended with $3.55 cash and four positions worth ~$3,289 out of a $10,000
            # book: about $6,700 evaporated, and the headline read -64% while realized was
            # +0.07%. This is exactly the failure the operator predicted when they told me to
            # be skeptical of my own work. The cap is now checked BEFORE any money moves, and
            # a live count is used rather than the stale `open_mr` from before the loop.
            _open_now = sum(1 for q in bk["positions"].values() if q.get("style") != "STRIKE")
            if _open_now >= cap:
                break                                  # full: stop scanning, spend nothing
            budget = _avail() / max(1, cap - _open_now)
            budget = min(budget, _avail() * 0.95)
            if budget < 50:
                break
            # 7.2.7 BOTH SIDES, REAL VENUE — see cost_of() below.
            _c7 = cost_of(px, sym, _book7)
            _eff7 = px * (1.0 + _c7 / 2.0)
            qty = budget / _eff7
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
            # ── 7.1.8 THE RATIO BENCH: replace the blanket stop with a measured one, and refuse
            # any shape whose arithmetic cannot pay. Non-bench sleeves are untouched.
            if cfg.get("graph_entry"):
                _okg, _tg, _sg, _whyg = _graph_shape(cfg, sym, bk.get("_out7"))
                if not _okg:
                    bk["cash"] += budget          # refund; this name never becomes a position
                    _vetoes.append({"sym": sym, "sleeve": cfg.get("_letter"),
                                    "why": "graph read — " + str(_whyg)})
                    continue
                tgt, stp = _tg, _sg
            elif cfg.get("measured_stop") or cfg.get("structure_entry"):
                _ok8, _t8, _s8, _why8 = _ratio_shape(
                    cfg, sym, tape.get(sym), h1 if isinstance(h1, float) else 0.01,
                    tgt, stp, _c7,
                    (bk.get("_bounce7") or {}).get(sym))
                if not _ok8:
                    bk["cash"] += budget            # refund; this name never becomes a position
                    _vetoes.append({"sym": sym, "sleeve": cfg.get("_letter"),
                                    "why": "ratio gate — " + str(_why8)})
                    continue
                tgt, stp = _t8, _s8
            # 7.3 V WIDE STOP: 880 STOP exits averaged -2.01% against 745 give-backs at
            # +1.82%. V pushes the stop out of noise range and takes profit early instead.
            _wsm = cfg.get("wide_stop_mult")
            if _wsm:
                stp = min(float(stp) * float(_wsm), 0.25)
            if sym in bk["positions"]:
                bk["cash"] += budget           # never overwrite a live position; refund and skip
                continue
            bk["positions"][sym] = {"qty": qty, "entry": _eff7, "raw_entry": px, "cost": _c7,
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

    # ── 7.2.7 THE REAL-VENUE COST LAW ─────────────────────────────────────────────
    # THE ERROR THIS FIXES, stated plainly because it changed a verdict:
    # this blanket returned 0.4% (px>=$1) / 0.6% (px<$1) for EVERY book, and the
    # workshop was judged against it. Meanwhile fee_model.py — this repo's own
    # itemised, venue-routed model — says the real round trip is:
    #
    #     stock / metal / energy   0.068%   ($0 commission + measured spread + slip)
    #     crypto                   0.325%   (Binance.US taker 0.10%/side + spread)
    #
    # So the equity books were charged SIX TIMES their real cost, and an audit run
    # against that blanket concluded fast trading could not pay. Re-scored at the
    # real model the same 2,403 closed trades say something different: energy
    # +$2,739, metal +$992, stock +$625, crypto -$16,836. The problem was never
    # turnover — it was CRYPTO turnover, where the fee is genuinely 5x the equity
    # fee and the gross edge is negative (-0.22%/trade, t=-3.09) on top.
    #
    # A cost model that is wrong in the expensive direction does not make a system
    # "conservative". It makes it blind to the trades that actually work.
    def cost_of(px, sym=None, book=None):
        c = _cost_for_sym(sym, book) if sym else None
        if c and c > 0:
            return c
        if book in ("stock", "metal", "energy"):
            return 0.0007          # $0-commission equity floor, ~ fee_model's 0.068%
        if book == "crypto":
            return 0.0033          # Binance.US taker round trip + spread
        return 0.004 if px >= 1 else 0.006

    hodl = None
    try:
        hodl = (json.loads((out / "BENCH_BOOKS.json").read_text()).get("books", {})
                .get("BENCH_HODL", {}).get("return_pct"))
    except Exception:
        pass

    # 7.3 X QUIET TAPE: today's net headline sentiment per name, from the project's
    # own news wire. Absent name -> no veto (silence is the default, not a guess).
    _news7 = {}
    try:
        _nh = json.loads((out / "news_history.json").read_text())
        for _tic, _rows in (_nh or {}).items():
            if isinstance(_rows, list) and _rows:
                _sv = _rows[-1].get("sent")
                if _sv is not None:
                    _news7[str(_tic).upper()] = float(_sv)
    except Exception:
        _news7 = {}

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
    # 7.1.9: last cycle's sleeve scoreboard, for P SURVIVOR's election (never this cycle's —
    # that would be look-ahead).
    _peers_prev: Dict[str, Any] = {}
    try:
        _prev = json.loads((out / STORE).read_text())
        for _bkn, _rows in (_prev.get("by_industry") or {}).items():
            _peers_prev[_bkn] = {r.get("sleeve"): r for r in (_rows or []) if r.get("sleeve")}
    except Exception:
        _peers_prev = {}
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
    # 7.4 per-book nulls, measured from the wipe epoch on the same tape the sleeves see
    _book_nulls: Dict[str, Any] = {}
    _since = str(st.get("wipe_epoch") or st.get("created_at") or "")
    for _bk7 in BOOKS:
        try:
            _u7 = sorted({t.get("sym") for _k, _b in st["sleeves"].items()
                          if _k.startswith(_bk7 + ":")
                          for t in (_b.get("trades") or []) if t.get("sym")})
            _book_nulls[_bk7] = _book_null_pct(_samp, _u7, _since)
        except Exception:
            _book_nulls[_bk7] = None

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
            bk["_news7"] = _news7                    # 7.3 X QUIET TAPE
            bk["_f4_calls"] = 0                      # 7.3 Y per-cycle EDGAR budget
            bk["_book7"] = book
            bk["_tape7"] = _tape7
            bk["_out7"] = str(out)
            bk.setdefault("start_equity", 10000.0)
            # 7.1.8: measured bounce reliability per name, so the ratio gate can compare a shape's
            # REQUIRED win rate against what the name has actually delivered.
            if "_bounce7" not in bk:
                _br = {}
                try:
                    for _c in (json.loads((out / "FINGERPRINTS.json").read_text()).get("cards") or []):
                        _v = ((_c.get("fp") or {}).get("bounce_reliability")
                              if isinstance(_c.get("fp"), dict) else None)
                        if _c.get("sym") and _v is not None:
                            _br[_c["sym"]] = float(_v)
                except Exception:
                    pass
                bk["_bounce7"] = _br
            # P SURVIVOR elects from the PREVIOUS cycle's published scoreboard — this cycle's
            # rows do not exist yet, and using them would be look-ahead. Reading last cycle's
            # verdict is exactly what a human rotating capital would have available.
            bk["_peers7"] = _peers_prev.get(book) or {}
            cfg = dict(cfg); cfg["_letter"] = sk
            _RIVER.update({"out": str(out), "sleeve": sk, "book": book})
            _run_sleeve(cfg, bk, marks, _cands_sk, conf_map, fastgreen, surge, strike_pool, cost_of)
            _RIVER.update({"out": None})
            eq = _equity(bk, marks) + bk.get("vault_usd", 0.0)
            ret = (eq / START - 1) * 100
            # ── 7.2.0 REALIZED IS THE SCORE (Law 1), AND IT MUST BE VISIBLE ─────────────
            # `ret` is equity-based, so it includes UNREALIZED marks on open positions. That
            # is legitimate as a mark-to-market number and dishonest as a headline: on the
            # 2026-08-01 tree six sleeves carried a headline with the OPPOSITE SIGN to their
            # realized P&L — metal:B CAP ONLY showed +1.163% with ZERO closed trades, all of
            # it unrealized. I read that board myself and told the operator "M FLOOR ARTIST is
            # green in all four books" when M's realized was crypto -$12.92 and stock -$50.56.
            # It was not the board lying to me; it was me reading the wrong column. Both
            # numbers ship from now on, and the split is explicit.
            _real = float(bk.get("realized_pnl", 0.0))
            _realized_pct = (_real / START) * 100.0
            _null = _book_nulls.get(book)
            _unreal_pct = ret - _realized_pct
            closed = [t for t in bk["trades"] if t["side"] == "SELL"]
            wins = sum(1 for t in closed if t["pnl"] > 0)
            rows.append({
                "sleeve": sk, "name": cfg["name"], "cap": cfg["cap"],
                "equity": round(eq, 2), "return_pct": round(ret, 3),
                "realized_pct": round(_realized_pct, 3), "unrealized_pct": round(_unreal_pct, 3),
                "realized_usd": round(_real, 2),
                "realized_pnl": round(bk["realized_pnl"], 2),
                "vault_usd": round(bk.get("vault_usd", 0.0), 2),
                # 7.4: crypto keeps its published 50/50 BTC-ETH null; every other book
                # now gets one built from its OWN universe instead of a dash.
                "delta_vs_hodl": (round(ret - float(hodl), 3)
                                  if (hodl is not None and book == "crypto")
                                  else (round(ret - float(_null), 3)
                                        if _null is not None else None)),
                "null_pct": (round(float(hodl), 3) if book == "crypto" and hodl is not None
                             else (round(float(_null), 3) if _null is not None else None)),
                "null_label": ("50/50 BTC-ETH hold" if book == "crypto"
                               else "equal-weight hold of this book's universe"),
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
            _b.pop("_tape7", None); _b.pop("_book7", None); _b.pop("_bounce7", None)
            _b.pop("_out7", None); _b.pop("_peers7", None); _b.pop("_geo7", None)
            _b.pop("_news7", None); _b.pop("_f4_calls", None)
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
