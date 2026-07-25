"""
silmaril.execution.fingerprint — PER-VALUABLE IDENTITY + REALISTIC STRATEGY FITTER

The operator's vision, finally driving live entries: the system should look at EACH valuable's
own chart the way a professional trader does — its multi-timeframe trend, how far it TYPICALLY
dips before it bounces, how far it TYPICALLY recovers, how volatile it is, its rhythm — and fit a
custom strategy to THAT valuable, not paint every market with one blanket 2%/2% brush.

Two pure functions, computed only from a symbol's OWN real price history (no synthetic data):

  fingerprint(prices, rows) -> the valuable's identity:
      trend over ~1d/2d/3d/1w, a trend label, whether it is in a strong multi-timeframe uptrend
      (or a genuine multi-day decline), its TYPICAL dip depth (median ~1h drawdown), its TYPICAL
      bounce (median recovery after those dips over ~1 day), its bounce reliability (how often it
      recovers to the pre-dip level), and its volatility.

  fit_strategy(fp, cost, floor_min, ...) -> a realistic, custom-fitted {dir, entry, target, stop}:
      ENTRY  = buy when the name has dipped ~its OWN typical amount (so we buy meaningful dips for
               that valuable, not a blanket threshold it rarely hits or hits constantly).
      TARGET = a REALISTIC fraction of the name's typical bounce (default 66%), floored to clear
               round-trip fees. Aiming at 2/3 of what the name usually recovers is what lifts the
               close rate and the win rate — an achievable goal, not an optimistic one. If even a
               realistic bounce can't clear fees, the fitter returns None and the name is skipped
               (fee-honest — some valuables simply have no post-cost mean-reversion edge).
      STOP   = scaled to the name's OWN typical dip (room to dip more than usual before giving up),
               floored by the book heatshield, capped so risk/reward never goes absurd.

The fit is attached to every resulting trade so each trade log shows the exact custom strategy
that was applied, derived from that valuable's fingerprint. Offline-safe; deterministic.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _clean(prices: List[float]) -> List[float]:
    return [float(x) for x in prices if x and x > 0]


def _returns(p: List[float], k: int) -> List[float]:
    return [p[i] / p[i - k] - 1 for i in range(k, len(p)) if p[i - k] > 0]


def _ret_over_window(rows, minutes: int, p: List[float], bars_fallback: int) -> float:
    """Return over the last `minutes` using real timestamps when available, else an index
    fallback assuming ~10-minute bars. rows = [[iso_ts, price], ...] (may include daily T00:00:00)."""
    if rows:
        try:
            intr = [(t, x) for t, x in rows if x and x > 0 and "T00:00:00" not in str(t)]
            if len(intr) >= 2:
                last_t = datetime.fromisoformat(intr[-1][0])
                if last_t.tzinfo is None:
                    last_t = last_t.replace(tzinfo=timezone.utc)
                cutoff = last_t.timestamp() - minutes * 60
                ref = None
                for t, x in intr:
                    tt = datetime.fromisoformat(t)
                    if tt.tzinfo is None:
                        tt = tt.replace(tzinfo=timezone.utc)
                    if tt.timestamp() <= cutoff:
                        ref = x
                    else:
                        break
                if ref and ref > 0:
                    return intr[-1][1] / ref - 1
        except Exception:
            pass
    if len(p) > bars_fallback and p[-1 - bars_fallback] > 0:
        return p[-1] / p[-1 - bars_fallback] - 1
    if len(p) >= 2 and p[0] > 0:
        return p[-1] / p[0] - 1
    return 0.0


def fingerprint(prices: List[float], rows=None, dip_h: int = 6, bounce_h: int = 144) -> Dict[str, Any]:
    p = _clean(prices)
    n = len(p)
    fp: Dict[str, Any] = {"n": n, "ok": False}
    if n < 30:
        return fp

    r1 = _returns(p, 1)
    vol = statistics.pstdev(r1) if len(r1) > 2 else 0.0

    t1d = _ret_over_window(rows, 1440, p, 144)
    t2d = _ret_over_window(rows, 2880, p, 288)
    t3d = _ret_over_window(rows, 4320, p, 432)
    t1w = _ret_over_window(rows, 10080, p, 1008)
    ups = sum(1 for t in (t1d, t2d, t3d, t1w) if t > 0.005)
    downs = sum(1 for t in (t1d, t2d, t3d, t1w) if t < -0.005)
    trend = "up" if ups >= 3 else "down" if downs >= 3 else "mixed"
    # a genuinely strong multi-timeframe uptrend (used for the regime override)
    strong_up = (t1d > 0 and t3d > 0.01 and t1w > 0.02 and downs == 0)
    falling = (downs >= 3 and t1w < -0.02 and t3d < -0.01)   # a GENUINE multi-day decline, not sideways noise

    # TYPICAL DIP: median magnitude of the negative ~1h moves this name makes
    dips = [x for x in _returns(p, dip_h) if x < 0]
    # 7.0.9: publish the dip-event count. The maturity gate asks "how many dip events have we
    # actually observed on this name" and had no field to read — see the fit_strategy note below.
    fp["dip_samples"] = len(dips)
    typical_dip = abs(statistics.median(dips)) if len(dips) >= 5 else (
        abs(statistics.median(_returns(p, dip_h))) if _returns(p, dip_h) else 0.0)

    # TYPICAL BOUNCE: after a ~typical dip, the median best forward recovery over bounce_h
    bounces: List[float] = []
    thr = max(typical_dip * 0.8, 0.002)
    i = dip_h
    while i < n - 1:
        if p[i - dip_h] > 0 and (p[i] / p[i - dip_h] - 1) <= -thr:
            fwd = p[i + 1: i + 1 + bounce_h]
            if fwd:
                bounces.append(max(fwd) / p[i] - 1)
            i += dip_h
        else:
            i += 1
    typical_bounce = statistics.median(bounces) if len(bounces) >= 3 else None

    # BOUNCE RELIABILITY: of those dips, how often price returned to the pre-dip level in horizon
    hits = tries = 0
    i = dip_h
    while i < n - 1:
        if p[i - dip_h] > 0 and (p[i] / p[i - dip_h] - 1) <= -thr:
            tries += 1
            if any(p[k] >= p[i - dip_h] for k in range(i + 1, min(n, i + 1 + bounce_h))):
                hits += 1
            i += dip_h
        else:
            i += 1
    reliability = (hits / tries) if tries >= 3 else None

    fp.update({"ok": True, "vol": round(vol, 5), "t1d": round(t1d, 4), "t2d": round(t2d, 4),
               "t3d": round(t3d, 4), "t1w": round(t1w, 4), "trend": trend,
               "strong_up": bool(strong_up), "falling": bool(falling),
               "typical_dip": round(typical_dip, 4),
               "typical_bounce": round(typical_bounce, 4) if typical_bounce is not None else None,
               "bounce_reliability": round(reliability, 3) if reliability is not None else None,
               "dip_samples": len(dips), "bounce_samples": len(bounces)})
    return fp


def fit_strategy(fp: Dict[str, Any], cost: float, floor_min: Optional[float],
                 realism: float = 0.66, min_entry: float = 0.003, max_entry: float = 0.05,
                 cap_target: float = 0.06, target_margin: float = 0.003,
                 stop_dip_mult: float = 3.0, cap_stop: float = 0.20,
                 min_reliability: float = 0.3,
                 falling_min_reliability: float = 0.6) -> Optional[Dict[str, Any]]:
    """Fit a realistic custom strategy for this valuable, or None if it can't clear fees."""
    if not fp.get("ok"):
        return None
    # ── 7.0.8 EVIDENCE OUTRANKS THE LABEL (the operator's founding doctrine, finally applied here).
    # This used to be a blanket `if falling: return None`, and it ran BEFORE the measured
    # bounce-reliability check — so a name's own recorded behaviour never got a vote. The cost was
    # enormous: 384 of the 473 unfitted names were rejected on that label alone, and 126 of them
    # carried a MEASURED bounce reliability of 0.6 or better. WIF-USD recovers from a 0.66% dip to
    # a 1.94% bounce 90% of the time; SAND, BLUR, ROSE, TIA and SNX look the same. Every one was
    # thrown away for being "falling".
    #
    # The point-in-time backtest said the same thing from the other direction: across 89 closed
    # trades DOWNTREND names won 76.2% and made +53.68, while a structure veto that blocked them
    # cost -284.98 and refused 16 consecutive winners on 2026-07-13.
    #
    # So the label no longer decides. A falling name may still be fitted IF its own tape shows it
    # reliably recovers; a falling name with weak or no recovery evidence is still refused, which
    # is the real falling-knife case. KILL: set falling_min_reliability to 1.1 to restore the old
    # blanket rejection.
    if fp.get("falling"):
        _relf = fp.get("bounce_reliability")
        if _relf is None or _relf < falling_min_reliability:
            return None
    rel = fp.get("bounce_reliability")
    if rel is not None and rel < min_reliability:
        return None  # measured, and it does NOT reliably recover -> skip (raises the win rate)

    td = fp.get("typical_dip") or min_entry
    tb = fp.get("typical_bounce")

    entry = min(max(td, min_entry), max_entry)

    if tb and tb > 0:
        target = tb * realism                     # aim at 2/3 of what it USUALLY recovers
    else:
        target = max(entry * 1.2, cost + target_margin)
    realistic_floor = cost + target_margin        # must clear round-trip fees with margin
    if target < realistic_floor:
        # a realistic bounce cannot clear fees on this name -> no honest edge, skip
        return None
    target = min(target, cap_target)

    # STOP: give the name room to dip MORE than it usually does before giving up (sit-through-heat),
    # scaled to the valuable's OWN typical dip, floored by the book heatshield, capped so risk/reward
    # never goes absurd (a 22% stop for a 6% target is not a trade a pro takes).
    stop = min(cap_stop, max(float(floor_min or 0.06), (fp.get("typical_dip") or 0.0) * stop_dip_mult))

    # ── 7.0.9 THE SILENT DEADLOCK, and this one has been costing real trades since 7.0-FINAL. ──
    # The maturity gate in paper_sim does:
    #       _ev7 = int(_ftm.get("dip_samples") or _ftm.get("n") or 0)
    # where _ftm is THIS dict. But this dict never carried either field, so _ev7 evaluated to 0 for
    # every name, on every cycle, forever — and every candidate was judged "immature" no matter how
    # much evidence stood behind it. XMR-USD sat on 672 samples and 295 observed dip events with a
    # 0.933 bounce reliability, and the gate read it as zero.
    #
    # Measured consequence on the 2026-07-25 tree: the crypto book found 12 qualifying candidates
    # and bought NONE for 40 hours straight (9 of 12 rejected "immature"). GEKKO kept trading only
    # because it is exempt from this gate by doctrine. The books were not being cautious; they were
    # reading a field that did not exist.
    return {"dir": "mr", "entry": round(entry, 4), "target": round(target, 4),
            "stop": round(stop, 4),
            "n": fp.get("n"), "dip_samples": fp.get("dip_samples"),
            "typical_dip": fp.get("typical_dip"), "typical_bounce": fp.get("typical_bounce"),
            "bounce_reliability": fp.get("bounce_reliability"), "trend": fp.get("trend"),
            "strong_up": fp.get("strong_up"), "vol": fp.get("vol")}


def summary_line(sym: str, fit: Dict[str, Any]) -> str:
    tb = fit.get("typical_bounce")
    rel = fit.get("bounce_reliability")
    return ("%s: dips ~%.2f%% -> aims %.2f%% (of ~%.2f%% typical bounce) · stop %.1f%% · %s%s%s"
            % (sym, (fit.get("typical_dip") or 0) * 100, fit["target"] * 100,
               (tb or 0) * 100, fit["stop"] * 100, fit.get("trend", "?"),
               " · reliable" if (rel is not None and rel >= 0.6) else "",
               " · STRONG-UP" if fit.get("strong_up") else ""))


def build_fingerprints(out_dir, symbols_prices: Dict[str, List[float]],
                       rows_by_sym: Optional[Dict[str, Any]] = None, cost: float = 0.002,
                       floor_by_sym=None, limit: int = 60) -> Dict[str, Any]:
    """Build a FINGERPRINTS.json snapshot for the dashboard (top names by bounce reliability)."""
    rows_by_sym = rows_by_sym or {}
    cards = []
    for sym, prices in symbols_prices.items():
        fp = fingerprint(prices, rows_by_sym.get(sym))
        if not fp.get("ok"):
            continue
        fit = fit_strategy(fp, cost, (floor_by_sym or {}).get(sym))
        cards.append({"sym": sym, "fp": fp, "fit": fit,
                      "fittable": fit is not None,
                      "summary": summary_line(sym, fit) if fit else (sym + ": no fee-clearing MR fit")})
    cards.sort(key=lambda c: (c["fittable"], (c["fp"].get("bounce_reliability") or 0)), reverse=True)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
               "tracked": len(cards), "fittable": sum(1 for c in cards if c["fittable"]),
               "cards": cards[:limit],
               "what": ("Per-valuable identities + the realistic custom strategy fitted to each from "
                        "its OWN chart: typical dip -> realistic bounce target (fee-cleared) -> "
                        "dip-scaled stop. This is what drives live entries — each trade uses the "
                        "strategy fitted to that valuable, not a blanket threshold.")}
    try:
        from .atomic_io import write_json_atomic
        write_json_atomic(__import__("pathlib").Path(out_dir) / "FINGERPRINTS.json", payload)
    except Exception:
        pass
    return payload
