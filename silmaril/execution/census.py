"""
silmaril.execution.census — 5.0 CENSUS ENGINE ("are we missing valuables?")

Daily/hourly roll-call of everything the feeds have ever shown us, per quadrant:

    listed        — symbols present in price_samples
    fresh_24h     — carried a REAL intraday tick in the last 24h (backfill excluded)
    stale         — exists but no real tick in 24h (the '92% ghosts' made auditable)
    backfill_only — only midnight daily candles ever seen (never live-tradable)

Plus the NEW-LISTING DETECTOR: CENSUS_ROSTER.json remembers first_seen for every
symbol forever (long-memory — survives wipes); anything first seen within 14 days
is surfaced as a new listing in OBSERVE quarantine. "Excluded correctly" and
"missing wrongly" are finally different colors.

Self-gates to ~hourly (parses the big samples file); read-only otherwise.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .atomic_io import write_json_atomic

STORE = "UNIVERSE_CENSUS.json"
ROSTER = "CENSUS_ROSTER.json"      # long-memory: NEVER wiped
SELF_GATE_MIN = 55
NEW_LISTING_DAYS = 14

# Quadrant classification — kept in lock-step with the dashboard's sets.
_METAL = {"GLD", "IAU", "SLV", "SIVR", "PPLT", "PALL", "CPER", "GDX", "GDXJ", "SIL",
          "XAU", "XAG", "XPT", "XPD", "GLDM", "AAAU"}
_ENERGY = {"XLE", "XOP", "OIH", "USO", "BNO", "UNG", "UGA", "DBO", "DBC", "URA",
           "URNM", "ICLN", "TAN", "FAN", "PBW", "WTI", "BRENT", "NG", "CL", "RB", "HO"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cls(sym: str) -> str:
    if sym.endswith("-USD"):
        return "crypto"
    if sym in _METAL:
        return "metal"
    if sym in _ENERGY:
        return "energy"
    return "stock"


def _parse(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def build_census(out_dir) -> Optional[Dict[str, Any]]:
    out = Path(out_dir)
    tgt = out / STORE
    if tgt.exists():
        # 2026-07-10: gate on the store's OWN generated_at, not file mtime —
        # git checkout resets every mtime to job start, so the mtime gate read
        # "fresh" on every Actions run and the census NEVER executed in any
        # lane (the live store was 35h stale while the gate said skip).
        age_min = None
        try:
            g = json.loads(tgt.read_text()).get("generated_at")
            if g:
                ts = datetime.fromisoformat(str(g).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age_min = (_now() - ts).total_seconds() / 60.0
        except Exception:
            age_min = None
        if age_min is None:
            age_min = (_now().timestamp() - tgt.stat().st_mtime) / 60.0
        if age_min < SELF_GATE_MIN:
            return None  # fresh enough — skip the heavy parse this cycle

    try:
        samples: Dict[str, List[Any]] = (json.loads(
            (out / "price_samples.json").read_text()).get("samples") or {})
    except Exception:
        return None

    try:
        roster: Dict[str, str] = json.loads((out / ROSTER).read_text())
    except Exception:
        roster = {}

    now = _now()
    quad: Dict[str, Dict[str, int]] = {q: {"listed": 0, "fresh_24h": 0, "stale": 0,
                                           "backfill_only": 0}
                                       for q in ("crypto", "stock", "metal", "energy")}
    new_names: List[Dict[str, str]] = []

    for sym, rows in samples.items():
        q = quad[_cls(sym)]
        q["listed"] += 1
        if sym not in roster:
            roster[sym] = now.isoformat()
        last_real: Optional[datetime] = None
        any_real = False
        for row in reversed(rows or []):
            try:
                t = str(row[0])
            except Exception:
                continue
            if "T00:00:00" in t:
                continue
            any_real = True
            last_real = _parse(t)
            break
        if not any_real:
            q["backfill_only"] += 1
        elif last_real and (now - last_real).total_seconds() <= 24 * 3600:
            q["fresh_24h"] += 1
        else:
            q["stale"] += 1
        fs = _parse(roster.get(sym, ""))
        if fs and (now - fs).days <= NEW_LISTING_DAYS:
            new_names.append({"sym": sym, "first_seen": roster[sym],
                              "quadrant": _cls(sym), "status": "OBSERVE (14d quarantine)"})

    for q in quad.values():
        q["pct_fresh"] = round(100.0 * q["fresh_24h"] / q["listed"], 1) if q["listed"] else 0.0

    new_names.sort(key=lambda r: r["first_seen"], reverse=True)
    payload = {
        "generated_at": now.isoformat(),
        "quadrants": quad,
        "new_listings": {"count": len(new_names), "window_days": NEW_LISTING_DAYS,
                         "recent": new_names[:12]},
        "roster_size": len(roster),
        "summary": " · ".join(f"{k} {v['listed']} listed / {v['pct_fresh']}% fresh"
                              for k, v in quad.items())
                   + f" · new≤{NEW_LISTING_DAYS}d: {len(new_names)}",
        "doctrine": ("Exclusions must be NAMED, never silent: stale and backfill_only "
                     "are the freshness filter doing its job in public. New listings "
                     "auto-enter a 14-day OBSERVE quarantine before any eligibility."),
    }
    write_json_atomic(out / ROSTER, roster)
    write_json_atomic(tgt, payload)
    return payload


if __name__ == "__main__":
    import sys
    r = build_census(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(r["summary"] if r else "census fresh — skipped (self-gate)")
