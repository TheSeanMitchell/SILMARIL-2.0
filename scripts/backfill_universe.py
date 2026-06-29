"""
scripts/backfill_universe.py — FULL UNIVERSE + 1-YEAR FINGERPRINT BACKFILL (2.6.1, fixed).

Writes up to 1 YEAR of daily history into docs/data/price_samples.json under the EXACT keys the
dashboard reads (crypto = BASE-USD with a hyphen; equities = plain ticker), MERGING with existing
intraday points so graphs show year + today. Real data only.

  CRYPTO  -> full Binance.US + Coinbase USD/USDT spot universe, via ccxt   (key: BTC-USD)
  STOCKS  -> SP500 + a broad ETF/equity set, via yfinance                  (key: AAPL)
  METALS  -> HARD_CURRENCY_FULL + metal ETFs                               (key: GLD)
  ENERGY  -> OIL_COMPLEX_FULL + energy ETFs                                (key: XLE)
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PS = ROOT / "docs" / "data" / "price_samples.json"

# broad investable ETF/equity coverage so it isn't just SP500
BROAD = [
    # sector SPDRs + broad market
    "SPY","QQQ","DIA","IWM","VTI","VOO","VEA","VWO","EFA","EEM","ACWI",
    "XLK","XLF","XLE","XLV","XLI","XLY","XLP","XLU","XLB","XLRE","XLC","SMH","SOXX","XBI","IBB","KRE","XHB","ITB","XRT","XME","XOP","OIH","KBE",
    # commodities / metals / energy
    "GLD","IAU","SLV","SIVR","PPLT","PALL","CPER","GDX","GDXJ","SIL","USO","BNO","UNG","UGA","DBO","DBC","DBA","URA","URNM","ICLN","TAN","FAN","PBW",
    # bonds / rates / vol
    "TLT","IEF","SHY","LQD","HYG","AGG","BND","TIP","GOVT","VIXY","UVXY",
    # big single names + thematic
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AMD","NFLX","JPM","BAC","XOM","CVX","COP","BRK-B","UNH","JNJ","V","MA","WMT","HD","PG","KO","PEP","DIS","BABA","ARKK","COIN","MSTR","MARA","RIOT","PLTR","SOFI",
]
METAL_ETF = ["GLD","IAU","SLV","SIVR","PPLT","PALL","CPER","GDX","GDXJ","SIL"]
ENERGY_ETF = ["XLE","XOP","OIH","USO","BNO","UNG","UGA","DBO","URA","URNM","ICLN","TAN","FAN"]

def _iso(ms): return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()

def _load():
    try: return json.loads(PS.read_text())
    except Exception: return {"samples": {}}

def _merge(samples, key, rows):
    if not rows: return
    m = {t: p for t, p in samples.get(key, [])}
    for t, p in rows: m[t] = p
    samples[key] = sorted([[t, p] for t, p in m.items()])

def backfill_crypto(samples):
    try: import ccxt
    except Exception as e: print("  ccxt missing:", e); return
    for exname in ("binanceus", "coinbase"):
        try:
            ex = getattr(ccxt, exname)({"enableRateLimit": True, "timeout": 30000}); mk = ex.load_markets()
        except Exception as e:
            print(f"  {exname} init failed: {e}"); continue
        pairs = [s for s, m in mk.items() if m.get("spot") and m.get("active") and m.get("quote") in ("USD", "USDT")]
        print(f"  {exname}: {len(pairs)} USD/USDT spot pairs")
        done = 0
        for sym in pairs:
            key = sym.split("/")[0] + "-USD"     # TRX/USDT -> TRX-USD  (matches dashboard)
            if len([1 for t, _ in samples.get(key, []) if "T00:00:00" in t]) > 300:
                continue
            try:
                oh = ex.fetch_ohlcv(sym, timeframe="1d", limit=365)
                _merge(samples, key, [[_iso(r[0]), r[4]] for r in oh if r and r[4]]); done += 1
            except Exception: pass
        print(f"    {exname}: backfilled {done} coins")

def backfill_equities(samples):
    try:
        import yfinance as yf
    except Exception as e:
        print("  yfinance missing:", e); return
    syms = set(BROAD) | set(METAL_ETF) | set(ENERGY_ETF)
    try:
        from silmaril.universe.expanded import SP500, HARD_CURRENCY_FULL, OIL_COMPLEX_FULL
        for lst in (SP500, HARD_CURRENCY_FULL, OIL_COMPLEX_FULL):
            for t in lst: syms.add(t[0] if isinstance(t, (list, tuple)) else t)
    except Exception as e:
        print("  universe import (non-fatal):", e)
    syms = sorted(s for s in syms if s)
    print(f"  equities/metals/energy: {len(syms)} symbols (yfinance 1y daily)")
    try:
        data = yf.download(syms, period="1y", interval="1d", auto_adjust=True, threads=True, progress=False)
        closes = data["Close"]                       # DataFrame: columns = tickers
    except Exception as e:
        print("  yfinance bulk failed:", e); return
    n = 0
    for s in syms:
        try:
            ser = closes[s].dropna() if hasattr(closes, "columns") else closes.dropna()
            rows = []
            for idx, v in ser.items():
                ts = idx.isoformat() if getattr(idx, "tzinfo", None) else idx.tz_localize("UTC").isoformat()
                rows.append([ts, float(v)])
            if rows: _merge(samples, s, rows); n += 1
        except Exception: pass
    print(f"    equities: backfilled {n} symbols")

def main():
    ps = _load(); samples = ps.get("samples", {}); before = len(samples)
    print("== FULL UNIVERSE BACKFILL (fixed keys) ==")
    backfill_crypto(samples)
    backfill_equities(samples)
    ps["samples"] = samples; PS.write_text(json.dumps(ps))
    filled = sum(1 for v in samples.values() if len(v) > 100)
    print(f"DONE. valuables {before}->{len(samples)} · {filled} now hold 100+ daily points (year view ready).")

if __name__ == "__main__":
    main()
