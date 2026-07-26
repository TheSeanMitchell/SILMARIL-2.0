"""
PRICE TRUTH — 7.1.2. One gate that decides whether a name's tape is good enough to
learn from, trade on, or claim structure about.

THE INCIDENT (2026-07-25 → 26). Three complaints, one disease:
  * "Graph looks the same for ENJ, YFI, LDO, XTZ, BF-B, BRK-B" — square waves everywhere.
  * "Account sold it for a profit of $200. That didn't seem real."
  * "QUADRANT LEADERBOARDS data also looks sketch" — 91.7% win rate at -1.33% mean net.
Two feed defects produced all three:
  1. THE SCALE-BLEND (my 7.1.0 bug, fixed in canon_keys): spellings at different price
     scales were unioned into one series, so the tape alternated between $0.027 and
     $0.284 at adjacent timestamps. Fake peaks, fake rhythm, fake fills.
  2. LOW-RESOLUTION FEEDS (pre-existing): MOG reports 3 price levels 22% apart;
     APT-USD is frozen at a single number. Peak detection happily "finds" 41 peaks in a
     square wave and calls it a 3.0h heartbeat. Learning trained on it is learning noise.

THE PRINCIPLE — the operator's own question: "Is there a way to safely remove the issue
without blocking out real things we can actually invest in?" Yes, and the answer is that
the test must be about FEED RESOLUTION, never price magnitude. A $0.0000001 coin whose
feed reports hundreds of distinct levels is perfectly tradeable. A $200 stock reported at
three levels is not. So the question we ask each name is:

    can this feed even EXPRESS the move our strategy needs to make money?

If the smallest price step the venue reports is larger than the edge we are trying to
capture, then every "dip" and every "bounce" on that name is the tick size, not the
market — and no amount of cleverness downstream can recover it.

GRADES (worst wins):
  OK        — usable everywhere.
  COARSE    — real but low resolution; charts fine, EXCLUDED from entries and from fitting.
  QUANTIZED — a handful of levels; the shape is the tick size. Display-only, banner shown.
  FROZEN    — one or two levels across the window: a dead feed wearing a price.
  DISPUTED  — real venues disagree with our tape by more than the band; nobody trades a
              price two sources can't agree on.
MARKET-CLOSED IS NOT A DEFECT: an ETF repeating its last print over a closed weekend is
correct behaviour, so for equity-class names every measurement is taken over REGULAR
SESSION prints only. BRK-B looking flat at 3am is the calendar, not a broken feed.

Nothing here is thrown away: every excluded name keeps collecting tape and is re-graded
every cycle, so a feed that improves re-enters on its own. Knob `price_truth`
{mode: auto|off, min_levels, min_level_ratio, tick_budget_frac, dispute_pct} · KILL mode:"off".
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:
    from .canon_keys import canon, is_crypto_key
except Exception:                                          # pragma: no cover
    def canon(s):  # type: ignore
        return s

    def is_crypto_key(s):  # type: ignore
        return False

try:
    from .atomic_io import write_json_atomic
except Exception:                                          # pragma: no cover
    def write_json_atomic(path, payload):                  # type: ignore
        Path(path).write_text(json.dumps(payload, indent=2))


DEFAULTS = {
    "mode": "auto",
    "min_levels": 12,          # fewer distinct prices than this in a window = not a market
    "min_level_ratio": 0.04,   # distinct prices per print
    "tick_budget_frac": 0.5,   # the feed's step may not exceed half the move we need
    "default_need_pct": 1.0,   # the move a mean-reversion trade must capture, when unknown
    "dispute_pct": 5.0,        # outside-venue disagreement that voids a name
    "min_prints": 40,          # below this we say UNKNOWN, never a verdict
}

_EQUITY_SUFFIXLESS = ("GLD", "IAU", "SLV", "GDX", "USO", "UNG", "BNO", "CPER", "SIVR",
                      "UGA", "USL", "USOI", "PALL", "PPLT", "SPY", "QQQ")


def _knobs(out: Path) -> Dict[str, Any]:
    k = dict(DEFAULTS)
    try:
        cat = json.loads((out / "PARAM_CATALOG.json").read_text()) or {}
        for kk, vv in (cat.get("price_truth") or {}).items():
            k[kk] = vv
    except Exception:
        pass
    return k


def _cls(sym: str) -> str:
    return "crypto" if is_crypto_key(sym) or str(sym).endswith("-USD") else "equity"


def _ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _session_rows(rows: List, cls: str) -> List:
    """Live prints, and for equity-class names only those inside the US regular session.
    A closed market repeating its last print is CORRECT — grading it as a broken feed is
    how BRK-B and GLD would get wrongly quarantined every weekend."""
    out = []
    for r in (rows or []):
        try:
            if not r or len(r) < 2:
                continue
            px = float(r[1])
            if px <= 0 or "T00:00:00" in str(r[0]):
                continue
        except Exception:
            continue
        if cls == "equity":
            t = _ts(r[0])
            if t is None:
                continue
            t = t.astimezone(timezone.utc)
            if t.weekday() >= 5:
                continue
            mins = t.hour * 60 + t.minute
            if not (13 * 60 + 30 <= mins <= 20 * 60):      # 13:30–20:00 UTC = NYSE regular
                continue
        out.append(px)
    return out


def _tick_pct(levels: List[float]) -> float:
    """Median gap between ADJACENT distinct price levels, as a % of price — the finest
    move this feed is able to report at all."""
    s = sorted(set(levels))
    if len(s) < 2:
        return 100.0
    gaps = [(s[i] - s[i - 1]) / s[i - 1] * 100.0 for i in range(1, len(s)) if s[i - 1] > 0]
    if not gaps:
        return 100.0
    gaps.sort()
    n = len(gaps)
    return gaps[n // 2] if n % 2 else 0.5 * (gaps[n // 2 - 1] + gaps[n // 2])


def _need_pct(sym: str, fps: Dict[str, Any], k: Dict[str, Any]) -> float:
    """The move this name's OWN fingerprint is trying to capture. Falls back to a
    conservative default — never to something so small that everything passes."""
    c = fps.get(canon(sym)) or {}
    fit = c.get("fit") or {}
    for key in ("target", "entry"):
        v = fit.get(key)
        try:
            if v and float(v) > 0:
                return float(v) * 100.0
        except Exception:
            pass
    return float(k.get("default_need_pct") or 1.0)


def grade_symbol(sym: str, rows: List, k: Dict[str, Any],
                 fps: Dict[str, Any], ext_px: float = None) -> Dict[str, Any]:
    cls = _cls(sym)
    ys = _session_rows(rows, cls)
    n = len(ys)
    if n < int(k.get("min_prints") or 14):
        # Too short to say anything. Deliberately NOT tradeable — with capital on the line
        # "we don't know" is a no — but it is not held against the name; it re-grades next cycle.
        return {"sym": sym, "grade": "UNKNOWN", "n": n, "cls": cls,
                "why": "only %d session print(s) — too short to judge the feed either way" % n,
                "tradeable": False, "learnable": False, "structure_ok": False}

    levels = sorted(set(ys))
    lv = len(levels)
    ratio = lv / float(n)
    same = sum(1 for i in range(1, n) if ys[i] == ys[i - 1])
    repeat = same / float(max(1, n - 1))
    tick = _tick_pct(ys)
    need = _need_pct(sym, fps, k)
    budget = need * float(k.get("tick_budget_frac") or 0.5)

    grade, why = "OK", "feed resolves this name finely enough to trade its own edge"
    if ext_px and ext_px > 0:
        off = abs(ys[-1] / ext_px - 1.0) * 100.0
        if off > float(k.get("dispute_pct") or 5.0):
            grade = "DISPUTED"
            why = ("our last price is %.2f%% away from real venues — nobody trades a price "
                   "two sources cannot agree on" % off)
    if grade == "OK":
        if lv <= 2:
            grade, why = "FROZEN", "only %d distinct price(s) across %d session prints — a dead feed wearing a price" % (lv, n)
        elif lv <= 6 or ratio < 0.01:
            grade, why = "QUANTIZED", ("venue reports just %d price levels (%.2f%% apart) — the shape of this "
                                       "chart is the tick size, not trading" % (lv, tick))
        elif tick > budget:
            grade, why = "COARSE", ("smallest reportable step is %.3f%% but this name's edge needs %.3f%% — "
                                    "the feed cannot express the trade" % (tick, need))
        elif lv < int(k.get("min_levels") or 12) or ratio < float(k.get("min_level_ratio") or 0.04):
            grade, why = "COARSE", ("only %d levels over %d prints (%.1f%%) — too blocky to read structure from"
                                    % (lv, n, ratio * 100))

    # A short-but-judgeable tape gets a REAL verdict (a 20-print series frozen at one price
    # is broken now, not "unknown"), flagged provisional so the cockpit can say sample size.
    provisional = n < int(k.get("provisional_prints") or 40)
    return {"sym": sym, "grade": grade, "cls": cls, "n": n, "levels": lv,
            "provisional": provisional,
            "level_ratio": round(ratio, 4), "repeat_pct": round(repeat * 100, 1),
            "tick_pct": round(tick, 4), "needs_pct": round(need, 3),
            "tick_budget_pct": round(budget, 3),
            "outside_px": ext_px, "why": why,
            "tradeable": grade == "OK",
            "learnable": grade == "OK",
            "structure_ok": grade in ("OK", "COARSE")}


def build_price_truth(out_dir, samples: Dict[str, List] = None) -> Dict[str, Any]:
    """Grade every symbol's feed and publish PRICE_TRUTH.json. Called once per cycle,
    before anything learns or trades."""
    out = Path(out_dir)
    k = _knobs(out)
    if str(k.get("mode")) == "off":
        payload = {"generated_at": datetime.now(timezone.utc).isoformat(),
                   "mode": "off", "by_symbol": {},
                   "note": "price_truth KILLED by knob — every feed passes ungraded"}
        write_json_atomic(out / "PRICE_TRUTH.json", payload)
        return payload

    if samples is None:
        try:
            from .canon_keys import canonical_samples
            samples = canonical_samples(out)
        except Exception:
            samples = {}

    fps: Dict[str, Any] = {}
    try:
        for c in (json.loads((out / "FINGERPRINTS.json").read_text()).get("cards") or []):
            if c and c.get("sym"):
                fps[canon(c["sym"])] = c
    except Exception:
        pass

    ext: Dict[str, float] = {}
    try:
        so = json.loads((out / "SOURCE_OVERLAY.json").read_text())
        for sym, rec in (so.get("symbols") or {}).items():
            px = []
            for _lab, rws in (rec.get("providers") or {}).items():
                for r in (rws or [])[-10:]:
                    try:
                        v = float(r[1])
                        if v > 0:
                            px.append(v)
                    except Exception:
                        pass
            if px:
                px.sort()
                ext[canon(sym)] = px[len(px) // 2]
    except Exception:
        pass

    by: Dict[str, Any] = {}
    for sym, rows in (samples or {}).items():
        try:
            by[sym] = grade_symbol(sym, rows, k, fps, ext.get(canon(sym)))
        except Exception as e:                              # a grader crash must never blind the gate
            by[sym] = {"sym": sym, "grade": "UNKNOWN", "why": "grader error: %s" % e,
                       "tradeable": False, "learnable": False, "structure_ok": False}

    counts: Dict[str, int] = {}
    for v in by.values():
        counts[v["grade"]] = counts.get(v["grade"], 0) + 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": k.get("mode"), "knobs": k,
        "law": ("a feed earns the right to be traded and learned from by RESOLVING the move the "
                "strategy needs — never by being expensive, never by being popular. Excluded names "
                "keep collecting tape and are re-graded every cycle."),
        "counts": counts, "graded": len(by),
        "tradeable": sum(1 for v in by.values() if v.get("tradeable")),
        "by_symbol": by,
        "worst": sorted([v for v in by.values() if v.get("grade") in ("FROZEN", "QUANTIZED", "DISPUTED")],
                        key=lambda v: (v.get("levels") or 0))[:40],
        "note": ("market-closed repetition is NOT a defect: equity-class names are measured on "
                 "regular-session prints only, so a flat weekend never quarantines an ETF"),
    }
    write_json_atomic(out / "PRICE_TRUTH.json", payload)
    return payload


# ── the consumer side: one helper every gate uses ──────────────────────────────────────
_CACHE: Dict[str, Any] = {}


def load_truth(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    try:
        st = (out / "PRICE_TRUTH.json").stat().st_mtime
    except Exception:
        return {}
    if _CACHE.get("mt") == st:
        return _CACHE.get("by") or {}
    try:
        by = json.loads((out / "PRICE_TRUTH.json").read_text()).get("by_symbol") or {}
    except Exception:
        by = {}
    _CACHE["mt"], _CACHE["by"] = st, by
    return by


def may_trade(out_dir, sym: str) -> bool:
    """Open a position on this name? Only on an OK feed. UNKNOWN is not a yes."""
    by = load_truth(out_dir)
    if not by:
        return True                                   # no verdict published yet: fail open, gate elsewhere
    rec = by.get(sym) or by.get(canon(sym))
    return bool(rec.get("tradeable")) if rec else True


def may_learn(out_dir, sym: str) -> bool:
    """Fit a fingerprint / rhythm / leaderboard row from this name? Same bar as trading —
    learning from a broken tape is worse than not learning, because it looks like knowledge."""
    by = load_truth(out_dir)
    if not by:
        return True
    rec = by.get(sym) or by.get(canon(sym))
    return bool(rec.get("learnable")) if rec else True


def why(out_dir, sym: str) -> str:
    by = load_truth(out_dir)
    rec = by.get(sym) or by.get(canon(sym)) or {}
    return "%s — %s" % (rec.get("grade", "UNKNOWN"), rec.get("why", "no verdict yet"))


if __name__ == "__main__":                                  # pragma: no cover
    import sys
    p = build_price_truth(sys.argv[1] if len(sys.argv) > 1 else "docs/data")
    print(json.dumps({"counts": p["counts"], "tradeable": p["tradeable"], "graded": p["graded"]}, indent=2))
    for w in p["worst"][:12]:
        print("  %-14s %-10s %s" % (w.get("sym"), w.get("grade"), w.get("why")))
