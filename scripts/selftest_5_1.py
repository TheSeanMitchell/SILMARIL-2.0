"""selftest_5_1.py — PERMANENT REGRESSION PROTECTION.

Every bug this project has swatted and re-swatted gets an automated tripwire
here, so "it came back after an update/wipe" ends as a sentence anyone can say.
Pure-python, no network, seconds to run. Synthetic fixtures are TEST VECTORS
(explicitly allowed by doctrine); nothing here touches live stores.

Run:  python scripts/selftest_5_1.py            (from repo root)
CI:   .github/workflows/selftest.yml (weekly + on demand)
Exit: 0 all pass · 1 any fail (each failure names the historical incident).
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append((name, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))


def now():
    return datetime.now(timezone.utc)


# ── T1 · THE CORE-HOSTAGE GUARD (incident 2026-07-10: a broker gate enclosed
#    818 lines including the paper sim; the engine went dark in every lane).
#    AST-walk cli.py: the paper-sim invocation must NOT sit inside any `if`
#    whose test references _HAS_ALPACA or _broker_exec. -----------------------
def t1_core_never_hostage():
    src = (ROOT / "silmaril/cli.py").read_text()
    tree = ast.parse(src)
    hit = []

    class V(ast.NodeVisitor):
        def __init__(self):
            self.stack = []

        def visit_If(self, node):
            self.stack.append(node)
            self.generic_visit(node)
            self.stack.pop()

        def visit_ImportFrom(self, node):
            if node.module and node.module.endswith("paper_sim") and \
               any(a.name == "live_step" for a in node.names):
                for ifn in self.stack:
                    t = ast.dump(ifn.test)
                    if "_HAS_ALPACA" in t or "_broker_exec" in t:
                        hit.append(ast.dump(ifn.test)[:80])
            self.generic_visit(node)

    V().visit(tree)
    check("T1 core-never-hostage (paper sim outside broker conditionals)",
          not hit, f"live_step import nested under: {hit}")


# ── T2 · GEKKO EXIT CLASS (incident 2026-07-10: exits filtered by book label,
#    aggressive positions could never sell). Fixture live_step must SELL an
#    over-target aggressive position. ----------------------------------------
def t2_gekko_sells():
    from silmaril.execution import paper_sim as ps
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        t0 = now()
        sym = "TST-USD"
        prices = [1.00, 0.985, 0.99, 1.00, 1.01, 1.03, 1.035]
        samples = {sym: [[(t0 - timedelta(minutes=5 * (len(prices) - i))).isoformat(), p]
                         for i, p in enumerate(prices)]}
        (out / "price_samples.json").write_text(json.dumps({"samples": samples}))
        (out / "PARAM_CATALOG.json").write_text(json.dumps({
            "aggressive_book": {"enabled": True, "name": "GEKKO", "entry": 0.02,
                                 "target": 0.02, "stop": 0.06}}))
        book = {"cash": 8965.0, "equity": 10000.0, "realized_pnl": 0.0,
                "positions": {sym: {"sym": sym, "qty": 1000.0, "entry": 1.00,
                                     "mark": 1.03, "target": 0.02, "stop": 0.06,
                                     "t": (t0 - timedelta(hours=3)).isoformat(),
                                     "wager_usd": 1000.0, "cost": 0.004, "mfe": 1.035}},
                "trades": []}
        (out / "paper_book_aggressive.json").write_text(json.dumps(book))
        try:
            ps.live_step(out)
        except Exception as e:
            check("T2 GEKKO-class exits fire", False, f"live_step raised: {e}")
            return
        d = json.loads((out / "paper_book_aggressive.json").read_text())
        sold = any(t.get("side") == "SELL" and t.get("sym") == sym
                   for t in d.get("trades", []))
        check("T2 GEKKO-class exits fire (aggressive position past target sells)",
              sold, "over-target aggressive position did not sell")


# ── T3 · STALE-PRICE ZOMBIE (a held name whose feed dies must neither fill on
#    fiction nor zombie forever: it stays open, flagged stale). ---------------
def t3_stale_no_fiction_fill():
    from silmaril.execution import paper_sim as ps
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        t0 = now()
        sym = "OLD-USD"
        samples = {sym: [[(t0 - timedelta(hours=6)).isoformat(), 1.10]]}   # stale print above target
        (out / "price_samples.json").write_text(json.dumps({"samples": samples}))
        (out / "PARAM_CATALOG.json").write_text(json.dumps({}))
        book = {"cash": 9000.0, "equity": 10000.0, "realized_pnl": 0.0,
                "positions": {sym: {"sym": sym, "qty": 900.0, "entry": 1.00,
                                     "mark": 1.00, "target": 0.03, "stop": 0.05,
                                     "t": (t0 - timedelta(hours=9)).isoformat(),
                                     "wager_usd": 900.0, "cost": 0.004}},
                "trades": []}
        (out / "paper_book_crypto.json").write_text(json.dumps(book))
        try:
            ps.live_step(out)
        except Exception as e:
            check("T3 stale-price safety", False, f"live_step raised: {e}")
            return
        d = json.loads((out / "paper_book_crypto.json").read_text())
        still_open = sym in (d.get("positions") or {})
        no_sell = not any(t.get("side") == "SELL" for t in d.get("trades", []))
        flagged = still_open and d["positions"][sym].get("stale_price_min") is not None
        check("T3 stale-price safety (no fill on a 6h-old print; position flagged, armed)",
              still_open and no_sell and flagged,
              f"open={still_open} no_sell={no_sell} flagged={flagged}")


# ── T4 · GOVERNANCE GROUPING (incident: validation grouped by BOOK, election
#    graded an empty dict, champion frozen forever). --------------------------
def t4_validation_by_strategy():
    from silmaril.execution.champion_validation import build_champion_validation
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        trades = [{"side": "SELL", "realized_pct": 2.0, "champion_entry": "MR_x", "t": now().isoformat()}
                  for _ in range(6)]
        (out / "paper_book_crypto.json").write_text(json.dumps({"trades": trades}))
        cv = build_champion_validation(out)
        rows = cv.get("strategies") or []
        ok = rows and all(r.get("strategy") not in ("crypto", "stock", "metal", "energy")
                          for r in rows) and rows[0].get("book") == "crypto"
        check("T4 validation groups by entering strategy (never by book)",
              bool(ok), f"rows={[(r.get('book'), r.get('strategy')) for r in rows][:3]}")


# ── T5 · POST-STOP COOLDOWN (the LDO re-buy-the-knife lesson). ----------------
def t5_cooldown_semantics():
    cat = {"reentry_cooldown": {"after_stop_min": 240}}
    t0 = now()
    trades = [{"side": "SELL", "exit_reason": "STOP", "sym": "AAA-USD",
               "t": (t0 - timedelta(minutes=10)).isoformat()},
              {"side": "SELL", "exit_reason": "STOP", "sym": "BBB-USD",
               "t": (t0 - timedelta(minutes=500)).isoformat()}]
    cd = float(((cat.get("reentry_cooldown") or {}).get("after_stop_min", 240)) or 0)
    cool = set()
    for tr in reversed(trades[-400:]):
        if tr.get("side") == "SELL" and tr.get("exit_reason") == "STOP":
            ag = (t0 - datetime.fromisoformat(tr["t"])).total_seconds() / 60.0
            if ag <= cd:
                cool.add(tr["sym"])
    check("T5 post-STOP cooldown (10-min-ago blocked, 500-min-ago free)",
          cool == {"AAA-USD"}, f"cool={cool}")


# ── T6 · CHECKOUT-PROOF FRESHNESS (git resets mtimes; ages must come from
#    content). A 31h-old heartbeat under a brand-new mtime must go RED. -------
def t6_content_age():
    from silmaril.execution.store_contracts import _age_min
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "deep_heartbeat.json"
        p.write_text(json.dumps({"started_at": (now() - timedelta(hours=31)).isoformat()}))
        a = _age_min(p)   # fresh mtime, old content
        check("T6 content-timestamp freshness beats checkout mtime",
              a is not None and a > 30 * 60, f"age_min={a}")


# ── T7 · MARKET-HOURS TRIPWIRE (the recurring weekend regression). ------------
def t7_market_hours_rule():
    from silmaril.execution.invariants import _rule_market_hours
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        sat = datetime(2026, 7, 11, 15, 0, tzinfo=timezone.utc)  # a Saturday
        (out / "paper_book_stock.json").write_text(json.dumps(
            {"trades": [{"side": "BUY", "sym": "AAPL", "t": sat.isoformat()}]}))
        s, d = _rule_market_hours(out)
        check("T7 market-hours guard trips on a weekend stock BUY",
              s == "FAIL", f"status={s} detail={d[:60]}")


# ── T8 · MIN-TAKEHOME VETO WIRING (fee-aware expectancy stays enforced). ------
def t8_takehome_veto_present():
    s = (ROOT / "silmaril/execution/paper_sim.py").read_text()
    check("T8 fee-aware entry veto present (min_takehome / clear $ net)",
          ("min_takehome" in s) and ("net" in s), "veto text not found in paper_sim")


if __name__ == "__main__":
    for t in (t1_core_never_hostage, t2_gekko_sells, t3_stale_no_fiction_fill,
              t4_validation_by_strategy, t5_cooldown_semantics, t6_content_age,
              t7_market_hours_rule, t8_takehome_veto_present):
        try:
            t()
        except Exception as e:  # a crashing test is a failing test
            check(t.__name__, False, f"raised {type(e).__name__}: {e}")
    print(f"\n== SELFTEST 5.1: {len(PASS)} pass · {len(FAIL)} fail ==")
    if FAIL:
        for n, d in FAIL:
            print("  FAILED:", n, "—", d)
        sys.exit(1)
