"""ladder.engine — build the whole ladder from prices, every run, from scratch.

There is no hidden state. The sleeves, the four category accounts, the master and every
benchmark are recomputed from the price history and the registered rules each day, so a
missed run, a failed push or a crashed runner cannot lose or corrupt anything: the next
run produces exactly the same past and adds the new day. What is recorded is checked
against what is recomputed (see cli.py), so a silent change to the past is impossible.

Two money paths follow the SAME decisions:
  * the REPLAY starts when enough history exists (late 2018) — context, never proof;
  * the FORWARD run opens every account with $10,000 at the epoch close — the experiment.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from . import portfolio as PF
from . import rules as RU
from .config import REGISTERED, registration_hash
from .data import Tape

CATS = list(REGISTERED["categories"].keys())


def _index_on_or_after(tape: Tape, date: str) -> Optional[int]:
    for i, d in enumerate(tape.dates):
        if d >= date:
            return i
    return None


def _thin(curve: List[Optional[float]], tape: Tape, start: int, end: int, step: int) -> List:
    out = []
    for j in range(start, end + 1):
        if curve[j] is None:
            continue
        if (j - start) % step == 0 or j == end:
            out.append([tape.dates[j], round(curve[j], 2)])
    return out


def build(tape: Tape) -> Dict:
    warm = REGISTERED["warmup_bars"]
    w = tape.first_full_index(warm)
    if w is None or w + 2 >= tape.n:
        raise RuntimeError("not enough history for the registered warmup")
    start = w + 1
    epoch = _index_on_or_after(tape, REGISTERED["epoch_date"])
    last = tape.n - 1
    pre_end = (epoch - 1) if epoch is not None else last

    out: Dict = {"registration_hash": registration_hash(), "data_through": tape.dates[-1],
                 "replay_start": tape.dates[start],
                 "epoch_date": REGISTERED["epoch_date"],
                 "epoch_reached": epoch is not None,
                 "categories": {}, "master": {}, "benchmarks": {}}

    acct_tracks: Dict[str, List] = {}
    acct_curves: Dict[str, List] = {}
    forward_values: Dict[str, Dict[str, float]] = {}

    def fwd_record(name: str, curve: List[Optional[float]]) -> None:
        if epoch is None:
            return
        for j in range(epoch, tape.n):
            if curve[j] is not None:
                forward_values.setdefault(tape.dates[j], {})[name] = round(curve[j], 2)

    for cat in CATS:
        c: Dict = {"assets": REGISTERED["categories"][cat], "sleeves": {}}
        tracks = {}
        for name, fn in RU.SLEEVES.items():
            tr, ev = fn(tape, cat, start)
            tracks[name] = tr
            rep = PF.simulate(tape, tr, start, label="%s:%s" % (cat, name))
            s = {"replay": PF.stats(rep["curve"], tape, start, pre_end),
                 "replay_trades": sum(1 for t in rep["trades"] if t["date"] <= tape.dates[pre_end]),
                 "replay_fees": round(sum(t["fee"] for t in rep["trades"]
                                          if t["date"] <= tape.dates[pre_end]), 2),
                 "avg_invested_pct": round(100 * rep["avg_invested"], 1),
                 "target_now": tr[last], "recent_events": [
                     {"date": tape.dates[j], "why": ev[j]} for j in sorted(ev)[-6:]]}
            if epoch is not None:
                fw = PF.simulate(tape, tr, epoch, label="%s:%s" % (cat, name))
                s["forward"] = PF.stats(fw["curve"], tape, epoch, last)
                s["forward_value"] = round(fw["curve"][last], 2)
                fwd_record("%s:%s" % (cat, name), fw["curve"])
            c["sleeves"][name] = s
        at, aev = RU.account_track(tracks, start, tape.n)
        acct_tracks[cat] = at
        rep = PF.simulate(tape, at, start, label="%s:ACCOUNT" % cat)
        acct_curves[cat] = rep["curve"]
        hold_rep = PF.simulate(tape, tracks["HOLD"], start, label="%s:HOLD" % cat)
        acc = {"replay": PF.stats(rep["curve"], tape, start, pre_end),
               "replay_trades": sum(1 for t in rep["trades"] if t["date"] <= tape.dates[pre_end]),
               "replay_fees": round(sum(t["fee"] for t in rep["trades"]
                                        if t["date"] <= tape.dates[pre_end]), 2),
               "target_now": at[last],
               "recent_events": [{"date": tape.dates[j], "why": aev[j]} for j in sorted(aev)[-8:]],
               "replay_curve": _thin(rep["curve"], tape, start, pre_end, 5),
               "hold_curve": _thin(hold_rep["curve"], tape, start, pre_end, 5)}
        if epoch is not None:
            fw = PF.simulate(tape, at, epoch, label="%s:ACCOUNT" % cat)
            fh = PF.simulate(tape, tracks["HOLD"], epoch, label="%s:HOLD" % cat)
            acc.update({"forward": PF.stats(fw["curve"], tape, epoch, last),
                        "forward_value": round(fw["curve"][last], 2),
                        "forward_hold_value": round(fh["curve"][last], 2),
                        "forward_trades": fw["trades"], "forward_holdings": fw["holdings"],
                        "forward_cash": fw["cash"],
                        "forward_curve": _thin(fw["curve"], tape, epoch, last, 1),
                        "forward_hold_curve": _thin(fh["curve"], tape, epoch, last, 1)})
            fwd_record("%s:ACCOUNT" % cat, fw["curve"])
        c["account"] = acc
        # what the rules are watching right now (signals on the newest close)
        cash = REGISTERED["cash_symbol"]
        c["watch"] = {"tbills_score": RU.blended(tape.px[cash], last),
                      "scores": {s: RU.blended(tape.px[s], last) for s in c["assets"]},
                      "above_200d": {s: (tape.px[s][last] > (RU.sma(tape.px[s], last, 200) or 9e18))
                                     for s in c["assets"]},
                      "basket_vol": RU.basket_vol(tape.px[c["assets"][0]], tape.px[c["assets"][1]],
                                                  last, REGISTERED["vol_window"])}
        out["categories"][cat] = c

    # ── the master ────────────────────────────────────────────────────────────────
    ms = start + max(REGISTERED["momentum_lookbacks"]) + 2
    mt, mev, score_log = RU.master_track(tape, acct_curves, acct_tracks, ms)
    rep = PF.simulate(tape, mt, ms, label="MASTER")
    ew = {s: 1.0 / 8 for cat in CATS for s in REGISTERED["categories"][cat]}
    ew_track = [None] * ms + [dict(ew)] * (tape.n - ms)
    spy_track = [None] * ms + [{"SPY": 1.0}] * (tape.n - ms)
    ew_rep = PF.simulate(tape, ew_track, ms, label="EQUAL-WEIGHT HOLD")
    spy_rep = PF.simulate(tape, spy_track, ms, label="SPY HOLD")
    m = {"replay_start": tape.dates[ms],
         "replay": PF.stats(rep["curve"], tape, ms, pre_end),
         "replay_trades": sum(1 for t in rep["trades"] if t["date"] <= tape.dates[pre_end]),
         "replay_fees": round(sum(t["fee"] for t in rep["trades"] if t["date"] <= tape.dates[pre_end]), 2),
         "avg_invested_pct": round(100 * rep["avg_invested"], 1),
         "target_now": mt[last],
         "seats_now": score_log[-1]["seats"] if score_log else [],
         "score_log_tail": score_log[-6:],
         "recent_events": [{"date": tape.dates[j], "why": mev[j]} for j in sorted(mev)[-10:]],
         "replay_curve": _thin(rep["curve"], tape, ms, pre_end, 5),
         "watch": {"tbills_score": RU.blended(tape.px[REGISTERED["cash_symbol"]], last),
                   "scores": {cat: RU.blended(acct_curves[cat], last) for cat in CATS}}}
    # calendar-year table for the replay (master vs equal-weight vs SPY)
    years = {}
    for j in range(ms, pre_end + 1):
        y = tape.dates[j][:4]
        years.setdefault(y, [j, j])[1] = j
    yt = []
    for y, (a, b) in sorted(years.items()):
        a0 = a - 1 if a > ms else a
        row = {"year": y}
        for key, cv in (("master", rep["curve"]), ("equal_weight", ew_rep["curve"]),
                        ("spy", spy_rep["curve"])):
            row[key] = round(100 * (cv[b] / cv[a0] - 1.0), 1)
        yt.append(row)
    m["replay_years"] = yt
    out["benchmarks"] = {
        "equal_weight_hold": {"replay": PF.stats(ew_rep["curve"], tape, ms, pre_end),
                              "replay_curve": _thin(ew_rep["curve"], tape, ms, pre_end, 5)},
        "spy_hold": {"replay": PF.stats(spy_rep["curve"], tape, ms, pre_end),
                     "replay_curve": _thin(spy_rep["curve"], tape, ms, pre_end, 5)}}
    if epoch is not None:
        fw = PF.simulate(tape, mt, epoch, label="MASTER")
        few = PF.simulate(tape, [None] * epoch + [dict(ew)] * (tape.n - epoch), epoch,
                          label="EQUAL-WEIGHT HOLD")
        fspy = PF.simulate(tape, [None] * epoch + [{"SPY": 1.0}] * (tape.n - epoch), epoch,
                           label="SPY HOLD")
        m.update({"forward": PF.stats(fw["curve"], tape, epoch, last),
                  "forward_value": round(fw["curve"][last], 2),
                  "forward_trades": fw["trades"], "forward_holdings": fw["holdings"],
                  "forward_cash": fw["cash"],
                  "forward_curve": _thin(fw["curve"], tape, epoch, last, 1)})
        out["benchmarks"]["equal_weight_hold"].update({
            "forward": PF.stats(few["curve"], tape, epoch, last),
            "forward_value": round(few["curve"][last], 2),
            "forward_curve": _thin(few["curve"], tape, epoch, last, 1)})
        out["benchmarks"]["spy_hold"].update({
            "forward": PF.stats(fspy["curve"], tape, epoch, last),
            "forward_value": round(fspy["curve"][last], 2),
            "forward_curve": _thin(fspy["curve"], tape, epoch, last, 1)})
        fwd_record("MASTER", fw["curve"])
        fwd_record("EQUAL-WEIGHT HOLD", few["curve"])
        fwd_record("SPY HOLD", fspy["curve"])
    out["master"] = m
    out["forward_values"] = forward_values
    return out
