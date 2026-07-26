#!/usr/bin/env python3
"""
DAILY BLOCK — the auto-filled half of DAILY WORKSHEET v2.

The v1 audit sheet asked the operator to transcribe forty numbers off a dashboard. That is
work a machine should do, and asking a human to do it guarantees three things: it takes too
long, it gets skipped on the days it matters most, and transcription errors become "findings."

This prints one compact block covering everything the machine can know about itself. The
operator pastes it and spends their ten minutes on the six questions only a human can answer.

Every line is read from a real store. Where a store is missing the line says so rather than
printing a zero — a zero is a claim, "absent" is the truth.

Usage:  python scripts/daily_block.py [docs/data]
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

W = 78


def _load(d: Path, name: str):
    try:
        return json.loads((d / name).read_text())
    except Exception:
        return None


def _lines(d: Path, name: str, limit: int = 4000):
    try:
        return [json.loads(x) for x in (d / name).read_text().splitlines()[-limit:] if x.strip()]
    except Exception:
        return []


def _age(ts) -> str:
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if not t.tzinfo:
            t = t.replace(tzinfo=timezone.utc)
        m = (datetime.now(timezone.utc) - t).total_seconds() / 60.0
        return "%dm" % m if m < 90 else ("%.1fh" % (m / 60) if m < 48 * 60 else "%.1fd" % (m / 1440))
    except Exception:
        return "?"


def hdr(t):
    print("\n" + t)
    print("-" * min(W, len(t) + 12))


def main(argv):
    d = Path(argv[1] if len(argv) > 1 else "docs/data")
    now = datetime.now(timezone.utc)
    print("=" * W)
    print("SILMARIL DAILY BLOCK · %s UTC" % now.strftime("%Y-%m-%d %H:%M"))
    print("=" * W)

    # ── books ────────────────────────────────────────────────────────────────────────
    live = _load(d, "paper_sim_live.json") or {}
    wipe = _load(d, "WIPE_MARKER.json") or {}
    hdr("BOOKS")
    print("  engine last ran: %s ago · last wipe: %s ago"
          % (_age(live.get("generated_at")), _age(wipe.get("wiped_at"))))
    for bk in ("crypto", "stock", "metal", "energy"):
        b = live.get(bk) or {}
        f = b.get("funnel") or {}
        eq = b.get("equity")
        armed = f.get("armed")
        why = str(f.get("arming_why") or "")[:52]
        print("  %-7s equity=%-10s open=%-2s realized=%-9s armed=%-5s %s"
              % (bk,
                 ("$%.2f" % eq) if isinstance(eq, (int, float)) else "—",
                 len(b.get("positions") or []),
                 ("$%.2f" % b["realized_pnl"]) if isinstance(b.get("realized_pnl"), (int, float)) else "—",
                 armed if armed is not None else "—", why))

    # ── feed truth ───────────────────────────────────────────────────────────────────
    pt = _load(d, "PRICE_TRUTH.json")
    hdr("FEED TRUTH  (can each tape express the move we need?)")
    if not pt:
        print("  PRICE_TRUTH.json absent — feeds ungraded this cycle")
    else:
        c = pt.get("counts") or {}
        print("  %s/%s tradeable · %s" % (pt.get("tradeable"), pt.get("graded"),
                                          " · ".join("%s %s" % (k, v) for k, v in sorted(c.items()))))
    psa = _load(d, "PRICE_SOURCE_AUDIT.json")
    if psa:
        print("  source audit: %s" % str(psa.get("verdict"))[:64])
        print("  divergences=%s · stale stores=%s · names with no recent print=%s"
              % (psa.get("divergence_count"), len(psa.get("stale_stores") or []),
                 psa.get("tape_gap_count")))

    # ── sleeves ──────────────────────────────────────────────────────────────────────
    lab = _load(d, "STRATEGY_LAB.json") or {}
    hdr("SLEEVES  (closed trades are the only evidence)")
    any_row = False
    for bkn, sl in (lab.get("by_industry") or {}).items():
        rows = sorted([s for s in (sl or []) if (s.get("closed") or 0) > 0 or (s.get("open") or 0) > 0],
                      key=lambda s: -(s.get("delta_vs_hodl") or -999))
        if not rows:
            print("  %-7s no sleeve holding or closing yet" % bkn)
            continue
        for s in rows[:4]:
            any_row = True
            print("  %-7s %s %-17s ret=%+7.3f%% dnull=%+7.3f%% open=%-2s closed=%-2s win=%5.1f%%"
                  % (bkn, s.get("sleeve"), str(s.get("name"))[:17],
                     s.get("return_pct") or 0.0, s.get("delta_vs_hodl") or 0.0,
                     s.get("open"), s.get("closed"), s.get("win_rate") or 0.0))
    if not any_row:
        print("  (no sleeve has opened or closed anything yet)")

    prom = _load(d, "SLEEVE_PROMOTION.json") or {}
    hdr("PROMOTION  (who has earned the book?)")
    for bkn, r in (prom.get("books") or {}).items():
        print("  %-7s %-18s arms_book=%-5s %s"
              % (bkn, r.get("status"), r.get("arms_book"), str(r.get("why") or "")[:44]))

    # ── vetoes ───────────────────────────────────────────────────────────────────────
    vet = _load(d, "SLEEVE_VETOES.json")
    hdr("REFUSALS  (quiet by design, or broken? this is the difference)")
    if not vet:
        print("  SLEEVE_VETOES.json absent — the workshop is not stating its reasons")
    else:
        print("  %s refusals this cycle · %s"
              % (vet.get("total"), " · ".join("%s %s" % (k, v) for k, v in (vet.get("counts") or {}).items()) or "none"))
        for v in (vet.get("vetoes") or [])[:5]:
            print("     %-7s %s %s" % (v.get("book"), v.get("sleeve"), str(v.get("why"))[:58]))

    # ── the river ────────────────────────────────────────────────────────────────────
    riv = _lines(d, "LAB_OUTCOMES.jsonl")
    good = [r for r in riv if not r.get("excluded")]
    hdr("THE RIVER  (sleeve closes feeding maturity)")
    print("  %s outcomes on record · %s counted · %s quarantined as fabricated"
          % (len(riv), len(good), len(riv) - len(good)))
    if good:
        wins = sum(1 for r in good if r.get("win"))
        net = sum(float(r.get("net_pct") or 0) for r in good) / len(good)
        print("  win rate %.1f%% · mean net %+.3f%%" % (wins / len(good) * 100, net))

    # ── graph coupling ───────────────────────────────────────────────────────────────
    gda = _load(d, "GRAPH_DECISION_AUDIT.json")
    hdr("GRAPH → DECISION  (is the graph earning the right to trade?)")
    if not gda:
        print("  GRAPH_DECISION_AUDIT.json absent")
    else:
        cs = gda.get("coupling_status") or {}
        print("  graph consumed by selection: %s · graded %s of %s closed trades"
              % (cs.get("consumed_by_decisions"), gda.get("trades_graded"), gda.get("trades_seen")))
        for k, v in (gda.get("features") or {}).items():
            print("     %-17s %-11s n=%-3s read_at_entry=%s"
                  % (k, v.get("verdict"), v.get("n"), v.get("read_by_selection")))

    # ── the gate ─────────────────────────────────────────────────────────────────────
    hdr("THE GATE  (100 out-of-sample trades / 90 unbroken days)")
    days = "?"
    try:
        t = datetime.fromisoformat(str(wipe.get("wiped_at")).replace("Z", "+00:00"))
        days = "%.1f" % ((now - t).total_seconds() / 86400.0)
    except Exception:
        pass
    print("  forward closes counted: %s/100 · days since last wipe: %s/90" % (len(good), days))
    print("  (any reset returns both to zero — that is the cost of resetting)")

    print("\n" + "=" * W)
    print("END OF BLOCK — now answer Q1-Q6. The questions are the part only you can do.")
    print("=" * W)
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
