"""Data diet — repo runs forever without ballooning. Trims per-symbol INTRADAY history to last N points
(DAILIES NEVER TOUCHED — long-term memory for the stock law + HOLD backtests), caps append ledgers.
snapshot_history.jsonl is sacred (the 90-day Binance proof) and is never pruned. Runs in deep-analytics."""
import json, os
from pathlib import Path
DATA = Path(__file__).resolve().parent.parent / "docs" / "data"

def main():
    try:
        cat = json.loads((DATA / "PARAM_CATALOG.json").read_text()).get("prune") or {}
    except Exception:
        cat = {}
    keep = int(cat.get("intraday_keep_per_symbol", 2000))
    cap = int(cat.get("ledger_cap", 3000))
    ps = DATA / "price_samples.json"
    if ps.exists():
        d = json.loads(ps.read_text()); S = d.get("samples", {})
        before = sum(len(v) for v in S.values())
        for sym, rows in S.items():
            dailies = [r for r in rows if "T00:00:00" in r[0]]
            intra = [r for r in rows if "T00:00:00" not in r[0]][-keep:]
            S[sym] = sorted(dailies + intra, key=lambda r: r[0])
        tmp = ps.with_suffix(".tmp"); tmp.write_text(json.dumps(d)); os.replace(tmp, ps)
        print("price_samples: %d -> %d points (dailies untouched)" % (before, sum(len(v) for v in S.values())))
    for name in ("REGIME_AB.json", "NEWS_TRIAL.json", "MASTER_DECISIONS.json"):
        f = DATA / name
        try:
            led = json.loads(f.read_text())
            if isinstance(led, list) and len(led) > cap:
                f.write_text(json.dumps(led[-cap:], indent=1)); print(name, "capped", cap)
        except Exception:
            pass

if __name__ == "__main__":
    main()
