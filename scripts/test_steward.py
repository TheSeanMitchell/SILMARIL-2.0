#!/usr/bin/env python3
"""test_steward.py — the battery that would have caught both historical faults on day one.

Runs offline on synthetic data. Every test guards a law the audited system broke or
nearly broke:
  FEE LAW        — a flat round trip costs the full declared cost (the old workshop
                   charged half for six weeks and nothing noticed).
  NO LOOKAHEAD   — signals cannot see past their bar; fills land strictly after it
                   (the old learning audit graded trades at their own exits).
  REGISTRATION   — the parameter hash in code matches REGISTRATION.md, so a quiet
                   tweak is impossible.
  HYSTERESIS     — a marginal challenger cannot evict an incumbent (churn control).
  KILLS          — a crash liquidates the book and it STAYS liquidated.
  CALENDAR       — trades happen at monthly seams only; every fill bar > signal bar.

    python scripts/test_steward.py     # exits non-zero on any failure
"""
from __future__ import annotations

import copy
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from steward import book as BK                     # noqa: E402
from steward import prices as P                    # noqa: E402
from steward.config import (REGISTERED, registration_hash,   # noqa: E402
                            round_trip)
from steward.signals import choose, momentum_score  # noqa: E402

FAILS = []


def check(label, ok, detail=""):
    print("  %-64s %s %s" % (label, "OK" if ok else "FAIL", detail if not ok else ""))
    if not ok:
        FAILS.append(label)


def days_from(start: str, n: int):
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def synth_series(dates, start_px, daily_ret):
    px, out = start_px, []
    for d in dates:
        out.append([d, round(px, 6)])
        px *= (1 + daily_ret)
    return out


# ── 1. FEE LAW ────────────────────────────────────────────────────────────────────

def test_fee_law(tmp):
    dates = days_from("2025-01-01", 3)
    store = {"BTC-USD": [[dates[0], 100.0], [dates[1], 100.0], [dates[2], 100.0]]}
    bk = BK.fresh_book("crypto")
    bk["pending"] = [{"side": "BUY", "sym": "BTC-USD", "signal_bar": dates[0], "reason": "t"}]
    BK._fill_pending(bk, "crypto", store, tmp)
    bk["pending"] = [{"side": "SELL", "sym": "BTC-USD", "signal_bar": dates[1], "reason": "t"}]
    BK._fill_pending(bk, "crypto", store, tmp)
    rt = round_trip("BTC-USD")
    lost_pct = (REGISTERED["start_cash"] - bk["cash"]) / REGISTERED["start_cash"] * 100
    want = rt / (1 + rt / 2) * 100                  # exact: half in, half out, compounded
    check("flat round trip costs the full declared cost (%.2f%%)" % (rt * 100),
          abs(lost_pct - want) < 1e-9, "lost %.6f%% want %.6f%%" % (lost_pct, want))


# ── 2. NO LOOKAHEAD ───────────────────────────────────────────────────────────────

def test_no_lookahead(tmp):
    dates = days_from("2025-01-01", 140)
    rows = synth_series(dates, 100.0, 0.004)
    asof = dates[130]
    s1 = momentum_score(rows, asof)
    s2 = momentum_score([r for r in rows if r[0] <= asof], asof)
    check("momentum score ignores bars after its asof date", abs(s1 - s2) < 1e-12)

    store = {"BTC-USD": [[dates[0], 100.0], [dates[1], 999.0], [dates[2], 100.0]]}
    bk = BK.fresh_book("crypto")
    bk["pending"] = [{"side": "BUY", "sym": "BTC-USD", "signal_bar": dates[0], "reason": "t"}]
    BK._fill_pending(bk, "crypto", store, tmp)
    pos = bk["positions"].get("BTC-USD")
    check("an order fills at the first bar AFTER its signal bar, never at it",
          pos is not None and pos["filled"] == dates[1] and pos["raw_px"] == 999.0)


# ── 3. REGISTRATION ───────────────────────────────────────────────────────────────

def test_registration():
    h = registration_hash()
    check("registration hash is stable across calls", h == registration_hash())
    reg = (ROOT / "REGISTRATION.md")
    if reg.exists():
        ok = ("registration-hash: %s" % h) in reg.read_text(encoding="utf-8")
        check("REGISTRATION.md carries the code's exact hash (%s)" % h, ok)
    else:
        check("REGISTRATION.md exists", False)


# ── 4. HYSTERESIS & GATE ──────────────────────────────────────────────────────────

def test_choose():
    gate = REGISTERED["abs_gate"]
    t = choose(["A"], {"A": gate + 0.02, "B": gate + 0.025}, 1)
    check("a challenger inside the margin cannot evict the incumbent", t == ["A"])
    t = choose(["A"], {"A": gate + 0.02, "B": gate + 0.05}, 1)
    check("a decisively better challenger takes the seat", t == ["B"])
    t = choose(["A"], {"A": gate - 0.05, "B": gate - 0.02}, 1)
    check("nothing above the gate means cash, even for an incumbent", t == [])
    t = choose([], {"A": gate + 0.05, "B": gate + 0.03, "C": gate + 0.01}, 2)
    check("open seats go to the best eligible names", t == ["A", "B"])


# ── 5. KILLS ──────────────────────────────────────────────────────────────────────

def test_kill(tmp):
    dates = days_from("2025-01-01", 4)
    store = {"BTC-USD": [[dates[0], 100.0], [dates[1], 100.0]]}
    bk = BK.fresh_book("crypto")
    bk["pending"] = [{"side": "BUY", "sym": "BTC-USD", "signal_bar": dates[0], "reason": "t"}]
    BK._fill_pending(bk, "crypto", store, tmp)
    store["BTC-USD"].append([dates[2], 55.0])       # -45% — through crypto's -40% kill
    BK._check_kills(bk, "crypto", store, tmp, None)
    check("a -45% crash flips the crypto book to KILLED", bk["status"] == "KILLED")
    check("the kill queues a full liquidation",
          any(o["side"] == "SELL" for o in bk["pending"]))
    store["BTC-USD"].append([dates[3], 54.0])
    BK._fill_pending(bk, "crypto", store, tmp)
    check("after the liquidation fills, the book is flat",
          not bk["positions"] and not bk["pending"])
    BK._maybe_rebalance(bk, "crypto", store, tmp)
    check("a KILLED book never rebalances again", not bk["pending"])


# ── 5b. DAILY GATE EXIT — fast out, slow in ───────────────────────────────────────

def test_gate_exit(tmp):
    dates = days_from("2025-01-01", 190)
    up = synth_series(dates[:150], 100.0, 0.004)          # strong trend, buys happen
    flat = synth_series(dates[150:], up[-1][1], -0.02)    # then a genuine crash
    store = {"BTC-USD": up + flat,
             "ETH-USD": synth_series(dates, 50.0, -0.001)}
    bk = BK.fresh_book("crypto")
    bk["pending"] = [{"side": "BUY", "sym": "BTC-USD", "signal_bar": dates[148], "reason": "t"}]
    view = {s: [r for r in rows if r[0] <= dates[149]] for s, rows in store.items()}
    BK._fill_pending(bk, "crypto", view, tmp)
    fired = None
    for i in range(150, 190):
        view = {s: [r for r in rows if r[0] <= dates[i]] for s, rows in store.items()}
        BK._daily_exits(bk, "crypto", view, tmp)
        if any(o["side"] == "SELL" for o in bk["pending"]):
            fired = dates[i]
            break
    check("a dying trend is exited the DAY the gate breaks, not at month-end",
          fired is not None and fired < dates[189])


# ── 6. CALENDAR — a 5-month synthetic campaign ────────────────────────────────────

def test_calendar(tmp):
    dates = days_from("2025-01-01", 290)
    store = {"BTC-USD": synth_series(dates, 100.0, 0.004),
             "ETH-USD": synth_series(dates, 50.0, 0.001)}
    bk = BK.fresh_book("crypto")
    events = []
    for i in range(150, 290):                       # feed the tape day by day
        view = {s: [r for r in rows if r[0] <= dates[i]] for s, rows in store.items()}
        BK._fill_pending(bk, "crypto", view, tmp)
        before = len(bk["pending"])
        BK._maybe_rebalance(bk, "crypto", view, tmp, today=dates[i])
        if len(bk["pending"]) > before:
            events.append(dates[i])
    months = {e[:7] for e in events}
    check("decisions land at most once per calendar month",
          len(events) == len(months), "events=%s" % events)
    check("the rising asset was actually bought and held",
          "BTC-USD" in bk["positions"])
    eq = BK.equity(bk, {s: r for s, r in store.items()})
    check("a 0.4%%/day uptrend leaves the book in profit", eq > 10000)


if __name__ == "__main__":
    import tempfile
    print("STEWARD REGRESSION BATTERY")
    tmp = Path(tempfile.mkdtemp())
    for fn in (lambda: test_fee_law(tmp), lambda: test_no_lookahead(tmp),
               test_registration, test_choose,
               lambda: test_kill(tmp), lambda: test_gate_exit(tmp),
               lambda: test_calendar(tmp)):
        try:
            fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            FAILS.append(str(e))
    print()
    if FAILS:
        print("FAILED:", len(FAILS))
        sys.exit(1)
    print("ALL PASS — the laws hold.")
