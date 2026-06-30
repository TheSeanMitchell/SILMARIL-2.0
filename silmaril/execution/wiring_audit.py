"""2.7 STRATEGY-WIRING AUDIT — an honest, self-updating map of which "intelligence" modules actually feed
the LIVE TRADING DECISION (entry / exit / champion selection) versus which are computed and then ignored.

It reads the REAL source of the trading-path files every cycle, so there is nothing to fake and nothing to
go stale: if a module gets wired into the trading path later, this flips it to FED automatically; if a wiring
is removed, it flips back. This exists because the most common failure mode here is "wired-but-starved" — a
module that is correctly computed but silently never consulted by the code that actually buys and sells.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# The files that constitute the LIVE TRADING DECISION path — entry, exit, sizing, and champion selection.
# A module only "feeds a live decision" if its name appears (is imported / called) in one of these.
TRADING_PATH = ["paper_sim.py", "strategy_lab.py", "capital_router.py", "champion.py", "champion_split.py"]

# Intelligence modules whose declared job is to INFORM trading decisions.
INTEL = {
    "conviction_score": "per-candidate MR conviction (dip depth + bounce reliability) — embodies rhythm/heat",
    "peak_rhythm":    "per-name peak/trough rhythm — when to expect the next bounce",
    "fingerprint":    "per-name behavioral fingerprint / repeat signature",
    "heat_tolerance": "how much adverse heat a name tolerates before the thesis fails",
    "heartbeat":      "cadence/heartbeat of a name's moves",
    "dr_strange":     "next-peak / expected-move projection",
    "edge_capture":   "edge-capture / repeat-striker engine (proven names like MKR)",
    "lifecycle":      "attention-lifecycle state classifier",
}


def build_wiring_audit(out_dir) -> dict:
    here = Path(__file__).parent
    src = {}
    for f in TRADING_PATH:
        try:
            src[f] = (here / f).read_text()
        except Exception:
            src[f] = ""

    modules = {}
    for mod, role in INTEL.items():
        consumers = [f for f, text in src.items() if mod in text]
        fed = bool(consumers)
        modules[mod] = {
            "feeds_live_decision": fed,
            "consumed_by": consumers,
            "role": role,
            "status": ("FED — consumed by " + ", ".join(consumers)) if fed
                      else "COMPUTED BUT IGNORED — not referenced by the live trading path",
        }

    fed = [m for m, r in modules.items() if r["feeds_live_decision"]]
    ignored = [m for m, r in modules.items() if not r["feeds_live_decision"]]
    payload = {
        "generated_at": _now(),
        "trading_path_files": TRADING_PATH,
        "what_the_engine_actually_decides_on": (
            "the active champion's parameters (entry dip / target / stop / direction) plus the freshness and "
            "corrupt-feed gates. Nothing else is consulted at entry, exit, or champion selection."),
        "modules": modules,
        "fed_count": len(fed),
        "ignored_count": len(ignored),
        "verdict": (
            f"{len(fed)}/{len(modules)} intelligence modules feed live decisions"
            + (f" ({', '.join(fed)})" if fed else "")
            + f"; {len(ignored)} are computed but ignored"
            + (f": {', '.join(ignored)}" if ignored else "")
            + ". Until an ignored module is wired into the trading path, it does not affect a single trade."),
    }
    try:
        from .atomic_io import write_json_atomic
        write_json_atomic(Path(out_dir) / "STRATEGY_WIRING.json", payload)
    except Exception:
        try:
            (Path(out_dir) / "STRATEGY_WIRING.json").write_text(json.dumps(payload, indent=2))
        except Exception:
            pass
    return payload


if __name__ == "__main__":
    import sys
    p = build_wiring_audit(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(p["verdict"])
    for m, r in p["modules"].items():
        print(f"  {m:16s} {r['status']}")
