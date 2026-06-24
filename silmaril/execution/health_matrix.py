"""
silmaril.execution.health_matrix — API / FEED HEALTH MATRIX (2.5.3). Observability.

Green/Yellow/Red status for every data feed, API key, and operational signal. A feed is
GREEN if its sample file updated recently, YELLOW if stale, RED if missing. Emits
HEALTH_MATRIX.json for the always-visible footer.
"""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from .atomic_io import write_json_atomic

def _now(): return datetime.now(timezone.utc).isoformat()

def _age_min(path: Path):
    try:
        d = json.loads(path.read_text())
        ts = d.get("updated") or d.get("updated_at") or d.get("generated_at")
        if not ts: return None
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - t.astimezone(timezone.utc)).total_seconds() / 60.0
    except Exception:
        return None

def _feed(out, name, fname, warn=30, stale=180):
    p = out / fname
    if not p.exists():
        return {"name": name, "status": "RED", "detail": "no file yet"}
    age = _age_min(p)
    if age is None:
        return {"name": name, "status": "YELLOW", "detail": "no timestamp"}
    s = "GREEN" if age <= warn else ("YELLOW" if age <= stale else "RED")
    return {"name": name, "status": s, "detail": f"{age:.0f}m ago"}

def build_health_matrix(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    feeds = [
        _feed(out, "Crypto prices (CCXT)", "ccxt_samples.json"),
        _feed(out, "Price samples", "price_samples.json"),
        _feed(out, "Metals feed", "metals_samples.json", warn=1440, stale=2880),
        _feed(out, "Energy feed", "energy_samples.json", warn=2880, stale=5760),
        _feed(out, "Paper sim cycle", "paper_sim_live.json", warn=30, stale=120),
        _feed(out, "Authority/news", "authority_events.json", warn=720, stale=2880),
    ]
    keys = {"ALPHA_VANTAGE_API_KEY": "Energy data", "OPENEXCHANGERATES_APP_ID": "Metals data",
            "FINNHUB_API_KEY": "Stock data", "FMP_API_KEY": "Fundamentals",
            "ALPACA_API_KEY": "Broker (paper)"}
    key_status = [{"name": v, "env": k,
                   "status": "GREEN" if os.environ.get(k) else "GRAY",
                   "detail": "configured" if os.environ.get(k) else "not set in this env"}
                  for k, v in keys.items()]
    # data footprint
    try:
        total = sum(p.stat().st_size for p in out.glob("*.json")) / 1024 / 1024
    except Exception:
        total = None
    reds = sum(1 for f in feeds if f["status"] == "RED")
    yellows = sum(1 for f in feeds if f["status"] == "YELLOW")
    overall = "RED" if reds else ("YELLOW" if yellows else "GREEN")
    payload = {"generated_at": _now(), "overall": overall,
               "feeds": feeds, "api_keys": key_status,
               "data_dir_mb": round(total, 1) if total else None,
               "summary": f"{overall} · {len([f for f in feeds if f['status']=='GREEN'])}/{len(feeds)} feeds green",
               "note": ("API-key status reflects THIS environment. In GitHub Actions the keys are "
                        "set as secrets; locally they show GRAY. Metals/energy 'RED' until their feed "
                        "writes its first samples.")}
    try: write_json_atomic(out / "HEALTH_MATRIX.json", payload)
    except Exception: pass
    return payload
