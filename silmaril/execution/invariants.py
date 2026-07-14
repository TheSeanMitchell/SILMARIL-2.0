"""
silmaril.execution.invariants — 5.0 LAW 11: INVARIANTS ENGINE

Contracts (Law 12) prove every store is SHAPED right and feedable. Invariants prove the
live state is LOGICALLY SAFE — the properties that must hold every cycle no matter what the
market did or which champion is trading. Where a contract catches "wired-but-starved," an
invariant catches "wired, fed, but doing something impossible" (a position with no stop, a
book that over-allocated, a trade born on a synthetic daily candle, GEKKO leaking into the
Master's funded set).

Each invariant is a pure, read-only check over real stores. Status is PASS / FAIL / PENDING
(a store that legitimately does not exist yet in the first cycles after install or wipe is
PENDING, never FAIL). Any FAIL flips the overall light red and names the exact violation in
INVARIANTS.json. A consecutive-all-green streak is tracked in INVARIANTS_STATE.json (long-
memory, wipe-surviving) toward the Definition-of-Done clause "contracts + invariants green
for 30 cycles." This module is wrapped by the caller and can never affect trading.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .atomic_io import write_json_atomic

STORE = "INVARIANTS.json"
STATE = "INVARIANTS_STATE.json"
BOOKS = ["crypto", "stock", "metal", "energy", "aggressive"]
START_CAP = 10000.0
DOD_STREAK = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load(out: Path, name: str) -> Optional[Any]:
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return None


def _finite(x: Any) -> bool:
    try:
        f = float(x)
        return f == f and f not in (float("inf"), float("-inf"))
    except Exception:
        return False


def _books(out: Path) -> Dict[str, Any]:
    d: Dict[str, Any] = {}
    for b in BOOKS:
        pb = _load(out, f"paper_book_{b}.json")
        if isinstance(pb, dict):
            d[b] = pb
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Individual invariants — each returns (status, detail).
# status: "PASS" | "FAIL" | "PENDING"
# ─────────────────────────────────────────────────────────────────────────────
def _inv_cash_finite(out: Path) -> Tuple[str, str]:
    books = _books(out)
    if not books:
        return "PENDING", "no paper books on disk yet"
    bad = []
    for b, pb in books.items():
        cash = pb.get("cash")
        rp = pb.get("realized_pnl", 0.0)
        if not _finite(cash) or float(cash) < -1e-6:
            bad.append(f"{b} cash={cash}")
        if not _finite(rp):
            bad.append(f"{b} realized_pnl={rp}")
    return ("FAIL", "; ".join(bad)) if bad else ("PASS", f"{len(books)} books: cash finite & non-negative")


def _inv_positions_protected(out: Path) -> Tuple[str, str]:
    books = _books(out)
    total = 0
    bad = []
    for b, pb in books.items():
        for sym, p in (pb.get("positions") or {}).items():
            total += 1
            tgt, stop = p.get("target"), p.get("stop")
            if not (_finite(tgt) and float(tgt) > 0):
                bad.append(f"{b}:{sym} target={tgt}")
            if not (_finite(stop) and float(stop) > 0):
                bad.append(f"{b}:{sym} stop={stop}")
    if total == 0:
        return "PASS", "no open positions (vacuously safe)"
    return ("FAIL", "; ".join(bad)) if bad else ("PASS", f"all {total} open positions carry target+stop")


def _inv_entry_positive(out: Path) -> Tuple[str, str]:
    books = _books(out)
    bad = []
    total = 0
    for b, pb in books.items():
        for sym, p in (pb.get("positions") or {}).items():
            total += 1
            e = p.get("entry")
            if not (_finite(e) and float(e) > 0):
                bad.append(f"{b}:{sym} entry={e}")
    if total == 0:
        return "PASS", "no open positions"
    return ("FAIL", "; ".join(bad)) if bad else ("PASS", f"all {total} entry prices > 0")


def _inv_no_overallocation(out: Path) -> Tuple[str, str]:
    books = _books(out)
    bad = []
    for b, pb in books.items():
        wag = 0.0
        for sym, p in (pb.get("positions") or {}).items():
            w = p.get("wager_usd")
            if _finite(w):
                wag += float(w)
        if wag > START_CAP * 1.05:
            bad.append(f"{b} deployed ${wag:.0f} > cap ${START_CAP*1.05:.0f}")
    return ("FAIL", "; ".join(bad)) if bad else ("PASS", f"no book over-allocated (≤ ${START_CAP*1.05:.0f})")


def _inv_champion_params_sane(out: Path) -> Tuple[str, str]:
    checked = 0
    bad = []
    for b in ("crypto", "stock", "metal", "energy"):
        sc = _load(out, f"champion_{b}.json")
        if not isinstance(sc, dict):
            continue
        lp = sc.get("live_params") or {}
        if not lp:
            continue
        checked += 1
        for k in ("entry", "target", "stop"):
            v = lp.get(k)
            if v is None:
                continue
            if not (_finite(v) and 0 < float(v) <= 1.0):
                bad.append(f"{b}.{k}={v}")
    if checked == 0:
        return "PENDING", "no champion live_params on disk yet"
    return ("FAIL", "; ".join(bad)) if bad else ("PASS", f"{checked} champions: entry/target/stop in (0,1]")


def _inv_no_synthetic_entry(out: Path) -> Tuple[str, str]:
    """Backfill-poisoning guard: a live trade must never have been entered on a synthetic
    daily candle (T00:00:00). If one did, a daily close leaked into the intraday entry path."""
    books = _books(out)
    bad = []
    scanned = 0
    for b, pb in books.items():
        for t in (pb.get("trades") or []):
            scanned += 1
            ts = str(t.get("t") or t.get("entry_t") or t.get("entry_time") or "")
            if "T00:00:00" in ts:
                bad.append(f"{b}:{t.get('sym')} entered @ {ts}")
    if scanned == 0:
        return "PASS", "no trades yet (vacuously safe)"
    return ("FAIL", "; ".join(bad[:6])) if bad else ("PASS", f"{scanned} trades: none entered on a synthetic candle")


def _inv_gekko_isolated(out: Path) -> Tuple[str, str]:
    """GEKKO (aggressive) must never appear in the Master's funded/allocated set."""
    ma = _load(out, "MASTER_ACCOUNT.json")
    if not isinstance(ma, dict):
        return "PENDING", "no MASTER_ACCOUNT.json yet"
    leak = []
    def _scan(obj, path):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if str(k).lower() in ("aggressive", "gekko") and v:
                    leak.append(f"{path}.{k}")
                _scan(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for it in obj:
                if isinstance(it, str) and it.lower() in ("aggressive", "gekko"):
                    leak.append(f"{path}[]={it}")
                else:
                    _scan(it, path)
    for key in ("allocation_plan", "proven_quadrants", "quadrant_recommendations", "allocation_pct"):
        if key in ma:
            _scan(ma[key], key)
    return ("FAIL", "GEKKO leaked into Master: " + "; ".join(leak)) if leak else \
           ("PASS", "GEKKO absent from Master funded/allocated set")


def _inv_realized_identity(out: Path) -> Tuple[str, str]:
    """Accounting identity: a book's realized_pnl equals the sum of its closed-trade P&Ls."""
    books = _books(out)
    bad = []
    checked = 0
    for b, pb in books.items():
        trades = pb.get("trades") or []
        closed = [t for t in trades if t.get("pnl") is not None and _finite(t.get("pnl"))]
        if not closed:
            continue
        checked += 1
        s = round(sum(float(t["pnl"]) for t in closed), 2)
        rp = round(float(pb.get("realized_pnl", 0.0) or 0.0), 2)
        _tol = max(0.05, 0.01 * len(closed))   # 5.11: per-trade rounding accumulates; 3¢ on 36 trades is arithmetic, not corruption
        if abs(s - rp) > _tol:
            bad.append(f"{b}: Σtrades ${s} ≠ realized ${rp}")
    if checked == 0:
        return "PASS", "no closed trades yet"
    return ("FAIL", "; ".join(bad)) if bad else ("PASS", f"{checked} books: realized_pnl = Σ closed trades")


def _inv_no_runaway(out: Path) -> Tuple[str, str]:
    books = _books(out)
    bad = []
    for b, pb in books.items():
        cash = pb.get("cash")
        if _finite(cash) and float(cash) > START_CAP * 10:
            bad.append(f"{b} cash ${float(cash):.0f} > 10× start")
    return ("FAIL", "; ".join(bad)) if bad else ("PASS", "no book cash exceeds 10× starting capital")


INVARIANTS: List[Tuple[str, str, Callable[[Path], Tuple[str, str]]]] = [
    ("INV1", "books cash finite & non-negative", _inv_cash_finite),
    ("INV2", "open positions carry target + stop", _inv_positions_protected),
    ("INV3", "position entry prices positive", _inv_entry_positive),
    ("INV4", "no book over-allocated", _inv_no_overallocation),
    ("INV5", "champion params in (0,1]", _inv_champion_params_sane),
    ("INV6", "no trade entered on a synthetic candle", _inv_no_synthetic_entry),
    ("INV7", "GEKKO isolated from Master", _inv_gekko_isolated),
    ("INV8", "realized P&L accounting identity", _inv_realized_identity),
    ("INV9", "no equity runaway", _inv_no_runaway),
    ("INV10", "market-hours guard (no weekend stock entries)", lambda out: _rule_market_hours(out)),
]



def _rule_market_hours(out):
    """5.1 — the recurring market-hours regression gets a standing tripwire:
    no STOCK BUY may carry a weekend timestamp (UTC Sat/Sun). Crypto/metal
    trade 24/7 and are exempt; energy pits vary, so stock is the hard rule."""
    import json as _json
    from datetime import datetime as _dt
    try:
        d = _json.loads((out / "paper_book_stock.json").read_text())
    except Exception:
        return "PENDING", "market-hours: no stock book yet"
    bad = []
    for t in (d.get("trades") or [])[-200:]:
        if t.get("side") != "BUY":
            continue
        try:
            wd = _dt.fromisoformat(str(t.get("t")).replace("Z", "+00:00")).weekday()
        except Exception:
            continue
        if wd >= 5:
            bad.append(f"{t.get('sym')}@{str(t.get('t'))[:16]}")
    if bad:
        return "FAIL", "market-hours VIOLATION — stock BUY on weekend: " + ", ".join(bad[:4])
    return "OK", "market-hours: no weekend stock entries (last 200 trades)"

def check_invariants(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    rows: List[Dict[str, str]] = []
    fails = 0
    for iid, name, fn in INVARIANTS:
        try:
            status, detail = fn(out)
        except Exception as e:
            status, detail = "FAIL", f"checker error: {e}"
        if status == "FAIL":
            fails += 1
        rows.append({"id": iid, "name": name, "status": status, "detail": detail})

    all_green = (fails == 0)

    # consecutive-green streak (wipe-surviving)
    st = _load(out, STATE) or {}
    streak = int(st.get("green_streak", 0))
    streak = streak + 1 if all_green else 0
    best = max(int(st.get("best_streak", 0)), streak)
    state = {"generated_at": _now().isoformat(), "green_streak": streak,
             "best_streak": best, "dod_target": DOD_STREAK,
             "dod_met": streak >= DOD_STREAK}
    write_json_atomic(out / STATE, state)

    reds = [r for r in rows if r["status"] == "FAIL"]
    pend = [r for r in rows if r["status"] == "PENDING"]
    verdict = ("ALL GREEN — every safety invariant holds" if all_green and not pend
               else f"ALL GREEN ({len(pend)} pending, first cycles)" if all_green
               else f"RED — {len(reds)} invariant(s) violated")
    payload = {"generated_at": _now().isoformat(), "all_green": all_green,
               "verdict": verdict, "green_streak": streak, "dod_target": DOD_STREAK,
               "dod_met": state["dod_met"], "checks": rows,
               "reds": [f"{r['id']} {r['name']}: {r['detail']}" for r in reds],
               "what": ("Per-cycle logical-safety invariants. Contracts prove stores are shaped "
                        "right; invariants prove the live state is doing nothing impossible. Any "
                        "RED names the exact violation. Green for %d cycles satisfies the DoD "
                        "clause." % DOD_STREAK)}
    write_json_atomic(out / STORE, payload)
    return payload


if __name__ == "__main__":
    import sys
    r = check_invariants(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(r["verdict"], "| streak", r["green_streak"])
    for c in r["checks"]:
        print(f"  {c['id']} {c['status']:7s} {c['name']} — {c['detail']}")
