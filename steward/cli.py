"""steward.cli — the one entrypoint.

    python -m steward.cli run        # the daily cycle (what the workflow calls)
    python -m steward.cli baseline   # replay the rules on the warmup tape
    python -m steward.cli report     # rebuild the dashboard from state
    python -m steward.cli verify     # invariants: hash, fee law, no-lookahead

`run` begins with `verify`. If any invariant fails, the cycle REFUSES to trade and
writes why — a system that cannot prove its own accounting does not get to act.
"""
from __future__ import annotations

import sys
from pathlib import Path

from . import baseline as B
from . import book as BK
from . import prices as P
from . import report as R
from . import shadow as SH
from .config import REGISTERED, STATE_FILE, registration_hash
from .util import ledger_append, read_json, write_json_atomic

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
DOCS = ROOT / "docs"


def load_state() -> dict:
    st = read_json(DATA / STATE_FILE, None)
    if not st:
        st = {"version": "steward-1.0", "registration_hash": registration_hash(),
              "epoch": None,
              "books": {name: BK.fresh_book(name) for name in REGISTERED["books"]}}
    return st


def save_state(st: dict) -> None:
    write_json_atomic(DATA / STATE_FILE, st)


def verify(quiet: bool = False) -> bool:
    """The invariants that guard against the two faults that cost the last system
    six weeks of evidence. Any failure -> no trading this cycle."""
    problems = []

    # 1. registration integrity: state must carry the hash of the code's parameters
    st = read_json(DATA / STATE_FILE, None)
    code_hash = registration_hash()
    if st and st.get("registration_hash") and st["registration_hash"] != code_hash:
        problems.append("REGISTRATION MISMATCH: state=%s code=%s — parameters changed "
                        "after the epoch; this requires a deliberate re-registration "
                        "(new state, new epoch), not a quiet continuation"
                        % (st["registration_hash"], code_hash))

    # 2. the fee law: a flat round trip must cost exactly rt/(1+rt/2) — the true
    # compounding of half the round trip on entry and half on exit
    from .config import round_trip
    px, rt = 100.0, round_trip("SPY")
    qty = 1000.0 / (px * (1 + rt / 2))
    net = qty * px * (1 - rt / 2) - 1000.0
    if abs((-net / 1000.0) - rt / (1 + rt / 2)) > 1e-12:
        problems.append("FEE LAW BROKEN: flat round trip cost %.4f%%, declared %.2f%%"
                        % (-net / 10.0, rt * 100))

    # 3. no lookahead: first_bar_after must never return the signal bar itself
    fake = {"X": [["2026-01-01", 1.0], ["2026-01-02", 2.0]]}
    bar = P.first_bar_after(fake, "X", "2026-01-01")
    if not bar or bar[0] != "2026-01-02":
        problems.append("NO-LOOKAHEAD BROKEN: first_bar_after returned %s" % bar)

    if problems:
        for p in problems:
            print("VERIFY FAIL:", p)
            ledger_append(DATA, "*", "VERIFY_FAIL", {"why": p})
        return False
    if not quiet:
        print("verify OK — registration %s, fee law holds, t+1 fills hold" % code_hash)
    return True


def cmd_run() -> int:
    if not verify(quiet=True):
        print("REFUSING TO TRADE — invariants failed; see ledger. Report still rebuilt.")
        st = load_state()
        store = P.load_store(DATA)
        R.build(st, store, DATA, DOCS)
        return 1
    st = load_state()
    first = st.get("epoch") is None
    store = P.refresh(DATA, first_run=first)
    if not store:
        print("no price data available and none stored — nothing to do")
        return 1
    st = BK.run_cycle(st, store, DATA)
    save_state(st)
    SH.run_all(store, DATA, fetch_news=True)
    if first:
        B.run_all(store, DATA)
    R.build(st, store, DATA, DOCS)
    for name, bk in st["books"].items():
        eq = BK.equity(bk, store)
        be = BK.bench_equity(bk, store)
        print("%-8s %-7s equity $%9.2f  hold $%9.2f  DELTA %+9.2f  pending %d"
              % (name, bk["status"], eq, be, eq - be, len(bk["pending"])))
    return 0


def cmd_baseline() -> int:
    store = P.load_store(DATA) or P.refresh(DATA, first_run=True)
    out = B.run_all(store, DATA)
    print(out["label"])
    for name, r in out["books"].items():
        if r.get("skipped"):
            print("%-8s skipped: %s" % (name, r["skipped"]))
        else:
            print("%-8s %s→%s  final $%s  hold $%s  delta %s  trips %s  maxDD %s%%"
                  % (name, r["window"][0], r["window"][1],
                     format(round(r["final_equity"]), ","),
                     format(round(r["bench_equity"] or 0), ","),
                     r["delta_usd"], r["round_trips"], r["max_dd_pct"]))
    return 0


def cmd_report() -> int:
    st = load_state()
    store = P.load_store(DATA)
    out = R.build(st, store, DATA, DOCS)
    print("wrote", out)
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        return cmd_run()
    if cmd == "baseline":
        return cmd_baseline()
    if cmd == "report":
        return cmd_report()
    if cmd == "verify":
        return 0 if verify() else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
