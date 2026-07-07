"""
silmaril.execution.conductor_log — 5.0 CONDUCTOR, RUNG C0 (log the status quo)

The Conductor is the end-state orchestrator — the Strategy of Strategies that will
one day route capital across books, champions, cabinets and aggression rungs by
CONTEXT. Rung C0 changes NOTHING about behavior; it does the one thing every honest
meta-policy must do first: record, every cycle, the context the engine saw and the
action the current rules took, with propensity 1.0, into an append-only ledger.

    context  = per-book (regime, champion, open count, cash fraction, equity)
               + session (utc hour, weekday) + marks freshness
    action   = "status_quo" (whatever the standing gates/champion did)
    propensity = 1.0 (we always take it — which is exactly what makes later
               counterfactual scoring of shadow policies legitimate)

CONDUCTOR_LEDGER.jsonl is LONG-MEMORY: it survives wipes (like EVOLUTION_LEDGER)
because 300+ logged decisions are the C1 gate. Rotation keeps the file bounded;
the lifetime counter in CONDUCTOR_STATE.json survives rotation.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .atomic_io import write_json_atomic

LEDGER = "CONDUCTOR_LEDGER.jsonl"
STATE = "CONDUCTOR_STATE.json"
BOOKS = ("crypto", "stock", "metal", "energy", "aggressive")
ROTATE_AT = 8000
KEEP_ON_ROTATE = 6000
C1_GATE = 300


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load(p: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def log_conductor(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    live = _load(out / "paper_sim_live.json") or {}
    regimes = live.get("regimes") or {}
    mh = live.get("marks_health") or {}
    now = _now()

    ctx: Dict[str, Any] = {}
    for bk in BOOKS:
        b = live.get(bk) or {}
        eq = float(b.get("equity") or 0.0) or 10000.0
        ctx[bk] = {
            "regime": regimes.get("crypto" if bk == "aggressive" else bk, "—"),
            "champion": live.get("champion_" + ("crypto" if bk == "aggressive" else bk)),
            "open": int(b.get("open_positions") or 0),
            "cash_frac": round(float(b.get("cash") or eq) / eq, 3),
            "eq": round(eq, 2),
        }

    row = {
        "t": now.isoformat(),
        "session": {"utc_hour": now.hour, "dow": now.weekday()},
        "freshness_min": mh.get("newest_sample_age_min"),
        "entry_warm": mh.get("entry_warm"),
        "books": ctx,
        "action": "status_quo",
        "propensity": 1.0,
    }

    lp = out / LEDGER
    try:
        with lp.open("a") as fh:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    except Exception:
        pass

    st = _load(out / STATE) or {"decisions_logged": 0,
                                "since": now.isoformat(),
                                "rung": "C0 — logging only (zero behavior change)"}
    st["decisions_logged"] = int(st.get("decisions_logged") or 0) + 1
    st["generated_at"] = now.isoformat()
    st["c1_gate"] = C1_GATE
    st["note"] = (f"{st['decisions_logged']}/{C1_GATE} decisions toward the C1 gate "
                  "(counterfactual shadow scoring). Propensity 1.0 by construction; "
                  "no policy influences trading until it clears the standard gates.")

    # bounded rotation (lifetime counter above is what actually matters)
    try:
        if lp.exists() and sum(1 for _ in lp.open()) > ROTATE_AT:
            lines = lp.read_text().splitlines()[-KEEP_ON_ROTATE:]
            lp.write_text("\n".join(lines) + "\n")
            st["last_rotation"] = now.isoformat()
    except Exception:
        pass

    write_json_atomic(out / STATE, st)
    return st


if __name__ == "__main__":
    import sys
    r = log_conductor(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(r["note"])
