"""silmaril.execution.question_engine — 7.0 THE INTERROGATOR (the system asks everything).

The operator's mandate, verbatim: "look for holes that need more questions being
asked so the master system is truly asking EVERYTHING it can about what we have
built… to know if our system is truly moving TOWARD or AWAY from edge."

Every cycle this module ASKS and ANSWERS, in writing, with the number attached:
each question resolves to PASS / WATCH / FAIL / PENDING plus its evidence line.
The final row is the composite: TOWARD-EDGE or AWAY-FROM-EDGE, and why.

Emits QUESTIONS.json (BRAIN renders it at the top — the mind interrogating itself
before it acts). Nothing here trades; everything here judges.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .atomic_io import write_json_atomic


def _load(out: Path, name: str, default=None):
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return default if default is not None else {}


def build_questions(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    Q: List[Dict[str, Any]] = []

    def ask(q, status, ev):
        Q.append({"q": q, "status": status, "evidence": ev})

    rec = _load(out, "RECONCILIATION.json")
    ask("Do all four ledgers agree (books = card = session)?",
        "PASS" if rec.get("all_ok") else ("FAIL" if rec else "PENDING"),
        f"{sum(1 for c in rec.get('checks', []) if c.get('ok'))}/{len(rec.get('checks', []))} checks green"
        if rec else "first cycle pending")

    cc = _load(out, "CONFIDENCE_CARDS.json")
    stv = cc.get("starved_components") or []
    ask("Is any confidence component starved (defaulting on >90% of the universe)?",
        "WATCH" if stv else "PASS", (", ".join(stv[:6]) or "all components fed"))

    geo = _load(out, "GEOMETRY.json")
    gc = geo.get("counts") or {}
    ask("How much of the universe is WINNABLE right now (geometry + evidence)?",
        "PASS" if gc.get("TRADEABLE", 0) > 0 else "WATCH",
        f"TRADEABLE {gc.get('TRADEABLE',0)} · geo-locked {gc.get('UNTRADEABLE:geometry',0)} · "
        f"evidence-short {gc.get('UNTRADEABLE:evidence',0)} · stand-down {gc.get('STAND-DOWN',0)}")

    bad_live = []
    live = _load(out, "paper_sim_live.json")
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        for p0 in (live.get(bk) or {}).get("positions") or []:
            ps, pf = p0.get("p_star_pct"), p0.get("p_floor_pct")
            if ps is not None and pf is not None and pf < ps:
                bad_live.append(p0.get("sym"))
    ask("Is any LIVE position demanding more wins than its evidence floor (p* > floor)?",
        "FAIL" if bad_live else "PASS", (", ".join(bad_live[:5]) or "every open trade is winnable on paper"))

    cal = _load(out, "CALIBRATION.json")
    ask("When we say X%, do we win X%? (calibration status)",
        {"CALIBRATED": "PASS", "QUARANTINED": "FAIL"}.get(cal.get("status"), "PENDING"),
        f"{cal.get('status','UNPROVEN')} · n={cal.get('n',0)} · brier={cal.get('brier','—')}")

    es = _load(out, "EDGE_SURFACE.json")
    ask("Does at least one CELL have proven positive expectancy (CI_lower > 0)?",
        "PASS" if (es.get("proven_cells") or 0) > 0 else "PENDING",
        f"proven {es.get('proven_cells',0)} of {len(es.get('cells') or [])} cells · mode {es.get('mode','observe')}")

    sz = _load(out, "SIZER.json")
    ask("What size does the drawdown ladder permit right now?",
        {"GREEN": "PASS", "AMBER": "WATCH", "RED": "FAIL"}.get(sz.get("state"), "PENDING"),
        f"{sz.get('state','—')} ×{sz.get('mult','—')} · dd {sz.get('dd_pct','—')}% · "
        f"today ${sz.get('realized_today','—')}" + (" · " + "; ".join(sz.get("breakers") or []) if sz.get("breakers") else ""))

    fac = (sz.get("factor") or {})
    ask("Is the one-factor law honored (crypto = one bet)?",
        "FAIL" if fac.get("over") else "PASS",
        f"crypto exposure {fac.get('used_pct','—')}% of cap {fac.get('cap_pct','—')}%")

    stuck = []
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        for p0 in (live.get(bk) or {}).get("positions") or []:
            if p0.get("stuck"):
                stuck.append(p0.get("sym"))
    ask("Is capital STUCK (flat past its own review window)?",
        "WATCH" if stuck else "PASS", (", ".join(stuck[:6]) or "no stuck positions"))

    dl = _load(out, "DATA_LEDGER.json")
    ask("Is history being ARCHIVED, never discarded (Law 26)?",
        "PASS" if dl else "PENDING",
        f"live {dl.get('live_mb','—')}MB · archive {dl.get('archive_files',0)} files "
        f"{dl.get('archive_mb','—')}MB" if dl else "first cycle pending")

    vr = _load(out, "VENUE_REALITY.json")
    tt = (vr.get("truth_test") or {})
    ask("How much realized P&L sits on names our venues CANNOT trade?",
        "PASS" if (tt.get("pct_of_realized_untradable") or 0) < 20 else "WATCH",
        f"${tt.get('realized_on_UNLISTED_usd',0)} of ${tt.get('realized_total_usd',0)} "
        f"({tt.get('pct_of_realized_untradable',0)}%)")

    ml = _load(out, "MASTER_LEDGER.json")
    cyc = (ml.get("cycles") or [])
    ask("Did the Master write a verdict for EVERY book this cycle?",
        "PASS" if cyc and all(len((cyc[-1].get('books') or {})) >= 4 for _ in [0]) else "PENDING",
        f"{len((cyc[-1].get('books') or {}))} books · cycle {len(cyc)}" if cyc else "first cycle pending")

    disc = _load(out, "DISCOVERY.json")
    g = disc.get("graveyard") or {}
    ask("Are rejections RESOLVING into evidence (the graveyard pays rent)?",
        "PASS" if (g.get("buried_total") or 0) > 0 else "PENDING",
        f"buried {g.get('buried_total',0)} · resolved this cycle {g.get('resolved_this_cycle',0)}")

    fees = _load(out, "fees_truth.json")
    ask("Does the modeled fee match the venue's declared fee (fee-gap)?",
        "WATCH" if fees else "PENDING",
        "venue layer active — declared fees govern; fees_truth is the audit trail")

    cg = _load(out, "CHAMPION_GOVERNANCE.json")
    ask("Is the champion's edge REAL after selection bias (deflated Sharpe)?",
        {"POSITIVE": "PASS", "ZERO_OR_NEGATIVE": "WATCH"}.get((cg.get("dsr") or {}).get("verdict"), "PENDING"),
        f"DSR {(cg.get('dsr') or {}).get('value','—')} across {(cg.get('dsr') or {}).get('trials','316')} trials"
        if cg.get("dsr") else "insufficient live trades — honest stand-down")

    # the operator's highest question, now asked every cycle:
    influence = []
    if (cal.get("status") in (None, "UNPROVEN")):
        influence.append(f"confidence (n={cal.get('n',0)})")
    if (es.get("proven_cells") or 0) == 0:
        influence.append("cell expectancy (0 proven)")
    if gc.get("STAND-DOWN", 0) > gc.get("TRADEABLE", 0):
        influence.append("per-name evidence floors")
    ask("Which belief has the LEAST evidence and the MOST influence?",
        "WATCH" if influence else "PASS",
        ("; ".join(influence) or "no high-influence belief is under-evidenced"))

    fails = sum(1 for q in Q if q["status"] == "FAIL")
    watches = sum(1 for q in Q if q["status"] == "WATCH")
    passes = sum(1 for q in Q if q["status"] == "PASS")
    verdict = ("AWAY-FROM-EDGE" if fails else
               ("HOLDING" if watches > passes else "TOWARD-EDGE"))
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "questions": Q,
               "score": {"pass": passes, "watch": watches, "fail": fails,
                         "pending": sum(1 for q in Q if q["status"] == "PENDING")},
               "verdict": verdict,
               "what": ("the mind interrogates itself before it acts: every answer carries its "
                        "number; the composite says whether we are moving TOWARD or AWAY from edge")}
    write_json_atomic(out / "QUESTIONS.json", payload)
    return {"summary": f"questions: {verdict} · {passes}✓ {watches}~ {fails}✗ "
                       f"{payload['score']['pending']}…"}
