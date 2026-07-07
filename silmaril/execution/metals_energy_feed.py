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
    # 5.0: delegated to the resilient, budget-guarded waterfall
    # (yfinance -> Stooq -> metalpriceapi -> Twelve Data -> OpenExchangeRates).
    # OXR is now a budget-capped LAST resort, not the primary — this is the fix for
    # the quota burn. Kept here for backward compatibility; run_feed uses the meta form.
    try:
        from .price_sources import fetch_metals_resilient
        prices, _ = fetch_metals_resilient(os.environ.get("SILMARIL_OUT", "docs/data"))
        return prices
    except Exception:
        return {}

def fetch_energy() -> Dict[str, float]:
    # 5.0: delegated to the resilient waterfall (yfinance -> Stooq -> Twelve Data ->
    # Alpha Vantage). AV is now budget-capped, not hammered every cycle.
    try:
        from .price_sources import fetch_energy_resilient
        prices, _ = fetch_energy_resilient(os.environ.get("SILMARIL_OUT", "docs/data"))
        return prices
    except Exception:
        return {}

def run_feed(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    os.environ.setdefault("SILMARIL_OUT", str(out))
    try:
        from .price_sources import fetch_metals_resilient, fetch_energy_resilient
        metals, m_meta = fetch_metals_resilient(out)
        energy, e_meta = fetch_energy_resilient(out)
    except Exception:
        metals, energy = fetch_metals(), fetch_energy()
        m_meta = e_meta = {}
    nm = _append(out, "metals_samples.json", metals)
    ne = _append(out, "energy_samples.json", energy)
    status = {"generated_at": _now_iso(), "metals_fetched": nm, "energy_fetched": ne,
              "metals": metals, "energy": energy,
              "metals_provenance": (m_meta or {}).get("provenance", {}),
              "energy_provenance": (e_meta or {}).get("provenance", {}),
              "budget_remaining": (m_meta or {}).get("budget_remaining", {}),
              "note": ("5.0 resilient sourcing: keyless yfinance/Stooq tried first every "
                       "cycle, so scarce keys are spared; OpenExchangeRates + Alpha Vantage "
                       "are budget-capped last resorts (see SOURCE_BUDGET.json). No synthetic "
                       "data — a symbol with no real quote holds its last sample.")}
    try: (out / "metals_energy_feed_status.json").write_text(json.dumps(status, indent=2))
    except Exception: pass
    return status

if __name__ == "__main__":
    import sys
    s = run_feed(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(f"metals fetched: {s['metals_fetched']} | energy fetched: {s['energy_fetched']}")
    print("(0 = no API key set; that is expected in the build sandbox)")
