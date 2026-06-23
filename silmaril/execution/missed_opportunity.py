"""
silmaril.execution.missed_opportunity — Measurement Spine #3.

Every runner SILMARIL did not bank becomes training data. For each name that
offered a real move but we captured little/none, log WHY, using the coverage
audit's funnel position:

    not scanned        → universe problem
    scanned, rejected  → filter problem (with the reject reason)
    bought, exited flat/down on an up move → execution problem (sold too early)
    never bought though considered → allocation problem (ran out of capital /
                                      ranked below cutoff)

This is the exact diagnostic chain the reviewer described. It turns your
manual "INTC ran and we missed it — HOW?" into an automatic, machine-readable
record with the cause attached. Writes docs/data/missed_opportunity.json.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

VERSION = "missed-opportunity-1.0"
RUNNER_THRESHOLD_PCT = 3.0   # a "runner" offered at least this favorable move


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def _dump(path: Path, obj):
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, separators=(",", ":"), allow_nan=False)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _norm(t: str) -> str:
    return str(t).upper().replace("/", "").replace("-", "")


def build_missed_opportunity(out_dir) -> Dict[str, Any]:
    """Cross-reference edge capture + coverage audit to log misses with cause."""
    out = Path(out_dir)
    edge = _load(out / "edge_capture.json", {}) or {}
    coverage = _load(out / "coverage_audit.json", {}) or {}
    # names Alpaca can't trade — a "miss" on these is not fixable, so flag them
    # separately instead of polluting the real (fixable) miss causes.
    try:
        untradeable = set(json.loads((out / "untradeable_assets.json").read_text())
                          .get("untradeable", []))
    except Exception:
        untradeable = set()

    # build lookup: was a ticker scanned? considered? rejected (why)? bought?
    scanned = set()
    bought = set(_norm(t) for t in (coverage.get("bought") or []))
    reject_reason = {}
    for r in (coverage.get("rejected_detail") or []):
        reject_reason[_norm(r.get("ticker"))] = r.get("reason")
    # top_100 carries everything ranked (scanned with a chain)
    for r in (coverage.get("top_100") or []):
        scanned.add(_norm(r.get("ticker")))
    for r in (coverage.get("rejected_detail") or []):
        scanned.add(_norm(r.get("ticker")))
    considered_n = (coverage.get("funnel") or {}).get("considered")

    movers = (edge.get("top_movers") or []) + (edge.get("missed_runners") or [])
    seen = set()
    misses = []
    for m in movers:
        t = m.get("ticker")
        s = _norm(t)
        if s in seen:
            continue
        seen.add(s)
        avail = float(m.get("available_pct") or 0.0)
        cap = float(m.get("captured_pct") or 0.0)
        edge_pct = m.get("edge_capture_pct")
        held = m.get("held")
        if avail < RUNNER_THRESHOLD_PCT:
            continue
        # we "captured well" if edge >= 50% — not a miss
        if edge_pct is not None and edge_pct >= 50.0:
            continue

        # classify the cause
        if _norm(t) in untradeable:
            cause = "not_on_alpaca"
            detail = "ran, but Alpaca doesn't list this asset — not tradeable"
        elif not held:
            if s not in scanned and s not in bought:
                cause = "universe_gap"
                detail = "not in scanned universe this cycle"
            elif s in reject_reason:
                cause = "filter_rejected"
                detail = f"rejected: {reject_reason[s]}"
            else:
                cause = "allocation_or_cutoff"
                detail = "scanned/considered but never bought (capital or rank cutoff)"
        else:
            if cap < 0:
                cause = "exited_at_loss_on_up_move"
                detail = f"held but exited DOWN {cap:.1f}% while the name offered +{avail:.1f}%"
            else:
                cause = "exited_too_early"
                detail = f"captured only {cap:.1f}% of a +{avail:.1f}% move (edge {edge_pct}%)"

        misses.append({
            "ticker": t,
            "available_pct": round(avail, 2),
            "captured_pct": round(cap, 2),
            "edge_capture_pct": edge_pct,
            "held": held,
            "cause": cause,
            "detail": detail,
            "crypto": m.get("crypto", False),
        })

    misses.sort(key=lambda m: m["available_pct"], reverse=True)

    # cause histogram — the at-a-glance "why are we leaving money on the table"
    from collections import Counter
    cause_hist = dict(Counter(m["cause"] for m in misses))

    # the dollar-weighted lesson: total available % left on the table
    total_available_missed = round(sum(m["available_pct"] for m in misses
                                       if not m["held"]), 1)

    payload = {
        "version": VERSION,
        "generated_at": _now(),
        "summary": {
            "total_misses": len(misses),
            "by_cause": cause_hist,
            "total_available_pct_left_on_table": total_available_missed,
            "runner_threshold_pct": RUNNER_THRESHOLD_PCT,
        },
        "misses": misses[:60],
        "note": ("Every runner (>= "
                 f"{RUNNER_THRESHOLD_PCT}% available) we didn't bank, with the "
                 "CAUSE traced through the funnel: universe_gap (never scanned), "
                 "filter_rejected (gate blocked it — reason attached), "
                 "allocation_or_cutoff (considered but not bought), "
                 "exited_too_early / exited_at_loss_on_up_move (held but sold "
                 "wrong). Fix the dominant cause first."),
    }
    _dump(out / "missed_opportunity.json", payload)
    return payload


if __name__ == "__main__":  # pragma: no cover
    import sys
    p = build_missed_opportunity(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/data"))
    print(json.dumps(p["summary"], indent=2))
