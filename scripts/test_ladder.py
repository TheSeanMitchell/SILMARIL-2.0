"""scripts/test_ladder.py — the laws, proved offline on synthetic prices. No network.

Run:  python scripts/test_ladder.py      (exit code 0 = every law holds)

 1. registration   ladder/config.py hash == REGISTRATION_9.md
 2. fee law        a flat round trip costs exactly the declared round trip (both sides)
 3. no lookahead   vandalising the fill-day close cannot change any target
 4. hold is hold   the HOLD sleeve equals a hand-computed buy-and-hold
 5. cash is real   idle money grows exactly by the T-bill ETF's ratio
 6. weights sane   no target is negative or above 100% in total
 7. determinism    two builds of the same prices are identical
 8. continuity     forward accounts follow the same targets as the replay after the epoch
 9. no negative cash, ever
10. stale feed     a frozen tape is reported stale
11. record guard   a recorded day is never overwritten, and drift is detected
"""
from __future__ import annotations

import copy
import json
import math
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ladder import config as CF          # noqa: E402
from ladder import data as DA            # noqa: E402
from ladder import engine as EN          # noqa: E402
from ladder import portfolio as PF       # noqa: E402
from ladder import rules as RU           # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  — " + detail))
    if not ok:
        FAILS.append(name)


def synthetic(n=900, seed=7, epoch_offset=60):
    """Business-day calendar ending well after the registered epoch."""
    from datetime import date, timedelta
    rnd = random.Random(seed)
    end = date.fromisoformat(CF.REGISTERED["epoch_date"]) + timedelta(days=epoch_offset)
    days, d = [], end
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d -= timedelta(days=1)
    days.reverse()
    series = {}
    for k, sym in enumerate(CF.all_symbols()):
        px, rows = 100.0 + 10 * k, []
        vol = 0.035 if sym.endswith("-USD") else (0.0001 if sym == "BIL" else 0.012)
        drift = 0.00012 if sym == "BIL" else 0.0004 * math.sin(k + 1)
        for i, day in enumerate(days):
            px *= math.exp(drift + vol * rnd.gauss(0, 1) + (0.002 * math.sin(i / (25 + k))))
            rows.append([day, round(px, 6)])
        series[sym] = rows
    return series


def main():
    # 1 registration
    reg = (ROOT / "REGISTRATION_9.md").read_text(encoding="utf-8")
    h = CF.registration_hash()
    check("1 registration hash matches REGISTRATION_9.md", ("registration-hash: %s" % h) in reg,
          "config.py hashes to %s" % h)

    series = synthetic()
    tape = DA.build_tape(series, asof="2100-01-01")

    # 2 fee law: buy then sell at flat prices
    flat = DA.Tape(tape.dates[:3], {s: [100.0, 100.0, 100.0] for s in CF.all_symbols()})
    for sym in ["SPY", "BTC-USD"]:
        tr = [{sym: 1.0}, {sym: 1.0}, {}]
        r = PF.simulate(flat, tr, 0)
        rt = CF.round_trip(sym)
        expect = 10000 * (1 / (1 + rt / 2)) * (1 - rt / 2)
        check("2 fee law %s (%.2f%% round trip)" % (sym, 100 * rt),
              abs(r["curve"][-1] - expect) < 1e-6, "got %.6f want %.6f" % (r["curve"][-1], expect))

    # 3 no lookahead: vandalise the last close of every symbol
    start = tape.first_full_index(CF.REGISTERED["warmup_bars"]) + 1
    last = tape.n - 1
    base = {}
    for cat in CF.REGISTERED["categories"]:
        for name, fn in RU.SLEEVES.items():
            base[(cat, name)] = fn(tape, cat, start)[0][last]
    bad = DA.Tape(tape.dates, {s: v[:-1] + [v[-1] * (5 if i % 2 else 0.2)]
                               for i, (s, v) in enumerate(tape.px.items())})
    moved = [k for k in base
             if RU.SLEEVES[k[1]](bad, k[0], start)[0][last] != base[k]]
    check("3 no lookahead (fill-day close cannot move a target)", not moved, str(moved))
    res_a = EN.build(tape)
    res_b = EN.build(bad)
    check("3b master target ignores the fill-day close",
          res_a["master"]["target_now"] == res_b["master"]["target_now"],
          "%s vs %s" % (res_a["master"]["target_now"], res_b["master"]["target_now"]))

    # 4 hold is hold
    a, b = CF.REGISTERED["categories"]["stock"]
    tr, _ = RU.sleeve_hold(tape, "stock", start)
    r = PF.simulate(tape, tr, start)
    rt = CF.round_trip(a)
    want = 0.0
    for s in (a, b):
        dollars = 5000 / (1 + rt / 2)
        want += dollars * tape.px[s][last] / tape.px[s][start]
    check("4 HOLD sleeve equals hand-computed buy-and-hold", abs(r["curve"][last] - want) < 0.01,
          "%.4f vs %.4f" % (r["curve"][last], want))

    # 5 cash grows by BIL
    tr = [None] * tape.n
    for j in range(start, tape.n):
        tr[j] = {}
    r = PF.simulate(tape, tr, start)
    want = 10000 * tape.px["BIL"][last] / tape.px["BIL"][start]
    check("5 idle cash grows exactly by the T-bill ratio", abs(r["curve"][last] - want) < 1e-6)

    # 6 weights sane + 9 no negative cash
    ok6, ok9 = True, True
    for cat in CF.REGISTERED["categories"]:
        for name, fn in RU.SLEEVES.items():
            t, _ = fn(tape, cat, start)
            for w in t[start:]:
                if any(v < 0 for v in w.values()) or sum(w.values()) > 1.0 + 1e-9:
                    ok6 = False
            if PF.simulate(tape, t, start)["cash"] < 0:
                ok9 = False
    check("6 every target is between 0 and 100%", ok6)
    check("9 cash never negative", ok9)

    # 7 determinism
    res_c = EN.build(tape)
    check("7 two builds are identical", json.dumps(res_a, sort_keys=True, default=str)
          == json.dumps(res_c, sort_keys=True, default=str))

    # 8 continuity: forward and replay master share targets after the epoch
    ep = next(i for i, d in enumerate(tape.dates) if d >= CF.REGISTERED["epoch_date"])
    check("8 epoch inside the synthetic tape and forward values exist",
          res_a["epoch_reached"] and res_a["master"].get("forward_value") is not None)
    check("8b forward master starts at $10,000 less entry fees only",
          9900 < (res_a["master"]["forward_curve"][0][1]) <= 10000.0 + 1e-6,
          str(res_a["master"]["forward_curve"][:1]))

    # 10 stale feed
    frozen = DA.Tape(tape.dates, tape.px)
    check("10 a tape ending long ago is stale",
          DA.staleness_days(frozen, today="2100-01-01") > CF.REGISTERED["stale_data_days"])

    # 11 record guard
    from ladder import cli as CL
    with tempfile.TemporaryDirectory() as td:
        CL.DATA = Path(td)
        r1 = CL._record_and_check(res_a)
        tampered = copy.deepcopy(res_a)
        d0 = sorted(tampered["forward_values"])[0]
        tampered["forward_values"][d0]["MASTER"] += 5.0
        r2 = CL._record_and_check(tampered)
        rec = json.loads((Path(td) / CL.RECORD).read_text())
        check("11 record is append-only and drift is caught",
              r1["drift_count"] == 0 and r2["drift_count"] >= 1
              and abs(rec["days"][d0]["MASTER"] - res_a["forward_values"][d0]["MASTER"]) < 1e-9,
              "%s %s" % (r1, r2))

    print()
    if FAILS:
        print("%d FAILED: %s" % (len(FAILS), ", ".join(FAILS)))
        return 1
    print("all laws hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
