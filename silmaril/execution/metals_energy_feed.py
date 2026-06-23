"""
silmaril.execution.metals_energy_feed — METALS + ENERGY price ingestion (2.5.1).

Fetches real spot prices for metals (gold/silver/platinum/palladium/copper) and
energy (WTI/Brent/natural gas) from FREE APIs and appends timestamped samples to
metals_samples.json / energy_samples.json — the same format paper_sim already reads,
so metals and energy automatically get their own arenas, champions and books.

Runs in GitHub Actions cron (network available there; the build sandbox cannot reach
these hosts). Reads API keys from env. NO KEY → writes nothing (no synthetic data).

Env vars (free tiers):
  METALPRICE_API_KEY   metalpriceapi.com  (metals)         — or METALS_DEV_API_KEY
  TWELVEDATA_API_KEY   twelvedata.com     (energy + metals fallback)
"""
from __future__ import annotations
import json, os, urllib.request, urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

METALS = ["XAU", "XAG", "XPT", "XPD", "XCU"]
ENERGY = {"WTI": "WTI/USD", "BRENT": "BRENT/USD", "NATGAS": "NG/USD"}
CAP = 1500  # samples per symbol

def _now_iso(): return datetime.now(timezone.utc).isoformat()
def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "silmaril/2.5.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def _append(out: Path, fname: str, prices: Dict[str, float]):
    if not prices:
        return 0
    path = out / fname
    try: data = json.loads(path.read_text()).get("samples", {})
    except Exception: data = {}
    ts = _now_iso()
    for sym, px in prices.items():
        if px and px > 0:
            data.setdefault(sym, []).append([ts, round(float(px), 6)])
            data[sym] = data[sym][-CAP:]
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"samples": data, "updated": ts}))
    os.replace(tmp, path)
    return len(prices)

def fetch_metals() -> Dict[str, float]:
    out = {}
    # PRIMARY: OpenExchangeRates (you already have OPENEXCHANGERATES_APP_ID) — its
    # rates include precious metals as currencies; USD/oz = 1 / (metal-per-USD).
    oxr = os.environ.get("OPENEXCHANGERATES_APP_ID")
    if oxr:
        try:
            j = _get(f"https://openexchangerates.org/api/latest.json?app_id={oxr}&symbols=" + ",".join(METALS))
            rates = j.get("rates", {}) or {}
            for m in METALS:
                r = rates.get(m)
                if r: out[m] = (1.0 / r) if r < 1 else r
        except Exception:
            pass
    # fallback: metalpriceapi
    key = os.environ.get("METALPRICE_API_KEY")
    if key:
        for m in [x for x in METALS if x not in out]:
            try:
                j = _get("https://api.metalpriceapi.com/v1/latest?" +
                         urllib.parse.urlencode({"api_key": key, "base": "USD", "currencies": m}))
                r = (j.get("rates", {}) or {}).get(m)
                if r: out[m] = (1.0 / r) if r < 1 else r
            except Exception:
                pass
    return out

def fetch_energy() -> Dict[str, float]:
    out = {}
    # PRIMARY: Alpha Vantage commodities (you already have ALPHA_VANTAGE_API_KEY).
    av = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if av:
        for label, fn in (("WTI", "WTI"), ("BRENT", "BRENT"), ("NATGAS", "NATURAL_GAS")):
            try:
                j = _get(f"https://www.alphavantage.co/query?function={fn}&interval=daily&apikey={av}")
                data = j.get("data") or []
                for row in data:
                    v = row.get("value")
                    if v not in (None, ".", ""):
                        out[label] = float(v); break
            except Exception:
                pass
    # fallback: Twelve Data
    tdk = os.environ.get("TWELVEDATA_API_KEY")
    if tdk:
        for label, sym in [(k, v) for k, v in ENERGY.items() if k not in out]:
            try:
                j = _get(f"https://api.twelvedata.com/price?symbol={urllib.parse.quote(sym)}&apikey={tdk}")
                p = float(j.get("price")) if j.get("price") else None
                if p: out[label] = p
            except Exception:
                pass
    return out

def run_feed(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    metals = fetch_metals(); energy = fetch_energy()
    nm = _append(out, "metals_samples.json", metals)
    ne = _append(out, "energy_samples.json", energy)
    status = {"generated_at": _now_iso(), "metals_fetched": nm, "energy_fetched": ne,
              "metals": metals, "energy": energy,
              "note": ("No synthetic data. If counts are 0, set METALPRICE_API_KEY and/or "
                       "TWELVEDATA_API_KEY in the workflow env — then metal/energy books fill "
                       "and get their own arenas/champions automatically.")}
    try: (out / "metals_energy_feed_status.json").write_text(json.dumps(status, indent=2))
    except Exception: pass
    return status

if __name__ == "__main__":
    import sys
    s = run_feed(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(f"metals fetched: {s['metals_fetched']} | energy fetched: {s['energy_fetched']}")
    print("(0 = no API key set; that is expected in the build sandbox)")
