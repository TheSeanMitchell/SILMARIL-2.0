"""
NEWS TRIAL — the 90-day observe-mode evidence ledger. Every cycle it tags fresh headlines with the tickers
in OUR universe + a naive buy/sell stance, records the price at log time, and (on later cycles) scores each
entry against what price ACTUALLY did next. It influences nothing — mode lives in FEATURE_GATES.json and
stays 'observe' until the hit-rate proves the signal is edge, not noise. The earlier informal news attempts
FAILED; this restarts the question with a real scoreboard.
"""
import json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

BUY_WORDS = ("surge", "soar", "rally", "beat", "record", "upgrade", "buy", "bull", "breakout", "approve", "partnership", "adopt")
SELL_WORDS = ("plunge", "crash", "miss", "downgrade", "sell", "bear", "lawsuit", "hack", "ban", "fraud", "bankrupt", "halt")

def _now(): return datetime.now(timezone.utc).isoformat()

def _stance(title: str) -> str:
    t = (title or "").lower()
    b = sum(w in t for w in BUY_WORDS); s = sum(w in t for w in SELL_WORDS)
    return "buy" if b > s else "sell" if s > b else "neutral"

def build_news_trial(out_dir, horizon_min: int = 240) -> Dict[str, Any]:
    out = Path(out_dir)
    ledp = out / "NEWS_TRIAL.json"
    try:
        led = json.loads(ledp.read_text())
        if not isinstance(led, list):
            led = []
    except Exception:
        led = []
    # current prices for tagging + scoring
    px = {}
    try:
        S = json.loads((out / "price_samples.json").read_text()).get("samples", {})
        for sym, rows in S.items():
            for t, p in reversed(rows):
                if p and p > 0 and "T00:00:00" not in t:
                    px[sym] = float(p); break
    except Exception:
        S = {}
    # 1) score matured entries that lack an outcome
    nowt = datetime.now(timezone.utc)
    scored = 0
    for e in led:
        if e.get("outcome") is not None or e.get("sym") not in px:
            continue
        try:
            age = (nowt - datetime.fromisoformat(e["t"])).total_seconds() / 60.0
        except Exception:
            continue
        if age >= horizon_min and e.get("px_at_log"):
            mv = px[e["sym"]] / e["px_at_log"] - 1.0
            e["px_after"] = px[e["sym"]]
            e["move_pct"] = round(mv * 100, 3)
            e["outcome"] = ("hit" if (e["stance"] == "buy" and mv > 0) or (e["stance"] == "sell" and mv < 0)
                            else "miss" if e["stance"] in ("buy", "sell") else "n/a")
            scored += 1
    # 2) log fresh headlines that name a universe ticker
    src = {}
    for fn in ("news_intelligence.json", "news_history.json"):
        try:
            src = json.loads((out / fn).read_text()); break
        except Exception:
            continue
    items = src.get("items") or src.get("articles") or src.get("events") or []
    # news_intelligence.json shape: {'stocks': [...], 'other': [...]} — flatten those buckets too
    for bucket in ("stocks", "other", "crypto", "events"):
        v = src.get(bucket)
        if isinstance(v, list):
            items = items + [x for x in v if isinstance(x, dict)]
        elif isinstance(v, dict):
            for vv in v.values():
                if isinstance(vv, list):
                    items = items + [x for x in vv if isinstance(x, dict)]
    seen = {(e.get("sym"), e.get("title")) for e in led}
    added = 0
    for it in items[:400]:
        title = it.get("title") or it.get("headline") or ""
        blob = " ".join(str(it.get(k, "")) for k in ("title", "headline", "summary", "tickers", "symbols"))
        for sym in px.keys():
            base = sym.split("-")[0]
            if len(base) < 2:
                continue
            if re.search(r"\b" + re.escape(base) + r"\b", blob, re.I):
                key = (sym, title)
                if key in seen:
                    continue
                led.append({"t": _now(), "sym": sym, "title": title[:160], "stance": _stance(title),
                            "px_at_log": px.get(sym), "outcome": None})
                seen.add(key); added += 1
                break
    led = led[-2000:]
    ledp.write_text(json.dumps(led, indent=1))
    done = [e for e in led if e.get("outcome") in ("hit", "miss")]
    hits = sum(1 for e in done if e["outcome"] == "hit")
    payload = {"generated_at": _now(), "entries": len(led), "scored": len(done),
               "hit_rate_pct": round(hits / len(done) * 100, 1) if done else None,
               "added_this_cycle": added, "scored_this_cycle": scored,
               "mode": "observe — influences nothing until FEATURE_GATES promotes it on real evidence"}
    (out / "NEWS_TRIAL_STATUS.json").write_text(json.dumps(payload, indent=1))
    return payload
