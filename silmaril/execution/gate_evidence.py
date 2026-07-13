"""gate_evidence.py — 5.1: the experimental-gates board finally counts REAL
evidence. The gates table showed "evidence 0/60" forever because nothing
tallied the observations the stores were already accumulating. This module
runs at the end of the spine, computes each gate's evidence from its actual
source store, and rewrites FEATURE_GATES_STATUS.json with honest counts.

Status policy (unchanged doctrine): everything stays OBSERVE except
heatshield_autotune, which may read WEIGHTED **only** when the paper_sim floor
resolver is actually applying the measured winner (see heatshield knob) — the
one gate the operator explicitly asked to make actionable, flipped by
evidence, bounded, reversible.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .atomic_io import write_json_atomic

STORE = "FEATURE_GATES_STATUS.json"


def _j(out: Path, name: str):
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return None


def _count_trades(d, book=None) -> int:
    if not isinstance(d, dict):
        return 0
    n = 0
    for bk, v in (d.items() if book is None else [(book, d.get(book))]):
        if isinstance(v, dict) and isinstance(v.get("trades"), list):
            n += len([t for t in v["trades"] if t.get("side") == "SELL"])
    return n


def build_gate_evidence(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    g = _j(out, STORE) or {}
    gates = g.get("gates")
    if not isinstance(gates, dict):
        gates = {}
        g["gates"] = gates

    hs = _j(out, "HEATSHIELD.json") or {}
    trace = _j(out, "DECISION_TRACE.json") or {}
    ra = _j(out, "REGIME_ACCURACY.json") or {}
    news = _j(out, "NEWS_TRIAL_STATUS.json") or {}
    ab = _j(out, "REGIME_AB.json") or {}
    tl = _j(out, "CHAMPION_TIMELINE.json") or {}
    sim = _j(out, "paper_sim_live.json") or {}
    dr = _j(out, "dr_strange.json") or {}

    fits = 0
    styled = 0
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        for p in (sim.get(bk) or {}).get("positions", []) or []:
            if p.get("target") is not None:
                fits += 1
            if p.get("style"):
                styled += 1
    traces = trace.get("traces") or []
    ab_obs = len(ab.get("observations") or ab.get("rows") or []) if isinstance(ab, dict) else 0
    graded = sum(int((v or {}).get("graded") or 0) for v in (ra.get("books") or {}).values())
    hs_n = int((hs.get("heatshield") or {}).get("trades") or hs.get("trades") or 0) or \
        int(hs.get("tight_stop", {}).get("trades", 0) if isinstance(hs.get("tight_stop"), dict) else 0)
    reigns = len(tl.get("reigns") or [])

    evidence = {
        "news_signals": (int(news.get("scored") or news.get("logged") or 0), 60,
                         "shadow hit-rate beats coin-flip at p<0.05 over min samples"),
        "dr_strange": (int(((dr.get("career") or {}).get("resolved")) or 0), 50,
                       "projection direction beats baseline drift over min samples \u00b7 live hit-rate %s%% on %s resolved"
                       % (round(float((dr.get("career") or {}).get("hit_rate") or 0) * 100, 1),
                          int((dr.get("career") or {}).get("resolved") or 0))),
        "lifecycle": (len(traces), 50, "state-conditioned MR beats unconditioned MR net-of-fees"),
        "fingerprint_weighting": (fits, 50, "fingerprint-ranked entries out-earn conviction-ranked entries"),
        "regime_conditioning": (ab_obs, 40, "regime-conditioned entries beat unconditioned net-of-fees (REGIME_AB proof)"),
        "style_switching": (styled, 40, "style-tagged entries (trend vs range) show a win-rate split worth acting on"),
        "heatshield_autotune": (hs_n, 60, "measured floor variant beats the alternative on forward trades"),
        "stock_news_ranking": (int(news.get("stock_ranked") or 0), 60, "news-ranked blue-chip entries beat trajectory-only entries"),
        "rotation_freshness": (reigns, 20, "faster champion rotation beats sticky rotation on realized P&L"),
    }

    hs_applied = bool(hs.get("autotune_applied"))
    for name, (have, need, what) in evidence.items():
        row = gates.get(name) if isinstance(gates.get(name), dict) else {}
        row.update({
            "status": ("WEIGHTED" if (name == "heatshield_autotune" and hs_applied and have >= need)
                       else row.get("status") or "OBSERVE"),
            "evidence_have": int(have),
            "evidence_need": int(need),
            "what_it_must_prove": what,
            "evidence_source": "real stores, tallied every cycle (5.1 gate_evidence)",
        })
        gates[name] = row

    g["generated_at"] = datetime.now(timezone.utc).isoformat()
    g["note"] = ("evidence counts are REAL tallies from the named stores; statuses flip only on their "
                 "stated proof, never on count alone (heatshield_autotune is the one live exception, "
                 "operator-directed, bounded, reversible via knob)")
    write_json_atomic(out / STORE, g)
    weighted = [k for k, v in gates.items() if v.get("status") == "WEIGHTED"]
    return {"summary": f"gates: {len(gates)} tallied · weighted: {', '.join(weighted) or 'none'}"}
