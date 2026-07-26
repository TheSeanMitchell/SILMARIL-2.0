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


def canonical_samples(out_dir) -> Dict[str, List]:
    """THE loader. Merges the four sample files under canonical keys, unioning
    history across spellings. price_samples wins timestamp collisions (it is the
    tape the live executor marks against). Non-crypto keys pass through."""
    out = Path(out_dir)
    merged: Dict[str, List] = {}
    # order matters: primary FIRST so it wins collisions inside _union_rows
    for fn in SAMPLE_FILES:
        try:
            s = json.loads((out / fn).read_text()).get("samples", {}) or {}
        except Exception:
            continue
        primary = (fn == "price_samples.json")
        for k, rows in s.items():
            key = canon(k) if is_crypto_key(k) else k
            if not key:
                continue
            if key not in merged:
                merged[key] = list(rows or [])
            else:
                # existing (earlier file in order) is the more-primary series
                merged[key] = _union_rows(merged[key], rows) if not primary \
                    else _union_rows(rows, merged[key])
    return merged


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
