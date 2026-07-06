"""
DAILY BASELINE (P11) — one snapshot per day of market anchors + system state, appended to
DAILY_BASELINE.json. SURVIVES WIPES. The long-run context ribbon every future analysis leans on.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ANCHORS = [("SPY", ["SPY"]), ("QQQ", ["QQQ"]), ("BTC", ["BTC-USD", "BTCUSD"]),
           ("ETH", ["ETH-USD", "ETHUSD"]), ("SOL", ["SOL-USD", "SOLUSD"]),
           ("GOLD", ["XAU", "XAUUSD", "GLD", "GC"]), ("SILVER", ["XAG", "XAGUSD", "SLV"]),
           ("OIL", ["USO", "CL"]), ("NATGAS", ["UNG", "NG"]), ("DOLLAR", ["UUP", "DXY"])]

def build_daily_baseline(out_dir):
    out = Path(out_dir)
    f = out / "DAILY_BASELINE.json"
    try:
        led = json.loads(f.read_text())
    except Exception:
        led = []
    today = datetime.now(timezone.utc).date().isoformat()
    if led and led[-1].get("date") == today:
        return led[-1]
    try:
        S = json.loads((out / "price_samples.json").read_text()).get("samples", {})
    except Exception:
        S = {}
    px = {}
    for name, cands in ANCHORS:
        px[name] = None
        for a in cands:
            rows = [(t, p) for t, p in S.get(a, []) if p and p > 0]
            if rows:
                px[name] = rows[-1][1]
                break
    try:
        rc = json.loads((out / "REGIME_CLASSIFIER.json").read_text()).get("by_book", {})
        regs = {b: (rc.get(b) or {}).get("regime") for b in ("crypto", "stock", "metal", "energy")}
    except Exception:
        regs = {}
    champs = {}
    for b in ("crypto", "stock", "metal", "energy"):
        try:
            champs[b] = json.loads((out / f"champion_{b}.json").read_text()).get("champion")
        except Exception:
            champs[b] = None
    entry = {"date": today, "t": datetime.now(timezone.utc).isoformat(), "anchors": px,
             "missing_anchors": [a for a, v in px.items() if v is None],
             "regimes": regs, "champions": champs}
    led.append(entry)
    f.write_text(json.dumps(led[-800:], indent=1))
    return entry
