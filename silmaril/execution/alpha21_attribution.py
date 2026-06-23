"""
silmaril.execution.alpha21_attribution — ALPHA 2.1 ATTRIBUTION & LEARNING.

This is the keystone of the Alpha 2.1 mandate: make SILMARIL answer, AUTOMATICALLY
and without human investigation, the eight questions that decide whether the
system can convert discovery into realized profit:

  1. Which agents create profit?          5. Where does profit leak after discovery?
  2. Which agents destroy profit?          6. Why is capital idle?
  3. Which opportunities were missed?      7. Why are winners exited?
  4. Why were they missed?                 8. Why are losers retained?

It does NOT add a new signal, agent, predictor, or dashboard (the phase lock). It
reads the measurement frameworks that already exist — agent_scorecard.json,
scoring.json, trade_forensics.json, edge_capture.json, missed_opportunity.json,
and the live account states — and emits ONE answer surface: alpha21_attribution.json.

Crucially it also closes the LEARNING side: it verifies whether the agent weight
multipliers actually track realized edge (Measure -> Learn), and it emits a
grade-derived `recommended_agent_weights` block the engine can consume to ADJUST
(Learn -> Adjust). Passive reporting is not enough; the adjustment is produced.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

VERSION = "alpha21-attribution-1.0"

# How many clean samples before an agent's realized edge is trusted.
MIN_SAMPLES_FOR_TRUST = 15
# Grade -> recommended influence multiplier (the ADJUST arm of the loop).
GRADE_WEIGHT = {"A": 1.30, "B": 1.10, "C": 1.00, "D": 0.80, "F": 0.55}
# A trade closed faster than this is flagged as churn (the operator's "buy then
# sell 15 minutes later" pattern).
CHURN_MINUTES = 30.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _mins(a: Optional[str], b: Optional[str]) -> Optional[float]:
    try:
        return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 60.0
    except Exception:
        return None


def build_alpha21_attribution(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)

    scorecard = _load(out / "agent_scorecard.json", {})
    scoring = _load(out / "scoring.json", {})
    forensics = _load(out / "trade_forensics.json", {})
    edge = _load(out / "edge_capture.json", {})
    missed = _load(out / "missed_opportunity.json", {})

    # ── Q1 / Q2 — which agents create vs destroy profit ──────────────────────
    grades = {c.get("agent"): c for c in (scorecard.get("cards") or [])}
    # realized return per agent from the scored outcomes
    per_agent: Dict[str, Dict[str, Any]] = {}
    for o in (scoring.get("outcomes") or []):
        a = o.get("agent")
        if not a:
            continue
        r = o.get("return_pct")
        if r is None:
            continue
        d = per_agent.setdefault(a, {"returns": [], "wins": 0, "n": 0})
        d["returns"].append(float(r))
        d["n"] += 1
        if float(r) > 0:
            d["wins"] += 1

    agent_rows = []
    for a, d in per_agent.items():
        n = d["n"]
        mean_ret = round(sum(d["returns"]) / n, 4) if n else 0.0
        card = grades.get(a) or {}
        agent_rows.append({
            "agent": a,
            "grade": card.get("grade"),
            "verdict": card.get("verdict"),
            "mean_return_pct": mean_ret,
            "win_rate": round(d["wins"] / n, 3) if n else 0.0,
            "samples": n,
            "trusted": n >= MIN_SAMPLES_FOR_TRUST,
        })
    agent_rows.sort(key=lambda r: r["mean_return_pct"], reverse=True)

    profit_makers = [r for r in agent_rows
                     if r["trusted"] and (r["grade"] in ("A", "B") or r["mean_return_pct"] > 0)]
    profit_destroyers = [r for r in agent_rows
                         if r["trusted"] and (r["grade"] in ("D", "F") or r["mean_return_pct"] < 0)]

    # ── Q3 / Q4 — which opportunities were missed, and why (classified) ──────
    CAUSE_TO_FAILURE = {
        "not_on_alpaca": "EXECUTION_FAILURE",          # broker can't trade it
        "exited_too_early": "EXIT_FAILURE",
        "exited_at_loss_on_up_move": "EXIT_FAILURE",
        "filter_rejected": "RANKING_FAILURE",
        "below_ranking_cutoff": "RANKING_FAILURE",
        "never_surfaced": "DISCOVERY_FAILURE",
        "not_discovered": "DISCOVERY_FAILURE",
        "harvest_missed": "HARVEST_FAILURE",
    }
    miss_by_failure: Dict[str, int] = {}
    missed_examples: Dict[str, List[str]] = {}
    for m in (missed.get("misses") or []):
        cause = m.get("cause") or "unknown"
        ftype = CAUSE_TO_FAILURE.get(cause, "DISCOVERY_FAILURE")
        miss_by_failure[ftype] = miss_by_failure.get(ftype, 0) + 1
        missed_examples.setdefault(ftype, [])
        if len(missed_examples[ftype]) < 6:
            missed_examples[ftype].append(m.get("ticker"))

    # ── Q5 — where profit leaks AFTER discovery (edge + churn + exits) ───────
    e_sum = edge.get("summary") or {}
    # real attribution fallback: when the live accounts have no trades, use the
    # paper sim's actual numbers so these metrics are NEVER null (2.12 mandate).
    try:
        _sim_attrib = json.loads((Path(out_dir) / "capital_allocation.json")
                                 .read_text()).get("attribution_no_nulls", {})
    except Exception:
        _sim_attrib = {}
    winners = forensics.get("biggest_winners") or []
    losers = forensics.get("biggest_losers") or []
    win_holds = [h for h in (_mins(w.get("entry_ts"), w.get("exit_ts")) for w in winners) if h is not None]
    loss_holds = [h for h in (_mins(l.get("entry_ts"), l.get("exit_ts")) for l in losers) if h is not None]
    all_holds = win_holds + loss_holds
    churn_share = (round(sum(1 for h in all_holds if h < CHURN_MINUTES) / len(all_holds), 3)
                   if all_holds else None)

    # ── Q6 — why is capital idle (deployment audit per account) ─────────────
    deployment = []
    for acc_file, label in [("alpaca_paper_state", "LEGACY"),
                            ("alpaca_h3_state", "HARVEST_3"),
                            ("alpaca_h5_state", "HARVEST_5")]:
        st = _load(out / f"{acc_file}.json", {})
        acct = st.get("account") or {}
        equity = float(acct.get("equity") or 0)
        cash = float(acct.get("cash") or 0)
        held = max(0.0, equity - cash)
        deploy_pct = round(held / equity * 100, 1) if equity else 0.0
        pa = st.get("policy_applied") or {}
        if pa.get("hard_stop_halt"):
            reason = "drawdown halt — opens blocked/throttled (see recovery mode)"
        elif deploy_pct < 25:
            reason = "few names cleared the gates (fresh-gate / confirmation / cooldown) this cycle"
        else:
            reason = "deployed"
        deployment.append({
            "account": label,
            "equity": round(equity, 2),
            "held_capital": round(held, 2),
            "idle_capital": round(cash, 2),
            "deployed_pct": deploy_pct,
            "idle_reason": reason,
        })

    # ── Q7 / Q8 — why winners exited / why losers retained ──────────────────
    med_win_hold = round(median(win_holds), 1) if win_holds else None
    med_loss_hold = round(median(loss_holds), 1) if loss_holds else None
    mean_win_pct = round(sum(w.get("realized_pct", 0) for w in winners) / len(winners), 2) if winners else None
    asymmetry = None
    if med_win_hold is not None and med_loss_hold is not None:
        asymmetry = ("losers held LONGER than winners — the system lets losers run "
                     "and cuts winners short" if med_loss_hold > med_win_hold
                     else "winners and losers held similar time")

    # ── LEARNING LOOP — does realized edge drive agent weight? + ADJUST ──────
    score_summary = scoring.get("summary") or {}
    weight_by_agent: Dict[str, float] = {}
    _src = score_summary.get("leaderboard") if isinstance(score_summary, dict) else None
    if isinstance(_src, list):
        for r in _src:
            if r.get("agent") is not None and r.get("weight_multiplier") is not None:
                weight_by_agent[r["agent"]] = float(r["weight_multiplier"])
    # recommended weights from realized-edge GRADE (the Adjust arm)
    recommended = {}
    for a, card in grades.items():
        g = card.get("grade")
        if g in GRADE_WEIGHT:
            recommended[a] = {
                "grade": g,
                "current_weight": weight_by_agent.get(a),
                "recommended_weight": GRADE_WEIGHT[g],
            }
    # is the loop effective? compare A-graders vs F-graders' current weights
    a_w = [weight_by_agent[a] for a, c in grades.items()
           if c.get("grade") == "A" and a in weight_by_agent]
    f_w = [weight_by_agent[a] for a, c in grades.items()
           if c.get("grade") == "F" and a in weight_by_agent]
    if a_w and f_w:
        loop_status = ("EFFECTIVE: Grade-A agents carry more weight than Grade-F"
                       if (sum(a_w) / len(a_w)) > (sum(f_w) / len(f_w))
                       else "INEFFECTIVE: Grade-A agents do NOT outweigh Grade-F — wire recommended_agent_weights")
    else:
        loop_status = "UNVERIFIED: not enough graded agents have a recorded weight yet"

    payload = {
        "version": VERSION,
        "generated_at": _now(),
        "answers": {
            "q1_agents_that_create_profit": [r["agent"] for r in profit_makers[:10]],
            "q2_agents_that_destroy_profit": [r["agent"] for r in profit_destroyers[:10]],
            "q3_opportunities_missed": (missed.get("summary") or {}).get("total_misses"),
            "q4_why_missed_by_failure_type": miss_by_failure,
            "q5_profit_leak_after_discovery": {
                "held_edge_capture_pct": (e_sum.get("avg_edge_capture_pct")
                    if e_sum.get("avg_edge_capture_pct") is not None
                    else _sim_attrib.get("held_edge_capture_pct", 0.0)),
                "reachable_edge_capture_pct": e_sum.get("reachable_edge_capture_pct") or 0.0,
                "alpaca_reachable_pct": e_sum.get("alpaca_reachable_pct") or 0.0,
                "median_hold_minutes": (round(median(all_holds), 1) if all_holds
                    else _sim_attrib.get("median_hold_minutes", 0.0)),
                "share_of_trades_churned_under_30min": (churn_share
                    if churn_share is not None
                    else _sim_attrib.get("share_churned_under_30min", 0.0)),
                "attribution_source": ("live_accounts" if all_holds else
                    "paper_sim (live accounts have no trades this window)"),
                "diagnosis": ("leak is dominated by CHURN — trades round-trip in minutes; "
                              "winners are not given time to run"
                              if churn_share and churn_share >= 0.5
                              else "leak spread across entry quality and capture"),
            },
            "q6_why_capital_idle": deployment,
            "q7_why_winners_exited": {
                "median_winner_hold_minutes": med_win_hold,
                "mean_winner_realized_pct": mean_win_pct,
                "finding": (f"winners exited at ~{mean_win_pct}% after only "
                            f"{med_win_hold} min median — taken off too early"
                            if med_win_hold is not None else "insufficient data"),
            },
            "q8_why_losers_retained": {
                "median_loser_hold_minutes": med_loss_hold,
                "asymmetry": asymmetry,
            },
        },
        "agent_attribution": agent_rows,
        "missed_examples_by_failure": missed_examples,
        "learning_loop": {
            "status": loop_status,
            "recommended_agent_weights": recommended,
            "note": ("Grade-derived weights are the ADJUST arm. Wire these into "
                     "cli.py's weight_lookup to close Measure->Learn->Adjust."),
        },
    }

    try:
        (out / "alpha21_attribution.json").write_text(json.dumps(payload, indent=2))
    except Exception as e:
        payload["_write_error"] = str(e)
    return payload


if __name__ == "__main__":
    import sys
    p = build_alpha21_attribution(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(json.dumps(p["answers"], indent=2))
