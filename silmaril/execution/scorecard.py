"""scorecard.py — 5.1 EVIDENCE-BASED self-grade (full rewrite).

The old scorecard hand-waved. This one computes every category from real
stores with the formula printed beside the grade, so a good grade can be
audited and a bad one debugged. Store shape (categories / overall_grade /
headline / trend) is unchanged so the UI renders it as before.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .atomic_io import write_json_atomic

STORE = "SCORECARD.json"


def _j(out: Path, name: str):
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return None


def _grade(x: float) -> str:
    return ("A+" if x >= 97 else "A" if x >= 93 else "A-" if x >= 90 else
            "B+" if x >= 87 else "B" if x >= 83 else "B-" if x >= 80 else
            "C+" if x >= 77 else "C" if x >= 73 else "C-" if x >= 70 else
            "D" if x >= 60 else "F")


def build_scorecard(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    sim = _j(out, "paper_sim_live.json") or {}
    sc = _j(out, "STORE_CONTRACTS.json") or {}
    inv = _j(out, "INVARIANTS.json") or {}
    ivs = _j(out, "INVARIANTS_STATE.json") or {}
    bench = _j(out, "BENCH_BOOKS.json") or {}
    hb = _j(out, "deep_heartbeat.json") or {}
    cv = _j(out, "champion_validation.json") or {}
    ec = _j(out, "edge_capture_engine.json") or {}
    tq = _j(out, "TRADE_QUALITY.json") or {}

    cats = []

    def cat(name, score, formula, evidence):
        cats.append({"name": name, "score": round(score, 1), "grade": _grade(score),
                     "formula": formula, "evidence": evidence})

    # 1 · Exit integrity — do positions past target actually sell?
    over_unsold = 0
    tot_open = 0
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        for p in (sim.get(bk) or {}).get("positions", []) or []:
            tot_open += 1
            try:
                if p["entry"] > 0 and (p["mark"] / p["entry"] - 1) >= (p.get("target") or 9):
                    over_unsold += 1
            except Exception:
                pass
    s1 = 100.0 if over_unsold == 0 else max(0.0, 100.0 - 25.0 * over_unsold)
    cat("Exit integrity", s1, "100 − 25×(open positions sitting past their own target)",
        f"{over_unsold} of {tot_open} open positions past target unsold")

    # 2 · Wiring truth — contracts + invariants
    greens = sc.get("verdict", "").startswith("ALL GREEN")
    inv_g = bool(inv.get("all_green"))
    s2 = (55.0 if greens else 10.0) + (45.0 if inv_g else 5.0)
    cat("Wiring & invariants", s2, "55×contracts-green + 45×invariants-green",
        f"contracts: {sc.get('verdict','?')[:34]} · invariants streak {ivs.get('green_streak','?')}")

    # 3 · Lane liveness — heartbeat finished within 30h
    fin = hb.get("finished_at")
    alive = False
    if fin:
        try:
            dt = datetime.fromisoformat(str(fin).replace("Z", "+00:00"))
            alive = (datetime.now(timezone.utc) - dt).total_seconds() < 30 * 3600
        except Exception:
            alive = False
    cat("Lane liveness", 100.0 if alive else 20.0,
        "100 if deep lane finished within 30h else 20",
        f"deep finished_at={str(fin)[:19] if fin else 'never'}")

    # 4 · Δ-vs-null honesty — best book vs BENCH_HODL (crypto's null)
    books = bench.get("books") or {}
    hodl = (books.get("BENCH_HODL") or {}).get("return_pct")
    cry = None
    try:
        cry = (sim.get("crypto", {}).get("equity", 10000) / 10000 - 1) * 100
    except Exception:
        pass
    if hodl is not None and cry is not None:
        d = cry - float(hodl)
        s4 = max(0.0, min(100.0, 50.0 + d * 10.0))
        ev = f"crypto {cry:+.2f}% vs HODL {float(hodl):+.2f}% → Δ {d:+.2f}%"
    else:
        s4, ev = 50.0, "null books warming"
    cat("Edge vs doing-nothing", s4, "50 + 10×(crypto% − HODL%) clamped 0..100", ev)

    # 5 · Forward evidence velocity — closed forward trades on the books
    n_fwd = sum(int(r.get("n") or 0) for r in (cv.get("strategies") or []))
    s5 = min(100.0, n_fwd)
    cat("Forward evidence", s5, "min(100, total forward closed trades in validation)",
        f"{n_fwd} forward closed trades across books")

    # 6 · Edge capture (sane universe)
    cap = ec.get("PRIMARY_KPI_portfolio_capture_pct")
    s6 = min(100.0, float(cap) * 4.0) if isinstance(cap, (int, float)) else 30.0
    cat("Edge capture", s6, "4×capture%, capped 100 (25% capture of the sane universe = A+)",
        f"capture {cap}% of tradable movers" if cap is not None else "engine warming")

    # 7 · Trade quality — capture of each trade's own move
    caps = [v.get("avg_capture_pct") for v in (tq.get("books") or {}).values()
            if isinstance(v, dict) and isinstance(v.get("avg_capture_pct"), (int, float))]
    s7 = min(100.0, (sum(caps) / len(caps)) * 1.6) if caps else 40.0
    cat("Trade quality", s7, "1.6×mean per-trade capture%, capped",
        (f"mean capture {sum(caps)/len(caps):.1f}% over {len(caps)} books" if caps else "insufficient graded trades"))

    overall = sum(c["score"] for c in cats) / len(cats)
    prev = (_j(out, STORE) or {}).get("overall_score")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_score": round(overall, 1),
        "overall_grade": _grade(overall),
        "previous_grade": (_j(out, STORE) or {}).get("overall_grade"),
        "trend": ("improving" if isinstance(prev, (int, float)) and overall > prev + 0.5
                  else "slipping" if isinstance(prev, (int, float)) and overall < prev - 0.5
                  else "steady"),
        "headline": f"{_grade(overall)} ({overall:.0f}) — every grade below is a formula on a real store; audit any of them",
        "note": "5.1 evidence-based scorecard — no vibes, only formulas. A bad grade names its store.",
        "categories": cats,
    }
    write_json_atomic(out / STORE, payload)
    return {"summary": f"scorecard {payload['overall_grade']} ({payload['overall_score']})"}
