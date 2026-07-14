"""conductor_report_card.py — 5.1B: the Conductor honesty & integrity system.

The operator's demand, verbatim spirit: "a full blown judgement system that
rates the Conductor's ability to pull in and out of market regimes … or judge
it harshly when it fails." Every grade here is a formula on real stores, and
the two new behaviors (regime-flip harvest, stale-capital fee-clear) plus
conviction sizing each carry their own A/B so the machine — not enthusiasm —
decides whether they stay.

A/B methods, stated plainly:
· HARVEST A/B — every REGIME_FLIP_HARVEST / FEE_CLEAR_TIME exit is logged to
  REGIME_EXIT_AB.jsonl (append-only, wipe-surviving). Once a row is ≥6h/≥24h
  old, this module prices the symbol NOW vs the exit fill: saved_pct>0 means
  selling beat holding. Kill criterion (pre-registered, Law 15): if median
  24h saved_pct ≤ 0 after 60 graded events, the knob should be turned off —
  the card will say so in plain words.
· SIZING A/B — every conviction-sized entry stores conv_frac + the flat-base
  wager it WOULD have used. On close, extra_$ = pnl − pnl×(base/wager).
  Positive total = conviction sizing out-earned flat-1000. Kill: total ≤ 0
  after 60 closed sized trades.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .atomic_io import write_json_atomic
from .paper_sim import load_all_samples

STORE = "CONDUCTOR_REPORT_CARD.json"
AB = "REGIME_EXIT_AB.jsonl"
BOOKS = ("crypto", "stock", "metal", "energy", "aggressive")


def _now():
    return datetime.now(timezone.utc)


def _j(out: Path, name: str):
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return None


def _px_now(samples, sym) -> Optional[float]:
    rows = samples.get(sym) or []
    for t, p in reversed(rows):
        if p and "T00:00:00" not in str(t):
            return float(p)
    return None


def build_conductor_report_card(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    samples = load_all_samples(out)
    sim = _j(out, "paper_sim_live.json") or {}
    bench = (_j(out, "BENCH_BOOKS.json") or {}).get("books") or {}
    mtf = (_j(out, "MTF_REGIME.json") or {}).get("books") or {}

    # ── 1 · HARVEST A/B ──────────────────────────────────────────────────
    rows: List[Dict[str, Any]] = []
    p = out / AB
    if p.exists():
        for ln in p.read_text().splitlines():
            try:
                rows.append(json.loads(ln))
            except Exception:
                continue
    graded6, graded24 = [], []
    for r in rows:
        t = r.get("t")
        try:
            age_h = (_now() - datetime.fromisoformat(str(t))).total_seconds() / 3600.0
        except Exception:
            continue
        now_px = _px_now(samples, r.get("sym"))
        if not now_px or not r.get("exit_px"):
            continue
        saved = (float(r["exit_px"]) / now_px - 1.0) * 100.0   # + = price fell after we sold
        if age_h >= 6:
            graded6.append(saved)
        if age_h >= 24:
            graded24.append(saved)

    def med(a):
        return round(sorted(a)[len(a) // 2], 2) if a else None

    harvest = {
        "events_logged": len(rows),
        "graded_6h": len(graded6), "median_saved_pct_6h": med(graded6),
        "graded_24h": len(graded24), "median_saved_pct_24h": med(graded24),
        "read": ("accruing — grades appear as events age past 6h/24h" if not graded6 else
                 f"selling on the flip has {'PAID' if (med(graded24) or med(graded6) or 0) > 0 else 'NOT paid'} "
                 f"so far (median saved {med(graded24) if graded24 else med(graded6)}%)"),
        "kill_criterion": "median 24h saved_pct ≤ 0 after 60 graded events → set regime_exit.mode=off",
    }

    # ── 2 · SIZING A/B ───────────────────────────────────────────────────
    extra = 0.0
    n_sized = 0
    for bk in BOOKS:
        d = _j(out, f"paper_book_{bk}.json") or {}
        for t in (d.get("trades") or []):
            if t.get("side") != "SELL" or t.get("conv_frac") is None:
                continue
            w = float(t.get("wager_usd") or 0)
            b = float(t.get("base_wager_usd") or 0)
            pnl = float(t.get("pnl") or 0)
            if w > 0 and b > 0:
                extra += pnl - pnl * (b / w)
                n_sized += 1
    sizing = {
        "closed_sized_trades": n_sized,
        "extra_usd_vs_flat_base": round(extra, 2),
        "read": ("accruing" if n_sized < 5 else
                 f"conviction sizing has {'out-earned' if extra > 0 else 'UNDER-earned'} flat sizing by ${abs(round(extra,2))}"),
        "kill_criterion": "extra ≤ $0 after 60 closed sized trades → set conviction_sizing.mode=off",
    }

    # ── 3 · STUCK CAPITAL (the money-on-the-table number) ────────────────
    stuck_rows = []
    stuck_usd = 0.0
    for bk in BOOKS:
        for pos in (sim.get(bk) or {}).get("positions", []) or []:
            try:
                age_h = (_now() - datetime.fromisoformat(str(pos.get("t")))).total_seconds() / 3600.0
            except Exception:
                continue
            upl = float(pos.get("upl_pct") or 0)
            if age_h >= 72 and upl < 0:
                w = float(pos.get("wager_usd") or 0)
                stuck_usd += w
                stuck_rows.append({"book": bk, "sym": pos.get("sym"),
                                    "age_h": round(age_h, 1), "upl_pct": upl, "wager_usd": w})
    stuck_rows.sort(key=lambda r: r["upl_pct"])
    stuck = {"positions": len(stuck_rows), "capital_usd": round(stuck_usd, 2),
             "worst": stuck_rows[:6],
             "read": "underwater ≥72h — the Conductor's cost line; fee-clear frees the green ones automatically"}

    # ── 4 · CRASH AVOIDANCE — red windows vs the HODL null ───────────────
    hodl = (bench.get("BENCH_HODL") or {}).get("return_pct")
    cry = None
    try:
        cry = round((sim.get("crypto", {}).get("equity", 10000) / 10000 - 1) * 100, 2)
    except Exception:
        pass
    crash = {
        "crypto_fast_red_now": bool((mtf.get("crypto") or {}).get("fast_red")),
        "crypto_vs_hodl_pct": (round(cry - float(hodl), 2)
                                if (cry is not None and hodl is not None) else None),
        "read": "Δ-vs-HODL is the crash referee: positive through red windows = the harvest/throttle earned its keep",
    }

    # ── 5 · REALIZED HARVEST (profit that actually banked) ───────────────
    total_net = 0.0
    for bk in BOOKS:
        d = _j(out, f"paper_book_{bk}.json") or {}
        total_net += float(d.get("realized_pnl") or 0)
    _sus_n, _sus_usd = 0, 0.0
    for _b, _pb in books.items():
        for _t in (_pb.get("trades") or []):
            if _t.get("side") == "SELL" and _t.get("integrity") == "SUSPECT_OSC":
                _sus_n += 1
                _sus_usd += float(_t.get("pnl") or 0.0)
    integrity = {"suspect_trades": _sus_n, "suspect_usd": round(_sus_usd, 2),
                 "verified_realized_usd": round(total_net - _sus_usd, 2),
                 "note": ("wins booked on an oscillation-quarantined tape count here, not in the "
                          "headline; recorder two-print confirmation ends the class")}
    profit = {"integrity": integrity,
              "cumulative_realized_usd_all_books": round(total_net, 2),
              "note": ("the honest 'do we have profits' number: realized only, fees inside. "
                       "Tracked as accounting — no sweep trades, no extra fees (the SGOV question, answered).")}

    payload = {
        "generated_at": _now().isoformat(),
        "what": ("the Conductor honesty & integrity card: every behavior that moves money "
                 "(flip-harvest, fee-clear, conviction sizing, throttle) is A/B-graded against "
                 "its own null, with pre-registered kill criteria. C0/C1 remain analysis-only; "
                 "nothing here grants the Master trading rights."),
        "harvest_ab": harvest,
        "sizing_ab": sizing,
        "stuck_capital": stuck,
        "crash_avoidance": crash,
        "realized_profit": profit,
    }
    write_json_atomic(out / STORE, payload)
    return {"summary": f"report card: harvest {harvest['graded_6h']}g · sized {n_sized} · "
                       f"stuck ${stuck['capital_usd']:.0f} · realized ${profit['cumulative_realized_usd_all_books']:.0f}"}
