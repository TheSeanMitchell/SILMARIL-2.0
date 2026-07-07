"""
AGGRESSION LADDER (P12) — what would 10/20/30/40/50% deployment have done on the SAME realized
trade sequence? Compounds the book's actual closed trades at each fraction. Report-only; feeds the
future sizing hypothesis with real forward evidence. Honest "insufficient" below 10 closed trades.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

def build_aggression_ladder(out_dir):
    out = Path(out_dir)
    try:
        fr = json.loads((out / "PARAM_CATALOG.json").read_text()).get("ladder_fracs") or \
             [0.10, 0.20, 0.30, 0.40, 0.50]
    except Exception:
        fr = [0.10, 0.20, 0.30, 0.40, 0.50]
    res = {}
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        try:
            trs = [t["realized_pct"] / 100.0 for t in
                   json.loads((out / f"paper_book_{bk}.json").read_text()).get("trades", [])
                   if t.get("side") == "SELL" and t.get("realized_pct") is not None]
        except Exception:
            trs = []
        if len(trs) < 10:
            res[bk] = {"n": len(trs), "status": "insufficient — needs ≥10 closed trades"}
            continue
        rows = []
        for f_ in fr:
            eq, peak, mdd = 1.0, 1.0, 0.0
            for r in trs:
                eq *= (1 + f_ * r)
                peak = max(peak, eq)
                mdd = max(mdd, 1 - eq / peak)
            rows.append({"deploy_frac": f_, "total_pct": round((eq - 1) * 100, 2),
                         "max_dd_pct": round(mdd * 100, 2)})
        res[bk] = {"n": len(trs), "ladder": rows}
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "books": res,
               "what": "Same realized trades, five deployment fractions — the sizing evidence ladder (report-only)."}
    (out / "AGGRESSION_LADDER.json").write_text(json.dumps(payload, indent=1))
    return payload
