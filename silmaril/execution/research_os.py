"""
silmaril.execution.research_os — 5.0 RESEARCH OPERATING SYSTEM (v1)

The layer ABOVE the engines (operator Notes, Part 2): the machine stops only
optimizing parameters and starts tracking WHAT IT SHOULD BE ASKING.

    Market → Observations → QUESTIONS → Hypotheses → Experiments → Evidence
           → Knowledge → Trading decisions → Allocation → Compounding

v1 delivers, honestly and with zero synthetic data:
  • QUESTION REGISTRY — every open research question is a row with evidence_have
    (auto-tallied from REAL stores every cycle where a hook exists), evidence_needed,
    blocked_by, information_value, and a computed priority. Research DEBT = the gap.
  • NEGATIVE KNOWLEDGE — things this program has PROVEN false, with the evidence.
    Permanent. (Professionals accumulate this faster than positive knowledge.)
  • BELIEFS WITH DECAY — every standing belief carries last_confirmed and
    retest_after_days; stale beliefs flip retest_required=True. Old truths expire.
  • FOUR-WAY CLASSIFICATION — KNOWN_TRUE / KNOWN_FALSE / UNKNOWN / CHANGING on
    every item.
  • UNKNOWN-UNKNOWNS panel — computed live: least-tested market, stalest belief,
    biggest evidence gap, weakest-instrumented question.
  • META-RESEARCH — priorities = "which experiment, if answered, pays the most",
    ranked by information_value then evidence gap. The roadmap writes itself.

RESEARCH_OS.json is LONG-MEMORY: append-only ids, survives every wipe (like
EVOLUTION_LEDGER / RESEARCH_QUEUE). Manual edits to text fields are preserved;
only the auto-evidence fields are refreshed. Read-only w.r.t. trading; wrapped
by the caller; can never break a cycle.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .atomic_io import write_json_atomic

STORE = "RESEARCH_OS.json"
VALUE_RANK = {"HIGH": 0, "MED": 1, "LOW": 2}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load(p: Path) -> Optional[Any]:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _days_since(iso: str) -> Optional[int]:
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return max(0, int((_now() - dt).total_seconds() // 86400))
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# SEEDS — the program's REAL open questions and REAL proven-false record.
# (ids are stable; new ids may be appended forever; none are ever deleted.)
# ─────────────────────────────────────────────────────────────────────────────
def _seed_questions() -> List[Dict[str, Any]]:
    return [
        {"id": "Q001", "question": "Does the elected champion beat BENCH_HODL (50/50 BTC-ETH hold) after fees, forward?",
         "classification": "UNKNOWN", "information_value": "HIGH",
         "evidence_needed": 100, "hook": "champion_forward_trades",
         "blocked_by": "forward closed trades (the live-money bar is the same 100)",
         "why_it_pays": "If holding beats the engine, every other question is decoration."},
        {"id": "Q002", "question": "Does FASTER champion rotation beat sticky rotation on realized P&L?",
         "classification": "UNKNOWN", "information_value": "HIGH",
         "evidence_needed": 20, "hook": "rotation_freshness_gate",
         "blocked_by": "rotation events with realized outcomes",
         "why_it_pays": "Directly gates how hard the new champion_rotation knobs can be pushed."},
        {"id": "Q003", "question": "Do stock-tuned entry thresholds (≈1% dips) wake the structurally idle stock book?",
         "classification": "UNKNOWN", "information_value": "HIGH",
         "evidence_needed": 30, "hook": "stock_forward_trades",
         "blocked_by": "stock-tuned knobs enabled + market-hours fills",
         "why_it_pays": "A whole quadrant of capital is ARMED-forever until this is answered."},
        {"id": "Q004", "question": "Is the regime classifier better than a coin flip 24h out?",
         "classification": "UNKNOWN", "information_value": "MED",
         "evidence_needed": 40, "hook": "regime_graded",
         "blocked_by": "graded regime calls (regime_accuracy)",
         "why_it_pays": "Every regime gate and override inherits this answer."},
        {"id": "Q005", "question": "Does the June-30 2%→2% profile survive round-trip fees forward (GEKKO is the probe)?",
         "classification": "CHANGING", "information_value": "HIGH",
         "evidence_needed": 35, "hook": "gekko_closed_trades",
         "blocked_by": "GEKKO closed round-trips",
         "why_it_pays": "Separates a real repeatable day from a survivorship story."},
        {"id": "Q006", "question": "Does FX's fee-to-target advantage hold on a REAL bid/ask practice feed?",
         "classification": "UNKNOWN", "information_value": "MED",
         "evidence_needed": 50, "hook": None,
         "blocked_by": "M0 FX feed not wired (pre-registered F0; no leverage ever)",
         "why_it_pays": "Cheapest venue theory in the backbone; aggressive books want it."},
        {"id": "Q007", "question": "Is the 8-pt / 1.5-h warmup enough live context to avoid falling-knife entries?",
         "classification": "UNKNOWN", "information_value": "MED",
         "evidence_needed": 30, "hook": "knife_cards",
         "blocked_by": "trade-quality cards on fresh-warmup entries",
         "why_it_pays": "Sets how aggressive cadence-proofing can safely get."},
    ]


def _seed_negative() -> List[Dict[str, Any]]:
    return [
        {"id": "N001", "finding": "Long momentum entries on this crypto universe LOSE",
         "classification": "KNOWN_FALSE", "evidence": "316-strategy arena, t = -14 on the momentum family",
         "proven": "2026-06", "note": "Permanent until a regime-conditioned retest says otherwise."},
        {"id": "N002", "finding": "Lifecycle states carry NO net entry edge",
         "classification": "KNOWN_FALSE", "evidence": "lifecycle OBSERVE study, 0-for gate; state-conditioned MR ≤ unconditioned net-of-fees",
         "proven": "2026-06"},
        {"id": "N003", "finding": "Composite scores built on stale daily windows buy nosedives",
         "classification": "KNOWN_FALSE", "evidence": "forensic post-mortem; fixed by fresh-window gating before any buy",
         "proven": "2026-06"},
        {"id": "N004", "finding": "A single external pinger is a reliable cadence source",
         "classification": "KNOWN_FALSE", "evidence": "50–66-min observed gaps starved the warmup gate for days",
         "proven": "2026-07", "note": "In-repo */10 fallback + cadence watchdog are the standing fix."},
    ]


def _seed_beliefs() -> List[Dict[str, Any]]:
    return [
        {"id": "B001", "belief": "Mean-reversion is the only positive edge here, marginal and cost-sensitive",
         "classification": "KNOWN_TRUE", "confidence": 0.7, "last_confirmed": "2026-06-30",
         "retest_after_days": 45, "evidence": "whole MR family green late-June; +$112 realized crypto book"},
        {"id": "B002", "belief": "Forward survivability is the only valid champion-selection criterion",
         "classification": "KNOWN_TRUE", "confidence": 0.8, "last_confirmed": "2026-07-06",
         "retest_after_days": 60, "evidence": "backtest-window champions decayed (surv 39 incident); OOS-consistent picks held"},
        {"id": "B003", "belief": "2% dips → 2% targets is the right SIDEWAYS crypto profile",
         "classification": "CHANGING", "confidence": 0.5, "last_confirmed": "2026-06-30",
         "retest_after_days": 21, "evidence": "one exceptional day (33/35); GEKKO forward record is the retest"},
    ]


# ─────────────────────────────────────────────────────────────────────────────
# LIVE EVIDENCE HOOKS — every tally below reads a REAL store, fully guarded.
# ─────────────────────────────────────────────────────────────────────────────
def _evidence(out: Path) -> Dict[str, int]:
    e: Dict[str, int] = {}
    cv = _load(out / "champion_validation.json") or {}
    try:
        rows = cv.get("strategies") or []
        decl = cv.get("declared_champion")
        row = next((r for r in rows if r.get("strategy") == decl), None) or {}
        e["champion_forward_trades"] = int(row.get("n") or 0)
    except Exception:
        e["champion_forward_trades"] = 0
    live = _load(out / "paper_sim_live.json") or {}
    try:
        e["stock_forward_trades"] = len((_load(out / "paper_book_stock.json") or {}).get("trades") or [])
    except Exception:
        e["stock_forward_trades"] = 0
    try:
        e["gekko_closed_trades"] = len((_load(out / "paper_book_aggressive.json") or {}).get("trades") or [])
    except Exception:
        e["gekko_closed_trades"] = 0
    ra = _load(out / "REGIME_ACCURACY.json") or {}
    e["regime_graded"] = int(ra.get("graded_total") or ra.get("graded") or
                             sum(int((v or {}).get("graded", 0)) for v in (ra.get("by_book") or {}).values())
                             if isinstance(ra.get("by_book"), dict) else 0)
    tq = _load(out / "TRADE_QUALITY.json") or {}
    try:
        cards = tq.get("cards") or tq.get("trades") or []
        e["knife_cards"] = len(cards) if isinstance(cards, list) else int(tq.get("count") or 0)
    except Exception:
        e["knife_cards"] = 0
    fg = _load(out / "FEATURE_GATES.json") or _load(out / "feature_gates.json") or {}
    try:
        rf = (fg.get("gates") or {}).get("rotation_freshness") or fg.get("rotation_freshness") or {}
        e["rotation_freshness_gate"] = int(rf.get("evidence") or rf.get("have") or 0)
    except Exception:
        e["rotation_freshness_gate"] = 0
    # utilization context for unknown-unknowns
    try:
        e["_open_by_book"] = {b: int((live.get(b) or {}).get("open_positions") or 0)
                              for b in ("crypto", "stock", "metal", "energy", "aggressive")}  # type: ignore[assignment]
    except Exception:
        e["_open_by_book"] = {}  # type: ignore[assignment]
    return e


def build_research_os(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    st = _load(out / STORE) or {}
    qs: List[Dict[str, Any]] = st.get("questions") or _seed_questions()
    neg: List[Dict[str, Any]] = st.get("negative_knowledge") or _seed_negative()
    bel: List[Dict[str, Any]] = st.get("beliefs") or _seed_beliefs()

    # append any NEW seed ids (upgrades never delete, never overwrite edits)
    have_ids = {q.get("id") for q in qs}
    qs += [q for q in _seed_questions() if q["id"] not in have_ids]
    have_ids = {n.get("id") for n in neg}
    neg += [n for n in _seed_negative() if n["id"] not in have_ids]
    have_ids = {b.get("id") for b in bel}
    bel += [b for b in _seed_beliefs() if b["id"] not in have_ids]

    ev = _evidence(out)
    now = _now()

    for q in qs:
        hook = q.get("hook")
        if hook and hook in ev:
            q["evidence_have"] = int(ev.get(hook) or 0)
        q.setdefault("evidence_have", 0)
        need = int(q.get("evidence_needed") or 0)
        q["debt"] = max(0, need - q["evidence_have"])
        q["status"] = ("ANSWER-READY" if need and q["evidence_have"] >= need
                       else ("ACCRUING" if q["evidence_have"] > 0 else "BLOCKED"))
        q["pct"] = round(100.0 * q["evidence_have"] / need, 1) if need else 0.0

    for b in bel:
        age = _days_since(b.get("last_confirmed", "")) or 0
        b["days_since_confirmed"] = age
        b["retest_required"] = bool(age > int(b.get("retest_after_days") or 9999))
        b["decay"] = "INCREASING" if b["retest_required"] else ("RISING" if age > (int(b.get("retest_after_days") or 9999) // 2) else "LOW")

    open_qs = [q for q in qs if q["status"] != "ANSWER-READY"]
    priorities = sorted(open_qs, key=lambda q: (VALUE_RANK.get(q.get("information_value", "LOW"), 3),
                                                -q.get("pct", 0.0)))
    top = priorities[0] if priorities else None

    opens = ev.get("_open_by_book") or {}
    least_tested = min(("crypto", "stock", "metal", "energy"),
                       key=lambda b: (ev.get(f"{b}_forward_trades", 0) if b == "stock"
                                      else (ev["champion_forward_trades"] if b == "crypto" else 0),
                                      opens.get(b, 0))) if opens else "metal"
    stalest = max(bel, key=lambda b: b.get("days_since_confirmed", 0)) if bel else None
    biggest_gap = max(open_qs, key=lambda q: q.get("debt", 0)) if open_qs else None

    unknown_unknowns = {
        "least_tested_market": least_tested,
        "stalest_belief": (stalest or {}).get("belief"),
        "stalest_belief_days": (stalest or {}).get("days_since_confirmed"),
        "biggest_evidence_gap": (biggest_gap or {}).get("question"),
        "biggest_gap_debt": (biggest_gap or {}).get("debt"),
        "uninstrumented_questions": [q["id"] for q in qs if not q.get("hook")],
        "note": "This panel is the roadmap-writer: fund whatever sits here.",
    }

    total_debt = sum(q.get("debt", 0) for q in qs)
    payload = {
        "generated_at": now.isoformat(),
        "doctrine": ("Research OS v1 — the machine now tracks what it does NOT know. "
                     "Questions accrue evidence from real stores; beliefs decay; "
                     "negative knowledge is permanent; priorities = expected information gain. "
                     "LONG-MEMORY: survives every wipe; ids append-only."),
        "questions": qs,
        "negative_knowledge": neg,
        "beliefs": bel,
        "priorities": [{"id": q["id"], "question": q["question"],
                        "value": q["information_value"], "have": q["evidence_have"],
                        "need": q["evidence_needed"], "status": q["status"]}
                       for q in priorities[:5]],
        "unknown_unknowns": unknown_unknowns,
        "research_debt_total": total_debt,
        "counts": {"questions": len(qs), "open": len(open_qs),
                   "answer_ready": len(qs) - len(open_qs),
                   "negative_knowledge": len(neg),
                   "beliefs_needing_retest": sum(1 for b in bel if b.get("retest_required"))},
        "summary": (f"{len(open_qs)}/{len(qs)} questions open · debt {total_debt} obs · "
                    f"top: {top['id'] if top else '—'} "
                    f"({top['evidence_have']}/{top['evidence_needed']})" if top else
                    f"{len(qs)} questions, all answer-ready"),
    }
    write_json_atomic(out / STORE, payload)
    return payload


if __name__ == "__main__":
    import sys
    r = build_research_os(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(r["summary"])
    for p in r["priorities"]:
        print(f"  {p['id']} [{p['value']}] {p['have']}/{p['need']} — {p['question'][:70]}")
