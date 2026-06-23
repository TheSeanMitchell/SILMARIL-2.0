"""
silmaril.execution.opportunity_audit — OPPORTUNITY AUDIT (2.5.1 P1). Explainability.

Every cycle, every name in the universe is classified with the EXACT reason it was
or wasn't traded — no black boxes. Uses the sim's own functions (_marks_from_samples,
freshness, champion entry threshold) so the audit matches reality, not a guess.
Answers "why did we miss AXS / SAND / DYDX?" with machine-readable evidence.
Emits OPPORTUNITY_AUDIT.json.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from .paper_sim import (load_all_samples, _marks_from_samples, _is_crypto,
                        is_tradeable, MAX_NAMES)
from .atomic_io import write_json_atomic

def _now(): return datetime.now().astimezone().isoformat()
def _load(out, n):
    try: return json.loads((out / n).read_text())
    except Exception: return {}

def _fresh_ok(px: List[float], crypto: bool) -> bool:
    if len(px) <= 20: return False
    return is_tradeable(px) if crypto else (len(set(px[-6:])) > 1)

def _entry_for(out: Path, book: str) -> float:
    champ = _load(out, f"champion_{book}.json")
    lp = champ.get("live_params") or {}
    return float(lp.get("entry") or (0.03 if book == "crypto" else 0.05))

def build_opportunity_audit(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    samples = load_all_samples(out)
    marks = _marks_from_samples(samples)
    series = {tk: [p for _, p in rows if p and p > 0] for tk, rows in samples.items()}
    books_out, by_ticker = {}, {}
    for book, crypto in (("crypto", True), ("stock", False)):
        entry = _entry_for(out, book)
        held = set((_load(out, f"paper_book_{book}.json").get("positions") or {}).keys())
        names = [s for s in marks if _is_crypto(s) == crypto]
        disc, ignored, rej = [], [], []
        for s in names:
            px = series.get(s, []); h1 = marks[s][1]
            move = round(h1 * 100, 2)
            if len(px) <= 20:
                dec, reason = "IGNORED", "insufficient_history (<20 samples)"
            elif h1 > -entry:
                dec, reason = "IGNORED", f"insufficient_drop: moved {move}%, rule needs <= -{entry*100:.0f}%"
            elif not _fresh_ok(px, crypto):
                dec, reason = "REJECTED", ("not_fresh: stale/ghost price (crypto 80% bar)" if crypto
                                          else "not_fresh: stock not actively quoting (market closed)")
            elif s in held:
                dec, reason = "REJECTED", "already_held: position open, no duplicate exposure"
            else:
                dec, reason = "DISCOVERED", f"qualified: dropped {move}% (<= -{entry*100:.0f}%), fresh, not held"
            row = {"ticker": s, "decision": dec, "reason": reason, "move_pct": move,
                   "entry_threshold_pct": -round(entry * 100, 1)}
            by_ticker[s] = {"book": book, "decision": dec, "reason": reason, "move_pct": move}
            (disc if dec == "DISCOVERED" else ignored if dec == "IGNORED" else rej).append(row)
        # rank discovered by depth; only top MAX_NAMES can be taken this cycle
        disc.sort(key=lambda r: r["move_pct"])
        for i, r in enumerate(disc):
            if i < MAX_NAMES:
                r["decision"] = "TRADEABLE_NOW"; r["reason"] = f"top-{MAX_NAMES} by drop depth (rank {i+1}) — eligible to trade"
            else:
                r["decision"] = "REJECTED"; r["reason"] = f"capacity_cap: ranked #{i+1}, only deepest {MAX_NAMES} taken/cycle"
            by_ticker[r["ticker"]] = {"book": book, "decision": r["decision"], "reason": r["reason"], "move_pct": r["move_pct"]}
        tradeable = [r for r in disc if r["decision"] == "TRADEABLE_NOW"]
        capacity_rej = [r for r in disc if r["decision"] == "REJECTED"]
        books_out[book] = {
            "entry_rule": f"buy when a fresh, unheld name has dropped >= {entry*100:.0f}% recently",
            "universe": len(names),
            "funnel": {
                "discovered_qualified": len(tradeable) + len(capacity_rej),
                "tradeable_now": len(tradeable),
                "rejected_capacity": len(capacity_rej),
                "rejected_not_fresh": sum(1 for r in rej if r["reason"].startswith("not_fresh")),
                "rejected_already_held": sum(1 for r in rej if r["reason"].startswith("already_held")),
                "ignored_insufficient_drop": sum(1 for r in ignored if "insufficient_drop" in r["reason"]),
            },
            "tradeable_now": tradeable[:15],
            "missed_capacity": capacity_rej[:15],
            "rejected_detail": rej[:20],
        }
    payload = {"generated_at": _now(), "books": books_out,
               "by_ticker": by_ticker,
               "how_to_read": ("Every name lands in exactly one bucket with the exact rule that put it there. "
                               "To answer 'why did we miss X', look up X in by_ticker."),
               "examples": {tk: by_ticker.get(tk, {"decision": "not_in_universe",
                            "reason": "no recent price samples for this symbol"})
                            for tk in ("AXS-USD", "SAND-USD", "DYDX-USD", "AXS", "SAND", "DYDX")},
               "note": "Explainability only. No decision logic changed — this reports the rules already in force."}
    try: write_json_atomic(out / "OPPORTUNITY_AUDIT.json", payload)
    except Exception: pass
    return payload

if __name__ == "__main__":
    import sys
    p = build_opportunity_audit(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    for bk, b in p["books"].items():
        print(f"{bk}: {b['funnel']}")
    print("examples:", {k: v["decision"] for k, v in p["examples"].items()})
