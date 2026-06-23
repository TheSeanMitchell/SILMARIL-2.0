"""
silmaril.execution.momentum_chain — the 10-min sample edge (June 17).

THE OPERATOR'S GOLDEN LAW: every run (~10 min) we snapshot every tracked
ticker's price with a timestamp, then measure its move across a CHAIN of
windows — since last read, 1h, 2h, 3h, 1d, 2d, 3d, 1w. That chain — NOT
news sentiment — decides what we buy and how hard. Sentiment is the floor;
momentum-since-last-read is the lead lever.

Two pieces here:
  1. record_samples(prices)  — append this run's prices to a timestamped
     rolling store (docs/data/price_samples.json). Trimmed to ~8 days.
  2. compute_chain(ticker)   — return the % move over each window plus a
     composite "heat" score and a 0-1 "fire meter".

The chain is the system's real edge: a hand trader can't re-evaluate every
name every 10 minutes; this does.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

VERSION = "momentum-chain-1.0"
SAMPLES_PATH_NAME = "price_samples.json"
MAX_SAMPLE_AGE_DAYS = 8

# windows, in minutes, from fastest to slowest
WINDOWS = [
    ("since_last", None),   # since the previous sample (the ~10-min read)
    ("h1", 60),
    ("h2", 120),
    ("h3", 180),
    ("d1", 1440),
    ("d2", 2880),
    ("d3", 4320),
    ("w1", 10080),
]

# weight of each window in the composite — 10-min read heaviest, decaying.
# (operator: "direction since the last 10 min should be the heaviest weight,
#  weighted down from there ... sentiment the least important")
CRYPTO_WEIGHTS = {"since_last": 0.40, "h1": 0.20, "h2": 0.12, "h3": 0.08,
                  "d1": 0.10, "d2": 0.04, "d3": 0.03, "w1": 0.03}
# stocks move slower & are less fickle → lean on the longer windows more,
# the 10-min read less (operator's exact intuition).
STOCK_WEIGHTS = {"since_last": 0.18, "h1": 0.18, "h2": 0.14, "h3": 0.12,
                 "d1": 0.20, "d2": 0.08, "d3": 0.05, "w1": 0.05}


def _load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def _dump(path, obj):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, separators=(",", ":"), allow_nan=False)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def _now():
    return datetime.now(timezone.utc)


def record_samples(out_dir, prices: Dict[str, float]) -> Dict[str, Any]:
    """Append this run's {ticker: price} to the rolling timestamped store.
    Trims anything older than MAX_SAMPLE_AGE_DAYS. Returns the store."""
    out = Path(out_dir)
    p = out / SAMPLES_PATH_NAME
    store = _load(p, {})
    if not isinstance(store, dict) or "samples" not in store:
        store = {"version": VERSION, "samples": {}}
    ts = _now().isoformat()
    cutoff = (_now() - timedelta(days=MAX_SAMPLE_AGE_DAYS)).isoformat()
    samples = store["samples"]
    for tk, pr in prices.items():
        if pr is None:
            continue
        try:
            pr = float(pr)
        except Exception:
            continue
        if pr <= 0:
            continue
        row = samples.get(tk) or []
        # PRICE-SANITY GUARD (June 17): reject an obviously-corrupt feed tick
        # — an implausible single-step jump vs the last good sample (e.g. the
        # ARB 0.0836 -> 0.000757 glitch, a 99% "drop" that was a bad feed
        # value). If the new price is <40% or >250% of the last sample, skip
        # it so it can't poison the chain or the graphs. (Real moves rarely
        # exceed this between two ~10-min reads; a true halt/gap will re-sync
        # on the next clean tick.)
        if row:
            last_good = row[-1][1]
            if last_good > 0:
                ratio = pr / last_good
                if ratio < 0.40 or ratio > 2.5:
                    store.setdefault("rejected_ticks", [])
                    store["rejected_ticks"] = (store["rejected_ticks"] + [{
                        "ticker": tk, "rejected_price": pr,
                        "last_good": last_good, "at": ts}])[-100:]
                    continue
        row.append([ts, round(pr, 8)])
        # trim old
        row = [r for r in row if r[0] >= cutoff]
        samples[tk] = row[-1200:]  # hard cap per ticker
    store["last_recorded"] = ts
    store["tickers"] = len(samples)
    _dump(p, store)
    return store


def _pct(old, new):
    if old is None or new is None or old <= 0:
        return None
    return (new - old) / old * 100.0


def _nearest_before(rows, target_dt):
    """Return the price at the sample closest to (and at/just before)
    target_dt, else the oldest sample we have."""
    best = None
    for ts, pr in rows:
        try:
            t = datetime.fromisoformat(ts)
        except Exception:
            continue
        if t <= target_dt:
            best = pr
        else:
            break
    return best if best is not None else (rows[0][1] if rows else None)


def compute_chain(out_dir, ticker: str, is_crypto: bool = True
                  ) -> Optional[Dict[str, Any]]:
    """Compute the multi-window % chain + composite heat + fire meter for a
    ticker from the sample store. Returns None if not enough samples yet."""
    out = Path(out_dir)
    store = _load(out / SAMPLES_PATH_NAME, {})
    rows = (store.get("samples") or {}).get(ticker) or []
    if len(rows) < 2:
        return None
    now_dt = _now()
    last_price = rows[-1][1]
    prev_price = rows[-2][1]
    chain = {}
    for name, mins in WINDOWS:
        if name == "since_last":
            chain[name] = _pct(prev_price, last_price)
        else:
            old = _nearest_before(rows, now_dt - timedelta(minutes=mins))
            chain[name] = _pct(old, last_price)

    weights = CRYPTO_WEIGHTS if is_crypto else STOCK_WEIGHTS
    # composite heat: weighted sum of available windows (renormalized over
    # the ones we actually have data for, so a young store still scores).
    num = 0.0
    wsum = 0.0
    for name, _ in WINDOWS:
        v = chain.get(name)
        if v is not None:
            num += v * weights[name]
            wsum += weights[name]
    composite = (num / wsum) if wsum > 0 else 0.0

    # FIRE METER (0-1): how many windows are GREEN, weighted. Operator: "even
    # small .3% gains across more than one segment is a sign of being on
    # fire ... it's the % changes and holds over time." So we reward
    # CONSISTENCY of green across windows, not raw magnitude.
    green_w = 0.0
    tot_w = 0.0
    for name, _ in WINDOWS:
        v = chain.get(name)
        if v is None:
            continue
        tot_w += weights[name]
        if v > 0:
            green_w += weights[name]
    fire = (green_w / tot_w) if tot_w > 0 else 0.0

    return {
        "ticker": ticker,
        "windows": {k: (round(v, 3) if v is not None else None)
                    for k, v in chain.items()},
        "composite": round(composite, 4),
        "fire": round(fire, 3),
        "last_price": last_price,
        "samples": len(rows),
        "asof": rows[-1][0],
    }


def compute_all_chains(out_dir, tickers_is_crypto: Dict[str, bool]
                       ) -> Dict[str, Any]:
    """Compute chains for many tickers and write a transparent board the UI
    can render (docs/data/momentum_chain.json)."""
    out = Path(out_dir)
    board = {}
    for tk, is_c in tickers_is_crypto.items():
        ch = compute_chain(out, tk, is_c)
        if ch:
            board[tk] = ch
    payload = {
        "version": VERSION,
        "generated_at": _now().isoformat(),
        "count": len(board),
        "note": ("Per-ticker price-move chain across windows (since last "
                 "read → week). Composite weights the 10-min read heaviest "
                 "for crypto, longer windows heavier for stocks. Fire = how "
                 "consistently green across windows. This drives ranking; "
                 "sentiment is only the floor."),
        "chains": board,
    }
    _dump(out / "momentum_chain.json", payload)
    return payload
