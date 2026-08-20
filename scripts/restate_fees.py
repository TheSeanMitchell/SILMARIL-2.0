#!/usr/bin/env python3
"""restate_fees.py — 7.5 THE ONE-MOVE RESTATEMENT.

WHAT THIS IS
------------
Every closed trade in STRATEGY_LAB.json is RE-PRICED at the real per-symbol venue
cost the engine uses today, charged on BOTH sides. Cash, realized P&L and equity are
rebuilt from the corrected numbers. One pass, whole history, nothing thrown away.

WHAT THIS IS *NOT* — and the distinction matters
-------------------------------------------------
This is a RESTATEMENT, not a re-simulation. The trades stay exactly as they happened;
only their pricing is corrected. It does NOT ask "would this trade have triggered at
the new fee?" — a higher fee moves break-even and give-back thresholds, so a true
re-simulation would produce a DIFFERENT SET of trades and would need the full tape
replayed. That is a different experiment and it is not this one.

An accountant restating a misapplied fee schedule does exactly this: same
transactions, corrected pricing. The restated numbers are honest for the trades that
happened. They are not a claim about trades that might have happened instead.

WHAT CHANGES
------------
  * every SELL gets a corrected realized_pct and pnl, stamped `restated: true`
  * cash and realized_pnl are rebuilt from the corrected P&L
  * open positions get a cost-inclusive entry basis at the real cost
  * peak_equity / max_dd_pct are RESET (the historical equity path cannot be
    recovered from trade records alone, and inventing one would be a lie)

    python scripts/restate_fees.py            # dry run — prints, writes nothing
    python scripts/restate_fees.py --write    # writes, after backing the file up
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
BLANKET = {True: 0.004, False: 0.006}          # px>=1, px<1 — the retired blanket


def load_tape():
    tape = {}
    try:
        sys.path.insert(0, str(ROOT))
        from silmaril.execution.canon_keys import canonical_samples
        tape = dict(canonical_samples(DATA) or {})
    except Exception:
        pass
    for fn in ("price_samples.json", "ccxt_samples.json",
               "metals_samples.json", "energy_samples.json"):
        try:
            d = json.loads((DATA / fn).read_text(encoding="utf-8"))
            for k, v in (d.get("samples") or {}).items():
                if isinstance(v, list) and v:
                    tape.setdefault(k, []).extend(v)
        except Exception:
            continue
    return tape


def true_cost(sym, book, tape, cache):
    """The real round trip for THIS name, from the same model the live engine uses."""
    key = (sym, book)
    if key in cache:
        return cache[key]
    c = None
    try:
        from silmaril.execution.paper_sim import round_trip_cost
        px = [p for _t, p in (tape.get(sym) or []) if p and p > 0]
        if px:
            c = float(round_trip_cost(px, book))
    except Exception:
        c = None
    if not c or c <= 0:                       # no tape for this name — class floor
        c = 0.0033 if book == "crypto" else 0.0007
    cache[key] = c
    return c


def main(write=False):
    lab_path = DATA / "STRATEGY_LAB.json"
    lab = json.loads(lab_path.read_text(encoding="utf-8"))
    tape = load_tape()
    cache = {}

    # When did the both-sides code go live? The earliest open position carrying
    # `raw_entry` marks it. Trades opened before that stored a RAW entry price and
    # paid nothing on the way in; trades after stored a cost-inclusive entry.
    cutoff = None
    for key, s in lab["sleeves"].items():
        for _sym, p in (s.get("positions") or {}).items():
            if "raw_entry" in p and p.get("t"):
                cutoff = min(cutoff or p["t"], p["t"])
    if not cutoff:
        cutoff = "9999"                        # nothing new yet: treat all as old-style
    print("both-sides code went live at: %s" % cutoff[:19])

    tot_before = tot_after = 0.0
    rows = []
    for key, s in lab["sleeves"].items():
        book = key.split(":")[0]
        old_real = float(s.get("realized_pnl", 0.0))
        new_real = 0.0
        n_re = 0
        for t in s.get("trades", []):
            if t.get("side") != "SELL":
                continue
            e, x, rp = t.get("entry"), t.get("exit"), t.get("realized_pct")
            pnl = float(t.get("pnl") or 0.0)
            if not e or not x or rp is None:
                new_real += pnl
                continue
            c = true_cost(t.get("sym"), book, tape, cache)
            # recover the RAW entry price this fill actually happened at
            was_new_style = str(t.get("opened_t") or "") >= cutoff
            if was_new_style:
                charged = (x / e - 1) * 100 - float(rp)     # ~ c_old/2 as a percent
                raw_entry = e / (1.0 + charged / 100.0)
            else:
                raw_entry = e
            # the notional this trade actually rode
            notional = abs(pnl / (float(rp) / 100.0)) if abs(float(rp)) > 1e-9 else 0.0
            # corrected: entry pays c/2, exit pays c/2, on the same raw prices
            eff_in = raw_entry * (1.0 + c / 2.0)
            eff_out = x * (1.0 - c / 2.0)
            new_pct = (eff_out / eff_in - 1.0) * 100.0 if eff_in > 0 else 0.0
            new_pnl = notional * new_pct / 100.0
            t["restated"] = True
            t["pnl_original"] = round(pnl, 2)
            t["realized_pct_original"] = rp
            t["cost_applied"] = round(c, 6)
            t["pnl"] = round(new_pnl, 2)
            t["realized_pct"] = round(new_pct, 3)
            new_real += new_pnl
            n_re += 1
        # rebuild cash and realized from the corrected P&L
        delta = new_real - old_real
        s["cash"] = float(s.get("cash", 0.0)) + delta
        s["realized_pnl"] = new_real
        # open positions: put them on a cost-inclusive basis at the real cost
        for sym, p in (s.get("positions") or {}).items():
            c = true_cost(sym, book, tape, cache)
            raw = float(p.get("raw_entry") or p.get("entry") or 0.0)
            if raw > 0:
                p["raw_entry"] = raw
                p["entry"] = raw * (1.0 + c / 2.0)
                p["cost"] = c
                p["restated"] = True
        # the equity path cannot be reconstructed from trade records; reset rather than invent
        mv = sum(float(p.get("qty", 0)) * float(p.get("mark") or p.get("entry") or 0)
                 for p in (s.get("positions") or {}).values())
        eq = float(s["cash"]) + mv + float(s.get("vault_usd", 0.0))
        s["peak_equity"] = max(10000.0, eq)
        s["max_dd_pct"] = 0.0
        tot_before += old_real
        tot_after += new_real
        if n_re:
            rows.append((key, n_re, old_real, new_real))

    rows.sort(key=lambda r: r[3] - r[2])
    print("\nBIGGEST RESTATEMENTS (realized $, before -> after)")
    for k, n, a, b in rows[:6]:
        print("  %-12s n=%-4d %+9.0f -> %+9.0f   (%+.0f)" % (k, n, a, b, b - a))
    print("  ...")
    for k, n, a, b in rows[-4:]:
        print("  %-12s n=%-4d %+9.0f -> %+9.0f   (%+.0f)" % (k, n, a, b, b - a))
    print("\nTOTAL realized across all sleeves: %+.0f -> %+.0f  (%+.0f)"
          % (tot_before, tot_after, tot_after - tot_before))
    print("sleeves restated: %d" % len(rows))

    lab["restated_at"] = datetime.now(timezone.utc).isoformat()
    lab["restatement_note"] = (
        "every closed trade re-priced at the real per-symbol venue cost, both sides. "
        "This is a RESTATEMENT (same trades, corrected pricing), NOT a re-simulation: "
        "it does not ask whether each trade would still have triggered at the higher "
        "fee. peak_equity/max_dd were reset because the historical equity path cannot "
        "be recovered from trade records.")

    if write:
        bak = DATA / "STRATEGY_LAB.json.pre_restate"
        shutil.copy2(lab_path, bak)
        lab_path.write_text(json.dumps(lab, indent=1), encoding="utf-8")
        print("\nwrote %s\nbackup at %s" % (lab_path, bak))
    else:
        print("\nDRY RUN — nothing written. Re-run with --write to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv))
