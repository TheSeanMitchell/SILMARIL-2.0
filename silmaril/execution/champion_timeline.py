"""
silmaril.execution.champion_timeline — DID CHAMPION ROTATION HELP? (2.5.5).

Builds the champion reign timeline from the real promotion log, then attributes every real crypto
fill to the champion that was active when it CLOSED — so you see, per reign: trades, win rate,
realized P&L, and avg hold. Answers the directive's #1 question with fills, not assumption. 100%
real data, OBSERVATIONAL ONLY. Emits CHAMPION_TIMELINE.json.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from .atomic_io import write_json_atomic

def _now(): return datetime.now(timezone.utc)
def _dt(s):
    try: return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None

def build_champion_timeline(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    try: gov = json.loads((out / "CHAMPION_GOVERNANCE.json").read_text())
    except Exception: gov = {}
    proms = sorted([p for p in (gov.get("recent_promotions") or []) if _dt(p.get("at"))],
                   key=lambda p: _dt(p.get("at")))
    try: bk = json.loads((out / "paper_book_crypto.json").read_text())
    except Exception: bk = {}
    sells = [t for t in bk.get("trades", []) if t.get("side") == "SELL" and t.get("pnl") is not None and _dt(t.get("t"))]

    # build reigns [(champion, start, end)]
    reigns = []
    for i, p in enumerate(proms):
        start = _dt(p["at"])
        end = _dt(proms[i + 1]["at"]) if i + 1 < len(proms) else _now()
        reigns.append({"champion": p["to"], "start": start, "end": end, "why": p.get("why", "")})
    # trades before the first promotion -> a "pre-log" bucket
    first_start = reigns[0]["start"] if reigns else _now()

    def attribute(xt):
        for r in reigns:
            if r["start"] <= xt < r["end"]:
                return r["champion"], r["start"].isoformat()
        return ("(before promotion log)", None)

    agg: Dict[str, Dict[str, Any]] = {}
    for t in sells:
        xt = _dt(t["t"])
        champ, rstart = attribute(xt)
        key = f"{champ}|{rstart or 'pre'}"
        a = agg.setdefault(key, {"champion": champ, "reign_start": rstart, "pnl": 0.0,
                                  "trips": 0, "wins": 0, "losses": 0})
        a["pnl"] += t["pnl"]; a["trips"] += 1
        if t["pnl"] > 0.005: a["wins"] += 1
        elif t["pnl"] < -0.005: a["losses"] += 1

    rows = []
    for r in reigns:
        key = f"{r['champion']}|{r['start'].isoformat()}"
        a = agg.get(key, {"pnl": 0.0, "trips": 0, "wins": 0, "losses": 0})
        dur_h = round((r["end"] - r["start"]).total_seconds() / 3600, 1)
        rows.append({
            "champion": r["champion"],
            "from": r["start"].isoformat(), "to": (r["end"].isoformat() if r["end"] < _now() else "now"),
            "duration_hours": dur_h, "why_promoted": r["why"],
            "trips": a["trips"], "wins": a["wins"], "losses": a["losses"],
            "win_rate_pct": round(a["wins"] / a["trips"] * 100, 1) if a["trips"] else None,
            "realized_usd": round(a["pnl"], 2),
            "usd_per_hour": round(a["pnl"] / dur_h, 2) if dur_h else None,
        })
    # pre-log bucket if any
    for key, a in agg.items():
        if a["champion"] == "(before promotion log)":
            rows.insert(0, {"champion": a["champion"], "from": "(earliest)", "to": first_start.isoformat(),
                            "duration_hours": None, "why_promoted": "", "trips": a["trips"],
                            "wins": a["wins"], "losses": a["losses"],
                            "win_rate_pct": round(a["wins"] / a["trips"] * 100, 1) if a["trips"] else None,
                            "realized_usd": round(a["pnl"], 2), "usd_per_hour": None})

    # verdict: did rotation help? compare the current (stable) reign's $/hr vs the churny early reigns
    productive = [r for r in rows if r["trips"] >= 3 and r["usd_per_hour"] is not None]
    best = max(productive, key=lambda r: r["usd_per_hour"]) if productive else None
    current = rows[-1] if rows else None
    if best and current and best["champion"] == current["champion"]:
        verdict = (f"The current stable champion {current['champion']} is also the most productive "
                   f"reign (${current['usd_per_hour']}/hr). Rotation settled on a winner and holding it "
                   f"is paying — stability, not churn, is the story.")
    elif len([r for r in rows if r["trips"] > 0]) <= 1:
        verdict = "Only one reign has traded meaningfully — not enough rotation history to judge yet."
    else:
        verdict = "Rotation history is mixed; compare $/hr across reigns below before trusting switches."

    payload = {
        "generated_at": _now().isoformat(),
        "status_label": "OBSERVATIONAL ONLY — attributes real fills to the active champion; changes nothing.",
        "reigns": rows, "total_switches": len(reigns),
        "verdict": verdict,
        "what": "Every champion reign with the real trades, win rate, and P&L produced under it.",
        "why": "Answers 'did champion rotation help?' by crediting each champion with the fills it actually oversaw.",
        "honest_note": ("Trades attributed by the champion active at EXIT time, from the real promotion log + "
                        "real fills. $/hr normalises for reign length. No synthetic data."),
    }
    try: write_json_atomic(out / "CHAMPION_TIMELINE.json", payload)
    except Exception: pass
    return payload
