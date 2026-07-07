"""
silmaril.execution.price_sources — 5.0 RESILIENT PRICE SOURCING (metals + energy, FX-ready)

Why this exists (operator fire, 2026-07-07): OpenExchangeRates was the PRIMARY metals
source and was being hit every ~10-minute cycle — ~100+ calls/day against a 1,000/month
free tier, 80% burned in the first week. Energy leaned on Alpha Vantage (25/day) the same
way. This module makes that class of failure impossible two ways at once:

  1. KEYLESS-FIRST WATERFALL. Free, unlimited sources are tried first, so a normal cycle
     spends ZERO scarce quota. Metals depth (5): yfinance → Stooq → metalpriceapi →
     Twelve Data → OpenExchangeRates. Energy depth (4): yfinance → Stooq → Twelve Data →
     Alpha Vantage. Only symbols still missing fall through to the next source.

  2. PER-SOURCE DAILY BUDGET GUARD (SOURCE_BUDGET.json). Every keyed source has a hard
     calls-per-UTC-day cap; once spent, it is skipped until the day rolls. Keyless sources
     are uncapped. A scarce key can now never be drained by cadence — the cap is the
     ceiling regardless of how often the cycle runs.

UNIT INTEGRITY (this is a trading feed — a unit mismatch is a fake crash → bad trades):
precious metals (XAU/XAG/XPT/XPD) are sourced ONLY from USD/oz providers, so every source
agrees on units. Copper trades in USD/lb, a different unit entirely, so it is pinned to a
SINGLE source (yfinance HG=F) and never cross-filled — series integrity over completeness.

No synthetic data ever: a symbol with no real quote this cycle is simply omitted, and the
caller's append step holds the last real sample. Network hosts are unreachable from the
build sandbox (works on Actions cron, like the rest of ingestion); parsing is unit-tested.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

BUDGET_STORE = "SOURCE_BUDGET.json"

# Hard per-UTC-day caps for KEYED sources. Keyless sources are absent here (uncapped).
# Set well under each free tier so a fallback always remains and no key is ever drained.
DAILY_CAPS: Dict[str, int] = {
    "openexchangerates": 20,   # 1,000/mo tier -> ~33/day; 20 keeps months of headroom
    "alpha_vantage": 15,       # 25/day tier
    "metalpriceapi": 90,       # generous free tiers; still capped
    "twelvedata": 250,         # 800/day tier
}

# Precious metals: USD/oz on every source below (safe to cross-fill).
PRECIOUS = ["XAU", "XAG", "XPT", "XPD"]
# Copper: USD/lb — DIFFERENT UNIT. Single-source only (never cross-filled).
COPPER = "XCU"

_YF_METAL = {"XAU": "GC=F", "XAG": "SI=F", "XPT": "PL=F", "XPD": "PA=F", "XCU": "HG=F"}
_YF_ENERGY = {"WTI": "CL=F", "BRENT": "BZ=F", "NATGAS": "NG=F"}
_STOOQ_METAL = {"XAU": "xauusd", "XAG": "xagusd", "XPT": "xptusd", "XPD": "xpdusd"}
_STOOQ_ENERGY = {"WTI": "cl.f", "BRENT": "cb.f", "NATGAS": "ng.f"}
_TD_METAL = {m: f"{m}/USD" for m in PRECIOUS}
_TD_ENERGY = {"WTI": "WTI/USD", "BRENT": "BRENT/USD", "NATGAS": "NG/USD"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "silmaril/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()


def _get_json(url: str, timeout: int = 20) -> Any:
    return json.loads(_get(url, timeout))


def _sane(px: Any, lo: float = 0.0, hi: float = 1e7) -> Optional[float]:
    try:
        v = float(px)
    except Exception:
        return None
    return v if (v > lo and v < hi) else None


# ─────────────────────────────────────────────────────────────────────────────
# Budget guard
# ─────────────────────────────────────────────────────────────────────────────
class SourceBudget:
    def __init__(self, out_dir) -> None:
        self.path = Path(out_dir) / BUDGET_STORE
        self.today = _now().strftime("%Y-%m-%d")
        try:
            st = json.loads(self.path.read_text())
        except Exception:
            st = {}
        if st.get("day") != self.today:
            st = {"day": self.today, "calls": {}}
        self.st = st
        self.st.setdefault("calls", {})

    def allow(self, source: str) -> bool:
        cap = DAILY_CAPS.get(source)
        if cap is None:
            return True  # keyless / uncapped
        return int(self.st["calls"].get(source, 0)) < cap

    def spend(self, source: str) -> None:
        if source in DAILY_CAPS:
            self.st["calls"][source] = int(self.st["calls"].get(source, 0)) + 1

    def remaining(self) -> Dict[str, int]:
        return {s: max(0, cap - int(self.st["calls"].get(s, 0)))
                for s, cap in DAILY_CAPS.items()}

    def save(self) -> None:
        try:
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self.st, indent=2))
            os.replace(tmp, self.path)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Individual source adapters — each returns {sym: price} for whatever it can serve.
# Every adapter is fully guarded; a failure just yields {} and the waterfall moves on.
# ─────────────────────────────────────────────────────────────────────────────
def _src_yfinance(symmap: Dict[str, str], want: List[str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    tickers = [symmap[s] for s in want if s in symmap]
    if not tickers:
        return out
    try:
        import yfinance as yf  # already a repo dependency; proven on Actions
    except Exception:
        return out
    inv = {symmap[s]: s for s in want if s in symmap}
    try:
        data = yf.download(tickers, period="5d", interval="1h",
                           progress=False, threads=False)
        closes = data["Close"] if "Close" in data else data
        for tk in tickers:
            try:
                series = closes[tk] if hasattr(closes, "columns") and tk in closes.columns else closes
                val = None
                for x in reversed(list(series.dropna().values)):
                    val = _sane(x)
                    if val:
                        break
                if val:
                    out[inv[tk]] = val
            except Exception:
                continue
    except Exception:
        # per-ticker fallback if the batch shape misbehaves
        for tk in tickers:
            try:
                h = yf.Ticker(tk).history(period="5d", interval="1h")
                if len(h):
                    v = _sane(h["Close"].dropna().iloc[-1])
                    if v:
                        out[inv[tk]] = v
            except Exception:
                continue
    return out


def _parse_stooq_csv(csv_text: str) -> Optional[float]:
    """Stooq l/ endpoint CSV: header row then one data row; Close is column index 6
    (Symbol,Date,Time,Open,High,Low,Close,Volume). 'N/D' means no data."""
    try:
        lines = [ln for ln in csv_text.strip().splitlines() if ln.strip()]
        if len(lines) < 2:
            return None
        cells = lines[1].split(",")
        if len(cells) < 7:
            return None
        return _sane(cells[6])
    except Exception:
        return None


def _src_stooq(symmap: Dict[str, str], want: List[str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for s in want:
        sym = symmap.get(s)
        if not sym:
            continue
        try:
            csv_text = _get(f"https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcv&h&e=csv")
            v = _parse_stooq_csv(csv_text)
            if v:
                out[s] = v
        except Exception:
            continue
    return out


def _src_metalpriceapi(want: List[str], key: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    try:
        j = _get_json("https://api.metalpriceapi.com/v1/latest?" +
                      urllib.parse.urlencode({"api_key": key, "base": "USD",
                                              "currencies": ",".join(want)}))
        rates = j.get("rates", {}) or {}
        for m in want:
            r = rates.get(m)
            v = _sane((1.0 / r) if (r and r < 1) else r)
            if v:
                out[m] = v
    except Exception:
        pass
    return out


def _src_twelvedata(symmap: Dict[str, str], want: List[str], key: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for s in want:
        sym = symmap.get(s)
        if not sym:
            continue
        try:
            j = _get_json(f"https://api.twelvedata.com/price?symbol="
                          f"{urllib.parse.quote(sym)}&apikey={key}")
            v = _sane(j.get("price"))
            if v:
                out[s] = v
        except Exception:
            continue
    return out


def _src_oxr(want: List[str], key: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    try:
        j = _get_json(f"https://openexchangerates.org/api/latest.json?app_id={key}"
                      f"&symbols=" + ",".join(want))
        rates = j.get("rates", {}) or {}
        for m in want:
            r = rates.get(m)
            v = _sane((1.0 / r) if (r and r < 1) else r)
            if v:
                out[m] = v
    except Exception:
        pass
    return out


def _src_alpha_vantage(want: List[str], key: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    fnmap = {"WTI": "WTI", "BRENT": "BRENT", "NATGAS": "NATURAL_GAS"}
    for label in want:
        fn = fnmap.get(label)
        if not fn:
            continue
        try:
            j = _get_json(f"https://www.alphavantage.co/query?function={fn}"
                          f"&interval=daily&apikey={key}")
            for row in (j.get("data") or []):
                v = _sane(row.get("value"))
                if v:
                    out[label] = v
                    break
        except Exception:
            continue
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Waterfalls
# ─────────────────────────────────────────────────────────────────────────────
def _run_waterfall(want: List[str], steps: List[Tuple[str, Callable[[List[str]], Dict[str, float]]]],
                   budget: SourceBudget) -> Tuple[Dict[str, float], Dict[str, str]]:
    """steps: ordered (source_name, fn(missing)->{sym:px}). Keyless sources have no cap;
    keyed sources are gated + charged via the budget. Stops when all wanted are filled."""
    got: Dict[str, float] = {}
    prov: Dict[str, str] = {}
    for name, fn in steps:
        missing = [s for s in want if s not in got]
        if not missing:
            break
        if not budget.allow(name):
            continue
        try:
            res = fn(missing) or {}
        except Exception:
            res = {}
        if name in DAILY_CAPS:
            budget.spend(name)  # one logical fetch attempt = one charge
        for s, px in res.items():
            if s not in got and _sane(px):
                got[s] = float(px)
                prov[s] = name
    return got, prov


def fetch_metals_resilient(out_dir) -> Tuple[Dict[str, float], Dict[str, Any]]:
    budget = SourceBudget(out_dir)
    mpk = os.environ.get("METALPRICE_API_KEY") or os.environ.get("METALS_DEV_API_KEY")
    tdk = os.environ.get("TWELVEDATA_API_KEY")
    oxr = os.environ.get("OPENEXCHANGERATES_APP_ID")

    # PRECIOUS — full cross-fillable waterfall (all USD/oz)
    steps: List[Tuple[str, Callable[[List[str]], Dict[str, float]]]] = [
        ("yfinance", lambda w: _src_yfinance(_YF_METAL, w)),
        ("stooq", lambda w: _src_stooq(_STOOQ_METAL, w)),
    ]
    if mpk:
        steps.append(("metalpriceapi", lambda w: _src_metalpriceapi(w, mpk)))
    if tdk:
        steps.append(("twelvedata", lambda w: _src_twelvedata(_TD_METAL, w, tdk)))
    if oxr:
        steps.append(("openexchangerates", lambda w: _src_oxr(w, oxr)))
    prices, prov = _run_waterfall(PRECIOUS, steps, budget)

    # COPPER — single unit-safe source only (USD/lb); never cross-filled
    try:
        cu = _src_yfinance(_YF_METAL, [COPPER])
        if COPPER in cu:
            prices[COPPER] = cu[COPPER]
            prov[COPPER] = "yfinance"
    except Exception:
        pass

    budget.save()
    meta = {"provenance": prov, "budget_remaining": budget.remaining(),
            "sources_available": {"yfinance": True, "stooq": True,
                                  "metalpriceapi": bool(mpk), "twelvedata": bool(tdk),
                                  "openexchangerates": bool(oxr)}}
    return prices, meta


def fetch_energy_resilient(out_dir) -> Tuple[Dict[str, float], Dict[str, Any]]:
    budget = SourceBudget(out_dir)
    tdk = os.environ.get("TWELVEDATA_API_KEY")
    av = os.environ.get("ALPHA_VANTAGE_API_KEY")
    want = ["WTI", "BRENT", "NATGAS"]

    steps: List[Tuple[str, Callable[[List[str]], Dict[str, float]]]] = [
        ("yfinance", lambda w: _src_yfinance(_YF_ENERGY, w)),
        ("stooq", lambda w: _src_stooq(_STOOQ_ENERGY, w)),
    ]
    if tdk:
        steps.append(("twelvedata", lambda w: _src_twelvedata(_TD_ENERGY, w, tdk)))
    if av:
        steps.append(("alpha_vantage", lambda w: _src_alpha_vantage(w, av)))
    prices, prov = _run_waterfall(want, steps, budget)

    budget.save()
    meta = {"provenance": prov, "budget_remaining": budget.remaining(),
            "sources_available": {"yfinance": True, "stooq": True,
                                  "twelvedata": bool(tdk), "alpha_vantage": bool(av)}}
    return prices, meta


if __name__ == "__main__":
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else "docs/data"
    m, mm = fetch_metals_resilient(d)
    e, em = fetch_energy_resilient(d)
    print("metals:", m, "\n  provenance:", mm["provenance"], "\n  budget:", mm["budget_remaining"])
    print("energy:", e, "\n  provenance:", em["provenance"])
    print("(empty in sandbox — network hosts unreachable here; runs on Actions cron)")
