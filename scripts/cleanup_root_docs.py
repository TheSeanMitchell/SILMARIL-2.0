"""
scripts/cleanup_root_docs.py — one-shot root declutter. ARCHIVES (never deletes) stale
per-version READMEs and old notes into archive/docs/ so the repo root is clean. Run once:
    python scripts/cleanup_root_docs.py            (dry run — shows what would move)
    python scripts/cleanup_root_docs.py --apply    (actually move them)
"""
from __future__ import annotations
import argparse, shutil
from pathlib import Path

ROOT = Path(".")
ARCHIVE = ROOT / "archive" / "docs"
# Keep these in root — current and foundational:
KEEP = {"README.md", "FOUNDING_CHARTER.md", "MASTER_AUDIT_2_5_3.md",
        "READ_ME_health_and_fallbacks.md"}

def main(apply: bool):
    docs = sorted([p for p in ROOT.glob("*.md")] + [p for p in ROOT.glob("*.txt")])
    stale = [p for p in docs if p.name not in KEEP]
    print(f"Root docs: {len(docs)} · keeping {len(docs)-len(stale)} · archiving {len(stale)}")
    if not stale:
        print("Nothing to archive."); return
    if apply:
        ARCHIVE.mkdir(parents=True, exist_ok=True)
    for p in stale:
        print(("  move " if apply else "  would move ") + p.name + " -> archive/docs/")
        if apply:
            dest = ARCHIVE / p.name
            if dest.exists(): dest = ARCHIVE / (p.stem + "_dup" + p.suffix)
            shutil.move(str(p), str(dest))
    print("\nKept in root:", ", ".join(sorted(KEEP)))
    if not apply:
        print("\nDRY RUN — re-run with --apply to move them. (Archived, not deleted; recoverable.)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    main(ap.parse_args().apply)
