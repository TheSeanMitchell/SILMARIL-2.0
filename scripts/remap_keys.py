"""2.6.1 — remap backfilled crypto history onto the keys the dashboard reads.
The year of daily data sits under BASEUSD / BASEUSDT; the graphs read BASE-USD. This merges the
history onto BASE-USD (keeping live intraday points too) so every crypto graph shows its full year.
Real data already in the file — no fetching, nothing synthetic."""
import json
from pathlib import Path
PS = Path(__file__).resolve().parents[1] / "docs" / "data" / "price_samples.json"

def base_usd(k):
    if k.endswith("USDT") and "-" not in k: return k[:-4] + "-USD"
    if k.endswith("USD") and "-" not in k and len(k) > 4: return k[:-3] + "-USD"
    return None

def main():
    d = json.loads(PS.read_text()); s = d.get("samples", {})
    merged = 0
    for k in list(s.keys()):
        tgt = base_usd(k)
        if not tgt or tgt == k: continue
        m = {t: p for t, p in s.get(tgt, [])}
        for t, p in s[k]: m.setdefault(t, p)
        if len(m) > len(s.get(tgt, [])):
            s[tgt] = sorted([[t, p] for t, p in m.items()]); merged += 1
    d["samples"] = s; PS.write_text(json.dumps(d))
    filled = sum(1 for k, v in s.items() if k.endswith("-USD") and len(v) > 100)
    print(f"remapped {merged} crypto keys -> BASE-USD · {filled} crypto graphs now have 100+ pts (year)")

if __name__ == "__main__":
    main()
