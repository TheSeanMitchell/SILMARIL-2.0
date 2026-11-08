"""ladder.data — daily adjusted closes, one calendar, completed bars only.

* Prices are ADJUSTED closes (splits and dividends folded in), so every holding and every
  benchmark is measured on total return. A position's value is always a RATIO of two
  closes from the same series, which stays correct when Yahoo back-adjusts history for a
  new dividend or split — the trap that the old append-only raw tape walked into.
* The clock is the NYSE calendar (SPY's trading days). Crypto is sampled on those dates.
* A bar dated today (UTC) is never used: today's close does not exist yet.
* If the feed fails, the last good file is used and the page says the data is stale.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import REGISTERED, all_symbols

PRICES_FILE = "ladder_prices.json"
HISTORY_START = "2014-01-01"


def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── fetching ──────────────────────────────────────────────────────────────────────

def _fetch_yfinance(symbols: List[str]) -> Dict[str, List[List]]:
    out: Dict[str, List[List]] = {}
    try:
        import yfinance as yf
    except Exception:
        return out
    for sym in symbols:                       # one at a time: gentler on rate limits
        for attempt in range(3):
            try:
                df = yf.Ticker(sym).history(start=HISTORY_START, interval="1d",
                                            auto_adjust=True, actions=False)
                closes = df["Close"].dropna()
                rows = [[ts.strftime("%Y-%m-%d"), round(float(px), 8)]
                        for ts, px in closes.items() if float(px) > 0]
                if rows:
                    out[sym] = rows
                    break
            except Exception:
                time.sleep(2 + 3 * attempt)
    return out


def _fetch_chart_api(symbols: List[str]) -> Dict[str, List[List]]:
    """Fallback: Yahoo's public chart endpoint, adjusted closes."""
    out: Dict[str, List[List]] = {}
    try:
        import requests
    except Exception:
        return out
    p1 = int(datetime(2014, 1, 1, tzinfo=timezone.utc).timestamp())
    p2 = int(time.time()) + 86400
    for sym in symbols:
        url = ("https://query2.finance.yahoo.com/v8/finance/chart/%s?period1=%d&period2=%d"
               "&interval=1d&events=div%%2Csplit&includeAdjustedClose=true" % (sym, p1, p2))
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (silmaril-ladder)"},
                             timeout=20)
            res = r.json()["chart"]["result"][0]
            ts = res["timestamp"]
            adj = res["indicators"]["adjclose"][0]["adjclose"]
            off = int(res.get("meta", {}).get("gmtoffset", 0))
            rows = []
            for t, px in zip(ts, adj):
                if px is None or px <= 0:
                    continue
                d = datetime.fromtimestamp(t + off, tz=timezone.utc).strftime("%Y-%m-%d")
                rows.append([d, round(float(px), 8)])
            if rows:
                out[sym] = rows
        except Exception:
            continue
    return out


def refresh(data_dir: Path) -> Tuple[Dict[str, List[List]], Dict]:
    """Fetch every symbol fresh; fall back per-symbol to the chart API, then to the
    last saved file. Returns (series, meta)."""
    data_dir = Path(data_dir)
    syms = all_symbols()
    got = _fetch_yfinance(syms)
    missing = [s for s in syms if s not in got]
    source = "yfinance"
    if missing:
        more = _fetch_chart_api(missing)
        got.update(more)
        if more:
            source = "yfinance+chart-api"
    old = load_saved(data_dir)
    still = [s for s in syms if s not in got]
    used_saved = []
    for s in still:
        if s in old.get("series", {}):
            got[s] = old["series"][s]
            used_saved.append(s)
    meta = {"fetched_at": datetime.now(timezone.utc).isoformat(), "source": source,
            "from_saved_file": used_saved,
            "missing": [s for s in syms if s not in got]}
    if len(got) == len(syms):
        (data_dir).mkdir(parents=True, exist_ok=True)
        tmp = data_dir / (PRICES_FILE + ".tmp")
        tmp.write_text(json.dumps({"meta": meta, "series": got}, separators=(",", ":")),
                       encoding="utf-8")
        tmp.replace(data_dir / PRICES_FILE)
    return got, meta


def load_saved(data_dir: Path) -> Dict:
    try:
        return json.loads((Path(data_dir) / PRICES_FILE).read_text(encoding="utf-8"))
    except Exception:
        return {}


# ── one aligned table ────────────────────────────────────────────────────────────

class Tape:
    """dates: the NYSE calendar (completed bars only). px[sym][i]: adjusted close on
    dates[i] (crypto forward-filled across at most 3 missing calendar dates)."""

    def __init__(self, dates: List[str], px: Dict[str, List[Optional[float]]]):
        self.dates = dates
        self.px = px
        self.n = len(dates)

    def first_full_index(self, warm: int) -> Optional[int]:
        """First index at which every symbol has `warm` valid closes behind it."""
        for i in range(self.n):
            ok = True
            for s, arr in self.px.items():
                if i - warm < 0 or any(v is None for v in arr[i - warm:i + 1]):
                    ok = False
                    break
            if ok:
                return i
        return None


def build_tape(series: Dict[str, List[List]], asof: Optional[str] = None) -> Tape:
    cutoff = asof or today_utc()
    cal_sym = REGISTERED["calendar_symbol"]
    dates = [d for d, _ in series[cal_sym] if d < cutoff]
    px: Dict[str, List[Optional[float]]] = {}
    for sym in all_symbols():
        m = {d: v for d, v in series.get(sym, []) if d < cutoff}
        col: List[Optional[float]] = []
        last, gap = None, 0
        for d in dates:
            v = m.get(d)
            if v is None:
                gap += 1
                v = last if (last is not None and gap <= 3) else None
            else:
                gap = 0
                last = v
            col.append(v)
        px[sym] = col
    return Tape(dates, px)


def staleness_days(tape: Tape, today: Optional[str] = None) -> int:
    from datetime import date
    t = date.fromisoformat(today or today_utc())
    return (t - date.fromisoformat(tape.dates[-1])).days if tape.dates else 9999
