"""
DATA INTEGRITY LAYER (Master Directive Phase 1) — Law 2: integrity before learning.
Deterministic per-symbol checks over the INTRADAY stream. Anything failing is written to
INTEGRITY_QUARANTINE.json (visible, never silently dropped) and the live engine refuses to trade it
until it clears. A +444,000% "move" is an artifact, not an edge — this layer is what keeps artifacts
out of every learning surface for the entire harvest.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

CEIL = {"crypto": 0.25, "stock": 0.12, "metal": 0.08, "energy": 0.10}   # per-STEP sanity ceiling
FROZEN_RUN = 6          # >= identical prints...
JUMP_AFTER_FREEZE = 0.05  # ...followed by a jump beyond this = halt/stale artifact

def _now(): return datetime.now(timezone.utc).isoformat()

def _intra(rows):
    return [(t, p) for t, p in rows if p and p > 0 and "T00:00:00" not in t]

def scan(samples, asset_class, ceilings=None):
    ceil = dict(CEIL); ceil.update(ceilings or {})
    q = []
    keys = set(samples.keys())
    for sym in keys:
        # STRICT twin rule: both BASE-USD and BASEUSD present → quarantine ONLY the non-canonical
        # (BASEUSD) twin. The canonical stays tradable; no substring collisions possible.
        if sym.endswith("USD") and not sym.endswith("-USD"):
            canon = sym[:-3] + "-USD"
            if canon in keys:
                q.append({"sym": sym, "check": "duplicate_symbol",
                          "detail": "non-canonical twin of %s — quarantined; canonical stays live" % canon,
                          "t": _now()})
    for sym, rows in samples.items():
        r = _intra(rows)[-80:]
        if len(r) < 3:
            continue
        c = ceil.get(asset_class(sym), 0.15)
        run = 1
        for i in range(1, len(r)):
            prev, cur = r[i - 1][1], r[i][1]
            if prev <= 0:
                q.append({"sym": sym, "check": "invalid_prev_close", "detail": str(prev), "t": r[i][0]})
                continue
            mv = cur / prev - 1
            if abs(mv) > c:
                kind = "split_signature" if any(abs(abs(mv) + 1 - m) < 0.02 for m in (10, 100, 0.1, 0.01)) \
                       else "magnitude_ceiling"
                q.append({"sym": sym, "check": kind,
                          "detail": "%+.1f%% in one step (ceiling %.0f%%)" % (mv * 100, c * 100),
                          "t": r[i][0]})
            run = run + 1 if cur == prev else 1
            if run >= FROZEN_RUN and i + 1 < len(r) and prev > 0:
                nxt = r[i + 1][1]
                if abs(nxt / cur - 1) > JUMP_AFTER_FREEZE:
                    q.append({"sym": sym, "check": "frozen_then_jump",
                              "detail": "%d identical prints then %+.1f%%" % (run, (nxt / cur - 1) * 100),
                              "t": r[i + 1][0]})
    return q

def build_integrity(out_dir):
    out = Path(out_dir)
    try:
        samples = json.loads((out / "price_samples.json").read_text()).get("samples", {})
    except Exception:
        samples = {}
    try:
        cat = json.loads((out / "PARAM_CATALOG.json").read_text())
        ceilings = (cat.get("integrity") or {}).get("step_ceiling") or {}
    except Exception:
        ceilings = {}
    from .paper_sim import asset_class
    q = scan(samples, asset_class, ceilings)
    HARD = {"magnitude_ceiling", "split_signature", "invalid_prev_close", "duplicate_symbol"}
    for e in q:
        e["quarantine"] = e["check"] in HARD     # frozen_then_jump = advisory (ghost filter already owns staleness)
    syms = sorted({e["sym"] for e in q if e["quarantine"]})
    payload = {"generated_at": _now(), "quarantined_symbols": syms, "entries": q[-300:],
               "what": ("Law 2 — integrity before learning. Symbols listed here are EXCLUDED from new "
                        "entries and from every learning surface until their data stream clears. "
                        "Visible by design: nothing is silently dropped.")}
    (out / "INTEGRITY_QUARANTINE.json").write_text(json.dumps(payload, indent=1))
    return payload

def quarantined(out_dir):
    try:
        return set(json.loads((Path(out_dir) / "INTEGRITY_QUARANTINE.json").read_text())
                   .get("quarantined_symbols", []))
    except Exception:
        return set()
