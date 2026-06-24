#!/usr/bin/env python3
"""
cleanup_workflows.py — archive stale / one-off GitHub workflow files.

GitHub Actions only runs YAML in .github/workflows/. Over time this repo accumulated ~22
workflows, most of them one-shot migrations and resets that should NOT be schedulable clutter.
This moves everything EXCEPT the active set into .github/workflows_archive/ (preserved, not
deleted — additive). Re-running is safe (idempotent).

USAGE (from repo root, via GitHub web UI you can't run this — run locally or in an Actions step):
    python scripts/cleanup_workflows.py            # archive stale workflows
    python scripts/cleanup_workflows.py --dry-run  # show what WOULD move, change nothing
    python scripts/cleanup_workflows.py --restore   # move everything back from archive
"""
import sys, shutil
from pathlib import Path

# The ONLY workflows that should stay schedulable. Everything else gets archived.
KEEP = {
    "daily.yml",                 # the one scheduled trading cadence
    "compact_history.yml",       # repo storage hygiene
    "backfill_history.yml",      # jumpstart price history
    "pristine_reset.yml",        # one-step clean reset
    "weekly_backup.yml",         # periodic backup
}

def main():
    dry = "--dry-run" in sys.argv
    restore = "--restore" in sys.argv
    wf = Path(".github/workflows")
    arc = Path(".github/workflows_archive")
    if not wf.exists():
        print("no .github/workflows directory — run from repo root"); return 1

    if restore:
        if not arc.exists():
            print("nothing to restore"); return 0
        for f in arc.glob("*.yml"):
            print(f"restore {f.name}")
            if not dry: shutil.move(str(f), str(wf / f.name))
        return 0

    arc.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in sorted(wf.glob("*.yml")):
        if f.name in KEEP or f.name.endswith(".bak"):
            continue
        print(f"archive {f.name}  ->  workflows_archive/")
        if not dry:
            shutil.move(str(f), str(arc / f.name))
        moved += 1
    kept = [f.name for f in sorted(wf.glob('*.yml')) if f.name in KEEP]
    print(f"\n{'DRY RUN — ' if dry else ''}archived {moved} workflow(s). Kept active: {', '.join(kept)}")
    print("Archived files are preserved in .github/workflows_archive/ and will NOT run.")
    print("Commit the change for it to take effect on GitHub.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
