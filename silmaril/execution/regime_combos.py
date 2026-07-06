"""
REGIME INTERACTION LEDGER (Phase 23 foundation) — the pulse of capital between quadrants.
Every hour, append the 4-book regime tuple + relative-strength ranks (24h slope) to
REGIME_COMBOS.jsonl. SURVIVES WIPES (market context, like price history). This is the raw evidence
the Cross-Market Rotation Engine will learn from — collect the push-and-pull NOW so the interplay
hypotheses have months of forward data behind them the day they wake.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

def build_regime_combos(out_dir):
    out = Path(out_dir)
    try:
        rc = json.loads((out / "REGIME_CLASSIFIER.json").read_text()).get("by_book", {})
    except Exception:
        return None
    row = {"t": datetime.now(timezone.utc).isoformat()}
    slopes = {}
    for bk in ("crypto", "stock", "metal", "energy"):
        v = rc.get(bk) or {}
        row[bk] = v.get("regime")
        row[bk + "_24h"] = v.get("slope_24h_pct")
        slopes[bk] = v.get("slope_24h_pct") if v.get("slope_24h_pct") is not None else -999
    if all(row[b] in (None, "NO DATA") for b in ("crypto", "stock", "metal", "energy")):
        return None   # feed outage / warmup — a dead row teaches nothing
    order = sorted(slopes, key=lambda b: -slopes[b])
    row["rs_rank"] = order                       # relative-strength order, leader first
    row["combo"] = "|".join(str(row[b] or "?")[0] for b in ("crypto", "stock", "metal", "energy"))
    f = out / "REGIME_COMBOS.jsonl"
    last = ""
    try:
        last = f.read_text().strip().splitlines()[-1]
    except Exception:
        pass
    if last:
        try:
            lt = json.loads(last).get("t", "")
            if lt[:13] == row["t"][:13]:          # dedupe: one row per hour
                return row
        except Exception:
            pass
    with f.open("a") as fh:
        fh.write(json.dumps(row) + "\n")
    return row
