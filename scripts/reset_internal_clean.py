"""
scripts/reset_internal_clean.py — clean-wipe the INTERNAL paper sim after the freshness fix.

This is the reset to run AFTER installing the weekend/stale-price fix. It wipes exactly the things
the corruption touched and nothing it didn't:
  - every internal paper book (crypto/stock/metal/energy) + all challenger arena books -> $10k clean
  - price_samples.json -> emptied (the polluted stale-price history that fed the fake trades)
  - MASTER_ACCOUNT.json -> deleted so the Master restarts fresh at $10k from the next run
  - snapshot_history.jsonl -> emptied (recorded polluted equity)
It does NOT touch code, champions config, or strategy params. After this, Monday starts genuinely clean.

Run:  python scripts/reset_internal_clean.py
"""
import json, glob
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "docs" / "data"
BASELINE = 10000.0
CLEAN_BOOK = {"cash": BASELINE, "positions": {}, "realized_pnl": 0.0, "trades": []}

def main():
    n = 0
    # 1) all internal + arena books
    for p in list(DATA.glob("paper_book_*.json")):
        p.write_text(json.dumps(CLEAN_BOOK, indent=2)); n += 1
    print(f"  reset {n} paper books -> ${BASELINE:.0f} clean")
    # 2) price samples (the polluted feed)
    ps = DATA / "price_samples.json"
    if ps.exists():
        ps.write_text(json.dumps({"samples": {}}, indent=2)); print("  cleared price_samples.json")
    # 3) master account -> fresh inception next run
    ma = DATA / "MASTER_ACCOUNT.json"
    if ma.exists():
        ma.unlink(); print("  deleted MASTER_ACCOUNT.json (fresh $10k inception)")
    # 4) snapshot history (polluted equity record)
    sh = DATA / "snapshot_history.jsonl"
    if sh.exists():
        sh.write_text(""); print("  cleared snapshot_history.jsonl")
    print("CLEAN. Next run starts from a pristine $10k across all books.")

if __name__ == "__main__":
    main()
