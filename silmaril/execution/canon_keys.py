"""
silmaril.execution.canon_keys — 7.1 THE ONE-KEY LAW.

THE INCIDENT (2026-07-25): the crypto book opened DOGEUSDT while a sleeve held DOGE-USD —
the SAME coin, twice, under two spellings. Root cause: load_all_samples() merged
price_samples.json (canonical "DOGE-USD") with ccxt_samples.json ("DOGEUSDT") RAW, so the
book's tradeable universe contained both spellings as if they were two different assets.
Downstream, every consumer keyed on the canonical spelling went blind to the other one:
the ticker modal found no chart for DOGEUSDT, the sleeve mark-stamper missed keys, the
movers journal paraded REQUSDT/LMWRUSDT ghosts, and the one-listing-per-base law was
violated at the book level.

The 7.0.2 canonical merge fixed this for FINGERPRINTS ONLY (a local _canon7 inside the
fingerprint block). This module makes that same law global: ONE canon() and ONE loader,
imported by every consumer, so a non-canonical crypto key can never again reach a book,
a sleeve, a journal, or a chart.

Laws:
  · canon() is total for crypto: every USDT/USDC/USD/slash spelling maps to BASE-USD.
  · Non-crypto keys (GLD, AAPL, WTI, XAU…) pass through untouched.
  · canonical_samples() UNIONS history across spellings by timestamp; on a timestamp
    collision the primary tape (price_samples.json) wins — ccxt depth deepens, never
    overrides, the canonical series.
  · canonicalize_positions() migrates any OPEN position/pending-order keys already
    booked under a non-canonical spelling, so an existing bad key cannot become a
    frozen, unmarkable, unexitable position (the frozen-workshop disease, in a book).
    Closed-trade HISTORY is never rewritten — the record stays as it was printed.
  · No synthetic data anywhere: this module only re-keys and unions what already exists.

Tripwires: selftest T107 (loader union), T108 (position migration).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

SAMPLE_FILES = ("price_samples.json", "ccxt_samples.json",
                "metals_samples.json", "energy_samples.json")

# dash-less real assets that CONTAIN "USD"-ish substrings must never be re-keyed
_NEVER_CANON = {"USD", "USDT", "USDC", "USO", "USL", "USOI"}   # USO/USL/USOI = energy ETFs


def is_crypto_key(sym: str) -> bool:
    """Mirror of paper_sim._is_crypto without importing it (no cycle)."""
    return "USD" in str(sym).upper()


def canon(sym: str) -> str:
    """The one canonical spelling for a symbol. Crypto → BASE-USD; everything else
    passes through unchanged. Total: never returns None, never raises."""
    s = str(sym or "").upper().strip()
    if not s or s in _NEVER_CANON:
        return s
    if "-" in s:                       # already BASE-QUOTE
        if s.endswith("-USDT") or s.endswith("-USDC"):
            return s.rsplit("-", 1)[0] + "-USD"
        return s
    if "/" in s:                       # ccxt "BASE/QUOTE"
        return s.split("/")[0] + "-USD"
    if ":" in s:                       # exchange-scoped "BINANCE:BTCUSDT"
        s = s.split(":")[-1]
    for suf in ("USDT", "USDC"):
        if s.endswith(suf) and len(s) > len(suf):
            return s[:-len(suf)] + "-USD"
    if s.endswith("USD") and len(s) > 3 and not s.endswith("-USD"):
        # BTCUSD → BTC-USD. Guard: 3-letter bases only after stripping, and never
        # a plain equity ticker (equities don't end in USD in our universe).
        return s[:-3] + "-USD"
    return s


def alt_keys(sym: str) -> List[str]:
    """Every spelling a series for this symbol might be stored under (for lookups
    against stores written before this law landed)."""
    c = canon(sym)
    base = c[:-4] if c.endswith("-USD") else c
    outs = [sym, c]
    if c.endswith("-USD"):
        outs += [base + "USDT", base + "USD", base + "USDC", base + "/USD", base + "/USDT"]
    seen, uniq = set(), []
    for k in outs:
        if k and k not in seen:
            seen.add(k)
            uniq.append(k)
    return uniq


def _union_rows(a: List, b: List) -> List:
    """Union two [t, px] series by timestamp; rows in `a` win collisions."""
    m = {}
    for t, p in (b or []):
        m[str(t)] = p
    for t, p in (a or []):
        m[str(t)] = p            # primary overrides on the same timestamp
    return sorted(([t, p] for t, p in m.items()), key=lambda r: r[0])


def _live_rows(rows: List) -> List:
    """Live intraday prints only — daily backfill candles carry a T00:00:00 stamp and
    would otherwise dominate any scale/shape measurement (the backfill-poisoning law)."""
    out = []
    for r in (rows or []):
        try:
            if not r or len(r) < 2:
                continue
            px = float(r[1])
            if px > 0 and "T00:00:00" not in str(r[0]):
                out.append([str(r[0]), px])
        except Exception:
            continue
    return out


def _median(xs: List[float]):
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def _ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _aligned_ratio(cand: List, ref: List, tol_s: float = 1800.0):
    """Median price ratio between a candidate spelling and the reference tape, measured
    on TIME-ALIGNED prints only (<=30 min apart). Comparing raw medians across different
    windows would call a coin that simply moved a 'scale conflict'; comparing the same
    moments cannot. Returns (ratio, n_pairs) or (None, 0) when the two never overlap."""
    if not cand or not ref:
        return None, 0
    rt = sorted([(t, p) for t, p in ((_ts(r[0]), r[1]) for r in ref) if t])
    if not rt:
        return None, 0
    times = [x[0] for x in rt]
    ratios = []
    step = max(1, len(cand) // 40)
    for r in cand[::step]:
        t = _ts(r[0])
        if not t:
            continue
        lo, hi = 0, len(times) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if times[mid] < t:
                lo = mid + 1
            else:
                hi = mid
        best = None
        for j in (lo - 1, lo):
            if 0 <= j < len(rt) and abs(rt[j][0] - t) <= tol_s:
                if best is None or abs(rt[j][0] - t) < abs(best[0] - t):
                    best = rt[j]
        if best and best[1] > 0:
            ratios.append(r[1] / best[1])
    m = _median(ratios)
    return m, len(ratios)


def _shape(rows: List) -> Dict[str, Any]:
    ys = [r[1] for r in rows]
    if not ys:
        return {"n": 0, "levels": 0, "repeat": 1.0}
    same = sum(1 for i in range(1, len(ys)) if ys[i] == ys[i - 1])
    return {"n": len(ys), "levels": len(set(ys)),
            "repeat": (same / max(1, len(ys) - 1))}


# A spelling may join the canonical series only if it is priced within this band of the
# reference at the SAME moments. 5% is far wider than any venue spread and far narrower
# than the conflicts this guard exists to stop (APT: 33,000x; ARB: 1,492x; BAL: 45x).
SCALE_TOL = 0.05


def canonical_samples_report(out_dir):
    """THE loader, with receipts. Returns (merged, report).

    7.1.2 INCIDENT — THE SCALE-BLEND: 7.1.0's one-key law unioned every spelling of a
    symbol on the assumption that DOGEUSDT and DOGE-USD are the same asset at the same
    price. For 271 of 358 overlapping ccxt keys that assumption was FALSE — the feed
    publishes a different (mis-mapped or stale) instrument under the near-canonical
    spelling: APT-USD $0.000131 vs APTUSD $4.376, ENJ-USD $0.027 vs ENJUSD $0.284,
    YFI-USD $2,087 vs YFIUSD $6,235. Blending them produced a series that alternates
    between price scales at adjacent timestamps — the square wave the operator saw on
    ENJ/YFI/LDO/XTZ/BF-B/BRK-B, the fake peaks that fed rhythm and fingerprints, the
    incoherent leaderboards (91.7% win rate at -1.33% mean), and marks a book could
    book a windfall against. One bad assumption, every downstream lie.

    The law now: ONE canonical key still means one series, but a spelling JOINS that
    series only if it is verifiably the same asset at the same price at the same moments.
    Everything else is rejected with a named reason and journaled — never blended,
    never silently dropped."""
    out = Path(out_dir)
    # ── gather every candidate spelling, keyed canonically ──────────────────────────
    cands: Dict[str, List[Dict[str, Any]]] = {}
    for fn in SAMPLE_FILES:
        try:
            s = json.loads((out / fn).read_text()).get("samples", {}) or {}
        except Exception:
            continue
        for k, rows in s.items():
            key = canon(k) if is_crypto_key(k) else k
            if not key:
                continue
            live = _live_rows(rows)
            cands.setdefault(key, []).append({
                "spelling": k, "file": fn, "rows": list(rows or []), "live": live,
                "primary": (fn == "price_samples.json"), "med": _median([r[1] for r in live]),
                "shape": _shape(live),
            })

    # ── the outside arbiter: real venue prices, when we have them ───────────────────
    ext: Dict[str, float] = {}
    try:
        so = json.loads((out / "SOURCE_OVERLAY.json").read_text())
        for sym, rec in (so.get("symbols") or {}).items():
            px = []
            for _lab, rws in (rec.get("providers") or {}).items():
                for r in (rws or [])[-40:]:
                    try:
                        v = float(r[1])
                        if v > 0:
                            px.append(v)
                    except Exception:
                        pass
            m = _median(px)
            if m:
                ext[canon(sym) if is_crypto_key(sym) else sym] = m
    except Exception:
        pass

    merged: Dict[str, List] = {}
    rejects: List[Dict[str, Any]] = []
    disputes: List[Dict[str, Any]] = []

    for key, cl in cands.items():
        if len(cl) == 1:
            merged[key] = cl[0]["rows"]
            continue
        # 1) pick the REFERENCE spelling
        arb = ext.get(key)
        ref = None
        if arb:
            scored = [(abs((c["med"] or 0) / arb - 1.0), c) for c in cl if c["med"]]
            if scored:
                scored.sort(key=lambda x: x[0])
                if scored[0][0] <= 0.15:            # an outside venue confirms this spelling
                    ref = scored[0][1]
                    ref["_why_ref"] = "matches outside venue (%.1f%% off)" % (scored[0][0] * 100)
        if ref is None:
            prim = [c for c in cl if c["primary"] and c["live"]]
            if prim:
                ref = max(prim, key=lambda c: c["shape"]["levels"])
                ref["_why_ref"] = "primary tape (the series the books mark against)"
            else:
                usable = [c for c in cl if c["live"]] or cl
                ref = max(usable, key=lambda c: c["shape"]["levels"])
                ref["_why_ref"] = "deepest live series (no primary, no outside venue)"
        # if an outside venue exists and even the reference disagrees hard, say so out loud
        if arb and ref.get("med") and abs(ref["med"] / arb - 1.0) > 0.15:
            disputes.append({"sym": key, "our_px": round(ref["med"], 10),
                             "outside_px": round(arb, 10),
                             "off_pct": round((ref["med"] / arb - 1.0) * 100, 3),
                             "spelling": ref["spelling"],
                             "why": "our tape disagrees with real venues — arbitration needed before this name is trusted"})
        # 2) admit only the spellings that are verifiably the SAME asset at the SAME moments
        rows = list(ref["rows"])
        for c in cl:
            if c is ref:
                continue
            sh = c["shape"]
            if sh["levels"] <= 2 and sh["repeat"] >= 0.95:
                rejects.append({"sym": key, "spelling": c["spelling"], "file": c["file"],
                                "reason": "FROZEN_SERIES", "levels": sh["levels"],
                                "repeat_pct": round(sh["repeat"] * 100, 1),
                                "why": "a flat series adds no history and manufactures fake steps when interleaved"})
                continue
            ratio, npair = _aligned_ratio(c["live"], ref["live"])
            if ratio is None or npair < 3:
                rejects.append({"sym": key, "spelling": c["spelling"], "file": c["file"],
                                "reason": "UNVERIFIABLE_NO_OVERLAP", "pairs": npair,
                                "why": "never priced at the same moments as the reference, so its scale cannot be checked"})
                continue
            if abs(ratio - 1.0) > SCALE_TOL:
                rejects.append({"sym": key, "spelling": c["spelling"], "file": c["file"],
                                "reason": "SCALE_CONFLICT", "ratio": round(ratio, 6),
                                "pairs": npair,
                                "ref_px": round(ref["med"] or 0, 10), "cand_px": round(c["med"] or 0, 10),
                                "why": "different price scale at the same moments — a different instrument, not this one"})
                continue
            rows = _union_rows(rows, c["rows"])       # verified same asset: history joins
        merged[key] = rows

    report = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "law": ("one canonical key = one series, but a spelling joins it only if an outside venue or "
                      "time-aligned price check proves it is the same asset at the same scale"),
              "scale_tolerance_pct": SCALE_TOL * 100,
              "symbols": len(merged), "candidates": sum(len(v) for v in cands.values()),
              "admitted": sum(len(v) for v in cands.values()) - len(rejects),
              "rejected": len(rejects), "rejects": rejects,
              "outside_arbiter_symbols": len(ext), "disputed": disputes}
    return merged, report


def canonical_samples(out_dir) -> Dict[str, List]:
    """THE loader. One canonical key per asset, history unioned ONLY across spellings
    proven to be the same asset at the same scale (see canonical_samples_report)."""
    return canonical_samples_report(out_dir)[0]


def canonicalize_positions(out_dir) -> Dict[str, Any]:
    """Idempotent migration: re-key any OPEN position or resting maker order booked
    under a non-canonical spelling. Runs at the top of every live cycle; a no-op
    when everything is already canonical. Every migration is journaled to
    CANON_MIGRATIONS.jsonl so the record shows exactly what was renamed and when.
    Closed trades are HISTORY and are never rewritten."""
    out = Path(out_dir)
    moved: List[Dict[str, Any]] = []
    nowiso = datetime.now(timezone.utc).isoformat()

    for bp in sorted(out.glob("paper_book_*.json")):
        try:
            book = json.loads(bp.read_text())
        except Exception:
            continue
        pos = book.get("positions") or {}
        changed = False
        for sym in list(pos.keys()):
            ck = canon(sym) if is_crypto_key(sym) else sym
            if ck == sym:
                continue
            if ck in pos:
                # canonical twin already held in the SAME book — do not merge blindly;
                # leave the row and flag it loudly for the operator.
                moved.append({"t": nowiso, "file": bp.name, "sym": sym, "to": ck,
                              "action": "FLAGGED_DUPLICATE", "why": "canonical twin already open in this book"})
                continue
            pos[ck] = pos.pop(sym)
            pos[ck]["migrated_from"] = sym
            changed = True
            moved.append({"t": nowiso, "file": bp.name, "sym": sym, "to": ck,
                          "action": "REKEYED_OPEN_POSITION",
                          "why": "one-key law — a non-canonical key cannot be marked or exited"})
        if changed:
            try:
                bp.write_text(json.dumps(book, indent=2))
            except Exception:
                pass

    mp = out / "MAKER_PENDING.json"
    try:
        pend = json.loads(mp.read_text())
        pchanged = False
        for bk, orders in list((pend or {}).items()):
            if not isinstance(orders, dict):
                continue
            for sym in list(orders.keys()):
                ck = canon(sym) if is_crypto_key(sym) else sym
                if ck != sym and ck not in orders:
                    orders[ck] = orders.pop(sym)
                    pchanged = True
                    moved.append({"t": nowiso, "file": "MAKER_PENDING.json", "sym": sym,
                                  "to": ck, "action": "REKEYED_MAKER_ORDER", "why": "one-key law"})
        if pchanged:
            mp.write_text(json.dumps(pend, indent=1))
    except Exception:
        pass

    if moved:
        try:
            with open(out / "CANON_MIGRATIONS.jsonl", "a") as f:
                for row in moved:
                    f.write(json.dumps(row) + "\n")
        except Exception:
            pass
    return {"migrated": len([m for m in moved if m["action"].startswith("REKEYED")]),
            "flagged": len([m for m in moved if m["action"] == "FLAGGED_DUPLICATE"]),
            "rows": moved}
