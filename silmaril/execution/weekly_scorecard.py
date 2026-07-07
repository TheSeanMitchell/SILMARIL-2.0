"""
WEEKLY SCORECARD (P14) — one honest platform report per ISO week, appended (survives nothing —
derived; purged on wipe by design).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

def build_weekly_scorecard(out_dir):
    out = Path(out_dir)
    now = datetime.now(timezone.utc)
    wk = "%d-W%02d" % now.isocalendar()[:2]
    f = out / "WEEKLY_SCORECARD.json"
    try:
        led = json.loads(f.read_text())
    except Exception:
        led = []
    row = {"week": wk, "t": now.isoformat(), "books": {}}
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        try:
            trs = json.loads((out / f"paper_book_{bk}.json").read_text()).get("trades", [])
        except Exception:
            trs = []
        sells = [t for t in trs if t.get("side") == "SELL" and t.get("realized_pct") is not None]
        wins = [t for t in sells if t["realized_pct"] > 0]
        row["books"][bk] = {"closed": len(sells),
                             "win_pct": round(len(wins) / len(sells) * 100, 1) if sells else None,
                             "net_pct_sum": round(sum(t["realized_pct"] for t in sells), 2) if sells else 0.0}
    try:
        q = json.loads((out / "INTEGRITY_QUARANTINE.json").read_text())
        row["quarantined_symbols"] = len(q.get("quarantined_symbols", []))
    except Exception:
        row["quarantined_symbols"] = None
    if led and led[-1].get("week") == wk:
        led[-1] = row
    else:
        led.append(row)
    f.write_text(json.dumps(led[-120:], indent=1))
    return row
