"""silmaril.execution.reconciliation — 5.3 (M9): four ledgers must AGREE, out loud.

F8 existed because no one ever asked two modules to reconcile. Now every cycle:
  book Σpnl  ==  report-card cumulative  (per book and total, within rounding)
  session realized(today) == books realized(today)
Any mismatch is a named, sized red line on HEALTH — and tripwire T38 fails the
battery. Emits RECONCILIATION.json.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .atomic_io import write_json_atomic

BOOKS = ("crypto", "stock", "metal", "energy", "aggressive")


def _now():
    return datetime.now(timezone.utc)


def _load(out: Path, name: str, default=None):
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return default if default is not None else {}


def build_reconciliation(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    checks = []
    tot_book, n_tr = 0.0, 0
    today = _now().date().isoformat()
    tot_today = 0.0
    for bk in BOOKS:
        d = _load(out, f"paper_book_{bk}.json")
        sells = [t for t in d.get("trades") or [] if t.get("side") == "SELL"]
        s = sum(float(t.get("pnl") or 0) for t in sells)
        tot_book += s
        n_tr += len(sells)
        tot_today += sum(float(t.get("pnl") or 0) for t in sells
                         if str(t.get("t", ""))[:10] == today)
        rp = float(d.get("realized_pnl") or 0)
        tol = max(0.05, 0.01 * len(sells))
        checks.append({"name": f"{bk}: Σtrade pnl == book.realized_pnl",
                       "a": round(s, 2), "b": round(rp, 2),
                       "delta": round(s - rp, 2), "ok": abs(s - rp) <= tol})
    rc = ((_load(out, "CONDUCTOR_REPORT_CARD.json").get("realized_profit") or {})
          .get("cumulative_realized_usd_all_books"))
    if rc is not None:
        tol = max(0.10, 0.01 * n_tr)
        checks.append({"name": "Σbooks == report card cumulative",
                       "a": round(tot_book, 2), "b": round(float(rc), 2),
                       "delta": round(tot_book - float(rc), 2),
                       "ok": abs(tot_book - float(rc)) <= tol})
    sess = _load(out, "SESSION_TODAY.json")
    sr, got = 0.0, False
    for bb in (sess.get("by_book") or {}).values():
        if bb.get("realized_usd") is not None:
            sr += float(bb["realized_usd"]); got = True
    if got:
        # like-for-like: the session covers the FOUR quadrants, as of ITS snapshot time
        cutoff = str(sess.get("generated_at") or "9999")
        start = str(sess.get("session_start_utc") or today)
        b4 = 0.0
        for bk in ("crypto", "stock", "metal", "energy"):
            for t in (_load(out, f"paper_book_{bk}.json").get("trades") or []):
                if (t.get("side") == "SELL" and start <= str(t.get("t", "")) <= cutoff):
                    b4 += float(t.get("pnl") or 0)
        tol = max(0.10, 0.01 * n_tr)
        checks.append({"name": "session == 4-quadrant books (same window)",
                       "a": round(sr, 2), "b": round(b4, 2),
                       "delta": round(sr - b4, 2), "ok": abs(sr - b4) <= tol})
    all_ok = all(c["ok"] for c in checks) if checks else True
    payload = {"generated_at": _now().isoformat(), "all_ok": all_ok, "checks": checks,
               "what": "four ledgers, one truth — any named delta here fails T38"}
    write_json_atomic(out / "RECONCILIATION.json", payload)
    bad = [c["name"] for c in checks if not c["ok"]]
    return {"summary": f"reconciliation: {'ALL GREEN' if all_ok else 'MISMATCH ' + str(bad)} "
                       f"({len(checks)} checks)"}
