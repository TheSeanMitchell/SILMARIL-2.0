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
    # ── 7.0 FINAL additions (Tier 0): three more truths that must hold, every cycle ──
    # FIX_EPOCH: the guard/mirror laws landed 2026-07-19. Rows/positions from BEFORE the laws
    # are reported as `legacy_*` (informational — the reset archives them); anything at or
    # after the epoch is enforced hard. Post-reset everything is post-epoch, so the checks
    # bind fully on the clean run.
    FIX_EPOCH = "2026-07-19"
    # (1) T54 CLASS CLOSED: no two trade rows anywhere share (sym, side, t).
    dup, legacy_dup = [], []
    open_committed = 0.0
    open_count = 0
    for bk in BOOKS:
        d = _load(out, f"paper_book_{bk}.json")
        seen = set()
        for t in d.get("trades") or []:
            k = (t.get("sym"), t.get("side"), t.get("t"))
            if k in seen:
                (dup if str(t.get("t", "")) >= FIX_EPOCH else legacy_dup).append(
                    f"{bk}:{t.get('sym')}@{t.get('t')}")
            seen.add(k)
        for s, p in (d.get("positions") or {}).items():
            open_count += 1
            open_committed += float(p.get("wager_usd") or (p.get("qty", 0) * p.get("entry", 0)) or 0)
    checks.append({"name": "no duplicate (sym,side,t) rows since fix epoch (T54)",
                   "a": 0, "b": len(dup), "delta": len(dup), "ok": not dup,
                   "dups": dup[:6], "legacy_pre_epoch": legacy_dup[:6],
                   "legacy_count": len(legacy_dup)})
    # (2) MASTER ⊆ BOOKS (mirror law): every Master position opened since the epoch must exist
    # in a real book. Pre-epoch parallel-sim holds (WDC/LCID class) are legacy, archived at reset.
    ma = _load(out, "MASTER_ACCOUNT.json")
    kb = (_load(out, "PARAM_CATALOG.json").get("master_brain") or {})
    if str(kb.get("mirror_canon", "auto")).lower() == "auto":
        bookpos = set()
        for bk in BOOKS:
            bookpos |= set((_load(out, f"paper_book_{bk}.json").get("positions") or {}).keys())
        mpos = ((ma.get("book") or {}).get("positions") or {})
        orphans = [s for s, p in mpos.items()
                   if s not in bookpos and str(p.get("t", "")) >= FIX_EPOCH]
        legacy_orph = [s for s, p in mpos.items()
                       if s not in bookpos and str(p.get("t", "")) < FIX_EPOCH]
        checks.append({"name": "Master holds nothing no book holds (mirror law, since epoch)",
                       "a": 0, "b": len(orphans), "delta": len(orphans),
                       "ok": not orphans, "orphans": orphans[:6],
                       "legacy_pre_epoch": legacy_orph[:6]})
    # (3) EQUITY TRUTH — the ONE money number every panel must read (Tier 0 / R5).
    live = _load(out, "paper_sim_live.json")
    books_eq = {bk: float((live.get(bk) or {}).get("equity") or 0) for bk in BOOKS}
    master_eq = float(ma.get("equity") or 0)
    total = round(sum(books_eq.values()) + master_eq, 2)
    start = 10000.0 * (len(BOOKS) + 1)
    truth = {"generated_at": _now().isoformat(),
             "books": {k: round(v, 2) for k, v in books_eq.items()},
             "master": round(master_eq, 2),
             "total_equity": total, "start_equity": start,
             "delta_usd": round(total - start, 2),
             "delta_pct": round((total / start - 1) * 100, 3) if start else None,
             "open_positions": open_count,
             "open_committed_usd": round(open_committed, 2),
             "what": ("THE one money number (Law 10 base). Every panel that shows money reads THIS "
                      "file; no panel computes equity again. Realized-banked must never render "
                      "without total_equity beside it.")}
    write_json_atomic(out / "EQUITY_TRUTH.json", truth)
    all_ok = all(c["ok"] for c in checks) if checks else True
    payload = {"generated_at": _now().isoformat(), "all_ok": all_ok, "checks": checks,
               "equity_truth": {"total": total, "delta_usd": truth["delta_usd"],
                                "open_committed_usd": truth["open_committed_usd"],
                                "open_positions": open_count},
               "what": "four ledgers, one truth — any named delta here fails T38"}
    write_json_atomic(out / "RECONCILIATION.json", payload)
    bad = [c["name"] for c in checks if not c["ok"]]
    return {"summary": f"reconciliation: {'ALL GREEN' if all_ok else 'MISMATCH ' + str(bad)} "
                       f"({len(checks)} checks)"}
