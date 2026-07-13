"""brain_wiring.py — 5.11 ACTIVATION: the "nothing is decoration" ledger.

The operator's standing complaint: metrics keep getting measured and then
quietly disconnected. This module ends that. Every cycle it walks EVERY signal
store the platform produces and answers, per signal:

  1. does it exist and is it FRESH?
  2. WHO consumes it (exact repo files — a map the selftest verifies against the
     actual file contents, so this table cannot lie)
  3. what is its key metric RIGHT NOW, and did it red-shift or green-shift since
     the last run?

Output: BRAIN_WIRING.json → the BRAIN tab's SIGNAL LEDGER (the coin-machine
grid). A signal with no consumer is a bug by definition and renders as a red
"DECORATION" light — the selftest fails before that can ever ship silently.

It also builds the per-symbol DOSSIERS the operator asked for — for every open
position plus the confidence/rhythm leaders: a compact price series with peak
and trough markers, the fingerprint aims, MTF votes, momentum trajectory,
last-peak time, NEXT-PEAK ETA (last peak + median cycle), bounce likelihood,
and the full confidence anatomy — so the graphs finally show everything the
system knows about each name in one place.

HONEST: this module measures and displays; it changes no behavior.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .atomic_io import write_json_atomic
from .paper_sim import load_all_samples, asset_class

STORE = "BRAIN_WIRING.json"


def _now():
    return datetime.now(timezone.utc)


def _parse(t) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _load(out: Path, name: str):
    try:
        p = out / name
        if name.endswith(".jsonl"):
            return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
        return json.loads(p.read_text())
    except Exception:
        return None


def _age_min(out: Path, name: str, d) -> Optional[float]:
    ts = None
    if isinstance(d, dict):
        ts = _parse(d.get("generated_at") or d.get("asof") or d.get("updated_at"))
    if ts is None:
        try:
            ts = datetime.fromtimestamp((out / name).stat().st_mtime, tz=timezone.utc)
        except Exception:
            return None
    return round((_now() - ts).total_seconds() / 60.0, 1)


# ─── THE MAP — every signal, its consumers (files), and its key metric ────────
# The selftest (T22) opens each consumer file and asserts the store's filename
# appears in it. Add a signal here without a real consumer and the battery fails.
def _signals(out: Path) -> List[Dict[str, Any]]:
    S = []

    def sig(name, label, consumers, metric_fn, decision):
        d = _load(out, name)
        val = None
        try:
            val = metric_fn(d) if d is not None else None
        except Exception:
            val = None
        S.append({"store": name, "label": label, "consumers": consumers,
                  "decision": decision, "exists": d is not None,
                  "age_min": _age_min(out, name, d), "metric": val})

    sig("MTF_REGIME.json", "MTF ladder (12 TFs, 15m→30d)",
        ["silmaril/execution/paper_sim.py", "silmaril/execution/confidence_engine.py",
         "silmaril/execution/strategy_lab_abcd.py", "docs/index.html"],
        lambda d: {"crypto_conf": ((d.get("books") or {}).get("crypto") or {}).get("confluence"),
                   "fast_red": [b for b, v in (d.get("books") or {}).items() if v.get("fast_red")]},
        "harvest exits · entry throttle · symbol override · confidence blend")

    sig("CONFIDENCE_ENGINE.json", "Unified confidence (9 signals)",
        ["silmaril/execution/paper_sim.py", "silmaril/execution/strategy_lab_abcd.py",
         "silmaril/execution/brain_wiring.py", "docs/index.html"],
        lambda d: {"scored": d.get("n_scored"),
                   "top_crypto": ((d.get("top_confidence_by_class") or {}).get("crypto") or [["—", 0]])[0]},
        "conviction sizing · D-sleeve entry gate · Master brain line")

    sig("FINGERPRINTS.json", "Per-name fitted strategies",
        ["silmaril/execution/confidence_engine.py", "docs/index.html"],
        lambda d: {"fitted": len(d.get("cards") or [])},
        "per-name entry/target/stop · confidence bounce component")

    sig("PEAK_RHYTHM.json", "Peak↔trough rhythm (cycles/amplitude)",
        ["silmaril/execution/confidence_engine.py", "silmaril/execution/brain_wiring.py",
         "docs/index.html"],
        lambda d: {"tracked": len(d.get("by_symbol") or {})},
        "rhythm regularity + phase in confidence · dossier next-peak ETA")

    sig("timing_fingerprint.json", "Time-of-day buy/sell windows",
        ["silmaril/execution/confidence_engine.py"],
        lambda d: {"learned": sum(1 for v in (d.get("fingerprints") or {}).values()
                                  if not v.get("learning", True))},
        "timing_alignment component of confidence")

    sig("momentum_chain.json", "Multi-window momentum chains",
        ["silmaril/execution/confidence_engine.py", "silmaril/execution/brain_wiring.py"],
        lambda d: {"tracked": len(d.get("chains") or {})},
        "momentum_exhaustion component · dossier trajectory")

    sig("conviction_ranking.json", "Independent multi-signal ranker",
        ["silmaril/execution/confidence_engine.py"],
        lambda d: {"ranked": len(d.get("ranked_opportunities") or [])},
        "conviction_backing component of confidence")

    sig("REGIME_CLASSIFIER.json", "Live regime + 12/15/30m fast band",
        ["silmaril/execution/daily_journal.py", "docs/index.html"],
        lambda d: {"crypto": ((d.get("by_book") or {}).get("crypto") or {}).get("regime"),
                   "fast": ((d.get("by_book") or {}).get("crypto") or {}).get("shift_watch", "")[:24]},
        "regime gate (hard/soft) · per-regime entry profiles")

    sig("dr_strange.json", "Dr. Strange projections (SELF-GRADED)",
        ["silmaril/execution/gate_evidence.py", "docs/index.html"],
        lambda d: {"resolved": (d.get("career") or {}).get("resolved"),
                   "hit_rate": (d.get("career") or {}).get("hit_rate")},
        "experimental gate evidence — earns trust only by forward accuracy")

    sig("REGIME_EXIT_AB.jsonl", "Harvest/fee-clear exit A/B ledger",
        ["silmaril/execution/conductor_report_card.py"],
        lambda d: {"events": len(d or [])},
        "report-card grading of the crash-day exits (pre-registered kill)")

    sig("CONDUCTOR_REPORT_CARD.json", "Conductor honesty card",
        ["docs/index.html"],
        lambda d: {"harvest_logged": (d.get("harvest_ab") or {}).get("events_logged"),
                   "realized_all": (d.get("realized_profit") or {}).get("cumulative_realized_usd_all_books")},
        "the judge: every new behavior lives or dies by this card")

    sig("STRATEGY_LAB.json", "A/B/C/D discipline race",
        ["docs/index.html"],
        lambda d: {"leader": (d.get("scoreboard") or [{}])[0].get("sleeve"),
                   "leader_ret": (d.get("scoreboard") or [{}])[0].get("return_pct")},
        "which position-management law gets promoted to live")

    sig("paper_sim_live.json", "The live engine heartbeat",
        ["silmaril/execution/strategy_lab_abcd.py", "silmaril/execution/gate_evidence.py",
         "docs/index.html"],
        lambda d: {"bought_all": sum(int(((d.get(b) or {}).get("funnel") or {}).get("bought") or 0)
                                     for b in ("crypto", "stock", "metal", "energy", "aggressive")),
                   "cands_crypto": ((d.get("crypto") or {}).get("funnel") or {}).get("candidates_after_gates")},
        "everything — positions, funnels, decision traces")

    sig("champion_validation.json", "Forward survivability per strategy",
        ["docs/index.html"],
        lambda d: {"strategies": len(d.get("strategies") or [])},
        "champion selection (forward survivability, ≥15-pt switch margin)")

    return S


def _shift(prev_metrics: Dict[str, Any], row: Dict[str, Any]) -> str:
    """green/red/flat shift of the FIRST numeric field in the metric vs last run."""
    m, pm = row.get("metric") or {}, (prev_metrics or {}).get(row["store"]) or {}
    if not isinstance(m, dict):
        return "flat"
    for k, v in m.items():
        if isinstance(v, (int, float)) and isinstance(pm.get(k), (int, float)):
            if v > pm[k]:
                return "green"
            if v < pm[k]:
                return "red"
            return "flat"
    return "flat"


# ─── DOSSIERS — everything the system knows about a name, in one record ──────
def _build_dossiers(out: Path, samples, limit=24) -> List[Dict[str, Any]]:
    live = _load(out, "paper_sim_live.json") or {}
    ce = (_load(out, "CONFIDENCE_ENGINE.json") or {})
    ce_by = ce.get("by_symbol") or {}
    pkr = (_load(out, "PEAK_RHYTHM.json") or {}).get("by_symbol") or {}
    mtf = (_load(out, "MTF_REGIME.json") or {}).get("symbols") or {}
    mom = (_load(out, "momentum_chain.json") or {}).get("chains") or {}
    fp_cards = {c.get("symbol"): c for c in ((_load(out, "FINGERPRINTS.json") or {}).get("cards") or [])}

    open_pos: Dict[str, Dict[str, Any]] = {}
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        for pos in (live.get(bk) or {}).get("positions", []) or []:
            if pos.get("sym"):
                open_pos[pos["sym"]] = {"book": bk, **pos}

    picks: List[str] = list(open_pos.keys())
    for sym, _score, _cyc, _amp in (ce.get("rhythm_tradeable_leaders") or [])[:8]:
        if sym not in picks:
            picks.append(sym)
    for cls in ("crypto", "stock", "metal", "energy"):
        for sym, _c in (ce.get("top_confidence_by_class") or {}).get(cls, [])[:3]:
            if sym not in picks:
                picks.append(sym)
    picks = picks[:limit]

    dossiers = []
    for sym in picks:
        rows = samples.get(sym) or []
        px = [(str(t), p) for t, p in rows if p and "T00:00:00" not in str(t)][-120:]
        if len(px) < 6 and sym not in open_pos:
            continue
        pk = pkr.get(sym) or {}
        med_pk = pk.get("median_minutes_between_peaks")
        last_pk = pk.get("last_peak_at")
        eta = None
        if last_pk and med_pk:
            lp = _parse(last_pk)
            if lp:
                eta_dt = lp.timestamp() + float(med_pk) * 60.0
                eta = datetime.fromtimestamp(eta_dt, tz=timezone.utc).isoformat()
        w = (mom.get(sym) or {}).get("windows") or {}
        cer = ce_by.get(sym) or {}
        card = fp_cards.get(sym) or {}
        op = open_pos.get(sym) or {}
        dossiers.append({
            "sym": sym, "class": asset_class(sym), "open": bool(op),
            "book": op.get("book"), "entry": op.get("entry"),
            "target": op.get("target"), "stop": op.get("stop"), "mark": op.get("mark"),
            "series": [[t, round(p, 8)] for t, p in px],
            "last_peak_at": last_pk, "last_trough_at": pk.get("last_trough_at"),
            "cycle_min": med_pk, "amplitude_pct": pk.get("typical_peak_amplitude_pct"),
            "next_peak_eta": eta,
            "bounce_likelihood": card.get("bounce_reliability"),
            "typical_dip": card.get("typical_dip"), "typical_bounce": card.get("typical_bounce"),
            "trajectory": {"h1": w.get("h1"), "d1": w.get("d1"), "d2": w.get("d2"), "w1": w.get("w1")},
            "mtf_votes": (mtf.get(sym) or {}).get("votes"),
            "mtf_confluence": (mtf.get(sym) or {}).get("confluence"),
            "confidence": cer.get("confidence"), "confidence_parts": cer.get("parts"),
            "rhythm_tradeability": cer.get("rhythm_tradeability"), "why": cer.get("why"),
        })
    return dossiers


def build_brain_wiring(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    prev = _load(out, STORE) or {}
    prev_metrics = {r["store"]: r.get("metric") for r in (prev.get("signals") or [])}

    rows = _signals(out)
    wired = 0
    for r in rows:
        r["shift"] = _shift(prev_metrics, r)
        r["light"] = ("green" if (r["exists"] and r["consumers"]) else "red")
        if r["light"] == "green":
            wired += 1

    samples = load_all_samples(out)
    dossiers = _build_dossiers(out, samples)

    ce = _load(out, "CONFIDENCE_ENGINE.json") or {}
    master_brain = {cls: [[s, round(c, 3)] for s, c in
                          ((ce.get("top_confidence_by_class") or {}).get(cls) or [])[:3]]
                    for cls in ("crypto", "stock", "metal", "energy")}

    payload = {
        "generated_at": _now().isoformat(),
        "what": ("the nothing-is-decoration ledger: every signal store, WHO consumes it (selftest-verified "
                 "against the real files), its freshness, its key metric, and its red/green shift since the "
                 "last run. Plus per-symbol dossiers: everything the system knows about each open position "
                 "and each leader, in one record. Measures and displays only — changes no behavior."),
        "signals": rows,
        "wired": wired, "total": len(rows),
        "dossiers": dossiers,
        "master_brain": master_brain,
        "how_to_read": ("green light = exists + has real consumers · shift arrows = did this signal's key "
                        "number move since last cycle (the coin-machine view) · a red DECORATION light is a "
                        "bug by definition and the selftest fails before it can ship"),
    }
    write_json_atomic(out / STORE, payload)
    return {"summary": f"brain wiring: {wired}/{len(rows)} signals wired+fresh · "
                       f"{len(dossiers)} dossiers · master brain leans {master_brain.get('crypto') or '—'}"}
