"""
scripts/venue_universe.py — 7.0 FINAL (Tier 2 / U2): VENUE TRUTH.

The question asked a thousand times, closed: the crypto universe was a hardcoded
top-100 list (silmaril/universe/expanded.py CRYPTO_TOP_100) merged with a
404-symbol ccxt/Kraken USDT ghost tape — NOT the operator's venues. This script
fetches the LIVE listings from the venues the operator can actually trade:

    · Binance.US   /api/v3/exchangeInfo          (spot, TRADING status)
    · Coinbase     /products (exchange API)      (online, USD/USDC quoted)
    · Robinhood    nummus currency_pairs         (best-effort; public endpoint,
                                                  tradability == 'tradable')

…canonicalizes every pair to BASE-USD, and writes docs/data/VENUE_UNIVERSE.json
with per-symbol venue flags. Consumers: the Master's venue gate (listed-union now
includes this file) and the funnel's honesty ("seen" should mean "fillable").

RUNS INSIDE GITHUB ACTIONS ONLY — the coding sandbox's egress proxy blocks these
domains. Keyless; no auth; read-only. A venue that fails to answer is recorded as
fetch_error for that venue and the previous listing for it is KEPT (never zeroed
by an outage) — staleness is stamped so the dashboard can say so.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "docs" / "data"
OUT = DATA / "VENUE_UNIVERSE.json"
UA = {"User-Agent": "SILMARIL-venue-truth/7.0 (research; contact via repo)"}
TIMEOUT = 25


def _get(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def canon(base: str) -> str:
    """BASE → BASE-USD, uppercased, defensively stripped."""
    b = str(base).upper().strip().replace("/", "").replace("-", "")
    return f"{b}-USD" if b else ""


def parse_binanceus(payload) -> set:
    out = set()
    for s in (payload or {}).get("symbols", []):
        try:
            if s.get("status") == "TRADING" and s.get("quoteAsset") in ("USD", "USDT", "USDC"):
                c = canon(s.get("baseAsset", ""))
                if c:
                    out.add(c)
        except Exception:
            continue
    return out


def parse_coinbase(payload) -> set:
    out = set()
    for p in (payload or []):
        try:
            if (p.get("quote_currency") in ("USD", "USDC")
                    and str(p.get("status", "")).lower() == "online"
                    and not p.get("trading_disabled")):
                c = canon(p.get("base_currency", ""))
                if c:
                    out.add(c)
        except Exception:
            continue
    return out


def parse_robinhood(payload) -> set:
    out = set()
    rows = (payload or {}).get("results", payload if isinstance(payload, list) else [])
    for p in rows or []:
        try:
            if str(p.get("tradability", "")).lower() == "tradable":
                base = (p.get("asset_currency") or {}).get("code") or str(p.get("symbol", "")).split("-")[0]
                c = canon(base)
                if c:
                    out.add(c)
        except Exception:
            continue
    return out


VENUES = (
    ("binanceus", "https://api.binance.us/api/v3/exchangeInfo", parse_binanceus),
    ("coinbase", "https://api.exchange.coinbase.com/products", parse_coinbase),
    ("robinhood", "https://nummus.robinhood.com/currency_pairs/", parse_robinhood),
)


def main() -> int:
    prev = {}
    try:
        prev = json.loads(OUT.read_text())
    except Exception:
        prev = {}
    prev_syms = prev.get("symbols") or {}

    now = datetime.now(timezone.utc).isoformat()
    listings, errors = {}, {}
    for name, url, parser in VENUES:
        try:
            got = parser(_get(url))
            listings[name] = got
            print(f"  {name}: {len(got)} USD-quotable listings")
        except Exception as e:  # outage → keep previous listing for this venue, stamp the error
            errors[name] = str(e)[:200]
            kept = {s for s, v in prev_syms.items() if (v.get("venues") or {}).get(name)}
            listings[name] = kept
            print(f"  {name}: FETCH ERROR ({e}) — kept {len(kept)} previous listings (never zeroed by an outage)")

    union = set().union(*listings.values()) if listings else set()
    symbols = {}
    for s in sorted(union):
        v = {name: (s in listings[name]) for name, _, _ in VENUES}
        symbols[s] = {"venues": v, "venue_count": sum(v.values())}

    payload = {
        "generated_at": now,
        "version": "venue-truth-7.0",
        "venues_fetched": [n for n, _, _ in VENUES if n not in errors],
        "fetch_errors": errors,
        "counts": {n: len(listings.get(n) or ()) for n, _, _ in VENUES},
        "union_count": len(union),
        "symbols": symbols,
        "what": ("LIVE listings from the operator's actual venues, canonicalized to -USD. "
                 "'Tradeable' = fresh data ∩ listed here. The +40% USDT ghost movers in the "
                 "opportunity journal are exactly the names ABSENT from this file. Refreshed "
                 "daily in Actions; a venue outage keeps its last listing with the error stamped, "
                 "so one bad fetch can never dark the gate."),
    }
    OUT.write_text(json.dumps(payload, indent=1))
    print(f"VENUE TRUTH: union {len(union)} symbols · errors: {list(errors) or 'none'} → {OUT}")
    # exit 0 even on partial errors — partial truth beats no file; errors are stamped in-band
    return 0


if __name__ == "__main__":
    sys.exit(main())
