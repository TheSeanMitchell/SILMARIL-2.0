"""5.0 FINAL-AUDIT CLEANUP (2026-07-10) — remove what the audit proved dead.

Doctrine: CODE is atticked (reversible), DATA that nothing writes or reads is
deleted (it either regenerates or was orphaned by a retired system). Every item
below was verified dead by the 2026-07-10 final audit:

  ATTIC (reversible):
    cli.py                 root monolith — zero references from workflows,
                           scripts, or docs; the live engine is silmaril/cli.py
                           (`python -m silmaril`). Differs from the 06-12 attic
                           copy, so it keeps its own dated name.
    execution/             root-level dir (3 modules) — nothing imports it;
                           the live package is silmaril/execution/.
    learning/              root-level dir (1 module) — nothing imports it;
                           the live package is silmaril/learning/.

  DELETE (dead data):
    docs/data/_legacy_charts_disabled.json   21 MB of disabled chart state.
    docs/data/decision_ledger.json           legacy sgov/alpaca ledger (writer
                                             disabled in cli.py long ago).
    docs/data/capital_flow.json              Alpaca-era; no reader, no writer.
    docs/data/harvest_accounts.json          Alpaca 3-account rollup; execution
                                             now gated OFF by _broker_policy.
    docs/data/alpaca_paper_state.json        ditto (per-account states).
    docs/data/alpaca_h3_state.json           ditto.
    docs/data/alpaca_h5_state.json           ditto.
    docs/data/archive/                       old snapshots folder; unused.

Run from the repo root (the workflow does): python scripts/cleanup_5_0_final.py
Prints a full ledger; every action individually wrapped; exits 0 always so the
commit step still runs on a partial pass.
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATTIC = ROOT / "attic"
STAMP = "2026-07-10"

ledger = []


def _attic_file(rel: str, new_name: str) -> None:
    src = ROOT / rel
    if not src.exists():
        ledger.append(f"skip (absent): {rel}")
        return
    ATTIC.mkdir(parents=True, exist_ok=True)
    dest = ATTIC / new_name
    try:
        shutil.move(str(src), str(dest))
        ledger.append(f"ATTIC: {rel} -> attic/{new_name}")
    except Exception as e:  # noqa: BLE001
        ledger.append(f"FAILED attic {rel}: {e}")


def _attic_dir(rel: str, new_name: str) -> None:
    src = ROOT / rel
    if not src.is_dir():
        ledger.append(f"skip (absent): {rel}/")
        return
    ATTIC.mkdir(parents=True, exist_ok=True)
    dest = ATTIC / new_name
    try:
        # drop __pycache__ before the move so the attic stays clean
        for pc in src.rglob("__pycache__"):
            shutil.rmtree(pc, ignore_errors=True)
        shutil.move(str(src), str(dest))
        ledger.append(f"ATTIC: {rel}/ -> attic/{new_name}/")
    except Exception as e:  # noqa: BLE001
        ledger.append(f"FAILED attic {rel}/: {e}")


def _delete(rel: str) -> None:
    p = ROOT / rel
    try:
        if p.is_dir():
            shutil.rmtree(p)
            ledger.append(f"DELETED dir: {rel}/")
        elif p.exists():
            sz = p.stat().st_size
            p.unlink()
            ledger.append(f"DELETED: {rel} ({sz/1e6:.1f} MB)")
        else:
            ledger.append(f"skip (absent): {rel}")
    except Exception as e:  # noqa: BLE001
        ledger.append(f"FAILED delete {rel}: {e}")


def main() -> None:
    _attic_file("cli.py", f"cli_root_RETIRED_{STAMP}.py")
    _attic_dir("execution", f"root_execution_RETIRED_{STAMP}")
    _attic_dir("learning", f"root_learning_RETIRED_{STAMP}")

    for rel in (
        "docs/data/_legacy_charts_disabled.json",
        "docs/data/decision_ledger.json",
        "docs/data/capital_flow.json",
        "docs/data/harvest_accounts.json",
        "docs/data/alpaca_paper_state.json",
        "docs/data/alpaca_h3_state.json",
        "docs/data/alpaca_h5_state.json",
        "docs/data/archive",
    ):
        _delete(rel)

    print("=== 5.0 FINAL CLEANUP LEDGER ===")
    for line in ledger:
        print(" ", line)
    print("=== done — code is in attic/ (reversible); data deletions regenerate nothing because nothing writes them ===")


if __name__ == "__main__":
    main()
