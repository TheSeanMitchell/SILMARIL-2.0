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
    # ---- 5.0 FINAL AUDIT (2026-07-10): the five evidence labs + the deep-lane
    # heartbeat. These starved silently for a week (the deep workflow died on
    # 2026-07-03 and, because its main step wasn't failure-tolerated, every
    # following step — including commit — was skipped). Registering them here
    # means a dead lane or a starved lab flips a named RED light within a day
    # instead of vanishing. DAILY_BASELINE / WEEKLY_SCORECARD are append
    # ledgers (list roots); "[]" asserts list shape, empty-is-honest.
    "DAILY_BASELINE.json": ["[]"],
    "WEEKLY_SCORECARD.json": ["[]"],
    "AGGRESSION_LADDER.json": ["generated_at", "books"],
    "STOCK_PARITY_AUDIT.json": ["generated_at", "recommendation"],
    "COMPLEXITY_LEDGER.json": ["generated_at", "rows"],
    "deep_heartbeat.json": ["started_at"],
}

# ---- FRESHNESS: store file -> max age in hours before an EXISTING, shape-valid
# store goes RED anyway. Shape checks catch mismatches; this catches the other
# silent killer — a store that stopped being written. Only stores with a hard
# cadence promise belong here (spine-owned = every cycle; heartbeat = 3x/day
# deep lane, so 30h tolerates one missed slot + cron slippage; weekly = 8d).
FRESHNESS_MAX_AGE_H: Dict[str, float] = {
    "DAILY_BASELINE.json": 30.0,
    "AGGRESSION_LADDER.json": 6.0,
    "STOCK_PARITY_AUDIT.json": 6.0,
    "COMPLEXITY_LEDGER.json": 6.0,
    "WEEKLY_SCORECARD.json": 192.0,
    "deep_heartbeat.json": 30.0,
    "BENCH_BOOKS.json": 6.0,
    "CHAMPION_UTILIZATION.json": 6.0,
    "RESEARCH_OS.json": 6.0,
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
    {"producer": "DAILY_BASELINE.json", "path": "[]",
     "consumer": "market-memory analogs + every future cross-market study (P11)"},
    {"producer": "AGGRESSION_LADDER.json", "path": "books",
     "consumer": "deployment-fraction decision (P12 evidence)"},
    {"producer": "STOCK_PARITY_AUDIT.json", "path": "recommendation",
     "consumer": "stock-book threshold retune (P6 evidence)"},
    {"producer": "deep_heartbeat.json", "path": "started_at",
     "consumer": "lane-death detector (deep analytics 3x/day)"},
]


def _age_min(p: Path) -> Optional[float]:
    """Age in minutes — from CONTENT timestamps, never file mtime.

    2026-07-10 PM: `git checkout` sets every file's mtime to job-start time, so
    an mtime-based age reads ~0 in every GitHub lane — the freshness layer
    shipped this morning was blind in production (the census self-gate had the
    same disease and never ran in Actions at all). We now read the newest
    timestamp the store itself declares (generated_at / finished_at /
    started_at / as_of, or the last row's t/date for append ledgers), falling
    back to mtime only when the content carries no timestamp.
    """
    try:
        d = json.loads(p.read_text())
        cands: List[str] = []
        if isinstance(d, dict):
            for k in ("generated_at", "finished_at", "started_at", "as_of", "t"):
                v = d.get(k)
                if isinstance(v, str) and len(v) >= 10:
                    cands.append(v)
        elif isinstance(d, list) and d and isinstance(d[-1], dict):
            for k in ("t", "generated_at", "date"):
                v = d[-1].get(k)
                if isinstance(v, str) and len(v) >= 10:
                    cands.append(v)
        best = None
        for v in cands:
            try:
                ts = datetime.fromisoformat(v.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if best is None or ts > best:
                    best = ts
            except Exception:
                continue
        if best is not None:
            now = datetime.now(timezone.utc)
            return max(0.0, (now - best).total_seconds() / 60.0)
    except Exception:
        pass
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
            continue
        # ---- freshness (5.0 final audit): a valid store that stopped being
        # written is the same lie as a starved field — surface it by name.
        cap_h = FRESHNESS_MAX_AGE_H.get(store)
        age = _age_min(p)
        if cap_h is not None and age is not None and age > cap_h * 60.0:
            checks.append({"store": store, "state": "RED",
                           "note": f"STALE: last write {age/60.0:.1f}h ago (cap {cap_h:.0f}h) — its producing lane is dead"})
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
