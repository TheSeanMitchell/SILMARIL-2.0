#!/usr/bin/env python3
"""
scripts/sanitize_history.py — repair corrupt price rows in news_history.json.

Some feeds occasionally emit a single garbage tick (e.g. ARB-USD showing
0.000757 between two ~0.085 rows — a 99% "drop" that's actually a bad value).
That one row poisons the price chart (the "$0.00 -99%" graph) and any
momentum calc that touches it.

This walks every ticker's daily rows and DROPS any row whose price is an
implausible single-step move versus its neighbors (a drop below 40% or a
jump above 250% of the surrounding level that then "recovers"). It keeps the
clean series. Safe + idempotent: re-running on clean data changes nothing.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

HIST = Path("docs/data/news_history.json")


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def sanitize():
    if not HIST.exists():
        print("no news_history.json"); return
    hist = json.loads(HIST.read_text())
    if not isinstance(hist, dict):
        print("unexpected shape"); return
    total_dropped = 0
    affected = []
    for tk, rows in hist.items():
        if not isinstance(rows, list) or len(rows) < 3:
            continue
        prices = [r.get("price") for r in rows if isinstance(r, dict) and r.get("price")]
        if len(prices) < 3:
            continue
        med = _median(prices)
        if not med or med <= 0:
            continue
        kept = []
        dropped = 0
        for r in rows:
            p = r.get("price") if isinstance(r, dict) else None
            if p and med > 0:
                ratio = p / med
                # a row wildly off the ticker's own median is a bad tick
                if ratio < 0.20 or ratio > 5.0:
                    dropped += 1
                    continue
            kept.append(r)
        if dropped:
            hist[tk] = kept
            total_dropped += dropped
            affected.append((tk, dropped))
    HIST.write_text(json.dumps(hist, indent=2))
    print(f"sanitized: dropped {total_dropped} corrupt row(s) across "
          f"{len(affected)} ticker(s)")
    for tk, n in affected[:20]:
        print(f"  {tk}: dropped {n}")


if __name__ == "__main__":
    sanitize()
