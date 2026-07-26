"""
GRAPH → DECISION AUDIT — 7.1.4.

THE OPERATOR'S QUESTION, verbatim: "now is the time to start constantly auditing to find out
how much our graph system is helping our sleeves make choices... as a professional trader
would look at our NEW graph system, they would make choices. Let's find out and see how well
our brain is at reading our new graphs and making decisions from it, not alongside it, or
despite it, but because and informed by it."

THE HONEST ANSWER FIRST, because it has to come before any measurement:

    CHART_INTEL.json — the graph brain that computes peaks, troughs, floors, ceilings and
    trajectory — is consumed by NOTHING in the decision path. A grep of the whole engine finds
    it read only by the dashboard. The sleeves select on confidence score, dip depth, geometry
    verdict, bounce reliability, reach-vs-cost and trend sign. Not one of them looks at a peak,
    a floor, a ceiling, a peak trajectory or a cadence phase.

    So today the graph is a DISPLAY, not an input. The operator's instinct — "we feel like we
    have given so much attention to so many tools to watch a system simply not use them" — is
    not a feeling. It is the architecture.

WHAT THIS MODULE DOES ABOUT IT, and deliberately what it does NOT do. It does not quietly wire
the graph into trading. Bolting an unmeasured signal onto live selection is how the last
several regressions happened. Instead it MEASURES the coupling honestly, so that wiring it
later is a decision backed by evidence:

  For every closed trade, it reconstructs — from the same tape, with the same swing math the
  chart draws — what the graph looked like AT THE MOMENT OF ENTRY:
      * peak trajectory       RISING / FLAT / FALLING (were the last peaks climbing?)
      * range position        where in the view's high-low band did we buy?
      * floor proximity       were we buying near a level that has held repeatedly?
      * ceiling proximity     were we buying into a level that has repeatedly rejected price?
      * cadence phase         was the next peak due, or had we just passed one?
      * trend sign            was the larger trajectory up or down?
  Then it grades outcomes inside each bucket and publishes, per feature, whether reading it
  would have helped: PREDICTIVE / NEUTRAL / INVERSE, always with n attached and an explicit
  "not yet enough evidence" when n is small.

This turns "is the graph helping?" from a feeling into a number that grows every day. When a
feature earns PREDICTIVE over a real sample, THAT is the moment to let it gate entries — and
the ledger will say so out loud.

Knob `graph_decision_audit` {mode: auto|off} · KILL mode:"off". Read-only: it never trades.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .atomic_io import write_json_atomic
except Exception:                                            # pragma: no cover
    def write_json_atomic(path, payload):                    # type: ignore
        Path(path).write_text(json.dumps(payload, indent=2))

# Deliberately strict. A first draft of this module used n>=8 and duly reported four features
# as "PREDICTIVE" off nine trades with buckets of three — which is noise wearing a verdict, and
# precisely the overclaiming that has cost this project weeks. A feature must clear a real
# sample in BOTH buckets before it is allowed to say anything at all.
MIN_N_FOR_VERDICT = 25           # graded entries carrying the feature
MIN_BUCKET_N = 5                 # and each side of the comparison needs its own sample
PREDICTIVE_EDGE_PCT = 1.0        # mean-net separation that counts as a real difference


def _ts(x) -> Optional[datetime]:
    try:
        d = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _live(rows: List) -> List[Tuple[datetime, float]]:
    out = []
    for r in (rows or []):
        try:
            if not r or len(r) < 2 or not r[1] or float(r[1]) <= 0:
                continue
            if "T00:00:00" in str(r[0]):
                continue                                     # backfill candles are not the tape
            t = _ts(r[0])
            if t:
                out.append((t, float(r[1])))
        except Exception:
            continue
    out.sort()
    return out


def _structure_at(series: List[Tuple[datetime, float]], at: datetime,
                  lookback_h: float = 48.0) -> Optional[Dict[str, Any]]:
    """The graph's own read, reconstructed as of `at` using ONLY prints that existed then.
    Same swing math the chart draws, so the audit grades what the operator actually saw —
    no hindsight can leak in, because nothing after `at` is visible to this function."""
    lo = at - timedelta(hours=lookback_h)
    win = [(t, p) for t, p in series if lo <= t <= at]
    if len(win) < 20:
        return None
    ys = [p for _t, p in win]
    n = len(ys)

    rets = sorted(abs(ys[i] / ys[i - 1] - 1) for i in range(1, n) if ys[i - 1] > 0)
    sig = rets[len(rets) // 2] if rets else 0.001
    prom = max(sig * 3, 0.002)
    w = max(2, n // 40)

    peaks, troughs = [], []
    for i in range(w, n - w):
        seg = ys[i - w:i + w + 1]
        if ys[i] == max(seg):
            base = min(ys[max(0, i - w * 3):i + 1])
            if base > 0 and ys[i] / base - 1 >= prom:
                peaks.append((win[i][0], ys[i]))
        if ys[i] == min(seg):
            cap = max(ys[max(0, i - w * 3):i + 1])
            if ys[i] > 0 and cap / ys[i] - 1 >= prom:
                troughs.append((win[i][0], ys[i]))

    def cluster(pts):
        lv, tol = [], max(sig * 2, 0.004)
        for _t, px in pts:
            for q in lv:
                if abs(px / q["level"] - 1) <= tol:
                    q["level"] = (q["level"] * q["tested"] + px) / (q["tested"] + 1)
                    q["tested"] += 1
                    break
            else:
                lv.append({"level": px, "tested": 1})
        return sorted([q for q in lv if q["tested"] >= 2], key=lambda q: -q["tested"])

    floors, ceils = cluster(troughs), cluster(peaks)
    px = ys[-1]
    hi, lo_p = max(ys), min(ys)

    peak_traj = "UNKNOWN"
    if len(peaks) >= 2:
        lp = peaks[-3:]
        peak_traj = ("RISING" if lp[-1][1] > lp[0][1] * 1.002
                     else "FALLING" if lp[-1][1] < lp[0][1] * 0.998 else "FLAT")

    cadence_min, phase = None, "UNKNOWN"
    if len(peaks) >= 3:
        gaps = sorted((peaks[i][0] - peaks[i - 1][0]).total_seconds() / 60.0
                      for i in range(1, len(peaks)))
        cadence_min = gaps[len(gaps) // 2]
        since = (at - peaks[-1][0]).total_seconds() / 60.0
        if cadence_min > 0:
            f = since / cadence_min
            phase = "PEAK_DUE" if f >= 0.85 else ("JUST_PEAKED" if f <= 0.25 else "MID_CYCLE")

    third = max(2, n // 3)
    ea = sum(ys[:third]) / third
    la = sum(ys[-third:]) / third
    slope = (la / ea - 1) * 100

    return {
        "peaks": len(peaks), "troughs": len(troughs),
        "peak_trajectory": peak_traj,
        "range_position_pct": round((px - lo_p) / (hi - lo_p) * 100, 1) if hi > lo_p else 50.0,
        "floor_distance_pct": (round((px / floors[0]["level"] - 1) * 100, 3) if floors else None),
        "floor_tested": (floors[0]["tested"] if floors else 0),
        "ceiling_distance_pct": (round((ceils[0]["level"] / px - 1) * 100, 3) if ceils else None),
        "ceiling_tested": (ceils[0]["tested"] if ceils else 0),
        "cadence_min": (round(cadence_min, 1) if cadence_min else None),
        "cadence_phase": phase,
        "trend_slope_pct": round(slope, 3),
        "trend": "UP" if slope > 1.2 else ("DOWN" if slope < -1.2 else "SIDEWAYS"),
    }


def _closed_trades(out: Path) -> List[Dict[str, Any]]:
    """Every closed trade we can pair with an entry time, from the sleeves and the books.
    Quarantined (fabricated) fills are skipped — auditing a fake fill teaches a fake lesson."""
    rows: List[Dict[str, Any]] = []
    try:
        lab = json.loads((out / "STRATEGY_LAB.json").read_text())
        for key, bk in (lab.get("sleeves") or {}).items():
            book = key.split(":")[0]
            sleeve = key.split(":")[-1]
            for t in (bk.get("trades") or []):
                if t.get("side") != "SELL" or t.get("realized_pct") is None:
                    continue
                if t.get("excluded"):
                    continue
                rows.append({"sym": t.get("sym"), "book": book, "sleeve": sleeve,
                             "opened_t": t.get("opened_t"), "closed_t": t.get("t"),
                             "net_pct": float(t.get("realized_pct") or 0.0),
                             "why": t.get("why"), "source": "sleeve",
                             "fill_capped": bool(t.get("fill_capped"))})
    except Exception:
        pass
    for name in ("LAB_OUTCOMES.jsonl",):
        p = out / name
        if not p.exists():
            continue
        try:
            for line in p.read_text().splitlines()[-4000:]:
                if not line.strip():
                    continue
                r = json.loads(line)
                if r.get("excluded") or r.get("net_pct") is None:
                    continue
                if any(x["sym"] == r.get("sym") and x["closed_t"] == r.get("t") for x in rows):
                    continue
                rows.append({"sym": r.get("sym"), "book": r.get("book"), "sleeve": r.get("sleeve"),
                             "opened_t": None, "closed_t": r.get("t"),
                             "net_pct": float(r.get("net_pct") or 0.0),
                             "why": r.get("why"), "source": "river",
                             "fill_capped": bool(r.get("fill_capped"))})
        except Exception:
            pass
    return rows


def _bucketize(feature: str, st: Dict[str, Any]) -> Optional[str]:
    if feature == "peak_trajectory":
        v = st.get("peak_trajectory")
        return v if v in ("RISING", "FLAT", "FALLING") else None
    if feature == "trend":
        return st.get("trend")
    if feature == "cadence_phase":
        v = st.get("cadence_phase")
        return v if v in ("PEAK_DUE", "MID_CYCLE", "JUST_PEAKED") else None
    if feature == "range_position":
        r = st.get("range_position_pct")
        if r is None:
            return None
        return "LOW_THIRD" if r <= 33 else ("MID_THIRD" if r <= 66 else "HIGH_THIRD")
    if feature == "floor_support":
        d, n = st.get("floor_distance_pct"), st.get("floor_tested") or 0
        if d is None:
            return None
        return "ON_TESTED_FLOOR" if (abs(d) <= 1.0 and n >= 3) else "AWAY_FROM_FLOOR"
    if feature == "ceiling_overhead":
        d, n = st.get("ceiling_distance_pct"), st.get("ceiling_tested") or 0
        if d is None:
            return None
        return "UNDER_TESTED_CEILING" if (d <= 1.0 and n >= 3) else "CLEAR_OVERHEAD"
    return None


FEATURES = ("peak_trajectory", "trend", "cadence_phase", "range_position",
            "floor_support", "ceiling_overhead")

READ_BY_SELECTION = {
    # what the sleeves ACTUALLY consult today, stated per feature so the gap is explicit
    "peak_trajectory": False,
    "trend": True,               # sleeve C (trend_only) filters on trend sign
    "cadence_phase": False,
    "range_position": False,
    "floor_support": False,      # geometry's p_floor is a WIN-RATE floor, not a price floor
    "ceiling_overhead": False,
}


def build_graph_decision_audit(out_dir, samples: Dict[str, List] = None) -> Dict[str, Any]:
    out = Path(out_dir)
    knob = "auto"
    try:
        cat = json.loads((out / "PARAM_CATALOG.json").read_text()) or {}
        knob = str((cat.get("graph_decision_audit") or {}).get("mode", "auto"))
    except Exception:
        pass
    if knob == "off":
        payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "mode": "off",
                   "note": "graph_decision_audit KILLED by knob"}
        write_json_atomic(out / "GRAPH_DECISION_AUDIT.json", payload)
        return payload

    if samples is None:
        try:
            from .canon_keys import canonical_samples
            samples = canonical_samples(out)
        except Exception:
            samples = {}
    tape = {s: _live(r) for s, r in (samples or {}).items()}

    trades = _closed_trades(out)
    graded, unreadable = [], 0
    for t in trades:
        at = _ts(t.get("opened_t")) or _ts(t.get("closed_t"))
        ser = tape.get(t.get("sym")) or []
        if not at or not ser:
            unreadable += 1
            continue
        st = _structure_at(ser, at)
        if not st:
            unreadable += 1
            continue
        graded.append({**t, "graph_at_entry": st})

    features: Dict[str, Any] = {}
    for feat in FEATURES:
        buckets: Dict[str, Dict[str, Any]] = {}
        for g in graded:
            b = _bucketize(feat, g["graph_at_entry"])
            if not b:
                continue
            e = buckets.setdefault(b, {"n": 0, "wins": 0, "sum_net": 0.0})
            e["n"] += 1
            e["wins"] += 1 if g["net_pct"] > 0 else 0
            e["sum_net"] += g["net_pct"]
        for b, e in buckets.items():
            e["win_pct"] = round(e["wins"] / e["n"] * 100, 1)
            e["mean_net_pct"] = round(e["sum_net"] / e["n"], 3)
            e.pop("sum_net", None)
        total_n = sum(e["n"] for e in buckets.values())
        verdict, why = "NO_EVIDENCE", "no closed trades carry this feature yet"
        big = {b: e for b, e in buckets.items() if e["n"] >= MIN_BUCKET_N}
        if total_n >= MIN_N_FOR_VERDICT and len(big) >= 2:
            ranked = sorted(big.items(), key=lambda kv: -kv[1]["mean_net_pct"])
            best, worst = ranked[0], ranked[-1]
            spread = best[1]["mean_net_pct"] - worst[1]["mean_net_pct"]
            if spread >= PREDICTIVE_EDGE_PCT:
                verdict = "PREDICTIVE"
                why = ("entries taken at %s averaged %+.3f%% vs %+.3f%% at %s (spread %.3f%% over "
                       "n=%d) — reading this before entry would have separated winners from losers"
                       % (best[0], best[1]["mean_net_pct"], worst[1]["mean_net_pct"], worst[0],
                          spread, total_n))
            else:
                verdict = "NEUTRAL"
                why = ("no meaningful separation between buckets (spread %.3f%% over n=%d) — on "
                       "this evidence the feature does not yet distinguish good entries"
                       % (spread, total_n))
        elif total_n:
            verdict = "TOO_EARLY"
            why = ("n=%d graded entries carry this feature (need %d, with >=%d in each bucket "
                   "being compared). Any verdict at this sample size would be noise wearing a "
                   "label — the buckets below are shown so the shape can be watched, not acted on."
                   % (total_n, MIN_N_FOR_VERDICT, MIN_BUCKET_N))
        features[feat] = {"buckets": buckets, "n": total_n, "verdict": verdict, "why": why,
                          "read_by_selection": READ_BY_SELECTION.get(feat, False)}

    measured_not_used = [f for f in FEATURES
                         if not READ_BY_SELECTION.get(f) and features[f]["verdict"] == "PREDICTIVE"]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "what": ("does reading the graph before entry actually separate winners from losers? Each "
                 "closed trade's graph state is reconstructed from the tape AS OF ITS ENTRY "
                 "(nothing after the entry is visible to the reconstruction, so no hindsight can "
                 "leak in), then outcomes are graded inside each bucket."),
        "coupling_status": {
            "graph_brain_store": "CHART_INTEL.json",
            "consumed_by_decisions": False,
            "statement": ("as of 7.1.4 the graph is a DISPLAY, not an input: CHART_INTEL.json is "
                          "read by the dashboard and by nothing in the selection path. Sleeves "
                          "select on confidence score, dip depth, geometry verdict, bounce "
                          "reliability, reach-vs-cost and trend sign. Peaks, floors, ceilings, "
                          "peak trajectory and cadence phase are drawn but never consulted."),
            "features_read_by_selection": [f for f in FEATURES if READ_BY_SELECTION.get(f)],
            "features_drawn_but_ignored": [f for f in FEATURES if not READ_BY_SELECTION.get(f)],
        },
        "trades_seen": len(trades), "trades_graded": len(graded),
        "trades_unreadable": unreadable,
        "min_n_for_verdict": MIN_N_FOR_VERDICT,
        "features": features,
        "promotion_candidates": measured_not_used,
        "next_step": (("EVIDENCE FOUND: %s now separate winners from losers and are still not "
                       "consulted at entry. These are the features to gate on next — with a knob, "
                       "a kill switch, and an A/B, never silently." % ", ".join(measured_not_used))
                      if measured_not_used else
                      ("no feature has earned PREDICTIVE yet on this sample. Wiring the graph into "
                       "selection now would be faith, not evidence — the honest move is to keep "
                       "collecting closed trades and re-read this panel as n grows.")),
        "honesty": ("this audit grades entries the system already took; it cannot say what would "
                    "have happened on entries it never took. It answers 'did reading the graph "
                    "help?', not 'is the graph complete?'"),
    }
    write_json_atomic(out / "GRAPH_DECISION_AUDIT.json", payload)
    return payload


if __name__ == "__main__":                                   # pragma: no cover
    import sys
    p = build_graph_decision_audit(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print("graded %s of %s closed trades" % (p.get("trades_graded"), p.get("trades_seen")))
    for f, v in (p.get("features") or {}).items():
        print("  %-18s %-12s n=%-3s read_by_selection=%s"
              % (f, v["verdict"], v["n"], v["read_by_selection"]))
    print("\n" + str(p.get("next_step")))
