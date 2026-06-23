"""
silmaril.execution.authority_validation — AUTHORITY VALIDATION (2.15 Priority 4).

Not detection — VALIDATION. For every authority event in the ledger, measure the
forward return of its beneficiaries at 1h/4h/1d/3d/7d, then build a per-authority
leaderboard (Trump +X%, Elon +Y%, Fed +Z%...). Only evidence. No assumptions.
This is the "does WHO-said-it actually move price" question, answered with data.
"""
from __future__ import annotations
import json, math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, List
from .paper_sim import load_all_samples

HORIZONS = {"1h": 1, "4h": 4, "1d": 24, "3d": 72, "7d": 168}

def _now(): return datetime.now(timezone.utc).isoformat()

def _series(samples, sym):
    return [(datetime.fromisoformat(t), p) for t, p in samples.get(sym, []) if p and p > 0]

def _fwd(ser, when, hours):
    base = None
    for t, p in ser:
        if t >= when: base = p; base_t = t; break
    if base is None: return None
    target = when + timedelta(hours=hours)
    fut = None
    for t, p in ser:
        if t >= target: fut = p; break
    if fut is None: return None
    return fut / base - 1

def build_authority_validation(out_dir) -> Dict[str, Any]:
    out = Path(out_dir); samples = load_all_samples(out)
    try: ledger = json.loads((out / "authority_ledger.json").read_text()).get("events", [])
    except Exception: ledger = []
    # per authority -> per horizon -> list of beneficiary forward returns
    agg: Dict[str, Dict[str, List[float]]] = {}
    measured = 0
    for ev in ledger:
        auth = ev.get("authority", "?")
        try: when = datetime.fromisoformat(ev.get("at"))
        except Exception: continue
        agg.setdefault(auth, {h: [] for h in HORIZONS})
        for b in ev.get("beneficiaries", []):
            ser = _series(samples, b)
            if not ser: continue
            sign = ev.get("sentiment", 1) or 1
            for h, hrs in HORIZONS.items():
                r = _fwd(ser, when, hrs)
                if r is not None:
                    agg[auth][h].append(r * (1 if sign >= 0 else -1)); measured += 1
    leaderboard = []
    for auth, hz in agg.items():
        row = {"authority": auth, "events": sum(len(hz[h]) for h in HORIZONS) // max(1, len(HORIZONS))}
        for h in HORIZONS:
            xs = hz[h]
            if len(xs) >= 5:
                m = mean(xs); sd = pstdev(xs) or 1e-9
                row[h] = round(m * 100, 2); row[h + "_t"] = round(m / (sd / math.sqrt(len(xs))), 1)
            else:
                row[h] = None; row[h + "_t"] = None
        leaderboard.append(row)
    leaderboard.sort(key=lambda r: (r.get("1d") or -99), reverse=True)
    payload = {"generated_at": _now(), "events_in_ledger": len(ledger),
               "beneficiary_measurements": measured,
               "authority_leaderboard": leaderboard,
               "horizons": list(HORIZONS.keys()),
               "status": ("validating live" if measured else
                          "ledger empty/young — authority forward returns accumulate as events are detected + time passes"),
               "note": "Forward return of beneficiaries after each authority event, sentiment-signed. Evidence only; >=5 obs and |t|>=2 before trusting an authority."}
    try: (out / "authority_validation.json").write_text(json.dumps(payload, indent=2))
    except Exception: pass
    return payload

if __name__ == "__main__":
    import sys; print(json.dumps(build_authority_validation(sys.argv[1] if len(sys.argv) > 1 else "docs/data"))[:300])
