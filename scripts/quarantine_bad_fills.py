#!/usr/bin/env python3
"""
QUARANTINE BAD FILLS — 7.1.4, one-time (idempotent, re-runnable, never destructive).

WHY THIS EXISTS. The 2026-07-26 "$242.19 · +11.533% · TARGET" fill on PNUT-USD was not a
trade — it was a position priced from two different numbers taken at two different moments.
The rails in 7.1.4 make that impossible going forward, but the fabricated win had ALREADY
been written into LAB_OUTCOMES.jsonl, which is the learning river the maturity gate and
sleeve promotion read. On the operator's tree it was 1 of only 5 outcomes: a single unreal
fill was 20% of the system's evidence about whether its sleeves work.

That is the honest reason the operator kept feeling the data was "tainted" and kept reaching
for a reset. A reset does clear it — and it also throws away the real evidence next to it.
This script is the surgical alternative: it finds outcomes that could only have come from a
pre-7.1.4 fabricated fill and marks them EXCLUDED, in place, with the reason attached.

THE TEST, deliberately narrow. An outcome is quarantined only if BOTH hold:
  * it exited on TARGET (a take-profit LIMIT — it cannot legitimately overshoot), and
  * its net was more than `tolerance` above the most generous target any sleeve can set.
Nothing else qualifies. A big STOP loss stays (losses were never inflated by this bug). A
big RIDE_TRAIL or REGIME_FLIP gain stays (those are market orders and may legitimately run).
A modest TARGET win stays. If the record does not prove fabrication, it is left alone.

THE LEARNING-PERMANENCE LAW IS RESPECTED: nothing is deleted. Rows are annotated with
`excluded: true` plus the reason, so the history remains auditable forever and consumers can
simply skip excluded rows. Run it, read the report, and keep your 90-day clock.

Usage:  python scripts/quarantine_bad_fills.py [docs/data] [--apply]
        (dry-run by default; --apply writes the annotations)
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# The most generous take-profit any sleeve can set (STRIKE 4%, MR 5%, geometry/patient up to
# ~6%). A TARGET exit meaningfully above this could not have been produced by a limit order.
MAX_LEGIT_TARGET_PCT = 6.0
TOLERANCE_PCT = 1.0          # cost/slippage headroom before we call something fabricated
LIMIT_EXITS = {"TARGET", "TAKE", "TAKE_LIMIT"}


def _is_fabricated(rec: dict) -> tuple:
    """(bool, reason). Only a limit-class exit far above any legal limit qualifies."""
    why = str(rec.get("why") or rec.get("exit_reason") or "").upper()
    if why not in LIMIT_EXITS:
        return False, ""
    net = rec.get("net_pct")
    if net is None:
        net = rec.get("realized_pct")
    try:
        net = float(net)
    except (TypeError, ValueError):
        return False, ""
    bar = MAX_LEGIT_TARGET_PCT + TOLERANCE_PCT
    if net <= bar:
        return False, ""
    return True, (
        "%s exit at %+.3f%% exceeds the most generous take-profit any sleeve can set (%.1f%% "
        "+%.1f%% tolerance). A limit order cannot fill above its limit, so this net could only "
        "have come from a pre-7.1.4 fill priced off a stale or derived number while the exit was "
        "priced off the live tape. Excluded from learning; retained for audit."
        % (why, net, MAX_LEGIT_TARGET_PCT, TOLERANCE_PCT)
    )


def sanitize(path: Path, apply: bool) -> dict:
    if not path.exists():
        return {"file": path.name, "present": False, "rows": 0, "quarantined": 0, "details": []}
    rows, bad = [], []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            rows.append(line)          # unparseable lines pass through untouched
            continue
        if rec.get("excluded"):
            rows.append(json.dumps(rec))
            continue
        is_bad, reason = _is_fabricated(rec)
        if is_bad:
            rec["excluded"] = True
            rec["excluded_by"] = "quarantine_bad_fills 7.1.4"
            rec["excluded_at"] = datetime.now(timezone.utc).isoformat()
            rec["why_excluded"] = reason
            bad.append({"t": rec.get("t"), "sym": rec.get("sym"), "book": rec.get("book"),
                        "sleeve": rec.get("sleeve"), "why": rec.get("why"),
                        "net_pct": rec.get("net_pct") or rec.get("realized_pct"),
                        "pnl": rec.get("pnl")})
        rows.append(json.dumps(rec))
    if apply and bad:
        shutil.copy2(path, path.with_suffix(path.suffix + ".pre_7_1_4"))
        path.write_text("\n".join(rows) + "\n")
    return {"file": path.name, "present": True, "rows": len(rows),
            "quarantined": len(bad), "details": bad}


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply = "--apply" in sys.argv
    data = Path(args[0]) if args else Path("docs/data")
    if not data.exists():
        print("no such directory: %s" % data)
        return 1

    print("QUARANTINE BAD FILLS 7.1.4 — %s" % ("APPLYING" if apply else "DRY RUN (pass --apply to write)"))
    print("  bar: a limit-class exit above %.1f%% + %.1f%% tolerance could not be a real limit fill\n"
          % (MAX_LEGIT_TARGET_PCT, TOLERANCE_PCT))

    total = 0
    for name in ("LAB_OUTCOMES.jsonl", "CHAMPION_FORWARD_LEDGER.jsonl", "LEDGER.jsonl"):
        r = sanitize(data / name, apply)
        if not r["present"]:
            print("  %-32s (absent)" % name)
            continue
        total += r["quarantined"]
        print("  %-32s %4d rows · %d quarantined" % (name, r["rows"], r["quarantined"]))
        for d in r["details"]:
            print("        %s  %-10s %-8s net %+.3f%%  pnl %s"
                  % (str(d.get("t"))[:19], d.get("sym"), (d.get("sleeve") or d.get("book") or ""),
                     float(d.get("net_pct") or 0), d.get("pnl")))

    print("\n  total quarantined: %d" % total)
    if total and not apply:
        print("  re-run with --apply to annotate (a .pre_7_1_4 backup is written first; nothing is deleted)")
    if not total:
        print("  learning river is clean — no fabricated limit fills found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
