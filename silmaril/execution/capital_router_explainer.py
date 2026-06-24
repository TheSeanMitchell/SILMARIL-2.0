"""
silmaril.execution.capital_router_explainer — CAPITAL ROUTER EXPLAINER (2.5.3).

Surfaces the math already computed in capital_allocation.json (allocation weights +
allocation_proof) in plain language: how much each strategy gets, WHY (survivability/edge),
and whether concentrating on the champion actually helps vs equal-weight. Emits
CAPITAL_ROUTER_EXPLAINED.json. Explainability only — does not change allocation.

IMPORTANT: this is RESEARCH on how a SINGLE hypothetical $10k would split across the top
crypto strategies. It is NOT how the four books trade — crypto/stock/metal/energy are each
their own independent $10k. This panel is clearly labelled as hypothetical.
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from .atomic_io import write_json_atomic

def _now(): return datetime.now().astimezone().isoformat()
def _load(out, n):
    try: return json.loads((out / n).read_text())
    except Exception: return {}

def build_capital_router_explainer(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    ca = _load(out, "capital_allocation.json")
    surv = _load(out, "champion_validation.json")
    surv_by = {}
    for row in (surv.get("strategies") or surv.get("results") or []):
        nm = row.get("name") or row.get("strategy")
        if nm: surv_by[nm] = row.get("survivability") or row.get("score")
    alloc = ca.get("allocation", {}) or {}
    books = ca.get("books", {}) or {}
    proof = ca.get("allocation_proof", {}) or {}
    lines = []
    for strat, w in sorted(alloc.items(), key=lambda kv: kv[1], reverse=True):
        b = books.get(strat, {})
        lines.append({
            "strategy": strat, "weight_pct": round(w * 100, 1),
            "allocated": b.get("allocated"), "realized_pnl": b.get("realized_pnl"),
            "survivability": surv_by.get(strat),
            "why": (f"weight {round(w*100,1)}% — higher survivability/edge strategies get a larger "
                    f"share of the hypothetical pool"),
        })
    payload = {
        "generated_at": _now(),
        "total_capital_hypothetical": ca.get("total_capital", 10000.0),
        "allocations": lines,
        "concentrating_helps": proof.get("concentrating_on_champion_helps"),
        "champion_weighted_edge_pct": proof.get("champion_weighted_edge_per_trade_pct"),
        "equal_weighted_edge_pct": proof.get("equal_weighted_edge_per_trade_pct"),
        "verdict": ("Concentrating on the champion beats equal-weight"
                    if proof.get("concentrating_on_champion_helps")
                    else "Equal-weight is as good as concentrating — edge is thin"),
        "what": "How a single hypothetical $10k would split across the top strategies, and why.",
        "why": "Shows the allocation is survivability/edge-driven, not arbitrary.",
        "important": ("HYPOTHETICAL research only. The four books (crypto/stock/metal/energy) each "
                      "trade their OWN independent $10k — they are NOT pooled. Single-account routing "
                      "is an endgame idea, not current behavior."),
    }
    try: write_json_atomic(out / "CAPITAL_ROUTER_EXPLAINED.json", payload)
    except Exception: pass
    return payload
