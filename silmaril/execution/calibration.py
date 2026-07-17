"""silmaril.execution.calibration — 7.0 THE GRADED CONFIDENCE (Brier + reliability).

The most damning fact of the 6.0 audit: the confidence score had ranked, gated and
sized for months WITHOUT EVER BEING CHECKED AGAINST AN OUTCOME. 7.0 ends that.

Every BUY stamps its prediction (the card's master_score) into
CALIBRATION_LEDGER.jsonl; every SELL closes the loop with the outcome. This module
grades the pairs each cycle:

  · Brier score  = mean (pred − outcome)²   (0 perfect · 0.25 coin-flip on 50/50)
  · Reliability deciles: "when we said 60%, we won ____%"
  · STATUS: UNPROVEN (n < min) → CALIBRATED → QUARANTINED (calibration error > tol)

QUARANTINE has TEETH: the Master swaps its gate input from confidence to raw
evidence-percentile until the score earns its authority back. A score that cannot
predict does not get to allocate (Law 23). KILL: calibration.mode:"off".
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .atomic_io import write_json_atomic

LEDGER = "CALIBRATION_LEDGER.jsonl"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load(out: Path, name: str, default=None):
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return default if default is not None else {}


def _rows(out: Path) -> List[dict]:
    try:
        return [json.loads(l) for l in (out / LEDGER).read_text().splitlines() if l.strip()]
    except Exception:
        return []


def build_calibration(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    kb = (_load(out, "PARAM_CATALOG.json").get("calibration") or {})
    min_n = int(kb.get("min_n", 25))
    tol = float(kb.get("max_decile_error", 0.20))
    rows = [r for r in _rows(out) if r.get("outcome") is not None and r.get("pred") is not None]
    n = len(rows)
    if n == 0:
        payload = {"generated_at": _now(), "n": 0, "status": "UNPROVEN",
                   "note": "no closed predicted trades yet — the ledger fills as trades close",
                   "what": "Brier + reliability: when we say X%, do we win X%? (Law 23)"}
        write_json_atomic(out / "CALIBRATION.json", payload)
        return {"summary": "calibration: UNPROVEN (n=0)"}
    brier = sum((float(r["pred"]) - (1.0 if r["outcome"] == "win" else 0.0)) ** 2
                for r in rows) / n
    dec: Dict[int, List[int]] = {}
    for r in rows:
        d = min(9, int(float(r["pred"]) * 10))
        a = dec.setdefault(d, [0, 0])
        a[0] += 1 if r["outcome"] == "win" else 0
        a[1] += 1
    deciles = []
    worst = 0.0
    for d in sorted(dec):
        k, m = dec[d]
        obs = k / m
        mid = d / 10 + 0.05
        err = abs(obs - mid) if m >= 5 else None
        if err is not None:
            worst = max(worst, err)
        deciles.append({"said_pct": int(mid * 100), "won_pct": round(obs * 100, 1),
                        "n": m, "abs_err": round(err, 3) if err is not None else None})
    status = ("UNPROVEN" if n < min_n else
              ("QUARANTINED" if worst > tol else "CALIBRATED"))
    payload = {"generated_at": _now(), "n": n, "brier": round(brier, 4),
               "coin_flip_brier": 0.25, "worst_decile_error": round(worst, 3),
               "deciles": deciles, "status": status,
               "teeth": ("QUARANTINED → the Master gates on raw evidence-percentile until "
                         "the score earns authority back (Law 23)"),
               "what": "when we say X%, do we win X%? graded every cycle, in writing"}
    write_json_atomic(out / "CALIBRATION.json", payload)
    return {"summary": f"calibration: {status} (n={n}, brier {round(brier,3)})"}
