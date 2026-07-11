"""conductor_c1.py — 5.1: the Conductor's second rung, built exactly as the
backbone specified: C1 = counterfactual shadow scoring of candidate meta-policies
against the C0 ledger. Pure math, ZERO behavior change; C2 (ε-explore on GEKKO)
and C3 (gated influence) stay locked behind their own evidence gates.

Method, stated honestly: C0 logs status-quo only (propensity 1.0), so true
off-policy estimates are impossible. What CAN be computed truthfully is the
matched-subset comparison: for each candidate policy, score only the cycles
where the policy's chosen action EQUALS what actually happened, using the real
next-cycle equity delta as the outcome. That yields "when conditions matched
this policy's prescription, here is what reality paid" — a coverage-weighted
prior, clearly labeled, never a causal claim. The C2 rung exists precisely to
buy the exploration this method cannot.

Gate: 300 logged decisions with computable outcomes. Below the gate it reports
progress and defines the candidates so the architecture is complete either way.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .atomic_io import write_json_atomic

GATE = 300
STORE = "CONDUCTOR_C1.json"
LEDGER = "CONDUCTOR_LEDGER.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_ledger(out: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    p = out / LEDGER
    if not p.exists():
        return rows
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


# ---- candidate policies (each with pre-registered death, Law 15) ----------
def _p_status_quo(ctx: Dict[str, Any]) -> str:
    return "deploy"


def _p_sit_out_downtrend(ctx: Dict[str, Any]) -> str:
    regs = (ctx.get("regimes") or {})
    return "sit_out" if any(v == "DOWNTREND" for v in regs.values()) else "deploy"


def _p_sideways_only(ctx: Dict[str, Any]) -> str:
    regs = (ctx.get("regimes") or {})
    cr = regs.get("crypto")
    return "deploy" if cr in (None, "SIDEWAYS") else "sit_out"


POLICIES = [
    {"id": "P0_status_quo", "fn": _p_status_quo,
     "what": "always deploy per current rules (the baseline — by construction matches every cycle)",
     "kill": "n/a — baseline"},
    {"id": "P1_sit_out_downtrend", "fn": _p_sit_out_downtrend,
     "what": "SIT OUT any cycle where any book reads DOWNTREND; otherwise status quo",
     "kill": "dies if matched-subset mean ≤ baseline mean after 150 matched cycles"},
    {"id": "P2_sideways_only", "fn": _p_sideways_only,
     "what": "deploy only while crypto regime is SIDEWAYS (the MR home field)",
     "kill": "dies if matched-subset mean ≤ baseline mean after 150 matched cycles"},
]


def _ctx_of(row: Dict[str, Any]) -> Dict[str, Any]:
    # real C0 row shape: {"t","session","books":{bk:{"regime","eq",...}}}
    books = row.get("books") or (row.get("context") or {}).get("books") or {}
    regimes = {bk: (v or {}).get("regime")
               for bk, v in books.items()
               if bk in ("crypto", "stock", "metal", "energy") and isinstance(v, dict)}
    if not regimes:  # tolerate any legacy shape
        c = row.get("context") or row
        regimes = {bk: (c.get(bk) or {}).get("regime")
                   for bk in ("crypto", "stock", "metal", "energy")
                   if isinstance(c.get(bk), dict)}
    return {"regimes": regimes}


def _equity_of(row: Dict[str, Any]) -> Optional[float]:
    # real C0 rows carry per-book "eq" under row["books"] (governed books only —
    # GEKKO stays out of the Master's math here too)
    books = row.get("books") or (row.get("context") or {}).get("books") or {}
    s = 0.0
    seen = False
    for bk in ("crypto", "stock", "metal", "energy"):
        v = books.get(bk)
        if isinstance(v, dict):
            e = v.get("eq", v.get("equity"))
            if isinstance(e, (int, float)):
                s += float(e)
                seen = True
    if seen:
        return s
    c = row.get("context") or row
    tot = c.get("total_equity") or c.get("combined_equity")
    return float(tot) if isinstance(tot, (int, float)) else None


def build_conductor_c1(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    rows = _load_ledger(out)
    # pair consecutive rows → (context, realized next-cycle delta in bps)
    samples = []
    for a, b in zip(rows, rows[1:]):
        ea, eb = _equity_of(a), _equity_of(b)
        if ea and eb and ea > 0:
            samples.append({"ctx": _ctx_of(a), "delta_bps": (eb / ea - 1.0) * 10000.0})
    n = len(samples)
    payload: Dict[str, Any] = {
        "generated_at": _now(),
        "rung": "C1 — shadow scoring (zero behavior change; C2/C3 remain evidence-locked)",
        "gate": {"need": GATE, "have": n, "open": n >= GATE},
        "method_honesty": ("matched-subset scoring on a propensity-1.0 log: each policy is graded "
                           "ONLY on cycles where its prescription equals what actually ran. This is a "
                           "coverage-weighted prior, NOT a causal uplift — C2's ε-exploration on GEKKO "
                           "is what buys real counterfactuals."),
        "policies": [],
    }
    base_mean = (sum(s["delta_bps"] for s in samples) / n) if n else None
    for pol in POLICIES:
        matched = [s["delta_bps"] for s in samples if pol["fn"](s["ctx"]) == "deploy"]
        m = len(matched)
        row = {"id": pol["id"], "what": pol["what"], "kill_criterion": pol["kill"],
               "matched_cycles": m,
               "coverage_pct": round(m / n * 100, 1) if n else None,
               "matched_mean_bps": round(sum(matched) / m, 2) if m else None,
               "baseline_mean_bps": round(base_mean, 2) if base_mean is not None else None,
               "read": None}
        if n < GATE:
            row["read"] = f"gate not open — {n}/{GATE} scored decisions"
        elif not m:
            row["read"] = "never matched — no honest read"
        else:
            edge = row["matched_mean_bps"] - row["baseline_mean_bps"]
            row["read"] = (f"matched cycles paid {edge:+.2f} bps vs baseline "
                           f"(prior only — awaits C2 exploration)")
        payload["policies"].append(row)
    write_json_atomic(out / STORE, payload)
    return {"summary": f"C1 {'OPEN' if n >= GATE else 'gate'} · {n}/{GATE} scored · "
                       f"{len(POLICIES)} shadow policies"}
