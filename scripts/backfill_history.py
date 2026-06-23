#!/usr/bin/env python3
"""
scripts/backfill_history.py — JUMPSTART fingerprints & charts (June 16).

Seeds docs/data/news_history.json with REAL historical daily closes so the
dashboard's % chips (today / vs-prev / wk), the per-stock clock graphs, and
the news/timing fingerprints light up IMMEDIATELY instead of waiting days
for the system to accumulate one snapshot per run.

Uses the historical-daily endpoints of providers you ALREADY have keys for
(Tiingo first, FMP fallback). Runs inside GitHub Actions where the secrets
and network exist (this cannot run from a restricted sandbox).

SAFE + ADDITIVE: only PREPENDS dated rows that are missing; never deletes or
overwrites an existing dated row. Re-runnable (idempotent per date). Does not
touch any agent/scoring/engine logic — it only backfills a data file the
analytics already read.

Usage (in Actions or locally with keys set):
    python scripts/backfill_history.py --days 30
    python scripts/backfill_history.py --days 30 --tickers AAPL,MSFT,NVDA
"""
from __future__ import annotations
import argparse, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

DATA = Path("docs/data")
NEWS_HISTORY = DATA / "news_history.json"


def _load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def _save(p, obj):
    Path(p).write_text(json.dumps(obj, indent=2))


def _tiingo_daily(ticker, key, days):
    """Tiingo end-of-day daily closes."""
    import requests
    from datetime import date, timedelta
    start = (date.today() - timedelta(days=days + 5)).isoformat()
    try:
        r = requests.get(
            f"https://api.tiingo.com/tiingo/daily/{ticker}/prices",
            params={"startDate": start, "token": key},
            headers={"Content-Type": "application/json"}, timeout=15)
        if r.status_code != 200:
            return []
        return [{"date": row["date"][:10], "price": float(row["adjClose"])}
                for row in (r.json() or [])
                if row.get("adjClose")]
    except Exception:
        return []


def _fmp_daily(ticker, key, days):
    """FMP historical daily closes (fallback)."""
    import requests
    try:
        r = requests.get(
            f"https://financialmodelingprep.com/api/v3/historical-price-full/{ticker}",
            params={"timeseries": days + 5, "apikey": key}, timeout=15)
        if r.status_code != 200:
            return []
        hist = (r.json() or {}).get("historical") or []
        return [{"date": h["date"][:10], "price": float(h["close"])}
                for h in hist if h.get("close")]
    except Exception:
        return []


def _coingecko_daily(ticker, days):
    """CoinGecko daily closes for a -USD crypto ticker (no key needed for the
    public range endpoint; key used if present to lift rate limits)."""
    import requests
    # map common tickers to CoinGecko ids
    CG = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "XRP": "ripple",
          "DOT": "polkadot", "UNI": "uniswap", "ARB": "arbitrum", "XLM": "stellar",
          "XMR": "monero", "ICP": "internet-computer", "HBAR": "hedera-hashgraph",
          "CRO": "crypto-com-chain", "INJ": "injective-protocol", "LDO": "lido-dao",
          "PYTH": "pyth-network", "ALGO": "algorand", "AAVE": "aave", "ATOM": "cosmos",
          "JTO": "jito-governance-token", "MANA": "decentraland", "XTZ": "tezos",
          "FET": "fetch-ai", "ADA": "cardano", "AVAX": "avalanche-2", "LINK": "chainlink",
          "DOGE": "dogecoin", "MATIC": "matic-network", "LTC": "litecoin"}
    base = str(ticker).upper().replace("-USD", "").replace("USD", "")
    cid = CG.get(base)
    if not cid:
        return []
    try:
        key = os.getenv("COINGECKO_API_KEY", "").strip()
        params = {"vs_currency": "usd", "days": str(days), "interval": "daily"}
        headers = {"x-cg-demo-api-key": key} if key else {}
        r = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart",
            params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            return []
        prices = (r.json() or {}).get("prices") or []
        out = []
        for ms, price in prices:
            from datetime import datetime, timezone
            d = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            out.append({"date": d, "price": float(price)})
        return out
    except Exception:
        return []


def backfill(tickers, days):
    tiingo = os.getenv("TIINGO_API_KEY", "").strip()
    fmp = os.getenv("FMP_API_KEY", "").strip()
    if not tiingo and not fmp:
        print("WARN: no TIINGO/FMP key — stocks won't backfill (crypto via "
              "CoinGecko still will)")

    hist = _load(NEWS_HISTORY, {})
    if not isinstance(hist, dict):
        hist = {}

    seeded_rows = 0
    seeded_tickers = 0
    for i, t in enumerate(tickers, 1):
        is_crypto = str(t).upper().endswith("-USD") or str(t).upper().endswith("USD")
        bars = []
        if is_crypto:
            bars = _coingecko_daily(t, days)         # crypto -> CoinGecko
        else:
            if tiingo:
                bars = _tiingo_daily(t, tiingo, days)  # stock -> Tiingo
            if not bars and fmp:
                bars = _fmp_daily(t, fmp, days)        # stock -> FMP fallback
        if not bars:
            continue
        bars = sorted(bars, key=lambda b: b["date"])[-days:]
        existing = hist.get(t) or []
        existing_dates = {r.get("date") for r in existing}
        added = 0
        for b in bars:
            if b["date"] in existing_dates:
                continue
            # minimal row matching the news_history schema; price+date+
            # open_read are what the fingerprint/delta math reads. Sentiment
            # fields left neutral/None — this is price backfill, not fake news.
            existing.append({
                "date": b["date"], "price": b["price"],
                "open_read": b["price"], "sent": None, "cat": None,
                "cat_label": None, "antic": None, "ipo": None,
                "event": None, "signal": None,
                "backfilled": True})
            added += 1
        if added:
            existing.sort(key=lambda r: r.get("date", ""))
            hist[t] = existing
            seeded_rows += added
            seeded_tickers += 1
        if i % 25 == 0:
            print(f"  ...{i}/{len(tickers)} processed, {seeded_rows} rows so far")
            time.sleep(0.3)  # be polite to the API

    _save(NEWS_HISTORY, hist)
    print(f"DONE: seeded {seeded_rows} historical rows across "
          f"{seeded_tickers} tickers into {NEWS_HISTORY}")
    print("Next engine run will compute deltas + fingerprints from these.")


def _default_tickers():
    """Pull the FULL universe from signals.json — BOTH stocks and crypto —
    so charts/fingerprints light up on everything."""
    sig = _load(DATA / "signals.json", {})
    debs = sig.get("debates") or []
    return [str(d.get("ticker")).upper() for d in debs if d.get("ticker")]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--tickers", type=str, default="")
    a = ap.parse_args()
    tk = ([x.strip().upper() for x in a.tickers.split(",") if x.strip()]
          if a.tickers else _default_tickers())
    if not tk:
        print("No tickers (pass --tickers or ensure signals.json exists)"); sys.exit(1)
    print(f"Backfilling {len(tk)} tickers, {a.days} days of daily closes...")
    backfill(tk, a.days)
