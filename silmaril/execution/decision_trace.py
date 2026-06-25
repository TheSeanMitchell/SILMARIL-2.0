"""
silmaril.execution.decision_trace — DECISION TRACE ENGINE (2.5.3). Explainability.

For each recent closed trade, reconstructs the decision chain: WHY entered (which champion,
what drop trigger, target/stop levels), WHY exited (target hit / stop hit / timeout), and the
outcome. Answers "why did this specific trade happen and end the way it did?" Emits
DECISION_TRACE.json. Measurement only.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from ._trade_helpers import closed_trades, _dt
from .atomic_io import write_json_atomic

def _now(): return datetime.now().astimezone().isoformat()
def _load(out, n):
    try: return json.loads((out / n).read_text())
    except Exception: return {}

def _classify_exit(tr):
    """Infer the exit reason from realized vs the strategy's target/stop."""
    r, tgt, stp = tr["realized_pct"], tr["target_pct"], tr["stop_pct"]
    if tgt is not None and r >= tgt * 0.98:
        return "TARGET_HIT", f"reached +{tgt}% take-profit"
    if stp is not None and r <= -stp * 0.98:
        return "STOP_HIT", f"hit -{stp}% stop-loss"
    if abs(r) < 0.15:
        return "TIMEOUT_FLAT", "held to max hold, never moved (weak setup)"
    if r > 0:
        return "TIMEOUT_GAIN", f"exited +{r}% on time/conditions before full target"
    return "TIMEOUT_LOSS", f"exited {r}% on time/conditions before stop"

def build_decision_trace(out_dir, limit: int = 200) -> Dict[str, Any]:
    out = Path(out_dir)
    trades = closed_trades(out)
    # most recent first by exit time
    trades = sorted(trades, key=lambda t: t["exit_t"] or "", reverse=True)[:limit]
    champs = {b: _load(out, f"champion_{b}.json").get("name") for b in ("crypto", "stock", "metal", "energy")}
    chains: List[Dict[str, Any]] = []
    for tr in trades:
        cls, why = _classify_exit(tr)
        et, xt = _dt(tr["entry_t"]), _dt(tr["exit_t"])
        hold_min = round((xt - et).total_seconds() / 60) if (et and xt) else None
        chains.append({
            "sym": tr["sym"], "book": tr["book"], "strategy": tr["strategy"],
            "is_book_champion": tr["strategy"] == champs.get(tr["book"]),
            "entry": {
                "price": tr["entry"], "at": tr["entry_t"],
                "why": (f"{tr['strategy']} fired: price dropped enough to trigger a mean-reversion "
                        f"entry; target +{tr['target_pct']}%, stop -{tr['stop_pct']}%"),
            },
            "exit": {
                "price": tr["exit"], "at": tr["exit_t"], "hold_min": hold_min,
                "realized_pct": tr["realized_pct"], "reason": cls, "why": why,
            },
            "outcome": "WIN" if tr["realized_pct"] > 0 else ("FLAT" if abs(tr["realized_pct"]) < 0.15 else "LOSS"),
        })
    # summary of exit reasons (the actionable part)
    reasons: Dict[str, int] = {}
    for c in chains:
        reasons[c["exit"]["reason"]] = reasons.get(c["exit"]["reason"], 0) + 1
    payload = {
        "generated_at": _now(), "n_traces": len(chains),
        "exit_reason_breakdown": reasons, "traces": chains,
        "what": "Per-trade decision chain: why entered, why exited, outcome.",
        "why": "Makes every trade auditable end-to-end instead of a bare P&L line.",
        "action": ("If TIMEOUT_GAIN dominates, exits fire before target = leaving edge on the table "
                   "(matches the EARLY_EXIT forensics finding)."),
        "note": "Exit reason inferred from realized vs target/stop (no stored per-trade exit tag yet).",
    }
    try: write_json_atomic(out / "DECISION_TRACE.json", payload)
    except Exception: pass
    return payload
