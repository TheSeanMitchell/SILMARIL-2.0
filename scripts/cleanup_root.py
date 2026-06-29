"""2.6.1/2.7 ROOT CLEANUP — declutter the repo root WITHOUT losing anything.
Moves the ~90 historical READ_ME/AUDIT/ROADMAP/NOTES markdown + old bootstrap files into attic/root_docs/
(reversible — nothing deleted). KEEPS the small set of files that should live at root. Does NOT touch any
.py code module (several legacy modules like kraken/alpaca are still imported by cli.py — deleting them
would break the cron; unwire them first in a later pass)."""
import shutil
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ATTIC = ROOT / "attic" / "root_docs"
KEEP = {
    "README.md", "FOUNDING_CHARTER.md", "ROADMAP_TO_BETA_1_0.md",
    "SILMARIL_BOOTSTRAP_2_7.md",            # the live forward bootstrap (add it to root)
    "requirements.txt", ".gitignore", "cli.py",
}
ATTIC.mkdir(parents=True, exist_ok=True)
moved = []
for p in ROOT.iterdir():
    if not p.is_file():
        continue
    if p.name in KEEP:
        continue
    if p.suffix.lower() in (".md", ".xml") or p.name.startswith("READ_ME") or p.name.startswith("README"):
        dest = ATTIC / p.name
        try:
            shutil.move(str(p), str(dest)); moved.append(p.name)
        except Exception as e:
            print("  skip", p.name, e)
print(f"archived {len(moved)} historical root docs -> attic/root_docs/ (reversible)")
for m in sorted(moved):
    print("  ->", m)
print("KEPT at root:", sorted(KEEP))
