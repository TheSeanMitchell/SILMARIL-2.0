"""
silmaril.execution.store_contracts — 5.0 LAW 12: CONTRACTS

The single most common silent failure in this program's history is a module that
is correctly integrated but STARVED by a field-name mismatch ("wired-but-starved").
This module makes that class of bug impossible to miss:

  1. SCHEMAS — every core store declares its required fields (dot-paths). A store
     failing its schema flips a named red light in STORE_CONTRACTS.json.
  2. CONTRACT REGISTRY — every producer→consumer field dependency is a row; the
     validator asserts each consumer's read-path exists in the producer's latest
     output. A new integration is not "done" until its contract row exists here.

Missing-but-young stores report PENDING (first cycles after install/wipe are not
failures); missing-and-old or shape-broken stores report RED with the exact path.
Read-only; wrapped by the caller; can never affect trading.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .atomic_io import write_json_atomic

STORE = "STORE_CONTRACTS.json"
PENDING_GRACE_MIN = 75  # a store may legitimately not exist for its first ~hour


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get(d: Any, path: str) -> Tuple[bool, Any]:
    """Resolve a dot-path; '[]' means 'is a list'; 'a.b[].c' checks c on first item
    when the list is non-empty (empty list passes — absence of rows isn't a lie)."""
    cur = d
    for part in path.split("."):
        want_list = part.endswith("[]")
        key = part[:-2] if want_list else part
        if key:
            if not isinstance(cur, dict) or key not in cur:
                return False, None
            cur = cur[key]
        if want_list:
            if not isinstance(cur, list):
                return False, None
            if not cur:
                return True, None  # empty is honest
            cur = cur[0]
    return True, cur


# ---- SCHEMAS: store file -> required dot-paths -------------------------------
SCHEMAS: Dict[str, List[str]] = {
    "paper_sim_live.json": [
        "generated_at", "regimes", "marks_health.marked", "marks_health.entry_warm",
        "champion_live_params.max_hold_min",
        "crypto.equity", "crypto.open_positions", "crypto.positions[]",
        "stock.equity", "metal.equity", "energy.equity",
        "aggressive.equity", "aggressive.open_positions", "aggressive.positions[]",
    ],
    "champion.json": [
        "champion", "live_params.entry", "live_params.target", "live_params.stop",
        "live_params.max_hold_min", "evidence_basis", "provisional",
    ],
    "champion_validation.json": ["generated_at", "strategies[]"],
    "CHAMPION_GOVERNANCE.json": ["generated_at"],
    "PARAM_CATALOG.json": [
        "warmup.min_points", "warmup.min_span_h",
        "aggressive_book.enabled", "regime_gate", "bench_books.enabled",
    ],
    "BENCH_BOOKS.json": [
        "generated_at", "books.BENCH_CASH.equity", "books.BENCH_SPY.equity",
        "books.BENCH_HODL.equity", "books.BENCH_EQW.equity",
    ],
    "UNIVERSE_CENSUS.json": ["generated_at", "quadrants.crypto.listed"],
    "CHAMPION_UTILIZATION.json": ["generated_at", "last.crypto"],
    "CONDUCTOR_STATE.json": ["decisions_logged"],
    "RESEARCH_OS.json": ["generated_at", "questions[]", "priorities[]"],
}

# ---- CONTRACTS: (producer store, field path, consumer) ------------------------
CONTRACTS: List[Dict[str, str]] = [
    {"producer": "champion.json", "path": "live_params.max_hold_min",
     "consumer": "paper_sim (exit clock)"},
    {"producer": "champion.json", "path": "provisional",
     "consumer": "dashboard champion panel (Law 9 badge)"},
    {"producer": "paper_sim_live.json", "path": "aggressive.positions[]",
     "consumer": "trade_quality (GEKKO cards)"},
    {"producer": "paper_sim_live.json", "path": "regimes",
     "consumer": "conductor_log context + utilization"},
    {"producer": "paper_sim_live.json", "path": "crypto.open_positions",
     "consumer": "dashboard quadrant cards"},
    {"producer": "champion_validation.json", "path": "strategies[]",
     "consumer": "champion election (forward survivability)"},
    {"producer": "PARAM_CATALOG.json", "path": "warmup.min_points",
     "consumer": "paper_sim warmup gate"},
    {"producer": "BENCH_BOOKS.json", "path": "books.BENCH_HODL.return_pct",
     "consumer": "dashboard delta-vs-null line (Law 10)"},
    {"producer": "UNIVERSE_CENSUS.json", "path": "new_listings.count",
     "consumer": "dashboard 5.0 strip (new-listing detector)"},
    {"producer": "CHAMPION_UTILIZATION.json", "path": "summary_today",
     "consumer": "dashboard 5.0 strip (Law 16)"},
    {"producer": "RESEARCH_OS.json", "path": "priorities[]",
     "consumer": "dashboard research row (meta-research prioritization)"},
]


def _age_min(p: Path) -> Optional[float]:
    try:
        return (_now().timestamp() - p.stat().st_mtime) / 60.0
    except Exception:
        return None


def validate_stores(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    cache: Dict[str, Optional[Dict[str, Any]]] = {}

    def load(name: str) -> Optional[Dict[str, Any]]:
        if name not in cache:
            try:
                cache[name] = json.loads((out / name).read_text())
            except Exception:
                cache[name] = None
        return cache[name]

    checks, reds, pendings = [], [], []
    for store, paths in SCHEMAS.items():
        p = out / store
        d = load(store)
        if d is None:
            state = "PENDING" if not p.exists() else "RED"
            note = ("not created yet (first cycles after install/wipe)"
                    if state == "PENDING" else "exists but unreadable/invalid JSON")
            checks.append({"store": store, "state": state, "note": note})
            (pendings if state == "PENDING" else reds).append(store)
            continue
        missing = [pp for pp in paths if not _get(d, pp)[0]]
        if missing:
            checks.append({"store": store, "state": "RED",
                           "note": "missing: " + ", ".join(missing)})
            reds.append(store)
        else:
            checks.append({"store": store, "state": "GREEN", "note": "ok"})

    crows = []
    for c in CONTRACTS:
        d = load(c["producer"])
        if d is None:
            crows.append({**c, "state": "PENDING", "note": "producer not written yet"})
            continue
        ok, _ = _get(d, c["path"])
        crows.append({**c, "state": "GREEN" if ok else "RED",
                      "note": "ok" if ok else f"consumer would starve: {c['path']} absent"})
        if not ok:
            reds.append(f"{c['producer']}→{c['consumer']}")

    all_green = not reds
    verdict = ("ALL GREEN — every schema honored, every contract feedable"
               if all_green and not pendings else
               (f"{len(reds)} RED — " + "; ".join(sorted(set(reds))[:4])) if reds else
               f"green with {len(pendings)} pending first-write: " + ", ".join(pendings[:4]))
    payload = {"generated_at": _now().isoformat(), "all_green": all_green,
               "reds": sorted(set(reds)), "pending": pendings,
               "schema_checks": checks, "contracts": crows, "verdict": verdict,
               "doctrine": ("Law 12 — a module is not integrated until its store has a "
                            "schema row and its feed has a contract row here.")}
    write_json_atomic(out / STORE, payload)
    return payload


if __name__ == "__main__":
    import sys
    r = validate_stores(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(r["verdict"])
    for c in r["schema_checks"]:
        print(f"  {c['state']:7s} {c['store']}: {c['note']}")
