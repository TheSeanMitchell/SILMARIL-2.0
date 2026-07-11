"""health_lights.py — 5.1: keep the Project-Health lights honest from the KEYED lanes.

Root cause fixed here: the dashboard's "DATA-SOURCE FALLBACK DEPTH" reads
api_health.json `key_groups`, which (a) the api-health-1.3 writer never emitted
and (b) was produced only in the analytics lane — the one lane that carries NO
API-key env. Result: permanent "0/N sources" zeros under green feeds.

This module runs in the every-cycle spine (daily/hourly lanes, which DO carry
the keys), computes provider depth per group from the environment, and MERGES
it into api_health.json without disturbing whatever the analytics suite wrote.
No network calls; configured = the key exists in env (keyless providers count
as always-configured).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .atomic_io import write_json_atomic

# group → list of (provider_name, env_var_or_None_for_keyless)
GROUPS: List[tuple] = [
    ("Crypto price", [("coingecko", None), ("freecryptoapi", "FREECRYPTOAPI_KEY"), ("ccxt/binanceus", None)]),
    ("Stock price", [("yfinance", None), ("alpaca", "ALPACA_API_KEY"), ("finnhub", "FINNHUB_KEY"),
                     ("alpha_vantage", "ALPHA_VANTAGE_KEY"), ("fmp", "FMP_KEY"), ("twelve_data", "TWELVE_DATA_KEY")]),
    ("News", [("marketaux", "MARKETAUX_KEY"), ("newsapi", "NEWSAPI_KEY"), ("google_rss", None)]),
    ("Metals", [("yfinance", None), ("openexchangerates", "OXR_APP_ID"), ("alpha_vantage", "ALPHA_VANTAGE_KEY")]),
    ("Energy", [("yfinance", None), ("alpha_vantage", "ALPHA_VANTAGE_KEY"), ("tiingo", "TIINGO_KEY")]),
    ("Macro/Fundamentals", [("fred", "FRED_KEY"), ("edgar", None), ("yfinance", None)]),
    ("Broker (pricing-only)", [("alpaca", "ALPACA_API_KEY"), ("alpaca_secret", "ALPACA_SECRET_KEY"), ("paper_feed", None)]),
]


def _depth(providers) -> Dict[str, Any]:
    active = []
    for name, env in providers:
        if env is None or os.environ.get(env):
            active.append(name)
    total = len(providers)
    n = len(active)
    status = "GREEN" if n >= 2 else ("YELLOW" if n == 1 else "GRAY")
    return {"providers_active": n, "providers_total": total, "status": status,
            "all": active}


def build_health_lights(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    path = out / "api_health.json"
    try:
        d = json.loads(path.read_text())
        if not isinstance(d, dict):
            d = {}
    except Exception:
        d = {}
    kg = []
    for need, providers in GROUPS:
        row = _depth(providers)
        row["need"] = need
        kg.append(row)
    d["key_groups"] = kg
    d["key_groups_note"] = ("computed each cycle in the keyed lanes (daily/hourly); "
                            "configured = key present in env, keyless providers always count")
    d["generated_at"] = datetime.now(timezone.utc).isoformat()
    d.setdefault("version", "api-health-1.3")
    write_json_atomic(path, d)
    greens = sum(1 for k in kg if k["status"] == "GREEN")
    return {"summary": f"key-groups: {greens}/{len(kg)} at 2+ providers"}
