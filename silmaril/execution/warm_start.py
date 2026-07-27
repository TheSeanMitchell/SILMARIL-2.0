"""
WARM START — 7.1.7. The bootstrap, done without lying.

THE PROBLEM, stated exactly. After a wipe the sleeves fill within minutes, but a BOOK cannot
arm until its workshop PROMOTES a sleeve, and promotion needs >=3 real closed trades with a
positive edge over doing nothing. So the operator waits days. Worse, look at what the seed
actually was during that wait: sleeve_promotion picks the PROVISIONAL sleeve by forward score,
and immediately after a wipe every sleeve has zero closes, so every score is None and the seed
is effectively a coin flip. The book then waits for whichever sleeve happens to close three
trades first — which may be the worst one in the workshop.

THE TEMPTING WRONG FIX, and why it is refused. It would be easy to "warm up" the books by
synthesising closed trades from a backtest. That would push fabricated rows into the very
river the maturity gate, the promotion ladder and the 100-trade clock read — the exact class
of corruption that produced the PNUT $242 and BRENT $198 fills we spent three releases
removing. This module NEVER writes a trade, NEVER touches LAB_OUTCOMES.jsonl, and NEVER arms
a book. Not one number it produces can reach the gate.

WHAT IT DOES INSTEAD. It answers one question from real stored tape: *which sleeve personality
would have done best on this book's names over the last N days, and how quickly would it have
resolved trades?* Then it hands that answer to sleeve_promotion as the PROVISIONAL seed. The
book still has to earn its arming with three real forward closes — but it now spends that wait
running the personality most likely to earn it, instead of a stranger picked at random.

HOW THE BACKTEST STAYS HONEST (every law from earlier releases applies here too):
  * only feeds PRICE_TRUTH graded OK — a stuck or quantized tape teaches nothing
  * only the canonical scale-guarded series — no blended spellings, no sawtooth
  * session-segmented — a trade can never exit into an overnight gap it could not trade
  * survivorship-free — positions still open at the window's end are MARKED and counted,
    never discarded, because dropping them counts only the winners that resolved
  * a take-profit fills at its LIMIT, a stop takes the WORSE of trigger and mark
  * each name uses ITS OWN fingerprint dip/target/stop, never a blanket threshold
  * measured against the do-nothing null (buy-and-hold), because beating nothing is the bar

WHAT IT PUBLISHES. `WARM_START.json`: per book, the recommended sleeve personality, the filter
that defines it, its backtested trade count / win rate / mean net / delta-vs-null, the median
hours a trade took to resolve, and from that an honest ETA to the three closes that arm the
book. Every row is stamped `evidence_class: "BACKTEST_HYPOTHESIS"` so nobody can mistake it
for forward evidence.

Knob `warm_start` {mode: auto|off, lookback_days, min_trades} · KILL mode:"off".
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .atomic_io import write_json_atomic
except Exception:                                            # pragma: no cover
    def write_json_atomic(path, payload):                    # type: ignore
        Path(path).write_text(json.dumps(payload, indent=2))

DEFAULTS = {
    "mode": "auto",
    "lookback_days": 30,
    "min_trades": 8,             # below this a personality has not earned a recommendation
    "gap_min": 90.0,             # session boundary: a gap longer than this splits the series
    "max_names_per_book": 120,   # keep the pass fast enough to run every cycle
}

# The sleeve personalities, expressed as the FILTER that defines each one. Sleeve behaviour is
# selected, never edited (Law 6) — so the warm start chooses between personalities that already
# exist; it never invents a new shape or tunes one.
PERSONALITIES: List[Dict[str, Any]] = [
    {"sleeve": "A", "name": "FOREVER RIDE", "filter": "all", "ride": True, "cap": 10},
    {"sleeve": "D", "name": "SNIPER", "filter": "confidence", "ride": True, "cap": 3},
    {"sleeve": "G", "name": "GEOMETRY SNIPER", "filter": "geometry", "ride": True, "cap": 4},
    {"sleeve": "H", "name": "PATIENT REVERT", "filter": "patient", "ride": False, "cap": 3},
    {"sleeve": "I", "name": "VOLATILITY HUNTER", "filter": "reach", "ride": True, "cap": 4},
    {"sleeve": "J", "name": "TREND RIDER", "filter": "trend", "ride": True, "cap": 4},
]


def _knobs(out: Path) -> Dict[str, Any]:
    k = dict(DEFAULTS)
    try:
        cat = json.loads((out / "PARAM_CATALOG.json").read_text()) or {}
        for kk, vv in (cat.get("warm_start") or {}).items():
            k[kk] = vv
    except Exception:
        pass
    return k


def _ts(x) -> Optional[float]:
    try:
        d = datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        if not d.tzinfo:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()
    except Exception:
        return None


def _segments(rows: List, cutoff: float, gap_s: float) -> List[List[Tuple[float, float]]]:
    """Live prints inside the lookback, cut into session-continuous segments."""
    live: List[Tuple[float, float]] = []
    for r in (rows or []):
        try:
            if not r or len(r) < 2 or not r[1] or float(r[1]) <= 0 or "T00:00:00" in str(r[0]):
                continue
            t = _ts(r[0])
            if t and t >= cutoff:
                live.append((t, float(r[1])))
        except Exception:
            continue
    live.sort()
    segs, cur = [], []
    for i, pt in enumerate(live):
        if cur and (pt[0] - live[i - 1][0]) > gap_s:
            segs.append(cur)
            cur = []
        cur.append(pt)
    if cur:
        segs.append(cur)
    return [s for s in segs if len(s) > 10]


def _sim(segs, dip: float, target: float, stop: float, cost: float,
         ride: bool, trail_give: float = 0.25) -> Dict[str, Any]:
    """Mean-reversion on ONE name, obeying every fill law the live engine obeys.

    Returns realized returns, exit reasons, and how long each trade took — the hold time is
    what turns 'which sleeve is best' into 'and how soon will it arm the book'."""
    rets: List[float] = []
    holds: List[float] = []
    exits = {"TAKE": 0, "STOP": 0, "TRAIL": 0, "OPEN_MARK": 0}
    for seg in segs:
        px = [p for _t, p in seg]
        ts = [t for t, _p in seg]
        n = len(px)
        i = 6
        while i < n - 1:
            ref = max(px[max(0, i - 6):i + 1])
            if ref <= 0 or (px[i] / ref - 1.0) > -dip:
                i += 1
                continue
            entry, ei = px[i], i
            j, best, out = i + 1, 0.0, None
            while j < n:
                ch = px[j] / entry - 1.0
                if ch <= -stop:                       # market stop: take the WORSE of the two
                    out = ("STOP", min(px[j], entry * (1.0 - stop)), j)
                    break
                if ch >= target:
                    if not ride:                      # limit: can never fill above the limit
                        out = ("TAKE", min(px[j], entry * (1.0 + target)), j)
                        break
                    best = max(best, ch)
                    if ch < best * (1.0 - trail_give):
                        out = ("TRAIL", px[j], j)     # trail exit is a market order
                        break
                j += 1
            if out is None:
                if n - 1 > ei:                        # survivorship: mark it, never drop it
                    rets.append((px[n - 1] / entry - 1.0) - cost)
                    holds.append((ts[n - 1] - ts[ei]) / 3600.0)
                    exits["OPEN_MARK"] += 1
                break
            why, fill, k = out
            rets.append((fill / entry - 1.0) - cost)
            holds.append((ts[k] - ts[ei]) / 3600.0)
            exits[why] += 1
            i = k + 1
    return {"rets": rets, "holds": holds, "exits": exits}


def _null_return(segs) -> float:
    """Buy-and-hold over the same window — the do-nothing bar every result must clear."""
    if not segs:
        return 0.0
    first = segs[0][0][1]
    last = segs[-1][-1][1]
    return (last / first - 1.0) if first > 0 else 0.0


def _passes(filt: str, sym: str, card: Dict[str, Any], geo: Dict[str, Any],
            fp: Dict[str, Any]) -> bool:
    if filt == "all":
        return True
    if filt == "confidence":
        return float(card.get("confidence") or 0) >= 0.45
    if filt == "patient":
        return float((fp.get("fp") or {}).get("bounce_reliability")
                     or card.get("bounce_reliability") or 0) >= 0.70
    if filt == "geometry":
        return str(geo.get("verdict") or "") == "TRADEABLE"
    if filt == "trend":
        return float((card.get("momentum") or {}).get("d1") or 0) > 0
    if filt == "reach":
        fit = fp.get("fit") or {}
        t, c = float(fit.get("target") or 0), float(fp.get("cost") or 0.004)
        return t > 0 and (t / max(c, 1e-6)) >= 3.0
    return True


def build_warm_start(out_dir, samples: Dict[str, List] = None) -> Dict[str, Any]:
    out = Path(out_dir)
    k = _knobs(out)
    now = datetime.now(timezone.utc)
    if str(k.get("mode")) == "off":
        payload = {"generated_at": now.isoformat(), "mode": "off",
                   "note": "warm_start KILLED by knob — books seed the old way (forward score only)"}
        write_json_atomic(out / "WARM_START.json", payload)
        return payload

    if samples is None:
        try:
            from .canon_keys import canonical_samples
            samples = canonical_samples(out)
        except Exception:
            samples = {}

    def _load(name):
        try:
            return json.loads((out / name).read_text())
        except Exception:
            return {}

    truth = (_load("PRICE_TRUTH.json").get("by_symbol") or {})
    cards = (_load("CONFIDENCE_CARDS.json").get("cards") or {})
    geos = (_load("GEOMETRY.json").get("by_symbol") or {})
    fps: Dict[str, Any] = {}
    for c in (_load("FINGERPRINTS.json").get("cards") or []):
        if c and c.get("sym"):
            fps[c["sym"]] = c

    try:
        from .paper_sim import asset_class, round_trip_cost
    except Exception:                                        # pragma: no cover
        def asset_class(s):
            return "crypto"

        def round_trip_cost(px):
            return 0.004

    cutoff = (now - timedelta(days=float(k.get("lookback_days") or 30))).timestamp()
    gap_s = float(k.get("gap_min") or 90.0) * 60.0

    # ── group the tradeable universe by book ─────────────────────────────────────────
    by_book: Dict[str, List[str]] = {}
    for sym in (samples or {}):
        rec = truth.get(sym)
        if rec is not None and not rec.get("tradeable"):
            continue                                          # only OK feeds may teach us anything
        try:
            bk = asset_class(sym)
        except Exception:
            continue
        if bk in ("crypto", "stock", "metal", "energy"):
            by_book.setdefault(bk, []).append(sym)

    books: Dict[str, Any] = {}
    for bk, syms in by_book.items():
        # deepest tapes first — they carry the most evidence per unit of compute
        syms = sorted(syms, key=lambda s: -len(samples.get(s) or []))[: int(k.get("max_names_per_book") or 120)]
        prepared = []
        for sym in syms:
            segs = _segments(samples.get(sym), cutoff, gap_s)
            if not segs:
                continue
            fp = fps.get(sym) or {}
            fit = fp.get("fit") or {}
            dip = float(fit.get("entry") or 0.0)
            tgt = float(fit.get("target") or 0.0)
            stp = float(fit.get("stop") or 0.06)
            if dip <= 0 or tgt <= 0:
                continue                                      # no fingerprint = no honest bar
            cost = float(fp.get("cost") or round_trip_cost([p for _t, p in segs[0]]) or 0.004)
            prepared.append((sym, segs, dip, tgt, stp, cost, fp))
        if not prepared:
            books[bk] = {"status": "NO_TAPE",
                         "why": "no name in this book has both a fitted fingerprint and a "
                                "session-continuous tape inside the lookback"}
            continue

        results = []
        for pers in PERSONALITIES:
            rets: List[float] = []
            holds: List[float] = []
            nulls: List[float] = []
            names = 0
            for (sym, segs, dip, tgt, stp, cost, fp) in prepared:
                if not _passes(pers["filter"], sym, cards.get(sym) or {}, geos.get(sym) or {}, fp):
                    continue
                names += 1
                r = _sim(segs, dip, tgt, stp, cost, pers["ride"])
                rets.extend(r["rets"])
                holds.extend(r["holds"])
                nulls.append(_null_return(segs))
            if len(rets) < int(k.get("min_trades") or 8):
                results.append({"sleeve": pers["sleeve"], "name": pers["name"],
                                "filter": pers["filter"], "names": names, "trades": len(rets),
                                "verdict": "TOO_FEW_TRADES"})
                continue
            mean_net = sum(rets) / len(rets)
            null_mean = (sum(nulls) / len(nulls)) if nulls else 0.0
            per_trade_null = null_mean / max(1.0, len(rets) / max(1, names))
            holds.sort()
            med_hold = holds[len(holds) // 2] if holds else None
            results.append({
                "sleeve": pers["sleeve"], "name": pers["name"], "filter": pers["filter"],
                "names": names, "trades": len(rets),
                "win_pct": round(sum(1 for r in rets if r > 0) / len(rets) * 100, 1),
                "mean_net_pct": round(mean_net * 100, 4),
                "total_net_pct": round(sum(rets) * 100, 2),
                "null_pct": round(per_trade_null * 100, 4),
                "delta_vs_null_pct": round((mean_net - per_trade_null) * 100, 4),
                "median_hold_h": (round(med_hold, 2) if med_hold is not None else None),
                "trades_per_name": round(len(rets) / max(1, names), 2),
                "verdict": "SCORED",
            })

        scored = [r for r in results if r.get("verdict") == "SCORED"]
        pick = None
        if scored:
            # best edge over doing nothing; ties broken by faster resolution, because the whole
            # point is reaching three real closes sooner
            scored.sort(key=lambda r: (-(r["delta_vs_null_pct"]), (r["median_hold_h"] or 1e9)))
            pick = scored[0]

        eta_h = None
        if pick and pick.get("median_hold_h") is not None and pick.get("trades_per_name"):
            # three closes, given this personality's own resolution rate across its filtered names
            per_name_rate = pick["trades_per_name"] / max(1.0, float(k.get("lookback_days") or 30) * 24.0)
            fleet_rate = per_name_rate * max(1, pick["names"])       # closes per hour, whole book
            if fleet_rate > 0:
                eta_h = round(3.0 / fleet_rate, 1)

        books[bk] = {
            "status": "RECOMMENDED" if pick else "NO_RECOMMENDATION",
            "recommended_sleeve": (pick or {}).get("sleeve"),
            "recommended_name": (pick or {}).get("name"),
            "why": ((("%s scored the best edge over doing nothing on this book's own tape "
                      "(delta %+.4f%%/trade over %d backtested trades, median hold %.2fh) and "
                      "resolves fastest among the ties")
                     % (pick["name"], pick["delta_vs_null_pct"], pick["trades"],
                        pick["median_hold_h"] or 0.0)) if pick else
                    "no personality cleared the minimum trade count on this book's tape"),
            "expected_hours_to_arm": eta_h,
            "eta_note": ("estimated time for this personality to produce the THREE real closes "
                         "the arming gate needs, at the rate it resolved trades historically. "
                         "It is an estimate from backtest, not a promise."),
            "candidates": sorted(results, key=lambda r: -(r.get("delta_vs_null_pct") or -1e9)),
            "universe_names": len(prepared),
        }

    payload = {
        "generated_at": now.isoformat(),
        "mode": k.get("mode"), "knobs": k,
        "evidence_class": "BACKTEST_HYPOTHESIS",
        "what": ("which sleeve personality would have done best on each book's OWN names over the "
                 "last %s days, and how quickly it resolved trades — used ONLY to choose the "
                 "PROVISIONAL seed so the workshop spends its wait running the most promising "
                 "personality instead of a coin flip." % k.get("lookback_days")),
        "hard_limits": [
            "writes no trade, ever — LAB_OUTCOMES.jsonl and every evidence ledger are untouched",
            "arms no book — the gate still needs 3 REAL forward closes with positive delta-vs-null",
            "counts toward nothing — the 100-trade / 90-day clock cannot see this file",
            "selects between existing personalities; never edits a sleeve's behaviour (Law 6)",
        ],
        "honesty": ("a backtest on stored tape is a hypothesis about the past. It says which "
                    "personality WOULD have worked, not which one WILL. Its only power here is "
                    "choosing where to start."),
        "books": books,
    }
    write_json_atomic(out / "WARM_START.json", payload)
    return payload


def recommended_sleeve(out_dir, book: str) -> Optional[str]:
    """The PROVISIONAL seed for a book with no forward evidence yet, or None."""
    try:
        d = json.loads((Path(out_dir) / "WARM_START.json").read_text())
        if str(d.get("mode")) == "off":
            return None
        rec = (d.get("books") or {}).get(book) or {}
        return rec.get("recommended_sleeve")
    except Exception:
        return None


if __name__ == "__main__":                                   # pragma: no cover
    import sys
    p = build_warm_start(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    for bk, r in (p.get("books") or {}).items():
        print("%-7s %-16s %s" % (bk, r.get("status"), r.get("recommended_name") or "—"))
        if r.get("expected_hours_to_arm") is not None:
            print("        ETA to 3 closes: ~%sh" % r["expected_hours_to_arm"])
        for c in (r.get("candidates") or [])[:4]:
            if c.get("verdict") == "SCORED":
                print("        %s %-17s d-null=%+.4f%% trades=%-4s win=%5.1f%% hold=%sh"
                      % (c["sleeve"], c["name"], c["delta_vs_null_pct"], c["trades"],
                         c["win_pct"], c["median_hold_h"]))
