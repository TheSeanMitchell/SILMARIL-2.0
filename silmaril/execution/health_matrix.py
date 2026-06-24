"""
silmaril.execution.health_matrix — UNIFIED HEALTH MATRIX (2.5.3). Observability.

Reads the project's authoritative api_health.json (freshness, prices, news, broker,
cron pressure, storage, domain clocks) and MERGES in API-key presence + the metals/
energy feeds + a green/yellow/red light per data source. One panel, every feed, every
key. Emits HEALTH_MATRIX.json. Reading the real source means lights are ACCURATE — no
more false RED from looking at the wrong filename.
"""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from .atomic_io import write_json_atomic

def _now(): return datetime.now(timezone.utc).isoformat()
def _load(out, n):
    try: return json.loads((out / n).read_text())
    except Exception: return {}

def _age_min(path: Path):
    """Robust freshness: try common timestamp fields, else fall back to file mtime."""
    try:
        d = json.loads(path.read_text())
        ts = (d.get("updated") or d.get("updated_at") or d.get("generated_at")
              or d.get("last_recorded") or d.get("last_updated"))
        if ts:
            t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - t.astimezone(timezone.utc)).total_seconds() / 60.0
    except Exception:
        pass
    try:
        return (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) / 60.0
    except Exception:
        return None

def _light(age, warn, stale):
    if age is None: return "YELLOW"
    return "GREEN" if age <= warn else ("YELLOW" if age <= stale else "RED")

def build_health_matrix(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    ah = _load(out, "api_health.json")     # authoritative, correct source

    feeds = []
    # crypto/stock prices — read from api_health (coverage) + the real price file
    prices = ah.get("prices", {})
    cov = prices.get("coverage_pct")
    page = _age_min(out / "price_samples.json")
    feeds.append({"name": "Prices (crypto+stock)", "status": _light(page, 30, 180),
                  "detail": (f"{cov:.0f}% coverage · {page:.0f}m ago" if cov is not None and page is not None
                             else f"{page:.0f}m ago" if page is not None else "—")})
    # news
    news = ah.get("news", {})
    ns = news.get("distinct_sources"); na = news.get("articles_in_cycle")
    feeds.append({"name": "News / Authority", "status": "GREEN" if ns else "YELLOW",
                  "detail": f"{ns} sources · {na} articles" if ns else "no sources this cycle"})
    # metals / energy
    for label, fname, warn, stale in (("Metals feed", "metals_samples.json", 1440, 2880),
                                       ("Energy feed", "energy_samples.json", 2880, 5760)):
        a = _age_min(out / fname)
        feeds.append({"name": label,
                      "status": "RED" if not (out / fname).exists() else _light(a, warn, stale),
                      "detail": "no file yet" if not (out / fname).exists() else (f"{a:.0f}m ago" if a is not None else "—")})
    # paper sim cycle
    pa = _age_min(out / "paper_sim_live.json")
    feeds.append({"name": "Paper sim cycle", "status": _light(pa, 30, 120),
                  "detail": f"{pa:.0f}m ago" if pa is not None else "—"})
    # broker
    broker = ah.get("broker", {})
    for acct, b in broker.items():
        if not isinstance(b, dict): continue
        errs = b.get("errors_recent_48h", 0) or 0
        st = "GREEN" if (b.get("configured") and errs < 5) else ("YELLOW" if b.get("configured") else "RED")
        feeds.append({"name": f"Broker {acct}", "status": st,
                      "detail": (f"eq ${b.get('equity',0):.0f}" + (f" · {errs} errs/48h" if errs else " · ok"))})

    # API keys (env): GREEN if set, GRAY if not. Names match the project's actual
    # GitHub secrets so configured providers read correctly (no false GRAY).
    KEY_GROUPS = {
        "Crypto price": ["COINGECKO_API_KEY", "FREECRYPTOAPI_API_KEY", "BIRDEYE_API_KEY"],
        "Stock price": ["FINNHUB_API_KEY", "ALPHA_VANTAGE_API_KEY", "TWELVEDATA_API_KEY", "FMP_API_KEY", "POLYGON_API_KEY", "TIINGO_API_KEY"],
        "News": ["NEWSAPI_KEY", "MARKETAUX_API_KEY", "FINNHUB_API_KEY"],
        "Metals": ["OPENEXCHANGERATES_APP_ID"],
        "Energy": ["ALPHA_VANTAGE_API_KEY", "EIA_API_KEY", "TWELVEDATA_API_KEY"],
        "Macro/Fundamentals": ["FMP_API_KEY", "FRED_API_KEY", "SEC_USER_AGENT_EMAIL"],
        "Broker (Alpaca)": ["ALPACA_API_KEY", "ALPACA_API_KEY_H3", "ALPACA_API_KEY_H5"],
    }
    key_groups = []
    for need, keys in KEY_GROUPS.items():
        present = [k for k in keys if os.environ.get(k)]
        # metals has a single provider by nature; treat 1 as OK there
        ok_floor = 1 if need == "Metals" else 2
        st = "GREEN" if len(present) >= ok_floor else ("YELLOW" if len(present) == 1 else "GRAY")
        key_groups.append({"need": need, "providers_total": len(keys),
                           "providers_active": len(present), "status": st,
                           "active": present, "all": keys,
                           "fallback_depth": len(present)})

    reds = sum(1 for f in feeds if f["status"] == "RED")
    yellows = sum(1 for f in feeds if f["status"] == "YELLOW")
    overall = "RED" if reds else ("YELLOW" if yellows else "GREEN")
    payload = {
        "generated_at": _now(), "overall": overall,
        "feeds": feeds, "key_groups": key_groups,
        "freshness": ah.get("freshness", {}),
        "prices": prices, "news": news,
        "cron_pressure": ah.get("cron_pressure", {}),
        "storage": ah.get("storage", {}),
        "domain_clocks": ah.get("domain_clocks", {}),
        "summary": f"{overall} · {sum(1 for f in feeds if f['status']=='GREEN')}/{len(feeds)} feeds green · {ah.get('freshness',{}).get('ok','?')}/{ah.get('freshness',{}).get('total','?')} files fresh",
        "note": ("Lights read the real api_health.json. API-key groups show fallback depth: "
                 "GREEN = 2+ providers configured (a fallback exists), YELLOW = 1 (no fallback), "
                 "GRAY = none. Goal: every group GREEN so no single provider outage can dark a feed."),
    }
    try: write_json_atomic(out / "HEALTH_MATRIX.json", payload)
    except Exception: pass
    return payload
