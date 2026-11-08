"""ladder.rules — the registered rules, as TARGET TRACKS.

A target track is a list, one entry per calendar index j, holding the weights IN FORCE for
a fill at the close of day j. Every decision for day j reads closes up to day j-1 only —
the fill day's own close is never an input. That is the no-lookahead law, and
scripts/test_ladder.py proves it by vandalising the fill-day price and checking that no
target moves.

Monthly rules decide on the first trading day of a new month (using the previous day's
close, i.e. the month-end). Daily exits may fire on any day.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from .config import REGISTERED
from .data import Tape

Weights = Dict[str, float]
Track = List[Optional[Weights]]
Events = Dict[int, str]


# ── signal arithmetic (all on closes up to and including index i) ───────────────

def sma(arr: List[float], i: int, n: int) -> Optional[float]:
    if i - n + 1 < 0:
        return None
    w = arr[i - n + 1:i + 1]
    if any(v is None for v in w):
        return None
    return sum(w) / n


def blended(arr: List[float], i: int) -> Optional[float]:
    rets = []
    for lb in REGISTERED["momentum_lookbacks"]:
        if i - lb < 0 or arr[i] is None or arr[i - lb] is None or arr[i - lb] <= 0:
            return None
        rets.append(arr[i] / arr[i - lb] - 1.0)
    return sum(rets) / len(rets)


def basket_vol(a: List[float], b: List[float], i: int, n: int) -> Optional[float]:
    """Annualised volatility of a daily-rebalanced 50/50 basket over the last n days."""
    if i - n < 0:
        return None
    rets = []
    for k in range(i - n + 1, i + 1):
        if None in (a[k], a[k - 1], b[k], b[k - 1]):
            return None
        rets.append(0.5 * (a[k] / a[k - 1] - 1.0) + 0.5 * (b[k] / b[k - 1] - 1.0))
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252.0)


def is_new_month(dates: List[str], j: int) -> bool:
    return j > 0 and dates[j][:7] != dates[j - 1][:7]


def _clean(w: Weights) -> Weights:
    return {k: round(v, 10) for k, v in w.items() if v > 1e-12}


# ── the four sleeves ─────────────────────────────────────────────────────────────

def sleeve_hold(tape: Tape, cat: str, start: int) -> Tuple[Track, Events]:
    a, b = REGISTERED["categories"][cat]
    tr: Track = [None] * tape.n
    for j in range(start, tape.n):
        tr[j] = {a: 0.5, b: 0.5}
    return tr, {start: "bought 50/50 and holds forever"}


def sleeve_trend(tape: Tape, cat: str, start: int) -> Tuple[Track, Events]:
    syms = REGISTERED["categories"][cat]
    n = REGISTERED["sma_days"]
    tr: Track = [None] * tape.n
    ev: Events = {}
    cur: Weights = {}
    for j in range(start, tape.n):
        if j == start or is_new_month(tape.dates, j):
            i = j - 1
            new: Weights = {}
            why = []
            for s in syms:
                avg = sma(tape.px[s], i, n)
                above = avg is not None and tape.px[s][i] > avg
                if above:
                    new[s] = 0.5
                why.append("%s %s its 200-day" % (s, "above" if above else "below"))
            new = _clean(new)
            if new != cur or j == start:
                ev[j] = "; ".join(why)
            cur = new
        tr[j] = dict(cur)
    return tr, ev


def sleeve_momentum(tape: Tape, cat: str, start: int) -> Tuple[Track, Events]:
    syms = REGISTERED["categories"][cat]
    cash = REGISTERED["cash_symbol"]
    hyst = REGISTERED["hysteresis"]
    tr: Track = [None] * tape.n
    ev: Events = {}
    held: Optional[str] = None
    for j in range(start, tape.n):
        i = j - 1
        hurdle = blended(tape.px[cash], i)
        scores = {s: blended(tape.px[s], i) for s in syms}
        if j == start or is_new_month(tape.dates, j):
            elig = {s: v for s, v in scores.items()
                    if v is not None and hurdle is not None and v > hurdle}
            pick = None
            if elig:
                best = max(elig, key=lambda s: elig[s])
                if held in elig and elig[held] >= elig[best] - hyst:
                    pick = held
                else:
                    pick = best
            if pick != held or j == start:
                ev[j] = ("monthly: %s (score %+.1f%% vs T-bills %+.1f%%)" %
                         (pick, 100 * scores[pick], 100 * (hurdle or 0)) if pick else
                         "monthly: nothing beats T-bills -> cash")
            held = pick
        elif held is not None:
            sc = scores.get(held)
            if sc is not None and hurdle is not None and sc <= hurdle:
                ev[j] = "daily exit: %s fell to %+.1f%% vs T-bills %+.1f%%" % (
                    held, 100 * sc, 100 * hurdle)
                held = None
        tr[j] = {held: 1.0} if held else {}
    return tr, ev


def sleeve_voltarget(tape: Tape, cat: str, start: int) -> Tuple[Track, Events]:
    a, b = REGISTERED["categories"][cat]
    tgt_vol = REGISTERED["vol_target"]
    band = REGISTERED["vol_band"]
    win = REGISTERED["vol_window"]
    tr: Track = [None] * tape.n
    ev: Events = {}
    expo: Optional[float] = None
    for j in range(start, tape.n):
        if j == start or is_new_month(tape.dates, j):
            v = basket_vol(tape.px[a], tape.px[b], j - 1, win)
            new = 0.0 if not v else min(1.0, tgt_vol / v)
            if expo is None or abs(new - expo) > band:
                ev[j] = "monthly: basket volatility %.0f%% -> hold %.0f%% of the account" % (
                    100 * (v or 0), 100 * new)
                expo = new
        tr[j] = _clean({a: 0.5 * expo, b: 0.5 * expo})
    return tr, ev


SLEEVES = {"HOLD": sleeve_hold, "TREND": sleeve_trend,
           "MOMENTUM": sleeve_momentum, "VOLTARGET": sleeve_voltarget}
WORKING = ["TREND", "MOMENTUM", "VOLTARGET"]


# ── the category account: the committee average ─────────────────────────────────

def account_track(sleeve_tracks: Dict[str, Track], start: int, n: int) -> Tuple[Track, Events]:
    tr: Track = [None] * n
    ev: Events = {}
    prev: Optional[Weights] = None
    for j in range(start, n):
        w: Weights = {}
        for name in WORKING:
            for s, v in (sleeve_tracks[name][j] or {}).items():
                w[s] = w.get(s, 0.0) + v / len(WORKING)
        w = _clean(w)
        if w != prev:
            ev[j] = "committee: " + (", ".join("%s %.0f%%" % (s, 100 * v)
                                               for s, v in sorted(w.items())) or "all T-bills")
        tr[j] = w
        prev = w
    return tr, ev


# ── the master: rotate into the category accounts that are working ──────────────

def master_track(tape: Tape, curves: Dict[str, List[Optional[float]]],
                 acct_tracks: Dict[str, Track], start: int) -> Tuple[Track, Events, List]:
    """curves[cat][i] = that category account's rule-curve equity at close i (from its
    own replay). Scores read curves up to i = j-1 only."""
    cash = REGISTERED["cash_symbol"]
    slots = REGISTERED["master_slots"]
    hyst = REGISTERED["hysteresis"]
    tr: Track = [None] * tape.n
    ev: Events = {}
    held: List[str] = []
    score_log = []
    for j in range(start, tape.n):
        i = j - 1
        hurdle = blended(tape.px[cash], i)
        scores = {c: blended(curves[c], i) for c in curves}
        if j == start or is_new_month(tape.dates, j):
            elig = {c: v for c, v in scores.items()
                    if v is not None and hurdle is not None and v > hurdle}
            ranked = sorted(elig, key=lambda c: -elig[c])
            cutoff = elig[ranked[slots - 1]] if len(ranked) >= slots else None
            keep = [c for c in held if c in elig and (cutoff is None or elig[c] >= cutoff - hyst)]
            for c in ranked:
                if len(keep) >= slots:
                    break
                if c not in keep:
                    keep.append(c)
            keep = keep[:slots]
            if keep != held or j == start:
                ev[j] = "monthly seats: %s (T-bills %+.1f%%; scores %s)" % (
                    " + ".join(keep) or "none -> cash", 100 * (hurdle or 0),
                    ", ".join("%s %+.1f%%" % (c, 100 * v) for c, v in
                              sorted(scores.items(), key=lambda kv: -(kv[1] or -9))
                              if v is not None))
            held = keep
            score_log.append({"date": tape.dates[j], "scores": {c: (round(v, 4) if v is not None else None)
                                                                 for c, v in scores.items()},
                              "tbills": round(hurdle, 4) if hurdle is not None else None,
                              "seats": list(held)})
        else:
            drop = [c for c in held if scores.get(c) is None or hurdle is None
                    or scores[c] <= hurdle]
            if drop:
                ev[j] = "daily exit: %s fell below T-bills" % ", ".join(drop)
                held = [c for c in held if c not in drop]
        w: Weights = {}
        for c in held:
            for s, v in (acct_tracks[c][j] or {}).items():
                w[s] = w.get(s, 0.0) + v / slots
        tr[j] = _clean(w)
    return tr, ev, score_log
