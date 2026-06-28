"""
scripts/reset_internal_clean.py — clean-wipe the INTERNAL paper books, PRESERVING graph/fingerprint data.

The corruption is stopped by the freshness FIX in paper_sim.py, not by deleting price history. So this
reset clears only the polluted TRADE RECORDS and restarts equity clean — it PRESERVES price_samples
(every asset's graph + fingerprint history), favicon caches, and all per-asset visual data, so nothing
on the dashboard goes blank. Crypto graphs also keep refilling automatically from the ccxt 300-candle
pull each run.

Wiped:    every internal + arena paper book -> $10k clean · MASTER_ACCOUNT.json (fresh inception)
          · snapshot_history.jsonl (equity curve restarts clean with the books)
PRESERVED: price_samples.json (graphs/fingerprints), favicons, all per-asset visual + fingerprint data.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "docs" / "data"
BASELINE = 10000.0
CLEAN_BOOK = {"cash": BASELINE, "positions": {}, "realized_pnl": 0.0, "trades": []}

def main():
    n = 0
    for p in list(DATA.glob("paper_book_*.json")):
        p.write_text(json.dumps(CLEAN_BOOK, indent=2)); n += 1
    print(f"  reset {n} paper books -> ${BASELINE:.0f} clean")
    ma = DATA / "MASTER_ACCOUNT.json"
    if ma.exists():
        ma.unlink(); print("  deleted MASTER_ACCOUNT.json (fresh $10k inception)")
    sh = DATA / "snapshot_history.jsonl"
    if sh.exists():
        sh.write_text(""); print("  cleared snapshot_history.jsonl (equity restarts clean)")
    # PRESERVED on purpose: price_samples.json (graphs + fingerprints), favicon caches, per-asset data.
    print("  PRESERVED: price_samples.json (graphs/fingerprints) + favicons — dashboard will NOT go blank")
    print("CLEAN. Books pristine at $10k; all graph/fingerprint/favicon history intact.")

if __name__ == "__main__":
    main()
