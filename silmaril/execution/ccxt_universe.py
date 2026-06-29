"""
silmaril.execution.ccxt_universe — the GHOST FIX (Alpha 2.13).

The problem: of ~628 names, only ~52 are genuinely fresh; the rest are stale
ghosts you can't trade. The fix you called for: pull a real, liquid universe from
Binance (or Coinbase) via CCXT, where every pair actually trades tick-to-tick.

This fetches the top-volume USDT spot pairs and their recent candles, then writes
them to docs/data/ccxt_samples.json in the same schema price_samples uses. The
paper sim and the strategy leaderboard merge this in automatically, so they test
the WIDE fresh universe instead of 52 names — hundreds of real, tradeable coins.

It writes to a SEPARATE file on purpose: the live Alpaca executor keeps reading
only price_samples.json (so it never tries to send a Binance-only pair to Alpaca
and eat a 422). The wide universe lives in the SIM until you decide to migrate
live execution to an exchange that lists it (Coinbase/Binance).

Network note: this needs to reach Binance, which GitHub Actions can do. It is
fully fail-safe — any network/auth error leaves the last good file in place and
the rest of the cycle proceeds. No API key is required for public market data.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

EXCHANGE = "binance"      # or "coinbase"
QUOTE = "USDT"
TOP_N = 600               # 2.6.1: full liquid coverage
                          # junk the freshness filter rejects; raise further only if runtime holds.
TIMEFRAME = "5m"
CANDLES = 300             # ~25h of 5m history per pair
STABLES = {"USDT", "USDC", "DAI", "TUSD", "FDUSD", "BUSD", "USDP", "PYUSD"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def refresh(out_dir, top_n: int = TOP_N, exchange: str = EXCHANGE) -> Dict[str, Any]:
    out = Path(out_dir)
    path = out / "ccxt_samples.json"
    try:
        import ccxt
    except Exception as e:
        return {"ok": False, "error": f"ccxt not installed: {e}"}

    try:
        ex = getattr(ccxt, exchange)({"enableRateLimit": True, "timeout": 20000})
        ex.load_markets()
        # rank by quote volume from one tickers call
        tickers = ex.fetch_tickers()
        ranked = []
        for sym, t in tickers.items():
            try:
                if not sym.endswith("/" + QUOTE):
                    continue
                base = sym.split("/")[0]
                if base in STABLES:
                    continue
                m = ex.markets.get(sym) or {}
                if m.get("spot") is False:
                    continue
                qv = t.get("quoteVolume") or 0
                ranked.append((sym, float(qv)))
            except Exception:
                continue
        ranked.sort(key=lambda x: x[1], reverse=True)
        picks = [s for s, _ in ranked[:top_n]]
    except Exception as e:
        return {"ok": False, "error": f"market/ticker fetch failed: {e}",
                "kept_existing": path.exists()}

    samples: Dict[str, List[List[Any]]] = {}
    fetched = 0
    for sym in picks:
        try:
            ohlcv = ex.fetch_ohlcv(sym, timeframe=TIMEFRAME, limit=CANDLES)
            key = sym.replace("/", "")            # BTC/USDT -> BTCUSDT (has 'USD' -> crypto)
            rows = [[datetime.fromtimestamp(c[0] / 1000, timezone.utc).isoformat(),
                     float(c[4])] for c in ohlcv if c and c[4]]
            if len(rows) >= 20:
                samples[key] = rows
                fetched += 1
        except Exception:
            continue

    if not samples:
        return {"ok": False, "error": "no OHLCV fetched", "kept_existing": path.exists()}

    try:
        path.write_text(json.dumps({"exchange": exchange, "quote": QUOTE,
                                    "timeframe": TIMEFRAME, "updated_at": _now(),
                                    "samples": samples}, indent=2))
    except Exception as e:
        return {"ok": False, "error": f"write failed: {e}"}

    return {"ok": True, "exchange": exchange, "pairs_fetched": fetched,
            "universe": len(samples), "updated_at": _now()}


if __name__ == "__main__":
    import sys
    print(json.dumps(refresh(sys.argv[1] if len(sys.argv) > 1 else "docs/data"), indent=2))
