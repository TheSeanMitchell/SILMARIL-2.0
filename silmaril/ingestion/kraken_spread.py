"""
silmaril.ingestion.kraken_spread — REAL bid/ask/spread from Kraken's PUBLIC API (2.5.5).

This is the missing data. SILMARIL's price_samples are mid-price only, which blocked a real
Reality Audit. Kraken's PUBLIC REST API needs NO keys, NO account, and returns live best bid/ask
and order-book depth — so we can capture REAL spread (and later real slippage estimates) for the
symbols we trade, and finally audit execution reality without inventing a single number.

Runs on the GitHub Actions runner (which can reach the internet); the build sandbox cannot reach
api.kraken.com, so this ships UNTESTED-FROM-HERE and must be verified on a real Actions run. It is
fully defensive: any failure leaves an empty/partial file and never breaks the cycle. Uses only the
stdlib (urllib) — zero new dependencies. Emits KRAKEN_SPREAD.json.
"""
from __future__ import annotations
import json, urllib.request, urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
try:
    from .._util_atomic import write_json_atomic  # type: ignore
except Exception:
    try:
        from ..execution.atomic_io import write_json_atomic
    except Exception:
        def write_json_atomic(p, obj):  # last-resort fallback
            Path(p).write_text(json.dumps(obj, indent=2))

KRAKEN = "https://api.kraken.com/0/public"
TIMEOUT = 12

def _get(path: str, params: dict | None = None) -> dict:
    url = f"{KRAKEN}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "silmaril-research/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode())

def _asset_pairs() -> Dict[str, str]:
    """Map 'BTC-USD' style -> Kraken pair key, using each pair's wsname (e.g. 'BTC/USD')."""
    out: Dict[str, str] = {}
    try:
        data = _get("AssetPairs").get("result", {}) or {}
    except Exception:
        return out
    for key, info in data.items():
        ws = info.get("wsname")          # e.g. "BTC/USD"
        if ws and ws.endswith("/USD"):
            out[ws.replace("/", "-")] = key   # "BTC-USD" -> kraken key
    return out

def build_kraken_spread(out_dir, symbols: List[str] | None = None) -> Dict[str, Any]:
    out = Path(out_dir)
    # which symbols do we care about? prefer the ones we actually trade (from price_samples)
    if symbols is None:
        try:
            ps = json.loads((out / "price_samples.json").read_text()).get("samples", {})
            symbols = [s for s in ps if s.endswith("-USD")]
        except Exception:
            symbols = []
    pair_map = _asset_pairs()
    wanted = {s: pair_map[s] for s in symbols if s in pair_map}
    rows: Dict[str, Any] = {}
    # Kraken Ticker accepts a comma list of pair keys; batch to stay polite
    keys = list(wanted.values())
    inv = {v: k for k, v in wanted.items()}
    for i in range(0, len(keys), 20):
        batch = keys[i:i + 20]
        try:
            res = _get("Ticker", {"pair": ",".join(batch)}).get("result", {}) or {}
        except Exception:
            continue
        for kkey, t in res.items():
            sym = inv.get(kkey) or inv.get(kkey.lstrip("X").replace("ZUSD", "USD"))
            try:
                ask = float(t["a"][0]); bid = float(t["b"][0]); last = float(t["c"][0])
            except Exception:
                continue
            mid = (ask + bid) / 2 if (ask and bid) else last
            spread_bps = round((ask - bid) / mid * 10000, 2) if mid else None
            rows[sym or kkey] = {"bid": bid, "ask": ask, "last": last,
                                 "spread_bps": spread_bps}
    spreads = [r["spread_bps"] for r in rows.values() if r.get("spread_bps") is not None]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status_label": "ACTIVE DECISION INPUT once wired to Reality Audit — currently OBSERVATIONAL.",
        "source": "Kraken public REST API (no keys, no account)",
        "symbols_quoted": len(rows),
        "median_spread_bps": round(sorted(spreads)[len(spreads) // 2], 2) if spreads else None,
        "by_symbol": rows,
        "what": "Real live best bid/ask and spread for our symbols, straight from Kraken.",
        "why": ("price_samples is mid-only; this is the REAL spread we lacked, enabling a Reality "
                "Audit with measured (not invented) execution costs."),
        "honest_note": ("Built to run on the GitHub Actions runner; the dev sandbox can't reach "
                        "api.kraken.com so this is unverified-from-here — confirm on a real run. "
                        "Defensive: partial/empty on any failure, never blocks the cycle. No keys needed."),
    }
    try: write_json_atomic(out / "KRAKEN_SPREAD.json", payload)
    except Exception: pass
    return payload
