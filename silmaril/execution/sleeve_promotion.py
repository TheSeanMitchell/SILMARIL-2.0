"""
silmaril.execution.sleeve_promotion — 7.0.2 THE PYRAMID'S MISSING RUNG.

The operator's law: sleeves (workshop probes) → the four industry books → the Master.
Until now the river only ran one way. Sleeves traded the books' candidates and wrote
resolved outcomes back as MATURITY evidence, but the books still picked their behaviour
from the backtest strategy grid — so crypto ran MR_patient_d3 while its own H PATIENT
REVERT sleeve was posting +2.46% at a 100% close rate, and energy ran HOLD_d3_t12 while
its H sleeve posted +8.3%. The workshop was winning and nobody upstairs was listening.

This module closes that rung. Each cycle it reads every sleeve's FORWARD record for a book,
elects the best one on real closed trades, and publishes the winner's DISCIPLINE for the
live book to adopt: position cap, recycle horizon, ride-winners, confidence gate, and the
patient/geometry flags.

What it does NOT do (operator's explicit instruction — "we do not want them altered, only
want the best of them selected for use"): it never edits SLEEVES, never changes how a sleeve
trades, and never touches the sleeve books. It only reads their scoreboard and hands the
winner's playbook upstairs.

Honesty rails:
  · Promotion requires REAL closed trades (min_closes), not open-position paper marks.
  · A sleeve must be beating its null (delta_vs_hodl) where that number exists; raw return
    is the fallback only when no null comparison is available yet.
  · A negative-expectancy sleeve is NEVER promoted — if the best sleeve is losing, the book
    keeps its own champion and the payload says so out loud.
  · Sticky by margin so the book cannot flip-flop between near-identical sleeves.
  · Knob: PARAM_CATALOG.sleeve_promotion {mode, min_closes, switch_margin_pct}. KILL: "off".
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .atomic_io import write_json_atomic

STORE = "SLEEVE_PROMOTION.json"
BOOKS = ("crypto", "stock", "metal", "energy")

# The discipline fields a sleeve can hand upstairs. These are POSITION-MANAGEMENT policy —
# not entry signals — which is exactly what a sleeve is: the same candidate stream, traded
# with a different hand.
DISCIPLINE_KEYS = ("cap", "recycle_h", "ride_winners", "conf_gate", "patient", "geometry", "vault")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(out: Path, name: str) -> Dict[str, Any]:
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return {}


def _score(row: Dict[str, Any]) -> Optional[float]:
    """Forward score for a sleeve. Δ-vs-null is the honest yardstick (Law 10); raw return is
    the fallback only while a book has no null comparison yet. None = not gradeable."""
    d = row.get("delta_vs_hodl")
    if d is not None:
        try:
            return float(d)
        except Exception:
            pass
    r = row.get("return_pct")
    try:
        return float(r) if r is not None else None
    except Exception:
        return None


def build_sleeve_promotion(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    cat = _load(out, "PARAM_CATALOG.json")
    knob = (cat.get("sleeve_promotion") or {})
    mode = str(knob.get("mode", "auto")).lower()
    min_closes = int(knob.get("min_closes", 3) or 3)
    margin = float(knob.get("switch_margin_pct", 0.75) or 0.75)

    lab = _load(out, "STRATEGY_LAB.json")
    by_ind = lab.get("by_industry") or {}
    sleeves_def = lab.get("sleeves_def") or {}
    prev = _load(out, STORE).get("books") or {}

    books: Dict[str, Any] = {}
    for bk in BOOKS:
        rows = by_ind.get(bk) or []
        graded = []
        for r in rows:
            closed = int(r.get("closed") or 0)
            sc = _score(r)
            if closed >= min_closes and sc is not None:
                graded.append((sc, r))
        prev_bk = prev.get(bk) or {}
        prev_sleeve = prev_bk.get("sleeve")

        if not graded:
            # 7.0.4 IMMEDIATE SEED: rather than leaving a book on an unrelated grid champion while its
            # workshop warms up, adopt the best sleeve on whatever evidence exists and mark it
            # PROVISIONAL. A book should start with our best current hand, not a stranger's.
            if bool(knob.get("seed_immediately", True)) and rows:
                seed = None
                for r in rows:
                    sc = _score(r)
                    if sc is None:
                        continue
                    if seed is None or sc > (_score(seed) or -1e9):
                        seed = r
                # ── 7.1.7 THE WARM START ───────────────────────────────────────────────
                # Right after a wipe every sleeve has zero closes, so _score() is None for
                # all of them and `seed` stays None — the PROVISIONAL pick was effectively a
                # coin flip, and the book then waited days for whichever sleeve happened to
                # close three trades first, good or bad. WARM_START.json answers that from
                # real stored tape: which personality had the best edge over doing nothing on
                # THIS book's own names, and which resolved trades fastest. It is a
                # hypothesis, never evidence — it seeds the hand and nothing else. The arming
                # gate is untouched: three REAL forward closes still stand between this pick
                # and a funded trade.
                # The real "no forward evidence" test is whether ANY sleeve has actually closed
                # a trade — not whether _score returned None. A freshly wiped sleeve carries
                # delta_vs_hodl: 0.0, so _score gives 0.0 for every one of them and `seed`
                # lands on whichever sorts first. That is the coin flip this release exists to
                # remove, and it hid behind a `seed is None` check that could never be true.
                _has_evidence = any(int(r.get("closed") or 0) > 0 for r in rows)
                _ws_used = None
                if seed is None or not _has_evidence:
                    try:
                        from .warm_start import recommended_sleeve as _rec
                        _pick = _rec(out, bk)
                        if _pick:
                            for r in rows:
                                if r.get("sleeve") == _pick:
                                    seed, _ws_used = r, _pick
                                    break
                    except Exception:
                        pass
                if seed is not None:
                    sk = seed.get("sleeve")
                    cfg = (sleeves_def.get(sk) or {}) if isinstance(sleeves_def, dict) else {}
                    books[bk] = {
                        "seed_source": ("warm_start (backtest hypothesis on this book's own tape)"
                                        if _ws_used else "forward score"),
                        "sleeve": sk, "name": seed.get("name"),
                        "discipline": {k: cfg.get(k) for k in DISCIPLINE_KEYS
                                       if cfg.get(k) is not None} or None,
                        "status": "PROVISIONAL",
                        "arms_book": False, "closes_needed": min_closes,
                        "why": (f"seeded with the best available sleeve {sk} {seed.get('name')} "
                                f"({(_score(seed) or 0):+.2f}%) — PROVISIONAL: under {min_closes} "
                                f"closed trades, so it holds the seat only until a sleeve proves itself"),
                        "evidence": {"closed": int(seed.get("closed") or 0),
                                     "win_rate": seed.get("win_rate"),
                                     "return_pct": seed.get("return_pct"),
                                     "delta_vs_hodl": seed.get("delta_vs_hodl"),
                                     "score": round(float(_score(seed) or 0), 3)},
                        "candidates_graded": 0, "changed": False, "previous": prev_sleeve,
                    }
                    continue
            books[bk] = {
                "sleeve": None, "name": None, "discipline": None,
                "status": "WAITING",
                "arms_book": False, "closes_needed": min_closes,
                "why": (f"no sleeve has {min_closes}+ closed trades yet — the book keeps its own "
                        f"champion until the workshop has real forward evidence to hand up"),
                "candidates_graded": 0,
            }
            continue

        graded.sort(key=lambda t: t[0], reverse=True)
        best_score, best = graded[0]

        # A losing sleeve is never promoted. If the workshop's best is under water, the book
        # keeps its own champion and we say so plainly.
        if best_score <= 0:
            books[bk] = {
                "sleeve": None, "name": None, "discipline": None,
                "status": "NO_POSITIVE_SLEEVE",
                "arms_book": False, "closes_needed": min_closes,
                "why": (f"best sleeve {best.get('sleeve')} {best.get('name')} scores "
                        f"{best_score:+.2f}% — negative expectancy is not promotable; the book "
                        f"keeps its own champion until a sleeve earns its way up"),
                "candidates_graded": len(graded),
            }
            continue

        chosen, why = best, (f"{best.get('sleeve')} {best.get('name')} leads the {bk} workshop "
                             f"at {best_score:+.2f}% over {int(best.get('closed') or 0)} closed trades")
        # Anti-flip-flop: an incumbent keeps the seat unless the challenger clears the margin.
        if prev_sleeve and prev_sleeve != best.get("sleeve"):
            inc = next((r for _s, r in graded if r.get("sleeve") == prev_sleeve), None)
            inc_score = _score(inc) if inc else None
            if inc_score is not None and best_score < inc_score + margin:
                chosen = inc
                why = (f"{prev_sleeve} holds: challenger {best.get('sleeve')} "
                       f"({best_score:+.2f}%) does not clear the {margin:.2f}pt margin over "
                       f"{inc_score:+.2f}%")

        sk = chosen.get("sleeve")
        cfg = (sleeves_def.get(sk) or {}) if isinstance(sleeves_def, dict) else {}
        discipline = {k: cfg.get(k) for k in DISCIPLINE_KEYS if cfg.get(k) is not None}
        books[bk] = {
            "sleeve": sk,
            "name": chosen.get("name"),
            "discipline": discipline or None,
            "status": "PROMOTED" if mode != "off" else "PROMOTED_SHADOW",
            "arms_book": mode != "off", "closes_needed": min_closes,
            "why": why,
            "evidence": {
                "closed": int(chosen.get("closed") or 0),
                "win_rate": chosen.get("win_rate"),
                "return_pct": chosen.get("return_pct"),
                "delta_vs_hodl": chosen.get("delta_vs_hodl"),
                "score": round(float(_score(chosen) or 0), 3),
            },
            "candidates_graded": len(graded),
            "changed": bool(prev_sleeve and prev_sleeve != sk),
            "previous": prev_sleeve,
        }

    payload = {
        "generated_at": _now(),
        "mode": mode,
        "min_closes": min_closes,
        "switch_margin_pct": margin,
        "books": books,
        "what": ("THE PYRAMID, RUNG 2: each industry book adopts the DISCIPLINE (position cap, "
                 "recycle horizon, ride-winners, confidence gate, patient/geometry flags) of the "
                 "best sleeve in its own workshop, judged on real closed trades vs the null. "
                 "Sleeve behaviour is never altered — only selected. The Master then mirrors the "
                 "books, so the workshop's best hand reaches the top of the pyramid."),
        "law": ("Promotion needs closed trades, positive expectancy, and a margin over the "
                "incumbent. A losing workshop promotes nobody. 7.1 ARMING: only PROMOTED "
                "arms its book to spend — PROVISIONAL seeds the discipline (the hand) but "
                "never the license; the book observes until its own workshop has proven a "
                "sleeve on real closed trades since the wipe."),
    }
    try:
        write_json_atomic(out / STORE, payload)
    except Exception:
        pass
    return payload


def promoted_discipline(out_dir, book: str) -> Dict[str, Any]:
    """What the live book should adopt this cycle. Empty dict = keep the book's own champion.
    Returns {} when the knob is off, so the kill switch is total."""
    out = Path(out_dir)
    cat = _load(out, "PARAM_CATALOG.json")
    if str((cat.get("sleeve_promotion") or {}).get("mode", "auto")).lower() == "off":
        return {}
    rec = ((_load(out, STORE).get("books") or {}).get(book) or {})
    if rec.get("status") not in ("PROMOTED", "PROVISIONAL"):
        return {}
    return dict(rec.get("discipline") or {})


if __name__ == "__main__":
    import sys
    p = build_sleeve_promotion(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    for b, r in (p.get("books") or {}).items():
        print(f"{b:8} {r.get('status'):18} {r.get('sleeve') or '—'} {r.get('name') or ''} :: {r.get('why')}")
