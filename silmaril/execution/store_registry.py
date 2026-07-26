"""silmaril.execution.store_registry — 7.0.2 THE SELF-HEALING CLEAN ROOM.

STORE_REGISTRY.json was a hand-built snapshot: any NEW store (or a store whose
builder was resurrected — THRESHOLD_TAKEHOME, KRAKEN_SPREAD, MASTER_LOG,
SESSION_ANATOMY after the 7.0.1 cascade repair) arrived "unregistered" and failed
T32. A registry that must be hand-maintained is a registry that goes stale.

This builder regenerates the registry EVERY cycle by RULE, so coverage is total by
construction and the operator never hand-edits a classification again:

  LEARNING — hard-won market knowledge; survives a standard wipe, dies on GENESIS
  STATE    — books/sleeves/master/sizer/maker; destroyed by EVERY wipe
  LEDGER   — append-only; evictions gzip to archive/ (Law 26)
  DERIVED  — regenerated each cycle; a copy older than the wipe is a LIE (swept)

Unknown stores default to DERIVED — the safe class: worst case it regenerates.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .atomic_io import write_json_atomic

LEARNING = {
    "FINGERPRINTS.json", "PEAK_RHYTHM.json", "timing_fingerprint.json", "dr_strange.json",
    "CONFIDENCE_ENGINE.json", "MTF_REGIME.json", "price_samples.json", "ccxt_samples.json",
    "metals_samples.json", "energy_samples.json", "REGIME_CLASSIFIER.json",
    "momentum_chain.json", "source_rankings.json", "fees_truth.json", "agent_beliefs.json",
    "DAILY_BASELINE.json", "RESEARCH_OS.json", "KRAKEN_SPREAD.json",
    # ── 7.0 FINAL (Tier 3 / V1): the vault leak, closed. These were classed DERIVED, so the
    # post-wipe "stale-derived sweep" (cli) deleted them right after a reset even though the
    # reset script PROMISED they were preserved forever — the exact wired-but-contradicted
    # failure class. Calibration is the machine's memory of its own honesty; the graveyard is
    # what it learned from what it did NOT do; conductor state is 807 logged decisions toward
    # C1/C2. None of that is a "derived view." All now survive a standard wipe by class.
    "CALIBRATION.json", "GRAVEYARD.json", "CONDUCTOR_STATE.json", "CONDUCTOR_REPORT_CARD.json",
    "knowledge_graph.json", "RESEARCH_QUEUE.json", "ROTATION_HYPOTHESES.json",
    "CENSUS_ROSTER.json", "INVARIANTS_STATE.json",
    # ── 7.1: same wired-but-contradicted class, caught by the fresh-tree battery. The reset
    # script deliberately PRESERVES VENUE_UNIVERSE.json (deleting the listings would make every
    # close UNROUTABLE until the next 09:2x refresh), but the registry classed it DERIVED — so
    # T53 called the preserved copy a stale lie on every fresh tree. It is a snapshot of the
    # OUTSIDE world (exchange listings), exactly like price_samples/KRAKEN_SPREAD: yesterday's
    # copy is yesterday's listings, not a ghost of pre-wipe book state. Classed to match.
    "VENUE_UNIVERSE.json",
}
STATE_HINTS = ("paper_book_", "BENCH_BOOKS", "STRATEGY_LAB", "MASTER_ACCOUNT",
               "MASTER_DECISIONS", "MASTER_LEDGER", "CHAMPION_GOVERNANCE", "champion_",
               "SIZER", "MAKER_PENDING", "paper_sim_live", "WIPE_MARKER")


def _cls(fname: str) -> str:
    if fname.endswith(".jsonl"):
        return "LEDGER"
    if fname in LEARNING:
        return "LEARNING"
    for h in STATE_HINTS:
        if fname.startswith(h) or h in fname:
            return "STATE"
    return "DERIVED"


def build_store_registry(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    stores: Dict[str, str] = {}
    for f in sorted(os.listdir(out)):
        if not (f.endswith(".json") or f.endswith(".jsonl")):
            continue
        if f == "STORE_REGISTRY.json":
            continue
        stores[f] = _cls(f)
    counts: Dict[str, int] = {}
    for v in stores.values():
        counts[v] = counts.get(v, 0) + 1
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": "7.0",
        "classes": {
            "LEARNING": "hard-won market knowledge; survives a standard wipe, resets on GENESIS",
            "STATE": "books · sleeves · master · sizer peak · maker book — destroyed by EVERY wipe",
            "DERIVED": "regenerated every cycle; a copy older than WIPE_MARKER is swept as a lie",
            "LEDGER": "append-only; evictions compact to docs/data/archive/*.jsonl.gz (Law 26)",
            "ARCHIVE": "docs/data/archive/ — gzip history, sacred through every wipe incl. GENESIS",
        },
        "counts": counts,
        "stores": stores,
        "what": ("7.0.2 SELF-HEALING: the registry is REBUILT BY RULE every cycle, so a new or "
                 "resurrected store can never be 'unregistered' again. Unknown → DERIVED (safe: "
                 "worst case it regenerates). T32 asserts total coverage; T53 asserts no DERIVED "
                 "store outlives a wipe."),
    }
    write_json_atomic(out / "STORE_REGISTRY.json", payload)
    return {"summary": f"store registry: {len(stores)} stores · "
                       + " · ".join(f"{k} {v}" for k, v in sorted(counts.items()))}
