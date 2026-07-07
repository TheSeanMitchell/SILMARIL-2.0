"""
silmaril.execution.utilization — 5.0 LAW 16: UTILIZATION IS MEASURED

Idle capital is a cost with a number on it. Every cycle, every book (the four
governed quadrants + GEKKO) gets exactly one status:

    DEPLOYED        — has open positions (capital working)
    BLOCKED_REGIME  — regime is DOWNTREND and this book's gate is 'hard'
    STARVED         — zero entry-warm symbols in its funnel (data, not markets)
    ARMED           — warm, ungated, waiting for a qualifying dip (patience)

Rolled up per-day for 30 days in CHAMPION_UTILIZATION.json. A champion that sits
ARMED 100% and DEPLOYED 0% for a week is a parameter-parity summons (the market's
'dip' is mis-sized for that room), not background noise.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .atomic_io import write_json_atomic

STORE = "CHAMPION_UTILIZATION.json"
BOOKS = ("crypto", "stock", "metal", "energy", "aggressive")
KEEP_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load(p: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _status(book: Dict[str, Any], regime: str, gate: str) -> str:
    if int(book.get("open_positions") or 0) > 0:
        return "DEPLOYED"
    if str(regime).upper() == "DOWNTREND" and str(gate).lower() == "hard":
        return "BLOCKED_REGIME"
    funnel = book.get("funnel") or {}
    if int(funnel.get("entry_warm") or 0) <= 0:
        return "STARVED"
    return "ARMED"


def build_utilization(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    live = _load(out / "paper_sim_live.json") or {}
    catalog = _load(out / "PARAM_CATALOG.json") or {}
    gates = catalog.get("regime_gate") or {}
    regimes = live.get("regimes") or {}

    st = _load(out / STORE) or {"days": {}}
    days: Dict[str, Any] = st.get("days") or {}
    today = _now().strftime("%Y-%m-%d")
    day = days.setdefault(today, {})

    last: Dict[str, str] = {}
    for bk in BOOKS:
        b = live.get(bk) or {}
        # GEKKO's gate is SOFT by doctrine; regime string shared with crypto.
        regime = regimes.get("crypto" if bk == "aggressive" else bk, "—")
        gate = "soft" if bk == "aggressive" else gates.get(bk, "soft")
        s = _status(b, regime, gate)
        last[bk] = s
        cell = day.setdefault(bk, {})
        cell[s] = int(cell.get(s, 0)) + 1

    # prune to KEEP_DAYS
    for k in sorted(days.keys())[:-KEEP_DAYS]:
        days.pop(k, None)

    def _line(bk: str) -> str:
        c = day.get(bk, {})
        tot = sum(c.values()) or 1
        dep = c.get("DEPLOYED", 0)
        top = max(c, key=c.get) if c else "—"
        return f"{('GEKKO' if bk == 'aggressive' else bk)} {last.get(bk, '—')}" \
               f" (dep {dep}/{tot}, mostly {top})"

    payload = {
        "generated_at": _now().isoformat(),
        "last": last,
        "days": days,
        "summary_today": " · ".join(_line(bk) for bk in BOOKS),
        "today_line": " ".join(f"{('G' if bk=='aggressive' else bk[0].upper())}:{last[bk][0]}"
                               for bk in BOOKS),
        "legend": "D=DEPLOYED A=ARMED B=BLOCKED_REGIME S=STARVED",
        "doctrine": ("Law 16 — ARMED-forever is a finding: it means this market's "
                     "'dip' is mis-sized for the current entry knobs (see the 5.0 "
                     "parameter-translation table), and it now has a public counter."),
    }
    st.update(payload)
    write_json_atomic(out / STORE, st)
    return st


if __name__ == "__main__":
    import sys
    r = build_utilization(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(r["summary_today"])
