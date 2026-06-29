"""2.6.1 cleanup: remove ONLY standalone obsolete files. Does NOT touch modules imported by cli.py
(kraken_mirror/kraken_spread/alpaca_paper are still wired — deleting them would break the cron; fully
unwiring kraken/alpaca is a careful cli.py edit for next session). Defensive: skips missing files."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SAFE_REMOVE = [
    "scripts/reset_alpaca_grocery_to_truth.py",
    ".github/workflows/reset_alpaca_grocery_to_truth.yml",
    ".github/workflows/diagnose_alpaca.yml",
    ".github/workflows/wipe_for_alpha_2_1.yml",
]
removed = []
for rel in SAFE_REMOVE:
    p = ROOT / rel
    if p.exists():
        p.unlink(); removed.append(rel)
print(f"removed {len(removed)} obsolete files:")
for r in removed: print("  -", r)
print("done. (kraken/alpaca code modules left intact — they're imported by cli.py; unwire them safely next session.)")
