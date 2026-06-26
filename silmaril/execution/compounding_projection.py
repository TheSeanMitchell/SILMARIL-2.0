"""
silmaril.execution.compounding_projection — RUNNING-AVERAGE PROJECTION (2.5.5 rebuild).

The operator's ask: stop making me do the math. Show what the account becomes over 1d/2d/1wk/1mo/
1yr based on our ACTUAL running daily average, and future-proof it so it updates itself every run.

How it works (all from real data — snapshot_history.jsonl, which records realized P&L each cycle):
  • daily_delta[d]   = end-of-day realized P&L on day d minus the day before  → real $/day earned
  • avg_daily_all    = mean of those daily deltas over every observed day
  • avg_daily_recent = mean over the last 3 observed days (catches the current rhythm)
  • current_equity   = cash + realized (the book's actual value right now)

Projections are LINEAR (additive): future = current_equity + avg_daily$ × days. For a fixed-$10k book
with fixed per-name sizing, profit accrues roughly linearly — this is the honest model, not a
hockey-stick compound curve. A compounded view is shown alongside for contrast but flagged as the
optimistic bound. Credibility decays with horizon and is labelled so nobody mistakes hope for forecast.

OBSERVATIONAL. Emits COMPOUNDING_PROJECTION.json. No trading logic touched.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

HORIZONS = [("1 day", 1), ("2 days", 2), ("1 week", 7), ("2 weeks", 14),
            ("1 month", 30), ("3 months", 90), ("1 year", 365)]

def _now(): return datetime.now(timezone.utc).isoformat()

def _daily_deltas(out: Path) -> List[tuple]:
    """[(day, end_realized, delta_vs_prev_day)] for the crypto book, oldest→newest."""
    p = out / "snapshot_history.jsonl"
    if not p.exists():
        return []
    byday: Dict[str, float] = {}
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        ts = r.get("ts") or r.get("generated_at") or ""
        pnl = r.get("crypto_realized_pnl", r.get("realized_pnl"))
        if ts and pnl is not None:
            byday[ts[:10]] = float(pnl)        # last value of the day wins
    days = sorted(byday)
    out_rows, prev = [], None
    for d in days:
        end = byday[d]
        out_rows.append((d, end, (end - prev) if prev is not None else None))
        prev = end
    return out_rows

def build_compounding_projection(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    rows = _daily_deltas(out)

    # current equity from the live book
    equity = None
    try:
        b = json.loads((out / "paper_book_crypto.json").read_text())
        equity = float(b.get("cash", 0)) + float(b.get("realized_pnl", 0))  # cash already nets sells; add realized as the growth marker
        realized = float(b.get("realized_pnl", 0))
        # better: equity = start(10k) + realized (+ open MTM ~ small). Use 10k + realized as the honest equity.
        equity = 10000.0 + realized
    except Exception:
        realized = 0.0
        equity = 10000.0

    deltas = [d for (_, _, d) in rows if d is not None]
    if not deltas:
        # fall back to realized / observed days if we at least know realized
        payload = {"generated_at": _now(), "status_label": "OBSERVATIONAL",
                   "note": "Need at least two days of snapshots to compute a running daily average.",
                   "current_equity": round(equity, 2), "realized_to_date": round(realized, 2)}
        try:
            from .atomic_io import write_json_atomic
            write_json_atomic(out / "COMPOUNDING_PROJECTION.json", payload)
        except Exception:
            (out / "COMPOUNDING_PROJECTION.json").write_text(json.dumps(payload, indent=2))
        return payload

    avg_all = sum(deltas) / len(deltas)
    recent = deltas[-3:] if len(deltas) >= 3 else deltas
    avg_recent = sum(recent) / len(recent)
    avg_daily_pct_all = avg_all / equity * 100 if equity else 0.0

    def project(avg_daily):
        rt = []
        for label, days in HORIZONS:
            linear = equity + avg_daily * days
            compounded = equity * ((1 + (avg_daily / equity if equity else 0)) ** days)
            cred = ("credible" if days <= 7 else "speculative" if days <= 30 else "hope-not-forecast")
            rt.append({"horizon": label, "days": days,
                       "projected_equity_linear": round(linear, 2),
                       "projected_gain_linear": round(linear - equity, 2),
                       "projected_equity_compounded": round(compounded, 2),
                       "credibility": cred})
        return rt

    payload = {
        "generated_at": _now(),
        "status_label": "OBSERVATIONAL — projection from our own running average; not a promise.",
        "current_equity": round(equity, 2),
        "realized_to_date": round(realized, 2),
        "observed_days": len(rows),
        "daily_history": [{"day": d, "end_realized": round(e, 2),
                           "delta": (round(dl, 2) if dl is not None else None)} for (d, e, dl) in rows],
        "avg_daily_usd_all": round(avg_all, 2),
        "avg_daily_usd_recent3": round(avg_recent, 2),
        "avg_daily_pct": round(avg_daily_pct_all, 3),
        "projection_on_all_avg": project(avg_all),
        "projection_on_recent3_avg": project(avg_recent),
        "what": "What the account becomes if our running daily average holds — linear (honest) + compounded (optimistic bound).",
        "honest_note": (f"Built on only {len(rows)} observed days, on a volatile single-book edge that is "
                        "heavily MKR-concentrated. The 1d–1wk numbers are the credible part; month/year "
                        "figures are illustrative of 'if this exact rhythm held', which it very likely will "
                        "not. A single losing day (we have had one: -$181) resets the slope. Read this as a "
                        "running scoreboard, not a forecast."),
    }
    try:
        from .atomic_io import write_json_atomic
        write_json_atomic(out / "COMPOUNDING_PROJECTION.json", payload)
    except Exception:
        (out / "COMPOUNDING_PROJECTION.json").write_text(json.dumps(payload, indent=2))
    return payload

if __name__ == "__main__":
    import sys
    print(json.dumps(build_compounding_projection(sys.argv[1] if len(sys.argv) > 1 else "docs/data"), indent=2)[:1600])
