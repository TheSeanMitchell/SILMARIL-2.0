"""Canonical key normalizer — run EVERY cycle so crypto graphs never break again.
Merges any BASEUSD / BASEUSDT / BASE/USD / BASE-USDT crypto key onto the canonical BASE-USD key the
dashboard reads, preserving all points. Stocks (plain tickers) are untouched. Idempotent + safe."""
import json
from pathlib import Path
PS = Path(__file__).resolve().parents[1] / "docs" / "data" / "price_samples.json"

def canon(k):
    if "-USD" in k and k.endswith("-USD"): return None          # already canonical
    if k.endswith("-USDT"): return k[:-5] + "-USD"
    if "/" in k: return k.split("/")[0] + "-USD"
    if k.endswith("USDT"): return k[:-4] + "-USD"
    if k.endswith("USD") and len(k) > 4: return k[:-3] + "-USD"
    return None                                                  # plain stock ticker

def main():
    d = json.loads(PS.read_text()); s = d.get("samples", {})
    merged = 0
    for k in list(s.keys()):
        tgt = canon(k)
        if not tgt or tgt == k: continue
        m = {t: p for t, p in s.get(tgt, [])}
        for t, p in s[k]: m.setdefault(t, p)
        if len(m) > len(s.get(tgt, [])):
            s[tgt] = sorted([[t, p] for t, p in m.items()]); merged += 1
    d["samples"] = s; PS.write_text(json.dumps(d))
    filled = sum(1 for k, v in s.items() if k.endswith("-USD") and len(v) > 100)
    print(f"canonicalized {merged} keys -> BASE-USD · {filled} crypto graphs hold full history")

if __name__ == "__main__":
    main()
