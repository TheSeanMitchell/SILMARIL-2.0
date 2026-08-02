#!/usr/bin/env python3
"""
REPAIR CAPITAL LEAK — 7.2.2, one-time, surgical, non-destructive.

WHY. Two capital leaks shipped in 7.2.1, both mine, both in the same change that let thesis
sleeves scan their own universe:

  1. THE CAP GUARD sat AFTER `bk["cash"] -= budget` and simply `break`ed, so a sleeve deducted
     a budget for a position it never created.
  2. `bk["positions"]` is keyed by SYMBOL, and the new universe scanner did not exclude names
     already held — so buying a held name OVERWROTE the live position and its capital vanished.

Measured on the operator's 2026-08-02 tree: crypto:R held $3,289 of positions with $3.55 cash
out of a $10,000 book. About $6,700 gone. Its headline read -64.5% while its realized read
+0.07% — two symptoms that looked unrelated, one release, both mine.

THE CHOICE THIS SCRIPT EXISTS TO AVOID. A full reset would fix the damaged books by destroying
290 closed trades and restarting a 90-day clock — throwing away the evidence to fix the ledger.
That trade is almost never worth it.

WHAT IT DOES INSTEAD. For every sleeve book it checks the one invariant that must always hold:

    cash + position_value + vault - realized_pnl  ==  starting equity

Money may move between those buckets; it may not leave. Where the identity is broken by more
than a dollar, the missing cash is restored — because the record shows it was deducted and
never spent. TRADE HISTORY IS NOT TOUCHED: every fill, entry, exit and realized P&L stays
exactly as it was, because those numbers were honest. Only the phantom deduction is undone,
and every repair is journaled to CAPITAL_REPAIR.jsonl with its arithmetic.

Usage:  python scripts/repair_capital_leak.py [docs/data] [--apply]
        (dry-run by default)
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

START = 10000.0
TOL = 1.0


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    data = Path(args[0]) if args else Path("docs/data")
    store = data / "STRATEGY_LAB.json"
    if not store.exists():
        print("no STRATEGY_LAB.json at %s" % store)
        return 1

    lab = json.loads(store.read_text())
    sleeves = lab.get("sleeves") or {}
    repairs = []

    for key, b in sleeves.items():
        cash = float(b.get("cash") or 0.0)
        vault = float(b.get("vault_usd") or 0.0)
        real = float(b.get("realized_pnl") or 0.0)
        start = float(b.get("start_equity") or START)
        posval = 0.0
        for p in (b.get("positions") or {}).values():
            try:
                posval += float(p.get("qty") or 0) * float(p.get("entry") or 0)
            except Exception:
                pass
        identity = cash + posval + vault - real
        gap = start - identity
        if gap > TOL:
            repairs.append({
                "sleeve": key, "missing_usd": round(gap, 2),
                "cash_before": round(cash, 2), "cash_after": round(cash + gap, 2),
                "position_value": round(posval, 2), "vault": round(vault, 2),
                "realized_pnl": round(real, 2),
                "why": ("cash + positions + vault - realized = %.2f, but this book started at "
                        "%.2f. The difference was deducted for positions that were never "
                        "created (cap guard) or that overwrote a live position (symbol key). "
                        "Restoring the phantom deduction; no trade record is altered."
                        % (identity, start)),
            })
            if apply:
                b["cash"] = round(cash + gap, 2)

    print("REPAIR CAPITAL LEAK 7.2.2 — %s" % ("APPLYING" if apply else "DRY RUN (pass --apply)"))
    print("  invariant: cash + position_value + vault - realized_pnl == starting equity\n")
    if not repairs:
        print("  every sleeve book balances. Nothing to repair.")
        return 0
    for r in repairs:
        print("  %-11s missing $%-9.2f  cash %.2f -> %.2f   (positions $%.2f, realized $%.2f)"
              % (r["sleeve"], r["missing_usd"], r["cash_before"], r["cash_after"],
                 r["position_value"], r["realized_pnl"]))
    print("\n  books needing repair: %d   total restored: $%.2f"
          % (len(repairs), sum(r["missing_usd"] for r in repairs)))

    if apply:
        shutil.copy2(store, store.with_suffix(".json.pre_repair"))
        store.write_text(json.dumps(lab, indent=1))
        with open(data / "CAPITAL_REPAIR.jsonl", "a") as f:
            for r in repairs:
                r["repaired_at"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(r) + "\n")
        print("\n  applied. backup at %s, journal at CAPITAL_REPAIR.jsonl"
              % store.with_suffix(".json.pre_repair").name)
        print("  trade history untouched — only the phantom deductions were undone.")
    else:
        print("\n  re-run with --apply to restore (a .pre_repair backup is written first)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
