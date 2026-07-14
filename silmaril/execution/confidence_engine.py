"""confidence_engine.py — 5.1 FINAL: the UNIFIED prediction/confidence layer.

The operator's directive: the confidence number that sizes trades must use
EVERYTHING the system knows how to predict — not the three inputs it used
before. This module gathers every available predictive signal per symbol and
blends them into one 0-1 score WITH a component breakdown, so the UI can show
*why* a name scored high, and so each component can be graded on whether it
actually predicts.

The signals it fuses (all already computed elsewhere; several were unused):
  · bounce_reliability   (fingerprint)   — how often this name's dips recover
  · rhythm_regularity    (peak_rhythm)   — is the high→low cycle PREDICTABLE?  [was unused]
  · rhythm_phase         (peak_rhythm)   — are we near a TROUGH (buy) or PEAK?  [was unused]
  · mtf_confluence       (mtf_regime)    — multi-timeframe agreement
  · dip_extension        (fingerprint)   — is this dip deeper than the name's typical?
  · trend_alignment      (fingerprint)   — multi-timeframe trend label

Plus a dedicated RHYTHM-TRADEABILITY score: flags the "sideways-volatile with a
constant, predictable peak rhythm" names the operator's theory targets — the
D-sleeve's hunting ground and gold/metal's eventual bread and butter.

Store: CONFIDENCE_ENGINE.json (per symbol: blended score + component parts +
rhythm-tradeability + a plain-English 'why'). Every component is exposed so the
gates board and Strategy Lab can learn which signals earn their weight.

HONEST: this is measurement + blending. Whether high confidence actually wins
more is graded forward (the report card / gates), never assumed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .atomic_io import write_json_atomic
from .paper_sim import load_all_samples, asset_class, _vol_sigma1h, _vol_native_entry

STORE = "CONFIDENCE_ENGINE.json"

# component weights — each earns/loses trust forward; these are the priors
W = {
    "bounce_reliability": 0.22,   # fingerprint: do this name's dips recover
    "rhythm_regularity": 0.16,    # peak_rhythm: is the cycle predictable
    "rhythm_phase": 0.12,         # peak_rhythm: near a trough (buy) vs peak
    "mtf_confluence": 0.12,       # mtf_regime: multi-timeframe agreement
    "dip_extension": 0.10,        # fingerprint: deeper-than-usual dip
    "timing_alignment": 0.10,     # timing_fingerprint: is NOW this name's best buy window
    "momentum_exhaustion": 0.08,  # momentum_chain: is the downward run exhausting
    "conviction_backing": 0.06,   # conviction_ranking: independent multi-signal score
    "trend_alignment": 0.04,      # fingerprint: multi-tf trend tailwind
}


def _now():
    return datetime.now(timezone.utc)


def _load(out: Path, name: str) -> Dict[str, Any]:
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return {}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _parse(t) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _rhythm_signals(pk: Dict[str, Any]) -> Dict[str, float]:
    """From a peak_rhythm by_symbol record → regularity, phase, tradeability."""
    if not pk:
        return {"regularity": 0.0, "phase": 0.5, "amplitude": 0.0, "cycle_min": None}
    med_pk = pk.get("median_minutes_between_peaks")
    avg_pk = pk.get("avg_minutes_between_peaks")
    med_tr = pk.get("median_minutes_between_troughs")
    amp = float(pk.get("typical_peak_amplitude_pct") or 0.0)
    if amp > 15.0:            # >15% "amplitude" is a ghost/twin price glitch, not a tradeable swing
        amp = 0.0

    # REGULARITY: median close to average = evenly-spaced cycles = predictable.
    # ratio near 1.0 → regular; far → erratic. Need enough extrema to trust it.
    reg = 0.0
    npk = int(pk.get("peaks_found") or 0)
    if med_pk and avg_pk and med_pk > 0 and avg_pk > 0 and npk >= 6:
        ratio = min(med_pk, avg_pk) / max(med_pk, avg_pk)   # 0..1, 1 = perfectly even
        reg = ratio
    # amplitude gate: a "rhythm" with no swing isn't tradeable
    reg *= _clamp(amp / 1.5)   # ~1.5%+ swings score full; tiny wiggles discounted

    # PHASE: near a trough → good time to buy (MR); near a peak → avoid.
    # Use predicted next peak + last trough to estimate where we sit in the cycle.
    phase = 0.5
    now = _now()
    lt = _parse(pk.get("last_trough_at"))
    lp = _parse(pk.get("last_peak_at"))
    if lt and lp:
        # if the last trough is MORE RECENT than the last peak, we're rising off a
        # bottom → high phase score (good MR entry just happened / imminent bounce)
        if lt > lp:
            mins_since_trough = (now - lt).total_seconds() / 60.0
            cyc = med_tr or med_pk or 120.0
            # freshest off the trough = best; decays as we approach the next peak
            phase = _clamp(1.0 - (mins_since_trough / cyc)) if cyc else 0.5
        else:
            # last peak more recent → we're falling from a top → poor entry timing
            phase = 0.25
    return {"regularity": _clamp(reg), "phase": _clamp(phase),
            "amplitude": amp, "cycle_min": med_pk}


def build_confidence_engine(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    samples = load_all_samples(out)
    fp = _load(out, "FINGERPRINTS.json")
    fp_cards = {c.get("symbol"): c for c in (fp.get("cards") or []) if c.get("symbol")}
    pkr = (_load(out, "PEAK_RHYTHM.json").get("by_symbol") or {})
    mtf = (_load(out, "MTF_REGIME.json").get("symbols") or {})
    # 5.1 FINAL — wire the brain to EVERY predictive signal we measure:
    tfp = (_load(out, "timing_fingerprint.json").get("fingerprints") or {})
    _mc_raw = _load(out, "momentum_chain.json").get("chains") or {}
    mom = _mc_raw if isinstance(_mc_raw, dict) else {}
    cvr = {}
    for _op in (_load(out, "conviction_ranking.json").get("ranked_opportunities") or []):
        _sy = _op.get("ticker") or _op.get("symbol")
        if _sy:
            cvr[_sy] = _op
    # current UTC time-of-day bucket for timing alignment
    _hhmm = _now().strftime("%H:%M")
    _hh = _now().hour + _now().minute / 60.0

    per_symbol: Dict[str, Any] = {}
    rhythm_leaders = []

    for sym, rows in samples.items():
        if asset_class(sym) == "crypto" and "-" not in sym:
            continue
        card = fp_cards.get(sym) or {}
        pk = pkr.get(sym) or {}
        mt = mtf.get(sym) or {}

        # ── components (each 0..1) ─────────────────────────────────────────
        c_bounce = _clamp(float(card.get("bounce_reliability") or 0.0))
        rsig = _rhythm_signals(pk)
        c_reg = rsig["regularity"]
        c_phase = rsig["phase"]
        c_mtf = _clamp((float(mt.get("confluence") or 0.0) + 8.5) / 17.0)  # -8.5..8.5 → 0..1
        # dip_extension: current 1h move vs the name's typical dip (deeper = better MR)
        typ = float(card.get("typical_dip") or 0.0)
        cur_move = 0.0
        try:
            px = [p for t, p in rows if p and "T00:00:00" not in str(t)]
            if len(px) >= 6:
                cur_move = px[-1] / max(px[-6], 1e-9) - 1.0
        except Exception:
            pass
        c_dip = _clamp(abs(min(cur_move, 0.0)) / typ) if typ > 0 else 0.0
        # trend_alignment: strong multi-tf uptrend is a tailwind even for MR
        tl = card.get("trend")
        c_trend = 1.0 if card.get("strong_up") else (0.6 if tl == "up" else 0.4 if tl == "mixed" else 0.2)

        # timing_alignment: how close is NOW to this name's measured best BUY window?
        # tod_curve values are 0..1 "how good is this bucket"; use the current bucket directly.
        c_timing = 0.5
        _tf = tfp.get(sym) or {}
        _curve = _tf.get("tod_curve") or {}
        if _curve and not _tf.get("learning", True):
            # nearest bucket to now
            _bv = _curve.get(_hhmm)
            if _bv is None:
                try:
                    _bk = min(_curve.keys(), key=lambda k: abs((int(k[:2]) + int(k[3:]) / 60.0) - _hh))
                    _bv = _curve.get(_bk)
                except Exception:
                    _bv = None
            if _bv is not None:
                # buying is best when the bucket value is LOW (price low in its daily range)
                c_timing = _clamp(1.0 - float(_bv))

        # momentum_exhaustion: a down-chain that's slowing = MR opportunity; up-chain = caution
        c_mom = 0.5
        _mc = mom.get(sym) or {}
        _win = _mc.get("windows") or {}
        # recent multi-window momentum: negative short-window run that is FLATTENING (d1 less
        # negative than d2) = exhausting downtrend = prime MR. Persistent up = caution.
        _d1 = float(_win.get("d1") or 0.0)
        _d2 = float(_win.get("d2") or 0.0)
        _h1 = float(_win.get("h1") or 0.0)
        if _d2 < -0.3 and _d1 >= _d2:          # was falling, now slowing/turning
            c_mom = _clamp(0.55 + min(abs(_d2), 3.0) / 6.0)
        elif _h1 > 0.5 or _d1 > 1.0:           # strong fresh up-run → don't fade blindly
            c_mom = _clamp(0.5 - min(_d1, 3.0) / 6.0)

        # conviction_backing: the independent multi-signal ranker's own score (0..1)
        c_conv = 0.5
        _cv = cvr.get(sym) or {}
        if _cv:
            _sc = _cv.get("score")
            if _sc is not None:
                c_conv = _clamp(float(_sc))

        parts = {
            "bounce_reliability": round(c_bounce, 3),
            "rhythm_regularity": round(c_reg, 3),
            "rhythm_phase": round(c_phase, 3),
            "mtf_confluence": round(c_mtf, 3),
            "dip_extension": round(c_dip, 3),
            "timing_alignment": round(c_timing, 3),
            "momentum_exhaustion": round(c_mom, 3),
            "conviction_backing": round(c_conv, 3),
            "trend_alignment": round(c_trend, 3),
        }
        score = sum(W[k] * v for k, v in parts.items())

        # ── RHYTHM-TRADEABILITY (the sideways-volatile-predictable flag) ───
        # high when: regular cycles + real amplitude + not in a strong directional
        # trend (pure oscillation), with enough peaks to trust the pattern.
        directionless = 1.0 - abs(float(mt.get("confluence") or 0.0)) / 8.5   # near 0 confluence = sideways
        rhythm_trade = _clamp(0.5 * c_reg + 0.3 * _clamp(rsig["amplitude"] / 2.5)
                              + 0.2 * _clamp(directionless))
        cyc = rsig["cycle_min"]

        why_bits = []
        if c_reg >= 0.5:
            why_bits.append("regular %.0fm cycle" % (cyc or 0))
        if c_phase >= 0.6:
            why_bits.append("fresh off a trough")
        if c_bounce >= 0.6:
            why_bits.append("%.0f%% bounce reliability" % (c_bounce * 100))
        if c_dip >= 0.6:
            why_bits.append("deeper dip than usual")
        if rhythm_trade >= 0.6:
            why_bits.append("RHYTHM-TRADEABLE (sideways+predictable)")
        why = " · ".join(why_bits) or "no strong predictive signal"

        rec = {
            "confidence": round(score, 3),
            "parts": parts,
            "rhythm_tradeability": round(rhythm_trade, 3),
            "cycle_min": cyc,
            "amplitude_pct": round(rsig["amplitude"], 2),
            "class": asset_class(sym),
            "why": why,
        }
        per_symbol[sym] = rec
        if rhythm_trade >= 0.5:
            rhythm_leaders.append((sym, round(rhythm_trade, 3), cyc, round(rsig["amplitude"], 2)))

    rhythm_leaders.sort(key=lambda x: -x[1])
    by_class_top = {}
    for cls in ("crypto", "stock", "metal", "energy"):
        names = sorted(((s, r["confidence"]) for s, r in per_symbol.items() if r["class"] == cls),
                       key=lambda x: -x[1])[:8]
        by_class_top[cls] = names

    # ── 5.11 WRAP · THE UNIVERSAL CONFIDENCE CARD ─────────────────────────────
    # The operator's baseball card: EVERY valuable gets the full stat block —
    # rhythm, fingerprint aims, its own vol bar, expected hold, momentum
    # trajectory, timing windows, book track record, and a COMPOUNDER SCORE
    # (conf × swing × cadence) that now tilts live sizing and ranks the
    # daily-compounding bread-and-butter (NEAR-style: high conf · ~300m · 2%+).
    _book_stats: Dict[str, Dict[str, Any]] = {}
    for _bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        try:
            _pb = json.loads((out / f"paper_book_{_bk}.json").read_text())
            for _t in _pb.get("trades") or []:
                if _t.get("side") != "SELL":
                    continue
                _sy = _t.get("sym")
                _st = _book_stats.setdefault(_sy, {"trades": 0, "wins": 0, "pnl": 0.0})
                _st["trades"] += 1
                _st["pnl"] += float(_t.get("pnl") or 0.0)
                if float(_t.get("pnl") or 0.0) > 0:
                    _st["wins"] += 1
        except Exception:
            pass
    _vn_knob = {}
    try:
        _vn_knob = json.loads((out / "PARAM_CATALOG.json").read_text()).get("vol_native") or {}
    except Exception:
        pass
    cards: Dict[str, Any] = {}
    _comp_rank = []
    for _sym, _rec in per_symbol.items():
        _rows = samples.get(_sym) or []
        _pxs = [pp for _tt, pp in _rows if pp and "T00:00:00" not in str(_tt)]
        _lastpx = _pxs[-1] if _pxs else None
        _pk = pkr.get(_sym) or {}
        _cyc = _pk.get("median_minutes_between_peaks")
        _amp = _rec.get("amplitude_pct") or 0.0
        _sig = _vol_sigma1h(_rows)
        _vbar = _vol_native_entry(_rows, _rec["class"], 0.03, dict(_vn_knob, mode="auto"))
        _card_fp = fp_cards.get(_sym) or {}
        _bs = _book_stats.get(_sym) or {}
        _conf = _rec["confidence"]
        # compounder: confidence × swing-quality × cadence-speed, each clamped
        _swf = min(max((_amp or 0) / 2.0, 0.6), 1.6)
        _caf = min(max((360.0 / max(float(_cyc or 720), 30.0)) ** 0.5, 0.6), 1.6)
        _comp = round(min(1.0, max(0.0, _conf * _swf * _caf / 1.6)), 3)
        _comp_rank.append((_sym, _comp))
        cards[_sym] = {
            "class": _rec["class"], "last_px": _lastpx,
            "confidence": _conf, "parts": _rec["parts"],
            "rhythm_tradeability": _rec["rhythm_tradeability"],
            "cycle_min": _cyc, "amplitude_pct": _amp,
            "last_peak_at": _pk.get("last_peak_at"), "last_trough_at": _pk.get("last_trough_at"),
            "expected_hold_min": (round(float(_cyc)) if _cyc else None),
            "sigma1h_pct": (round(_sig * 100, 3) if _sig else None),
            "vol_native_bar_pct": (round(_vbar * 100, 3) if _vbar else None),
            "typical_dip_pct": (round(float(_card_fp.get("typical_dip") or 0) * 100, 3) or None),
            "typical_bounce_pct": (round(float(_card_fp.get("typical_bounce") or 0) * 100, 3) or None),
            "bounce_reliability": _card_fp.get("bounce_reliability"),
            "trend": _card_fp.get("trend"), "strong_up": _card_fp.get("strong_up"),
            "mtf_confluence": (mtf.get(_sym) or {}).get("confluence"),
            "momentum": ((_load(out, "momentum_chain.json") or {}).get("chains") or {}).get(_sym, {}).get("windows"),
            "timing_best_buy": (tfp.get(_sym) or {}).get("best_buy_window"),
            "timing_best_sell": (tfp.get(_sym) or {}).get("best_sell_window"),
            "book_trades": _bs.get("trades", 0), "book_wins": _bs.get("wins", 0),
            "book_win_pct": (round(100 * _bs["wins"] / _bs["trades"], 1) if _bs.get("trades") else None),
            "book_pnl_usd": round(_bs.get("pnl", 0.0), 2),
            "compounder_score": _comp,
            "why": _rec.get("why"),
        }
    _comp_rank.sort(key=lambda x: -x[1])
    write_json_atomic(out / "CONFIDENCE_CARDS.json", {
        "generated_at": _now().isoformat(),
        "what": ("the universal confidence card — every valuable's full baseball-card stat block: "
                 "rhythm cycle + expected hold, fingerprint aims, its OWN vol bar, momentum "
                 "trajectory, timing windows, our track record on it, and the COMPOUNDER score "
                 "(conf × swing × cadence) that tilts live sizing. Card↔strategy matching is the "
                 "scientific heart: the chart shows the card, the card explains the chart."),
        "n_cards": len(cards),
        "compounder_leaders": _comp_rank[:15],
        "cards": cards,
    })

    payload = {
        "generated_at": _now().isoformat(),
        "what": ("the unified confidence layer — every predictive signal (fingerprint bounce reliability, "
                 "PEAK RHYTHM regularity + phase, MTF confluence, dip extension, trend) fused into one "
                 "0-1 score per valuable, with the component breakdown exposed. Feeds conviction sizing "
                 "and the D-sleeve sniper. Whether high confidence actually wins more is graded forward."),
        "weights": W,
        "n_scored": len(per_symbol),
        "rhythm_tradeable_leaders": rhythm_leaders[:20],
        "top_confidence_by_class": by_class_top,
        "by_symbol": per_symbol,
        "how_to_read": ("confidence = weighted blend of all signals; rhythm_tradeability flags the "
                        "sideways-volatile-predictable names (constant peak↔trough rhythm) the sniper hunts. "
                        "cycle_min = typical minutes between peaks; amplitude_pct = typical swing size."),
    }
    write_json_atomic(out / STORE, payload)
    return {"summary": f"confidence engine: {len(per_symbol)} scored · {len(cards)} cards · "
                       f"{len(rhythm_leaders)} rhythm-tradeable · top crypto "
                       f"{(by_class_top.get('crypto') or [['—']])[0][0]}"}


def confidence_for(out_dir, sym: str) -> Optional[float]:
    """Cheap lookup for the sizing path — returns the blended score or None."""
    try:
        d = json.loads((Path(out_dir) / STORE).read_text())
        return (d.get("by_symbol", {}).get(sym) or {}).get("confidence")
    except Exception:
        return None
