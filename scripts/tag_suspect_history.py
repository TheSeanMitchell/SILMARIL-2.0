#!/usr/bin/env python3
"""tag_suspect_history.py — ONE-SHOT honesty backfill (2026-07-13 sawtooth day).

Trades booked BEFORE the two-print recorder fix carry no integrity tag, so the
report card's suspect/verified split can't see them. This script re-examines
every SELL from 2026-07-13: if the symbol's stored tape around the trade shows
the oscillation signature (or sits in the phantom +2.5–4.5% band on a name the
detector flags today), it is retro-tagged integrity=SUSPECT_OSC. Idempotent —
already-tagged trades are skipped. Run once via the integrity_backfill workflow.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from silmaril.execution.paper_sim import load_all_samples, _osc_ratio  # noqa: E402

OUT = Path("docs/data")
DAY = "2026-07-13"


def main() -> int:
    samples = load_all_samples(OUT)
    osc_today = set()
    for sym, rows in samples.items():
        px = [p for t, p in rows if p and "T00:00:00" not in str(t) and str(t)[:10] == DAY]
        if _osc_ratio(px):
            osc_today.add(sym)
    total_n, total_usd = 0, 0.0
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        f = OUT / f"paper_book_{bk}.json"
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        changed = False
        for t in d.get("trades") or []:
            if t.get("side") != "SELL" or not str(t.get("t", "")).startswith(DAY):
                continue
            if t.get("integrity") == "SUSPECT_OSC":
                continue
            rp = t.get("realized_pct")
            phantom_band = rp is not None and 2.5 <= float(rp) <= 4.5
            if t.get("sym") in osc_today and phantom_band:
                t["integrity"] = "SUSPECT_OSC"
                changed = True
                total_n += 1
                total_usd += float(t.get("pnl") or 0.0)
        if changed:
            f.write_text(json.dumps(d, indent=1))
            print(f"{bk}: tagged; file written")
    print(f"BACKFILL COMPLETE: {total_n} trades retro-tagged SUSPECT_OSC · ${total_usd:.2f} "
          f"moved from headline to the integrity line (report card shows it next cycle)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
