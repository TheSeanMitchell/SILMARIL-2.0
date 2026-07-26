"""
silmaril.execution.source_overlay — 7.1 THE OUTSIDE WORLD ON THE GRAPH.

The operator's brief, repeated across July 24-25: "imports other graphs from other sites
like Coinbase or Yahoo Finance … overlay it with three sources so we know … make sure the
system is aware if there is a price difference between sources."

Until now the "multi-source overlay" traced our OWN four internal files against each other
— honest cross-feed verification, but not what was asked. This module fetches genuinely
EXTERNAL series, from named third parties, for the names that matter, and publishes them
in SOURCE_OVERLAY.json for the Everything Graph to draw as tracing-paper lines with a
time-aligned agreement verdict per name.

Providers (all public, no keys, no synthetic fallback — an absent provider is an absent
line, stated as such):
  crypto        → Coinbase (ccxt), Kraken (ccxt)
  stock/ETF     → Yahoo Finance (yfinance)
  metal/energy  → Yahoo Finance futures (GC=F, SI=F, CL=F, BZ=F, NG=F, …) for the spot
                  symbols, and yfinance directly for the ETFs

Honesty rails:
  · Scope is bounded: open positions (books + GEKKO + every sleeve) ∪ recent trades ∪
    the books' current top candidates, capped (knob source_overlay.max_symbols, def 24).
  · Hard wall-clock budget (def 75s): the pass degrades by covering fewer names, never
    by inventing data or stalling the cycle. Runs in the FULL (non-FAST) pass only.
  · Agreement is TIME-ALIGNED: our last live print vs the provider print nearest in time
    (≤15 min apart). Comparing prints from different moments is not a comparison.
  · A held name whose sources disagree >0.5% is listed in `disagreements` — a data-
    integrity alarm the operator asked for by name ("make sure the system is aware").

KILL: PARAM_CATALOG.source_overlay.mode "off". Tripwire: selftest T111.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .atomic_io import write_json_atomic
from .canon_keys import canon, alt_keys, is_crypto_key

STORE = "SOURCE_OVERLAY.json"

# spot commodity symbols → the Yahoo futures ticker that actually trades them
_YF_SPOT = {"XAU": "GC=F", "XAG": "SI=F", "XPT": "PL=F", "XPD": "PA=F", "XCU": "HG=F",
            "WTI": "CL=F", "BRENT": "BZ=F", "NATGAS": "NG=F",
            "GASOLINE": "RB=F", "HEATOIL": "HO=F"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(out: Path, name: str) -> Dict[str, Any]:
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return {}


def _scope_symbols(out: Path, cap: int) -> List[str]:
    """The names worth verifying: everything we HOLD, recently traded, or are about to
    consider. Canonical keys, bounded."""
    syms: List[str] = []

    def add(s):
        if not s:
            return
        c = canon(s) if is_crypto_key(s) else str(s).upper()
        if c and c not in syms:
            syms.append(c)

    live = _load(out, "paper_sim_live.json")
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        b = live.get(bk) or {}
        for p in (b.get("positions") or []):
            add((p or {}).get("sym"))
        for t in (b.get("recent_trades") or [])[:6]:
            add((t or {}).get("sym"))
        for d in (b.get("decision_trace_live") or [])[:4]:
            add((d or {}).get("sym"))
    lab = _load(out, "STRATEGY_LAB.json")
    for _sk, sb in (lab.get("sleeves") or {}).items():
        for s in (sb.get("positions") or {}).keys():
            add(s)
    return syms[:max(1, cap)]


def _crypto_series(sym: str, budget_left) -> Dict[str, List]:
    """Coinbase + Kraken 5m closes via ccxt. Absent listing = absent line."""
    outp: Dict[str, List] = {}
    try:
        import ccxt  # already a hard requirement of the project
    except Exception:
        return outp
    base = sym[:-4] if sym.endswith("-USD") else sym
    pairs = [base + "/USD", base + "/USDT"]
    for ex_id, label in (("coinbase", "coinbase"), ("kraken", "kraken")):
        if budget_left() <= 0:
            break
        try:
            ex = _crypto_series._ex.get(ex_id)
            if ex is None:
                ex = getattr(ccxt, ex_id)({"enableRateLimit": True, "timeout": 8000})
                _crypto_series._ex[ex_id] = ex
            rows = None
            for p in pairs:
                try:
                    o = ex.fetch_ohlcv(p, timeframe="5m", limit=96)
                    if o:
                        rows = [[datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc)
                                 .isoformat(), float(c[4])] for c in o if c and c[4]]
                        break
                except Exception:
                    continue
            if rows and len(rows) >= 3:
                outp[label] = rows
        except Exception:
            continue
    return outp


_crypto_series._ex = {}


def _yahoo_series(sym: str) -> Dict[str, List]:
    """Yahoo 5m closes for equities/ETFs, or the mapped futures for spot commodities."""
    try:
        import yfinance as yf
    except Exception:
        return {}
    tk = _YF_SPOT.get(sym, sym)
    try:
        h = yf.Ticker(tk).history(period="2d", interval="5m")
        if h is None or h.empty:
            return {}
        rows = [[idx.tz_convert("UTC").isoformat() if idx.tzinfo else idx.isoformat(),
                 float(px)] for idx, px in h["Close"].items() if px and px == px]
        return {"yahoo(" + tk + ")": rows[-160:]} if len(rows) >= 3 else {}
    except Exception:
        return {}


def _our_last_live(out_samples: Dict[str, List], sym: str) -> Optional[List]:
    for k in alt_keys(sym):
        rows = out_samples.get(k)
        if not rows:
            continue
        for t, p in reversed(rows):
            ts = str(t)
            if p and float(p) > 0 and "T00:00:00" not in ts:   # never compare to a backfill candle
                return [ts, float(p)]
    return None


def _aligned_spread(ours: List, prov_rows: List, tol_min: float = 15.0) -> Optional[Dict[str, Any]]:
    """Spread between OUR last live print and the provider print nearest in time.
    None when nothing overlaps within tolerance — stated, never guessed."""
    try:
        t0 = datetime.fromisoformat(str(ours[0]).replace("Z", "+00:00"))
        best, bdt = None, None
        for t, p in prov_rows:
            try:
                dt = abs((datetime.fromisoformat(str(t).replace("Z", "+00:00")) - t0)
                         .total_seconds()) / 60.0
            except Exception:
                continue
            if p and float(p) > 0 and (bdt is None or dt < bdt):
                best, bdt = float(p), dt
        if best is None or bdt is None or bdt > tol_min:
            return None
        return {"spread_pct": round((best / float(ours[1]) - 1) * 100, 4),
                "aligned_within_min": round(bdt, 1)}
    except Exception:
        return None


def build_source_overlay(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    knob = (_load(out, "PARAM_CATALOG.json").get("source_overlay") or {})
    if str(knob.get("mode", "auto")).lower() == "off":
        return {"mode": "off"}
    cap = int(knob.get("max_symbols", 24) or 24)
    budget_s = float(knob.get("budget_s", 75) or 75)
    disagree_pct = float(knob.get("disagree_pct", 0.5) or 0.5)
    t0 = time.monotonic()

    def budget_left():
        return budget_s - (time.monotonic() - t0)

    from .canon_keys import canonical_samples
    ours_all = canonical_samples(out)
    syms = _scope_symbols(out, cap)

    symbols: Dict[str, Any] = {}
    disagreements: List[Dict[str, Any]] = []
    covered = 0
    for sym in syms:
        if budget_left() <= 3:
            break
        provs = _crypto_series(sym, budget_left) if sym.endswith("-USD") else _yahoo_series(sym)
        if not provs:
            symbols[sym] = {"providers": {}, "agreement": {"verdict": "NO_EXTERNAL_SOURCE",
                            "why": "no public provider returned a series for this name (nothing drawn, nothing invented)"}}
            continue
        covered += 1
        ours = _our_last_live(ours_all, sym)
        worst = None
        agrees = {}
        for label, rows in provs.items():
            a = _aligned_spread(ours, rows) if ours else None
            agrees[label] = a or {"verdict": "NO_TIME_OVERLAP"}
            if a and (worst is None or abs(a["spread_pct"]) > abs(worst)):
                worst = a["spread_pct"]
        verdict = ("UNVERIFIED" if worst is None
                   else ("AGREE" if abs(worst) <= disagree_pct else "DISAGREE"))
        symbols[sym] = {"providers": provs,
                        "agreement": {"verdict": verdict,
                                      "worst_spread_pct": worst,
                                      "vs_our_print": ours,
                                      "per_provider": agrees}}
        if verdict == "DISAGREE":
            disagreements.append({"sym": sym, "spread_pct": worst,
                                  "note": "our tape and a live venue disagree — price suspect until they converge"})

    payload = {
        "generated_at": _now(),
        "symbols": symbols,
        "scoped": len(syms), "covered": covered,
        "disagreements": disagreements,
        "budget_s": budget_s, "spent_s": round(time.monotonic() - t0, 1),
        "providers": "coinbase + kraken (crypto, via ccxt public OHLCV) · yahoo finance (equities/ETFs; mapped futures for spot metals/energy)",
        "what": ("REAL third-party price series for every name we hold or are weighing, so the "
                 "Everything Graph can overlay outside charts on ours like tracing paper and flag "
                 "any disagreement. Refreshed on the full (top-of-hour) pass; the panel prints its own age."),
        "law": "no synthetic series, ever — an absent provider is an absent line, and it says so",
    }
    try:
        write_json_atomic(out / STORE, payload)
    except Exception:
        pass
    return payload


if __name__ == "__main__":
    import sys
    r = build_source_overlay(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(json.dumps({k: r[k] for k in ("scoped", "covered", "spent_s", "disagreements") if k in r}, indent=1))
