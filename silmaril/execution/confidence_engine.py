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
from .paper_sim import load_all_samples, asset_class

STORE = "CONFIDENCE_ENGINE.json"

# component weights — each earns/loses trust forward; these are the priors
W = {
    "bounce_reliability": 0.30,
    "rhythm_regularity": 0.20,
    "rhythm_phase": 0.15,
    "mtf_confluence": 0.15,
    "dip_extension": 0.12,
    "trend_alignment": 0.08,
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

        parts = {
            "bounce_reliability": round(c_bounce, 3),
            "rhythm_regularity": round(c_reg, 3),
            "rhythm_phase": round(c_phase, 3),
            "mtf_confluence": round(c_mtf, 3),
            "dip_extension": round(c_dip, 3),
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
    return {"summary": f"confidence engine: {len(per_symbol)} scored · "
                       f"{len(rhythm_leaders)} rhythm-tradeable · top crypto "
                       f"{(by_class_top.get('crypto') or [['—']])[0][0]}"}


def confidence_for(out_dir, sym: str) -> Optional[float]:
    """Cheap lookup for the sizing path — returns the blended score or None."""
    try:
        d = json.loads((Path(out_dir) / STORE).read_text())
        return (d.get("by_symbol", {}).get(sym) or {}).get("confidence")
    except Exception:
        return None
