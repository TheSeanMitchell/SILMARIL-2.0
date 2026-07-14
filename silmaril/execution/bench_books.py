"""
silmaril.execution.bench_books — 5.0 NULL LAYER (Law 10: the Null Twin)

Four strategy-free $10k baseline books that only mark to market. They hold, they
never trade, and every governed book is judged against them so "up" always means
"up versus doing nothing":

    BENCH_CASH — accrues the risk-free knob APY (PARAM_CATALOG.bench_books.cash_apy)
    BENCH_SPY  — buys SPY once at first mark, holds forever
    BENCH_HODL — 50/50 BTC-USD / ETH-USD at first mark, holds forever
    BENCH_EQW  — equal-weight basket of up to 8 fresh crypto names snapshotted at
                 creation (point-in-time; the basket is frozen so there is zero
                 survivorship rewriting)

Doctrine: marks come ONLY from real ingested samples (price_samples.json) — a leg
with no real price simply waits, labeled, rather than inventing one. The books are
excluded from the Master and from championship by construction (separate store).
After any wipe (WIPE_MARKER.json newer than creation) every book re-baselines to a
fresh $10k so the comparison always starts where the governed books started.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .atomic_io import write_json_atomic

STORE = "BENCH_BOOKS.json"
START_CASH = 10000.0
HIST_CAP = 400          # equity-curve points kept per book
MARK_MIN_GAP_MIN = 8    # don't append history more than ~once a cycle


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def _load_json(p: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _latest_real_price(samples: Dict[str, List[Any]], sym: str,
                       max_age_h: float = 48.0) -> Optional[Tuple[str, float]]:
    """Newest NON-backfill sample for sym, or None. Backfill daily candles carry a
    bare midnight timestamp — Law: 'T00:00:00' points never feed a mark."""
    rows = samples.get(sym) or []
    for row in reversed(rows):
        try:
            t, px = row[0], float(row[1])
        except Exception:
            continue
        if "T00:00:00" in str(t):
            continue
        dt = _parse(t)
        if dt is None:
            continue
        if (_now() - dt).total_seconds() > max_age_h * 3600:
            return None
        if px > 0:
            return str(t), px
    return None


def _fresh_crypto_names(samples: Dict[str, List[Any]], limit: int = 8) -> List[str]:
    """Deterministic basket seed: fresh (24h) -USD names, newest-first then alpha."""
    scored = []
    for sym in samples:
        if not sym.endswith("-USD"):
            continue
        hit = _latest_real_price(samples, sym, max_age_h=24.0)
        if hit:
            scored.append((hit[0], sym))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    names = sorted(s for _, s in scored[: limit * 2])[:limit]
    return names


def _new_book(name: str, note: str) -> Dict[str, Any]:
    return {"name": name, "created_at": _iso(_now()), "start_cash": START_CASH,
            "units": {}, "entry": {}, "equity": START_CASH, "return_pct": 0.0,
            "status": "initializing", "note": note, "history": []}


def _fresh_state(apy: float) -> Dict[str, Any]:
    return {
        "generated_at": _iso(_now()),
        "doctrine": ("NULL LAYER — strategy-free baselines; real marks only; never "
                     "Master-funded; never champion-eligible; re-baseline on wipe. "
                     "Every governed book is judged as delta-vs-null (Law 10)."),
        "cash_apy": apy,
        "books": {
            "BENCH_CASH": _new_book("BENCH_CASH", f"risk-free hurdle — accrues {apy*100:.2f}% APY (knob)"),
            "BENCH_SPY":  _new_book("BENCH_SPY", "SPY buy & hold — the stock-book null"),
            "BENCH_QQQ":  _new_book("BENCH_QQQ", "QQQ buy & hold — the growth/tech market null"),
            "BENCH_HODL": _new_book("BENCH_HODL", "50/50 BTC-ETH hold — the crypto/GEKKO null (MR must beat HOLDING)"),
            "BENCH_EQW":  _new_book("BENCH_EQW", "equal-weight fresh-crypto basket, frozen at creation — selection-vs-exposure null"),
        },
    }


def build_bench_books(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    knob = ((_load_json(out / "PARAM_CATALOG.json") or {}).get("bench_books") or {})
    if knob.get("enabled") is False:
        return {"summary": "disabled by knob"}
    apy = float(knob.get("cash_apy", 0.04) or 0.04)

    st = _load_json(out / STORE)
    wipe = _load_json(out / "WIPE_MARKER.json") or {}
    wiped_at = _parse(wipe.get("wiped_at", "")) if wipe else None

    def _stale_after_wipe(s: Optional[Dict[str, Any]]) -> bool:
        if not s:
            return True
        c = _parse(((s.get("books") or {}).get("BENCH_CASH") or {}).get("created_at", ""))
        return bool(wiped_at and c and c < wiped_at)

    if _stale_after_wipe(st):
        st = _fresh_state(apy)
    st["cash_apy"] = apy

    psj = _load_json(out / "price_samples.json") or {}
    samples: Dict[str, List[Any]] = psj.get("samples") or {}

    books = st["books"]
    now = _now()

    # ---- CASH: pure accrual off the knob (labeled basis, not a market mark) ----
    cash = books["BENCH_CASH"]
    days = max(0.0, (now - (_parse(cash["created_at"]) or now)).total_seconds() / 86400.0)
    cash["equity"] = round(START_CASH * ((1.0 + apy) ** (days / 365.0)), 2)
    cash["status"] = "accruing"
    cash["basis"] = f"knob APY {apy*100:.2f}% — replace with FRED 3-mo when wired"

    # ---- Price-holding books ----
    def _mark_holdings(book: Dict[str, Any], legs: Dict[str, float]) -> None:
        """legs: sym -> weight. Buys once (first time every leg has a real price),
        then marks forever. Missing feed => status says so, no invention."""
        if not book["units"]:
            prices = {s: _latest_real_price(samples, s) for s in legs}
            missing = [s for s, p in prices.items() if p is None]
            if missing:
                book["status"] = "awaiting real feed: " + ", ".join(sorted(missing))
                return
            for s, w in legs.items():
                px = prices[s][1]  # type: ignore[index]
                book["units"][s] = round((START_CASH * w) / px, 8)
                book["entry"][s] = px
            book["status"] = "holding"
        eq, stale = 0.0, []
        for s, u in book["units"].items():
            hit = _latest_real_price(samples, s)
            if hit is None:
                stale.append(s)
                eq += u * float(book["entry"].get(s, 0.0))
            else:
                eq += u * hit[1]
        book["equity"] = round(eq, 2)
        book["status"] = "holding" if not stale else ("holding (stale marks: " + ", ".join(sorted(stale)) + ")")

    _mark_holdings(books["BENCH_SPY"], {str(knob.get("spy", "SPY")): 1.0})
    if "BENCH_QQQ" not in books:   # states created before 5.11 WRAP gain the QQQ null in place
        books["BENCH_QQQ"] = _new_book("BENCH_QQQ", "QQQ buy & hold — the growth/tech market null")
    _mark_holdings(books["BENCH_QQQ"], {str(knob.get("qqq", "QQQ")): 1.0})
    _mark_holdings(books["BENCH_HODL"], {"BTC-USD": 0.5, "ETH-USD": 0.5})

    eqw = books["BENCH_EQW"]
    if not eqw["units"]:
        basket = knob.get("eqw_basket") or _fresh_crypto_names(samples, 8)
        if basket:
            eqw["basket"] = basket
            _mark_holdings(eqw, {s: 1.0 / len(basket) for s in basket})
        else:
            eqw["status"] = "awaiting fresh crypto universe"
    else:
        _mark_holdings(eqw, {s: 0 for s in eqw["units"]})  # weights unused post-buy

    # ---- returns + capped history ----
    for b in books.values():
        b["return_pct"] = round((b["equity"] / START_CASH - 1.0) * 100.0, 3)
        h = b.get("history") or []
        last_t = _parse(h[-1][0]) if h else None
        if last_t is None or (now - last_t).total_seconds() >= MARK_MIN_GAP_MIN * 60:
            h.append([_iso(now), b["equity"]])
        b["history"] = h[-HIST_CAP:]

    st["generated_at"] = _iso(now)
    st["summary"] = " · ".join(
        f"{n.replace('BENCH_', '')} {b['return_pct']:+.2f}%" for n, b in books.items())
    write_json_atomic(out / STORE, st)
    return st


if __name__ == "__main__":
    import sys
    r = build_bench_books(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(json.dumps({k: r[k] for k in ("generated_at", "summary")}, indent=2))
