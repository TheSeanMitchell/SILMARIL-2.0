"""steward.prices — the append-only daily tape.

Rules, learned the hard way by the system this one replaces:
  * RAW daily closes (no dividend adjustment). Adjustment rewrites history, and a
    signal computed on rewritten history is a signal that changed after the fact.
    Ignoring dividends is a small drag AGAINST the equity books — the safe direction.
  * APPEND-ONLY: a (date, close) pair, once stored, is never overwritten. If a feed
    disagrees with the past, the past wins and the disagreement is logged.
  * PARTIAL BARS ARE NOT BARS: any bar dated today (UTC) is dropped. Crypto trades
    24/7 and today's "close" is a lie until midnight.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .config import PRICES_FILE, all_fetch_symbols
from .util import read_json, today_utc, write_json_atomic


def load_store(data_dir: Path) -> Dict[str, List]:
    d = read_json(Path(data_dir) / PRICES_FILE, {})
    return d.get("series", {}) if isinstance(d, dict) else {}


def save_store(data_dir: Path, series: Dict[str, List]) -> None:
    write_json_atomic(Path(data_dir) / PRICES_FILE,
                      {"version": "steward-prices-1.0", "series": series})


def fetch_daily(symbols: List[str], period: str = "60d") -> Dict[str, List]:
    """Fetch raw daily closes from yfinance. Returns {sym: [[date, close], ...]}.
    Guarded: a failed symbol is simply absent — the caller decides what staleness means."""
    out: Dict[str, List] = {}
    try:
        import yfinance as yf
    except Exception:
        return out
    try:
        df = yf.download(symbols, period=period, interval="1d", auto_adjust=False,
                         progress=False, group_by="ticker", threads=True)
    except Exception:
        return out
    today = today_utc()
    for sym in symbols:
        try:
            sub = df[sym] if len(symbols) > 1 else df
            closes = sub["Close"].dropna()
            rows = []
            for ts, px in closes.items():
                d = ts.strftime("%Y-%m-%d")
                if d >= today:               # partial bars are not bars
                    continue
                if px and float(px) > 0:
                    rows.append([d, round(float(px), 8)])
            if rows:
                out[sym] = rows
        except Exception:
            continue
    return out


def merge_append_only(store: Dict[str, List], fresh: Dict[str, List]) -> Dict[str, List]:
    """New dates append; existing dates are IMMUTABLE. Returns the merged store."""
    for sym, rows in fresh.items():
        have = {r[0] for r in store.get(sym, [])}
        merged = store.get(sym, []) + [r for r in rows if r[0] not in have]
        merged.sort(key=lambda r: r[0])
        store[sym] = merged
    return store


def refresh(data_dir: Path, first_run: bool = False) -> Dict[str, List]:
    """The daily fetch-and-merge. First run pulls 2 years to warm the 126-bar signal."""
    store = load_store(data_dir)
    period = "2y" if (first_run or not store) else "60d"
    fresh = fetch_daily(all_fetch_symbols(), period=period)
    store = merge_append_only(store, fresh)
    if fresh:
        save_store(data_dir, store)
    return store


# ── read helpers ──────────────────────────────────────────────────────────────────

def closes(store: Dict[str, List], sym: str) -> List:
    return store.get(sym, [])


def latest_bar(store: Dict[str, List], sym: str) -> Optional[List]:
    rows = store.get(sym) or []
    return rows[-1] if rows else None


def close_on_or_before(store: Dict[str, List], sym: str, date: str) -> Optional[float]:
    best = None
    for d, px in store.get(sym, []):
        if d <= date:
            best = px
        else:
            break
    return best


def first_bar_after(store: Dict[str, List], sym: str, date: str) -> Optional[List]:
    """The first completed bar strictly after `date` — the t+1 fill bar."""
    for row in store.get(sym, []):
        if row[0] > date:
            return row
    return None


def bars_after(store: Dict[str, List], sym: str, date: str, n: int) -> Optional[List]:
    """The bar n trading bars after `date`, for shadow forward-return grading."""
    rows = [r for r in store.get(sym, []) if r[0] > date]
    return rows[n - 1] if len(rows) >= n else None


def staleness_days(store: Dict[str, List], sym: str,
                   today: Optional[str] = None) -> Optional[int]:
    """Days between a symbol's newest bar and `today` (wall clock unless injected —
    tests feed a synthetic clock so the calendar logic is provable offline)."""
    from datetime import date as _date
    lb = latest_bar(store, sym)
    if not lb:
        return None
    y, m, d = (int(x) for x in lb[0].split("-"))
    ty, tm, td = (int(x) for x in (today or today_utc()).split("-"))
    return (_date(ty, tm, td) - _date(y, m, d)).days
