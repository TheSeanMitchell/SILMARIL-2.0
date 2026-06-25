"""
silmaril.execution.crypto_concentration — CRYPTO EDGE CONCENTRATION REPORT (2.5.5).

Answers one question with brutal honesty: how much of the crypto book's profit is a broad,
repeatable edge vs a handful of names? Per-symbol realized P&L, the top-name share, what the
book looks like with the top contributor removed, and a concentration verdict. 100% real fills,
no synthetic data. OBSERVATIONAL ONLY. Emits CRYPTO_CONCENTRATION.json.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from .atomic_io import write_json_atomic

def _now(): return datetime.now(timezone.utc).isoformat()

def build_crypto_concentration(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    try: bk = json.loads((out / "paper_book_crypto.json").read_text())
    except Exception: bk = {}
    sells = [t for t in bk.get("trades", []) if t.get("side") == "SELL" and t.get("pnl") is not None]
    by = defaultdict(lambda: {"pnl": 0.0, "trips": 0, "wins": 0, "losses": 0})
    for t in sells:
        s = t["sym"]; p = t["pnl"]
        by[s]["pnl"] += p; by[s]["trips"] += 1
        if p > 0.005: by[s]["wins"] += 1
        elif p < -0.005: by[s]["losses"] += 1
    total = round(sum(v["pnl"] for v in by.values()), 2)
    ranked = sorted(by.items(), key=lambda x: -x[1]["pnl"])
    rows = [{"sym": s, "pnl": round(v["pnl"], 2), "trips": v["trips"], "wins": v["wins"],
             "losses": v["losses"], "pct_of_net": (round(v["pnl"] / total * 100, 1) if total else None)}
            for s, v in ranked]
    winners = [v["pnl"] for v in by.values() if v["pnl"] > 0]
    losers = [v["pnl"] for v in by.values() if v["pnl"] < 0]
    top = ranked[0] if ranked else None
    top_sym = top[0] if top else None
    top_pnl = round(top[1]["pnl"], 2) if top else 0
    without_top = round(total - top_pnl, 2)
    # cumulative share of top 3 / top 5 of gross WINNERS (concentration of the upside)
    gross_win = round(sum(winners), 2) or 1
    top3_win = round(sum(v["pnl"] for _, v in ranked[:3] if v["pnl"] > 0), 2)
    # Herfindahl on positive contributions (0..1; higher = more concentrated)
    hhi = round(sum((v["pnl"] / gross_win) ** 2 for _, v in ranked if v["pnl"] > 0), 3)

    if top and total and top_pnl >= total:
        verdict = (f"SINGLE-NAME EDGE. {top_sym} alone is {round(top_pnl/total*100)}% of net profit; "
                   f"without it the book is ${without_top}. This is concentration risk, not breadth.")
    elif hhi > 0.4:
        verdict = "HIGHLY CONCENTRATED upside — a few names carry the book."
    else:
        verdict = "Reasonably broad — profit is spread across multiple names."

    payload = {
        "generated_at": _now(), "status_label": "OBSERVATIONAL ONLY — measures the book; changes nothing.",
        "total_realized_usd": total, "round_trips": len(sells), "symbols_traded": len(by),
        "top_contributor": {"sym": top_sym, "pnl": top_pnl,
                            "pct_of_net": (round(top_pnl / total * 100, 1) if total else None)},
        "book_without_top_contributor_usd": without_top,
        "winners_count": len(winners), "winners_total_usd": round(sum(winners), 2),
        "losers_count": len(losers), "losers_total_usd": round(sum(losers), 2),
        "top3_winner_share_pct": round(top3_win / gross_win * 100, 1),
        "upside_concentration_hhi": hhi,
        "per_symbol": rows,
        "verdict": verdict,
        "what": "How concentrated the crypto edge is — per-symbol, with the top name removed.",
        "why": "A single good name can fake a system edge. This shows whether the edge is broad or narrow.",
        "honest_note": ("Lifetime crypto account book, real fills only. 'pct_of_net' can exceed 100% when one "
                        "name's profit is larger than the net (because other names lost). No synthetic data."),
    }
    try: write_json_atomic(out / "CRYPTO_CONCENTRATION.json", payload)
    except Exception: pass
    return payload
