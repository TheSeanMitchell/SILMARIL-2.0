"""2.6.1 cleanup: remove obsolete workflow files + root clutter. Keeps the essential workflows.
Does NOT delete code modules imported by cli.py."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
KEEP_WF = {"daily.yml","backfill_universe.yml","cleanup_clutter.yml","reset_internal_clean.yml",
           "compact_history.yml","weekly_backup.yml"}
OBSOLETE_WF = ["backfill_history.yml","backtest.yml","correlation_check.yml","diagnose.yml",
    "diagnose_alpaca.yml","full_reset.yml","heal_starting_balance.yml","migrate_alpha_3_0.yml",
    "pristine_reset.yml","reflection.yml","reset.yml","reset_10k.yml","reset_alpaca_grocery_to_truth.yml",
    "risk_unfreeze.yml","senate.yml","stress_test.yml","sweep_switch.yml","train_from_backtest.yml",
    "wipe_for_alpha_2_1.yml"]
removed = []
wf = ROOT / ".github" / "workflows"
for name in OBSOLETE_WF:
    p = wf / name
    if p.exists() and name not in KEEP_WF:
        p.unlink(); removed.append(f".github/workflows/{name}")
# obsolete scripts (standalone, not imported)
for rel in ["scripts/reset_alpaca_grocery_to_truth.py"]:
    p = ROOT / rel
    if p.exists(): p.unlink(); removed.append(rel)
print(f"removed {len(removed)} obsolete files:")
for r in removed: print("  -", r)
print(f"kept essential workflows: {sorted(KEEP_WF)}")
print("done.")
