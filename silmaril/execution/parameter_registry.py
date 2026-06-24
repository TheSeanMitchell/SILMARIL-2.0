"""
silmaril.execution.parameter_registry — UNIFIED PARAMETER-CHAMPION REGISTRY (2.5.4).

ONE place that shows every rotating-champion parameter the system elects on each daily run:
strategy, drop threshold, bounce-back target, the drop×bounce combo, and the hold-timer — each
with its current champion, challenger, what it's optimized for, a short leaderboard, rotation
status, and a health flag so a human OR an AI can verify at a glance that each is alive and
sensible. Adding a new parameter later = add one small reader function to PARAM_READERS.
Emits PARAMETER_REGISTRY.json. Measurement/observability — does not itself change behavior.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from .atomic_io import write_json_atomic

def _now(): return datetime.now(timezone.utc).isoformat()
def _load(out, n):
    try: return json.loads((out / n).read_text())
    except Exception: return {}

def _entry(parameter, champion, challenger, optimized_for, metric, leaderboard, status, source, rotates="every daily run"):
    # health: green if we have a champion + a non-trivial leaderboard; yellow if champion only; red if none
    if champion in (None, "", "—"):
        health = "RED"; note = "no champion elected yet (data-gated or no signals)"
    elif leaderboard and len(leaderboard) >= 2:
        health = "GREEN"; note = "electing from a live leaderboard"
    else:
        health = "YELLOW"; note = "champion present, thin leaderboard"
    return {"parameter": parameter, "champion": champion, "challenger": challenger,
            "optimized_for": optimized_for, "metric_value": metric,
            "leaderboard": leaderboard or [], "status": status, "health": health,
            "health_note": note, "rotates": rotates, "source": source}

def build_parameter_registry(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    gov = _load(out, "CHAMPION_GOVERNANCE.json")
    thr = _load(out, "THRESHOLD_CHAMPION.json")
    tim = _load(out, "TIMER_OPTIMIZATION.json")
    entries: List[Dict[str, Any]] = []

    # 1) Strategy champion (from governance)
    dc = gov.get("declared_champion") or {}
    ladder = gov.get("promotion_ladder") or {}
    inc = ladder.get("Incubation") or ladder.get("Candidate") or []
    challenger = next((x for x in inc if x != dc.get("strategy") and str(x).startswith("MR")), None)
    entries.append(_entry(
        "Strategy", dc.get("strategy"), challenger, "forward survivability",
        dc.get("survivability_score"),
        [{"value": s, "note": ""} for grp in ("Production", "Candidate", "Incubation") for s in (ladder.get(grp) or []) if str(s).startswith("MR")][:5],
        gov.get("governance_status", "—"), "CHAMPION_GOVERNANCE.json"))

    # 2) Drop threshold champion
    combo = thr.get("champion_combo") or {}
    grid = thr.get("grid") or []
    entries.append(_entry(
        "Drop threshold", (str(thr.get("champion_drop_pct")) + "%") if thr.get("champion_drop_pct") is not None else None,
        (str(thr.get("accuracy_champion_combo", {}).get("drop")) + "%") if thr.get("accuracy_champion_combo") else None,
        "expectancy across bounce targets", combo.get("expectancy_pct"),
        [{"value": f"{g['drop']}%", "note": f"exp {g['expectancy_pct']}% · hit {g['hit_rate_pct']}%"} for g in grid[:5]],
        "ROTATING (crypto)", "THRESHOLD_CHAMPION.json"))

    # 3) Bounce-back target champion
    entries.append(_entry(
        "Bounce-back target", (str(thr.get("champion_bounce_pct")) + "%") if thr.get("champion_bounce_pct") is not None else None,
        (str(thr.get("accuracy_champion_combo", {}).get("bounce")) + "%") if thr.get("accuracy_champion_combo") else None,
        "expectancy across drop triggers", combo.get("bounce"),
        [{"value": f"{g['bounce']}%", "note": f"exp {g['expectancy_pct']}% · hit {g['hit_rate_pct']}%"} for g in grid[:5]],
        "ROTATING (crypto)", "THRESHOLD_CHAMPION.json"))

    # 4) Drop x Bounce COMBO champion (the headline)
    acc = thr.get("accuracy_champion_combo") or {}
    entries.append(_entry(
        "Drop×Bounce combo",
        (f"drop {combo['drop']}% → target {combo['bounce']}%") if combo else None,
        (f"drop {acc['drop']}% → target {acc['bounce']}% (accuracy)") if acc else None,
        "best expectancy combo", combo.get("expectancy_pct"),
        [{"value": f"{g['drop']}%→{g['bounce']}%", "note": f"exp {g['expectancy_pct']}% · hit {g['hit_rate_pct']}% · n={g['signals']}"} for g in grid[:5]],
        "ROTATING (crypto)", "THRESHOLD_CHAMPION.json"))

    # 5) Hold-timer champion (per book; surface crypto headline + note others gated)
    tbooks = tim.get("by_book") or {}
    cryp = tbooks.get("crypto") or {}
    opt = cryp.get("optimal_timeout_min")
    lb = []
    for k, d in (cryp.get("by_timeout") or {}).items():
        lb.append({"value": ("no timer" if k == "none" else k + "m"), "note": f"avg {d['avg_realized_pct']}% · win {d['win_pct']}%"})
    lb = sorted(lb, key=lambda x: float(x["note"].split("avg ")[1].split("%")[0]), reverse=True)[:5]
    gated = [b for b in ("stock", "metal", "energy") if b not in tbooks]
    entries.append(_entry(
        "Hold-timer", ("no timer" if (opt is None and cryp) else (str(opt) + " min" if opt else None)),
        None, "edge captured per trade", cryp.get("optimal_avg_realized_pct"),
        lb, "ROTATING (crypto)" + (f" · {','.join(gated)} data-gated" if gated else ""), "TIMER_OPTIMIZATION.json"))

    greens = sum(1 for e in entries if e["health"] == "GREEN")
    payload = {
        "generated_at": _now(),
        "parameters": entries,
        "summary": f"{len(entries)} champion-elected parameters · {greens} GREEN",
        "how_to_extend": ("Add a new rotating parameter by appending one reader here that returns "
                          "_entry(...). It then shows up in this registry and its panel automatically."),
        "what": "Every parameter SILMARIL elects a champion for on each daily run, in one view.",
        "why": "So a human or an AI can verify at a glance that each champion is alive, sensible, and rotating.",
        "note": ("Observability layer. Each parameter's election logic lives in its own engine; this "
                 "just unifies them. Health: GREEN = electing from a live leaderboard, YELLOW = thin, "
                 "RED = none yet (data-gated)."),
    }
    try: write_json_atomic(out / "PARAMETER_REGISTRY.json", payload)
    except Exception: pass
    return payload
