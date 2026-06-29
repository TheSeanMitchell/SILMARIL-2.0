"""
scripts/backfill_universe.py — FULL UNIVERSE + 1-YEAR FINGERPRINT BACKFILL (2.6.1).

Fills docs/data/price_samples.json with up to 1 YEAR of daily price history for EVERY valuable in
EVERY quadrant, so graphs/fingerprints are full from day one (year/month/week views all covered; the
live 5-minute sampler keeps filling the intraday/days detail going forward).

  CRYPTO  -> the FULL Binance.US + Coinbase USD/USDT spot universe (every listed coin), via ccxt.
  STOCKS  -> SP500 list, via yfinance.
  METALS  -> HARD_CURRENCY_FULL, via yfinance.
  ENERGY  -> OIL_COMPLEX_FULL, via yfinance.

Defensive per-symbol; merges into existing samples (won't clobber coins that already have history).
Run via the "Backfill Universe" workflow. Real data only — nothing synthetic.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PS = ROOT / "docs" / "data" / "price_samples.json"

def _iso(ms): return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()

def _load():
    try: return json.loads(PS.read_text())
    except Exception: return {"samples": {}}

def backfill_crypto(samples):
    try: import ccxt
    except Exception as e: print("  ccxt missing:", e); return
    for exname in ("binanceus", "coinbase"):
        try:
            ex = getattr(ccxt, exname)({"enableRateLimit": True, "timeout": 30000})
            mk = ex.load_markets()
        except Exception as e:
            print(f"  {exname} init failed: {e}"); continue
        pairs = [s for s, m in mk.items()
                 if m.get("spot") and m.get("active") and m.get("quote") in ("USD", "USDT")]
        print(f"  {exname}: {len(pairs)} USD/USDT spot pairs")
        for i, sym in enumerate(pairs):
            key = sym.replace("/", "")
            if len(samples.get(key, [])) > 300:   # already has real history
                continue
            try:
                oh = ex.fetch_ohlcv(sym, timeframe="1d", limit=365)
                rows = [[_iso(r[0]), r[4]] for r in oh if r and r[4]]
                if rows: samples[key] = rows
            except Exception:
                pass
            if i % 100 == 0: print(f"    {exname} {i}/{len(pairs)}")

def backfill_equities(samples):
    try:
        import yfinance as yf
        from silmaril.universe.expanded import SP500, HARD_CURRENCY_FULL, OIL_COMPLEX_FULL
    except Exception as e:
        print("  yfinance/universe import failed:", e); return
    syms = []
    for lst in (SP500, HARD_CURRENCY_FULL, OIL_COMPLEX_FULL):
        for t in lst:
            s = t[0] if isinstance(t, (list, tuple)) else t
            if s: syms.append(s)
    syms = sorted(set(syms))
    print(f"  stocks+metals+energy: {len(syms)} symbols (yfinance 1y daily)")
    try:
        data = yf.download(syms, period="1y", interval="1d", group_by="ticker",
                           threads=True, progress=False)
    except Exception as e:
        print("  yfinance bulk failed:", e); return
    for s in syms:
        try:
            ser = data[s]["Close"].dropna()
            rows = []
            for idx, v in ser.items():
                ts = idx.isoformat() if getattr(idx, "tzinfo", None) else idx.tz_localize("UTC").isoformat()
                rows.append([ts, float(v)])
            if rows: samples[s] = rows
        except Exception:
            pass

def main():
    ps = _load(); samples = ps.get("samples", {})
    before = len(samples)
    print("== FULL UNIVERSE BACKFILL ==")
    print("crypto (Binance.US + Coinbase full USD universe, 1y daily)...")
    backfill_crypto(samples)
    print("stocks / metals / energy (yfinance 1y daily)...")
    backfill_equities(samples)
    ps["samples"] = samples
    PS.write_text(json.dumps(ps))
    print(f"DONE. valuables: {before} -> {len(samples)} with up to 1y daily fingerprint history.")

if __name__ == "__main__":
    main()
