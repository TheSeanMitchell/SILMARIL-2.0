"""
silmaril.data_sources.multi_source — FALLBACK CHAINS (2.5.3 reliability).

Every data need has an ordered list of providers. fetch_with_fallback() tries each in
turn until one returns data, so a single provider outage can never dark a feed for more
than the time it takes to fall through to the next one — within the SAME run. Add a
provider's API key as a GitHub secret and it automatically joins the chain.

The build sandbox can't reach these hosts; this runs in GitHub Actions. Providers with
no key configured are skipped (not errors).
"""
from __future__ import annotations
import json, os, urllib.request, urllib.parse
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

def _now(): return datetime.now(timezone.utc).isoformat()
def _get(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "silmaril/2.5.3"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

# ── PROVIDER CHAINS ──────────────────────────────────────────────────────────
# Each provider: (name, env_key_or_None, fetch_fn(symbol)->price|None).
# env_key None = keyless public endpoint (always available, used as a free fallback).

def _coingecko(sym):
    cg = os.environ.get("COINGECKO_API_KEY")
    base = sym.replace("-USD", "").lower()
    ids = {"btc": "bitcoin", "eth": "ethereum", "sol": "solana"}  # extend as needed
    cid = ids.get(base, base)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={cid}&vs_currencies=usd"
    if cg: url += f"&x_cg_demo_api_key={cg}"
    j = _get(url); return (j.get(cid, {}) or {}).get("usd")

def _cryptocompare(sym):
    k = os.environ.get("CRYPTOCOMPARE_API_KEY")
    base = sym.replace("-USD", "")
    url = f"https://min-api.cryptocompare.com/data/price?fsym={base}&tsyms=USD"
    if k: url += f"&api_key={k}"
    j = _get(url); return j.get("USD")

def _binance_public(sym):
    base = sym.replace("-USD", "")
    j = _get(f"https://api.binance.com/api/v3/ticker/price?symbol={base}USDT")
    return float(j["price"]) if j.get("price") else None

def _finnhub_stock(sym):
    k = os.environ.get("FINNHUB_API_KEY")
    if not k: return None
    j = _get(f"https://finnhub.io/api/v1/quote?symbol={sym}&token={k}")
    return j.get("c") or None

def _alphavantage_stock(sym):
    k = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not k: return None
    j = _get(f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={sym}&apikey={k}")
    q = j.get("Global Quote", {}) or {}
    v = q.get("05. price")
    return float(v) if v else None

def _twelvedata_stock(sym):
    k = os.environ.get("TWELVEDATA_API_KEY")
    if not k: return None
    j = _get(f"https://api.twelvedata.com/price?symbol={sym}&apikey={k}")
    return float(j["price"]) if j.get("price") else None

def _fmp_stock(sym):
    k = os.environ.get("FMP_API_KEY")
    if not k: return None
    j = _get(f"https://financialmodelingprep.com/api/v3/quote-short/{sym}?apikey={k}")
    return (j[0].get("price") if isinstance(j, list) and j else None)

def _freecryptoapi(sym):
    k = os.environ.get("FREECRYPTOAPI_API_KEY")
    if not k: return None
    base = sym.replace("-USD", "")
    try:
        j = _get(f"https://api.freecryptoapi.com/v1/getData?symbol={base}", headers={"Authorization": f"Bearer {k}", "User-Agent": "silmaril/2.5.3"})
        sym0 = (j.get("symbols") or [{}])[0]
        return float(sym0.get("last") or sym0.get("price")) if sym0 else None
    except Exception:
        return None

def _polygon_stock(sym):
    k = os.environ.get("POLYGON_API_KEY")
    if not k: return None
    j = _get(f"https://api.polygon.io/v2/aggs/ticker/{sym}/prev?apiKey={k}")
    res = (j.get("results") or [{}])[0]
    return res.get("c") or None

def _tiingo_stock(sym):
    k = os.environ.get("TIINGO_API_KEY")
    if not k: return None
    j = _get(f"https://api.tiingo.com/iex/?tickers={sym}&token={k}")
    return (j[0].get("last") if isinstance(j, list) and j else None)

CHAINS: Dict[str, List] = {
    "crypto_price": [
        ("CoinGecko", "COINGECKO_API_KEY", _coingecko),
        ("FreeCryptoAPI", "FREECRYPTOAPI_API_KEY", _freecryptoapi),
        ("Binance(public)", None, _binance_public),       # keyless — always available
    ],
    "stock_price": [
        ("Finnhub", "FINNHUB_API_KEY", _finnhub_stock),
        ("Polygon", "POLYGON_API_KEY", _polygon_stock),
        ("Tiingo", "TIINGO_API_KEY", _tiingo_stock),
        ("TwelveData", "TWELVEDATA_API_KEY", _twelvedata_stock),
        ("AlphaVantage", "ALPHA_VANTAGE_API_KEY", _alphavantage_stock),
        ("FMP", "FMP_API_KEY", _fmp_stock),
    ],
}

def fetch_with_fallback(need: str, symbol: str) -> Dict[str, Any]:
    """Try each provider in the chain until one returns a price. Returns which provider
    won and how many were tried, so the health layer can show the active source."""
    chain = CHAINS.get(need, [])
    tried = []
    for name, key, fn in chain:
        if key and not os.environ.get(key):
            continue  # provider not configured — skip, not an error
        tried.append(name)
        try:
            px = fn(symbol)
            if px and px > 0:
                return {"ok": True, "price": float(px), "source": name,
                        "providers_tried": tried, "at": _now()}
        except Exception:
            continue
    return {"ok": False, "price": None, "source": None, "providers_tried": tried, "at": _now()}

def chain_status() -> Dict[str, Any]:
    """For the health panel: per need, how many providers are configured (fallback depth)."""
    out = {}
    for need, chain in CHAINS.items():
        configured = [n for n, k, _ in chain if (k is None or os.environ.get(k))]
        out[need] = {"depth": len(configured), "total": len(chain), "active": configured}
    return out

if __name__ == "__main__":
    print("Fallback chains configured:")
    for need, s in chain_status().items():
        print(f"  {need}: {s['depth']}/{s['total']} providers ready -> {s['active']}")
