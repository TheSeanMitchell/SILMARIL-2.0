#!/usr/bin/env python3
"""cleanup_5_1_docs — attic every pre-5.1 root explanation doc (confirm-gated).
Additive philosophy: nothing is deleted; files move to attic/docs_pre_5_1/ via git mv.
Run only through its workflow with confirm=ATTIC.
"""
import subprocess, sys
from pathlib import Path

LEGACY = [
    "ARENA_ROTATION_FIX.txt", "AUDIT_2026_07_07_INSTALLER.md", "AUDIT_2026_07_10_FINAL.md",
    "COMPLETION_LEDGER.md", "DELETE_THESE_LEGACY_FILES.txt", "FOUNDING_CHARTER.md",
    "FULL_STRATEGY_POPULATION_FIX.txt", "INSTALL_5_0.md", "INSTALL_5_0_FINAL.md",
    "INSTALL_FX_QUOTA_FIX.md", "INSTALL_RESCUE.md", "INSTALL_fingerprint_strategy.md",
    "INSTALL_participation_and_invariants.md", "INSTALL_sell_fix_and_stock_unblock.md",
    "NOTES_APPLIED_2026_07_10.md", "OPS_RUNBOOK.txt", "ROADMAP_TO_BETA_1_0.md",
    "SILMARIL_3_0_MASTER_DIRECTIVE.md", "SILMARIL_4.0_FINAL_DIRECTIVE.md",
    "SILMARIL_5_0_BACKBONE.md", "SILMARIL_5_0_SCALE_GUIDE.md", "SILMARIL_BOOTSTRAP_2_7.md",
    "SILMARIL_BOOTSTRAP_2_HARDENING_AND_CLEANUP.md", "Silmaril_4_0_Notes.txt",
]

def main():
    if "ATTIC" not in sys.argv:
        print("refusing: pass ATTIC to confirm"); return 1
    dest = Path("attic/docs_pre_5_1"); dest.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in LEGACY:
        p = Path(f)
        if p.exists():
            subprocess.run(["git", "mv", f, str(dest / f)], check=False)
            moved += 1
    print(f"attic'd {moved}/{len(LEGACY)} legacy docs → {dest}/ (history preserved)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
