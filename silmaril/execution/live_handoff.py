"""
LIVE HANDOFF — the output switch, made real and safe.

Every cycle this reads PARAM_CATALOG.json -> live_output {enabled, source} and emits
LIVE_ORDERS_PREVIEW.json: the EXACT orders that would go to a live broker this cycle from the chosen
source (master | all_quadrants | crypto | stock | metal | energy). While enabled=false (the shipped
default) nothing leaves the building — but the operator watches, for weeks, the precise order stream a
live account would receive, order types included (maker limit entries/targets, stop-market floor — the
fee-optimal Binance.US shape). Flipping to live later changes ZERO logic: same stream, real adapter.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

def _now(): return datetime.now(timezone.utc).isoformat()

def build_live_orders_preview(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    try:
        cat = json.loads((out / "PARAM_CATALOG.json").read_text())
    except Exception:
        cat = {}
    lo = cat.get("live_output") or {}
    source = str(lo.get("source", "master"))
    enabled = bool(lo.get("enabled", False))

    # which books feed the stream?
    books: List[str] = []
    if source == "all_quadrants":
        books = ["crypto", "stock", "metal", "energy"]
    elif source in ("crypto", "stock", "metal", "energy"):
        books = [source]
    else:  # master: only quadrants the Master ACCEPTED this cycle
        try:
            ma = json.loads((out / "MASTER_ACCOUNT.json").read_text())
            tail = (ma.get("decision_log_tail") or [])
            books = (tail[0].get("accepted") if tail else []) or []
        except Exception:
            books = []

    orders = []
    try:
        live = json.loads((out / "paper_sim_live.json").read_text())
    except Exception:
        live = {}
    for bk in books:
        B = live.get(bk) or {}
        for a in (B.get("actions") or []):
            if a.get("act") == "BUY":
                orders.append({"book": bk, "sym": a.get("sym"), "side": "BUY",
                               "order_type": "LIMIT (maker) at signal price",
                               "then": "LIMIT (maker) take-profit at target + STOP-MARKET at floor"})
        for p in (B.get("positions") or []):
            if p.get("target"):
                orders.append({"book": bk, "sym": p.get("sym"), "side": "MAINTAIN",
                               "order_type": "resting LIMIT take-profit %+.2f%% / STOP-MARKET %-.2f%%"
                                             % (p["target"] * 100, (p.get("stop") or 0) * 100)})
    payload = {"generated_at": _now(), "enabled": enabled, "source": source,
               "orders_this_cycle": len([o for o in orders if o["side"] == "BUY"]),
               "resting_orders": len([o for o in orders if o["side"] == "MAINTAIN"]),
               "orders": orders[:200],
               "what": ("The exact order stream a live account would receive from source='%s'. enabled=%s — "
                        "while false, this is a rehearsal ledger only; flipping it later changes no logic."
                        % (source, enabled))}
    try:
        from .atomic_io import write_json_atomic
        write_json_atomic(out / "LIVE_ORDERS_PREVIEW.json", payload)
    except Exception:
        (out / "LIVE_ORDERS_PREVIEW.json").write_text(json.dumps(payload, indent=1))
    return payload
