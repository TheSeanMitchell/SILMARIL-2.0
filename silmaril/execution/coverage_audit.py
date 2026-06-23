"""
silmaril.execution.coverage_audit — Priority #0: prove the funnel.

Every cycle answers, in machine-readable form:
  - how many tickers were SCANNED (the full universe that had data)
  - how many were CONSIDERED (made the candidate pool)
  - how many were REJECTED, and WHY (per-ticker reason)
  - the TOP-100 / TOP-20 by the 10-min chain
  - what was actually BOUGHT

This is the foundation of the measurement spine: you cannot trust an
edge-capture number if you cannot prove what was even looked at. If a runner
was missed, the FIRST question is "did we scan it?" — this answers that with
no guessing.

Writes docs/data/coverage_audit.json.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

VERSION = "coverage-audit-1.0"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _dump(path: Path, obj):
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, separators=(",", ":"), allow_nan=False)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _is_crypto(t: str) -> bool:
    t = str(t).upper()
    return t.endswith("-USD") or (t.endswith("USD") and len(t) > 4)


def build_coverage_audit(
    out_dir,
    debates: List[Dict[str, Any]],
    pool: List[Dict[str, Any]],
    bought_by_account: Dict[str, List[str]],
    chain: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute the scan→consider→reject→buy funnel with reasons.

    debates: every ticker that had data this cycle (the scanned universe)
    pool:    the candidate pool (what passed the gates)
    bought_by_account: {account_id: [tickers]} actually sent as buys
    chain:   momentum_chain {ticker: {composite, fire, windows}}
    """
    out = Path(out_dir)
    chain = chain or {}

    scanned = [str(d.get("ticker")) for d in debates if d.get("ticker")]
    pool_set = {str(d.get("ticker")) for d in pool}
    bought_set = set()
    for lst in (bought_by_account or {}).values():
        for t in lst:
            bought_set.add(str(t).upper().replace("/", "").replace("-", ""))

    def _norm(t):
        return str(t).upper().replace("/", "").replace("-", "")

    # reject reasons — for everything scanned but NOT in the pool, say why
    def _reject_reason(d) -> str:
        t = str(d.get("ticker"))
        s = float(d.get("sentiment_score") or 0.0)
        c = (chain.get(t.upper()) or chain.get(t.upper().replace("USD", "-USD"))
             or chain.get(t.upper().replace("-USD", "USD")))
        comp = float(c.get("composite") or 0.0) if c else None
        fire = float(c.get("fire") or 0.0) if c else None
        slr = (c.get("windows") or {}).get("since_last") if c else None
        if c is None:
            return "no_chain_samples_yet"
        if s <= -0.5:
            return "negative_news_sentiment"
        if comp is not None and comp <= 0.5 and (slr is None or slr < 0.5):
            return "insufficient_momentum"
        if fire is not None and fire < 0.6 and (slr is None or slr < 0.5):
            return "fire_meter_too_low"
        return "below_ranking_cutoff"

    rejected = []
    considered = []
    for d in debates:
        t = str(d.get("ticker"))
        if t in pool_set:
            considered.append(t)
        else:
            rejected.append({"ticker": t, "reason": _reject_reason(d)})

    # top-100 / top-20 by chain composite+fire
    ranked = []
    for d in debates:
        t = str(d.get("ticker"))
        c = (chain.get(t.upper()) or chain.get(t.upper().replace("USD", "-USD"))
             or chain.get(t.upper().replace("-USD", "USD")))
        if c and c.get("composite") is not None:
            score = float(c["composite"]) + float(c.get("fire") or 0.0)
            ranked.append((t, round(score, 3), _is_crypto(t),
                           _norm(t) in bought_set))
    ranked.sort(key=lambda x: x[1], reverse=True)

    def _fmt(rows):
        return [{"ticker": t, "score": s, "crypto": cr, "bought": b}
                for t, s, cr, b in rows]

    # reject-reason histogram (the at-a-glance "why are we missing things")
    from collections import Counter
    reason_hist = dict(Counter(r["reason"] for r in rejected))

    # coverage by class
    stk_scanned = [t for t in scanned if not _is_crypto(t)]
    cry_scanned = [t for t in scanned if _is_crypto(t)]

    payload = {
        "version": VERSION,
        "generated_at": _now(),
        "funnel": {
            "scanned": len(scanned),
            "considered": len(considered),
            "rejected": len(rejected),
            "bought": len(bought_set),
        },
        "by_class": {
            "stocks_scanned": len(stk_scanned),
            "crypto_scanned": len(cry_scanned),
        },
        "reject_reasons": reason_hist,
        "top_100": _fmt(ranked[:100]),
        "top_20": _fmt(ranked[:20]),
        "bought": sorted(bought_set),
        "rejected_detail": rejected[:500],
        "note": ("Proof of coverage: every scanned ticker is either considered "
                 "or rejected with a reason. If a runner was missed, find it in "
                 "rejected_detail to see exactly why."),
    }
    _dump(out / "coverage_audit.json", payload)
    return payload
