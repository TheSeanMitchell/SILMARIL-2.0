"""ladder.headlines — THE HEADLINE TEST. Watch-only. It can never place, change or block a trade.

The question it answers, with numbers, over about a year:
  1. DIRECTION — does a week of headline tone call the NEXT week's direction?
  2. WARNING   — does a surge in headline volume come before an unusually big move?

How it stays honest:
  * Its rules are frozen in HEADLINE_RULES below, with their own fingerprint, written in
    REGISTRATION_HEADLINES.md before the first headline was scored. The trading rules
    (ladder/config.py) are not touched, and this module imports nothing that trades.
  * No lookahead: every call is graded from the first market close that happens AFTER the
    headlines were read (the same as a person reading the news tonight and acting at
    tomorrow's close), over the next 5 trading days, against T-bills.
  * One call per category per week, so the graded weeks do not overlap.
  * A headline is counted once, on the day it is first seen.
  * If the feed fails, the day is recorded as missing and the week shows its coverage.
    A failure here never stops the trading run.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

HEADLINE_RULES = {
    "name": "SILMARIL 9 - HEADLINE TEST (watch-only)",
    "registered_on": "2026-11-08",
    "source": "Google News RSS search, en-US, last 24 hours, one query per category",
    "queries": {
        "crypto": 'bitcoin OR ethereum OR crypto',
        "stock": '"stock market" OR Nasdaq OR "S&P 500" OR "Wall Street"',
        "metal": '"gold price" OR "silver price" OR "gold prices"',
        "energy": '"oil price" OR "oil prices" OR crude OR OPEC OR "Middle East"',
    },
    "words_up": ["surge", "surges", "surged", "soar", "soars", "soared", "rally", "rallies",
                 "rallied", "record", "jump", "jumps", "jumped", "gain", "gains", "gained",
                 "rise", "rises", "rising", "rose", "climb", "climbs", "climbed", "higher",
                 "boom", "bullish", "rebound", "rebounds", "strong", "beat", "beats", "upgrade"],
    "words_down": ["plunge", "plunges", "plunged", "crash", "crashes", "crashed", "fall",
                   "falls", "falling", "fell", "drop", "drops", "dropped", "slump", "slumps",
                   "tumble", "tumbles", "tumbled", "sink", "sinks", "sank", "lower", "loss",
                   "losses", "bearish", "selloff", "sell-off", "fear", "fears", "weak", "slide",
                   "slides", "slid", "miss", "misses", "downgrade", "rout"],
    # oil reacts to supply news the other way round from most assets
    "energy_words_up": ["sanctions", "conflict", "war", "attack", "attacks", "escalation",
                        "escalating", "disruption", "outage", "blockade", "tensions", "cuts"],
    "energy_words_down": ["ceasefire", "truce", "peace", "glut", "oversupply", "surplus"],
    "headline_score": "+1 if it has an up word and no down word, -1 the reverse, else 0",
    "week": "Monday to Sunday (UTC). The call is made on the first run of the new week.",
    "tone": "(up headlines - down headlines) / all headlines in the week",
    "call_threshold": 0.10,      # tone >= +0.10 calls UP, <= -0.10 calls DOWN, else no call
    "min_days_covered": 4,       # a week with fewer than 4 days of headlines makes no call
    "horizon_closes": 5,
    "grade": "category basket (50/50 of its two assets) return over the next 5 closes, "
             "minus T-bills, from the first close after the headlines were read",
    "surge": "week volume >= 2 x the median of the previous 8 weeks (needs 4+ prior weeks)",
    "warning_grade": "next-5-close |basket move| divided by the median |5-close move| of the "
                     "prior 252 closes",
    "pass_direction": "100+ graded calls, hit rate z >= 2.5 versus a coin flip, AND the average "
                      "signed excess return >= +0.5% per call (enough to pay for trading it)",
    "kill_direction": "100+ graded calls and z <= 0.5",
    "pass_warning": "30+ surges, the next week's move averages >= 1.5x normal, t >= 2.5",
    "kill_warning": "30+ surges and the next week's move is not bigger than normal on average",
    "if_passed": "a conversation about a re-registration. Never an automatic trade.",
}

STORE = "ladder_headlines.json"
CATS = ["crypto", "stock", "metal", "energy"]


def rules_hash() -> str:
    blob = json.dumps(HEADLINE_RULES, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


# ── scoring ───────────────────────────────────────────────────────────────────────

_WORD = re.compile(r"[a-z][a-z\-']*")


def clean_title(t: str) -> str:
    """Google appends ' - Publisher'; drop it so the same story from two outlets matches."""
    t = (t or "").strip()
    if " - " in t:
        t = t.rsplit(" - ", 1)[0]
    return t


def score_title(title: str, cat: str) -> int:
    words = set(_WORD.findall(title.lower()))
    up = set(HEADLINE_RULES["words_up"])
    down = set(HEADLINE_RULES["words_down"])
    if cat == "energy":
        up |= set(HEADLINE_RULES["energy_words_up"])
        down |= set(HEADLINE_RULES["energy_words_down"])
    u, d = bool(words & up), bool(words & down)
    return 1 if (u and not d) else (-1 if (d and not u) else 0)


def title_key(cat: str, title: str) -> str:
    norm = re.sub(r"[^a-z0-9 ]", "", title.lower())
    norm = re.sub(r"\s+", " ", norm).strip()
    return hashlib.sha1((cat + "|" + norm).encode("utf-8")).hexdigest()[:16]


# ── fetching ──────────────────────────────────────────────────────────────────────

def fetch(cat: str) -> Optional[List[str]]:
    """Titles from the last 24 hours, or None if the feed failed."""
    try:
        import requests
        import xml.etree.ElementTree as ET
        q = HEADLINE_RULES["queries"][cat] + " when:1d"
        url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(q)
               + "&hl=en-US&gl=US&ceid=US:en")
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (silmaril-ladder headline test)"},
                         timeout=20)
        if r.status_code != 200:
            return None
        root = ET.fromstring(r.content)
        return [clean_title(it.findtext("title") or "") for it in root.findall("./channel/item")]
    except Exception:
        return None


# ── the store ─────────────────────────────────────────────────────────────────────

def load(data_dir: Path) -> Dict:
    try:
        st = json.loads((Path(data_dir) / STORE).read_text(encoding="utf-8"))
    except Exception:
        st = {}
    st.setdefault("rules_hash", rules_hash())
    for k, v in (("days", []), ("weeks", []), ("seen", {}), ("recent", {})):
        st.setdefault(k, v)
    return st


def save(data_dir: Path, st: Dict) -> None:
    p = Path(data_dir) / STORE
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(st, indent=1), encoding="utf-8")
    tmp.replace(p)


def record_day(st: Dict, now: datetime, fetched: Dict[str, Optional[List[str]]]) -> None:
    """Count each headline once, on the day it is first seen."""
    day = now.strftime("%Y-%m-%d")
    row = {"date": day, "read_at": now.isoformat(), "cats": {}}
    for cat in CATS:
        titles = fetched.get(cat)
        if titles is None:
            row["cats"][cat] = {"ok": False}
            continue
        new, up, down, sample = 0, 0, 0, []
        for t in titles:
            if not t:
                continue
            k = title_key(cat, t)
            if k in st["seen"]:
                continue
            st["seen"][k] = day
            s = score_title(t, cat)
            new += 1
            up += s > 0
            down += s < 0
            if s != 0 and len(sample) < 6:
                sample.append({"title": t[:160], "score": s})
        row["cats"][cat] = {"ok": True, "n": new, "up": up, "down": down}
        if sample:
            st["recent"][cat] = {"date": day, "headlines": sample}
    if any(d["date"] == day for d in st["days"]):
        st["days"] = _merge_day(st["days"], row)
    else:
        st["days"].append(row)
    cutoff = (now - timedelta(days=21)).strftime("%Y-%m-%d")
    st["seen"] = {k: v for k, v in st["seen"].items() if v >= cutoff}
    st["days"] = st["days"][-400:]


def _merge_day(days: List[Dict], row: Dict) -> List[Dict]:
    """A second run on the same day adds only the headlines it had not seen yet."""
    out = []
    for d in days:
        if d["date"] != row["date"]:
            out.append(d)
            continue
        merged = dict(d)
        for cat, c in row["cats"].items():
            old = d["cats"].get(cat, {"ok": False})
            if not c.get("ok"):
                merged["cats"][cat] = old
            elif not old.get("ok"):
                merged["cats"][cat] = c
            else:
                merged["cats"][cat] = {"ok": True, "n": old["n"] + c["n"],
                                       "up": old["up"] + c["up"], "down": old["down"] + c["down"]}
        out.append(merged)
    return out


# ── weekly calls and grading (prices come from the ladder's tape) ───────────────

def _week_id(d: datetime) -> str:
    y, w, _ = d.isocalendar()
    return "%d-W%02d" % (y, w)


def first_close_after_read(dates: List[str], read_at: datetime) -> Optional[int]:
    """The first close that happens after the headlines were read. ETFs close by 21:00 UTC,
    crypto at 24:00 UTC: a read before 20:00 UTC can still act at that day's close."""
    day = read_at.strftime("%Y-%m-%d")
    if read_at.hour >= 20:
        day = (read_at + timedelta(days=1)).strftime("%Y-%m-%d")
    for i, d in enumerate(dates):
        if d >= day:
            return i
    return None


def make_weekly_calls(st: Dict, now: datetime, cats_assets: Dict[str, List[str]]) -> None:
    """On the first run of a new ISO week, call each category from the previous 7 days."""
    wk = _week_id(now)
    if any(w["week"] == wk for w in st["weeks"]):
        return
    start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")
    window = [d for d in st["days"] if start <= d["date"] < today]
    for cat in CATS:
        prior = [w for w in st["weeks"] if w["cat"] == cat][-8:]
        ok_days = [d["cats"][cat] for d in window if d["cats"].get(cat, {}).get("ok")]
        n = sum(c["n"] for c in ok_days)
        up = sum(c["up"] for c in ok_days)
        down = sum(c["down"] for c in ok_days)
        tone = (up - down) / n if n else 0.0
        call = None
        if len(ok_days) >= HEADLINE_RULES["min_days_covered"] and n:
            if tone >= HEADLINE_RULES["call_threshold"]:
                call = "UP"
            elif tone <= -HEADLINE_RULES["call_threshold"]:
                call = "DOWN"
        vols = [w["n"] for w in prior if w["cat"] == cat and w.get("days_covered", 0) >= HEADLINE_RULES["min_days_covered"]]
        surge = None
        if len(vols) >= 4 and len(ok_days) >= HEADLINE_RULES["min_days_covered"]:
            med = sorted(vols)[len(vols) // 2]
            surge = bool(med > 0 and n >= 2 * med)
        st["weeks"].append({"week": wk, "cat": cat, "read_at": now.isoformat(),
                            "days_covered": len(ok_days), "n": n, "up": up, "down": down,
                            "tone": round(tone, 4), "call": call, "surge": surge,
                            "assets": cats_assets[cat], "graded": False})


def grade(st: Dict, dates: List[str], px: Dict[str, List[Optional[float]]], cash_sym: str) -> None:
    h = HEADLINE_RULES["horizon_closes"]
    for w in st["weeks"]:
        if w.get("graded") or (w["call"] is None and not w.get("surge")):
            continue
        b = first_close_after_read(dates, datetime.fromisoformat(w["read_at"]))
        if b is None or b + h > len(dates) - 1:
            continue
        a1, a2 = w["assets"]
        try:
            ret = 0.5 * (px[a1][b + h] / px[a1][b] - 1) + 0.5 * (px[a2][b + h] / px[a2][b] - 1)
            rf = px[cash_sym][b + h] / px[cash_sym][b] - 1
        except (TypeError, ZeroDivisionError):
            continue
        w["base_date"], w["end_date"] = dates[b], dates[b + h]
        w["excess_pct"] = round(100 * (ret - rf), 3)
        if w["call"]:
            sign = 1 if w["call"] == "UP" else -1
            w["signed_pct"] = round(sign * 100 * (ret - rf), 3)
            w["hit"] = w["signed_pct"] > 0
        if w.get("surge"):
            moves = []
            for k in range(max(h, b - 252), b - h + 1):
                try:
                    m = 0.5 * (px[a1][k + h] / px[a1][k] - 1) + 0.5 * (px[a2][k + h] / px[a2][k] - 1)
                    moves.append(abs(m))
                except (TypeError, ZeroDivisionError):
                    pass
            typical = sorted(moves)[len(moves) // 2] if moves else None
            if typical:
                w["move_ratio"] = round(abs(ret) / typical, 3)
        w["graded"] = True


def verdicts(st: Dict) -> Dict:
    calls = [w for w in st["weeks"] if w.get("graded") and w.get("call")]
    n = len(calls)
    hits = sum(1 for w in calls if w.get("hit"))
    z = (hits - 0.5 * n) / math.sqrt(0.25 * n) if n else None
    avg = sum(w["signed_pct"] for w in calls) / n if n else None
    d_status = "COLLECTING"
    if n >= 100 and z is not None:
        if z >= 2.5 and (avg or 0) >= 0.5:
            d_status = "PASSED"
        elif z <= 0.5:
            d_status = "KILLED"
    surges = [w for w in st["weeks"] if w.get("graded") and w.get("surge") and w.get("move_ratio")]
    m = len(surges)
    logs = [math.log(max(w["move_ratio"], 1e-6)) for w in surges]
    mean_ratio = sum(w["move_ratio"] for w in surges) / m if m else None
    t = None
    if m >= 3:
        mu = sum(logs) / m
        sd = math.sqrt(sum((x - mu) ** 2 for x in logs) / (m - 1))
        t = mu / (sd / math.sqrt(m)) if sd > 0 else None
    w_status = "COLLECTING"
    if m >= 30 and t is not None:
        if (mean_ratio or 0) >= 1.5 and t >= 2.5:
            w_status = "PASSED"
        elif sum(logs) / m <= 0:
            w_status = "KILLED"
    return {"direction": {"status": d_status, "calls": n, "need": 100, "hits": hits,
                          "hit_rate_pct": round(100 * hits / n, 1) if n else None,
                          "z": round(z, 2) if z is not None else None,
                          "avg_signed_pct": round(avg, 3) if avg is not None else None},
            "warning": {"status": w_status, "surges": m, "need": 30,
                        "avg_move_ratio": round(mean_ratio, 2) if mean_ratio else None,
                        "t": round(t, 2) if t is not None else None}}


# ── the daily pass ────────────────────────────────────────────────────────────────

def run(data_dir: Path, tape, cats_assets: Dict[str, List[str]], cash_sym: str,
        fetch_news: bool = True, now: Optional[datetime] = None) -> Dict:
    now = now or datetime.now(timezone.utc)
    st = load(data_dir)
    if st.get("rules_hash") != rules_hash():
        st["rules_changed"] = {"stored": st.get("rules_hash"), "code": rules_hash(),
                               "noticed_at": now.isoformat()}
    if fetch_news:
        record_day(st, now, {c: fetch(c) for c in CATS})
    make_weekly_calls(st, now, cats_assets)
    grade(st, tape.dates, tape.px, cash_sym)
    st["verdicts"] = verdicts(st)
    st["generated_at"] = now.isoformat()
    save(data_dir, st)
    last_week = {}
    for w in st["weeks"]:
        last_week[w["cat"]] = w
    days_with_data = sum(1 for d in st["days"] if any(c.get("ok") for c in d["cats"].values()))
    return {"rules_hash": rules_hash(), "verdicts": st["verdicts"], "latest_week": last_week,
            "recent": st["recent"], "days_recorded": days_with_data,
            "first_day": st["days"][0]["date"] if st["days"] else None,
            "graded_calls": [w for w in st["weeks"] if w.get("graded") and w.get("call")][-8:],
            "rules_changed": st.get("rules_changed")}
