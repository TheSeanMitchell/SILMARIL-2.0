"""
silmaril.execution.authority_events — AUTHORITY EVENT ENGINE (Alpha 2.13).

When an authority moves a market — Trump names a company, Elon tweets, the Fed
signals, Nvidia announces — the alpha is in the CASCADE of beneficiaries, not just
the named ticker:

    Trump mentions Intel
      → INTC (primary)
      → TSM, AMAT, LRCX, KLAC (foundry / chip-equipment suppliers, secondary)
      → semiconductors (sector)
      → SOXX, SMH (ETFs)

This module is that map. `RELATIONSHIP_GRAPH` encodes authority → primary →
secondary → sector → ETF for the entities that actually move tickers, and
`map_beneficiaries()` walks the cascade with a sentiment sign. `scan_headlines()`
detects authority mentions in headline text and returns the mapped beneficiaries.

Honest scope: the MAP and the cascade are built and testable now. The DETECTION
needs live headline TEXT (NewsAPI / Marketaux are wired as feeds, but the headline
strings must be passed in). Until that's connected, `build_authority_events`
runs fail-safe on whatever headlines it can find and otherwise emits an empty,
clearly-labelled result. No fabricated events. And — consistent with the gameplan
— this is intelligence/context: it does NOT move capital until a measured forward
edge justifies it (the lifecycle/leaderboard discipline applies here too).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# authority entity -> cascade. Curated for entities that demonstrably move tickers.
RELATIONSHIP_GRAPH: Dict[str, Dict[str, Any]] = {
    "trump": {
        "aliases": ["trump", "white house", "potus"],
        "themes": {
            "intel|semiconductor|chips act|foundry": {
                "primary": ["INTC"], "secondary": ["TSM", "AMAT", "LRCX", "KLAC", "ASML"],
                "sector": "semiconductors", "etfs": ["SOXX", "SMH"]},
            "tariff|china|trade": {
                "primary": [], "secondary": ["CAT", "DE", "BA"],
                "sector": "industrials", "etfs": ["XLI"]},
            "oil|drill|energy": {
                "primary": ["XOM", "CVX"], "secondary": ["OXY", "SLB"],
                "sector": "energy", "etfs": ["XLE"]},
            "crypto|bitcoin": {
                "primary": ["COIN", "MSTR"], "secondary": ["MARA", "RIOT"],
                "sector": "crypto", "etfs": ["BITO"]},
        },
    },
    "elon": {
        "aliases": ["elon", "musk", "tesla ceo"],
        "themes": {
            "tesla|ev|robotaxi|fsd": {
                "primary": ["TSLA"], "secondary": ["RIVN", "LCID"],
                "sector": "ev", "etfs": ["DRIV"]},
            "doge|dogecoin": {
                "primary": ["DOGE-USD"], "secondary": [],
                "sector": "crypto", "etfs": []},
            "spacex|starlink|space": {
                "primary": [], "secondary": ["RKLB", "ASTS"],
                "sector": "space", "etfs": ["UFO"]},
        },
    },
    "fed": {
        "aliases": ["fed", "powell", "fomc", "federal reserve", "rate cut", "rate hike"],
        "themes": {
            "cut|dovish|ease": {
                "primary": [], "secondary": ["XLF", "KRE"],
                "sector": "rates-sensitive", "etfs": ["TLT", "IWM"]},
            "hike|hawkish|tighten": {
                "primary": [], "secondary": [],
                "sector": "defensive", "etfs": ["XLU", "UUP"]},
        },
    },
    "nvidia": {
        "aliases": ["nvidia", "jensen huang", "nvda"],
        "themes": {
            ".*": {
                "primary": ["NVDA"], "secondary": ["TSM", "SK", "MU", "VRT", "SMCI"],
                "sector": "ai-infrastructure", "etfs": ["SMH", "SOXX"]},
        },
    },
}


def _sentiment(text: str) -> int:
    t = text.lower()
    pos = sum(w in t for w in ("surge", "win", "approve", "boost", "deal", "cut",
                               "beat", "soar", "rally", "back", "support"))
    neg = sum(w in t for w in ("ban", "tariff", "probe", "sue", "drop", "hike",
                               "warn", "cut off", "sanction", "reject", "crash"))
    return 1 if pos > neg else -1 if neg > pos else 0


def map_beneficiaries(headline: str) -> List[Dict[str, Any]]:
    """Detect authority entities in a headline and return the beneficiary cascade."""
    t = headline.lower()
    hits = []
    for ent, spec in RELATIONSHIP_GRAPH.items():
        if not any(re.search(r"\b" + re.escape(a) + r"\b", t) for a in spec["aliases"]):
            continue
        for theme_pat, casc in spec["themes"].items():
            if re.search(theme_pat, t):
                hits.append({
                    "authority": ent,
                    "theme": theme_pat.split("|")[0],
                    "sentiment": _sentiment(headline),
                    "primary": casc["primary"],
                    "secondary": casc["secondary"],
                    "sector": casc["sector"],
                    "etfs": casc["etfs"],
                    "headline": headline[:140],
                })
                break
    return hits


def scan_headlines(headlines: List[str]) -> List[Dict[str, Any]]:
    out = []
    for h in headlines:
        if isinstance(h, str):
            out.extend(map_beneficiaries(h))
    return out


def _gather_headlines(out: Path) -> List[str]:
    """Best-effort: pull any headline-like strings the system already has on disk.
    Returns [] if none — never fabricates."""
    heads: List[str] = []
    for fn in ("news_intelligence.json", "catalysts.json", "authority_catalyst.json"):
        try:
            d = json.loads((out / fn).read_text())
        except Exception:
            continue

        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("note", "headline", "title", "thesis") and isinstance(v, str) and len(v) > 12:
                        heads.append(v)
                    else:
                        walk(v)
            elif isinstance(o, list):
                for x in o[:200]:
                    walk(x)
        walk(d)
    return heads[:400]


# search terms per authority entity for the live RSS feed (nuzunews pattern:
# feedparser on Google News RSS — free, no key, real headline text)
_RSS_QUERIES = [
    "Trump", "Elon Musk", "Nvidia", "OpenAI", "Federal Reserve",
    "US Treasury", "Congress stocks", "Jensen Huang", "Intel chips",
]


def fetch_authority_headlines(queries: List[str] = None, per_query: int = 12) -> List[str]:
    """Live headlines via Google News RSS (needs network — GitHub Actions has it,
    this build box does not). Fully fail-safe: returns [] on any error."""
    try:
        import feedparser
        import urllib.parse
    except Exception:
        return []
    heads: List[str] = []
    for q in (queries or _RSS_QUERIES):
        try:
            url = ("https://news.google.com/rss/search?q="
                   + urllib.parse.quote(q) + "&hl=en-US&gl=US&ceid=US:en")
            feed = feedparser.parse(url)
            for e in feed.entries[:per_query]:
                t = getattr(e, "title", "")
                if t and len(t) > 12:
                    heads.append(t)
        except Exception:
            continue
    # de-dup preserving order
    seen, out = set(), []
    for h in heads:
        if h not in seen:
            seen.add(h); out.append(h)
    return out


def build_authority_events(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    live = fetch_authority_headlines()          # Google News RSS (live)
    disk = _gather_headlines(out)               # whatever is already on disk
    heads = live + [h for h in disk if h not in set(live)]
    events = scan_headlines(heads)

    # record beneficiaries + timestamp so forward-return EVIDENCE accumulates over
    # cron runs (you cannot measure the forward return of an event detected now)
    now = datetime.now(timezone.utc).isoformat()
    try:
        ledger = json.loads((out / "authority_ledger.json").read_text())
    except Exception:
        ledger = {"events": []}
    for e in events:
        ledger["events"].append({"at": now, "authority": e["authority"],
                                 "theme": e["theme"], "sentiment": e["sentiment"],
                                 "beneficiaries": (e["primary"] + e["secondary"]),
                                 "headline": e["headline"]})
    ledger["events"] = ledger["events"][-1000:]
    try:
        (out / "authority_ledger.json").write_text(json.dumps(ledger, indent=2))
    except Exception:
        pass

    payload = {
        "generated_at": now,
        "source": "google_news_rss (live)" if live else "disk_fallback",
        "headlines_scanned": len(heads),
        "live_headlines": len(live),
        "events_detected": len(events),
        "events": events[:50],
        "ledger_size": len(ledger["events"]),
        "graph_entities": list(RELATIONSHIP_GRAPH.keys()),
        "status": ("LIVE detection active (Google News RSS)" if live and events else
                   "live feed reachable, no authority/theme matches this run" if live else
                   "framework ready — RSS feed not reachable from here; runs on cron"),
        "note": ("Beneficiary cascade fires on live headlines via feedparser + "
                 "Google News RSS (the nuzunews pattern). Events are logged to "
                 "authority_ledger.json so forward-return evidence builds over time. "
                 "Intelligence/context only — no capital until forward edge is proven."),
    }
    try:
        (out / "authority_events.json").write_text(json.dumps(payload, indent=2))
    except Exception:
        pass
    return payload


if __name__ == "__main__":
    import sys
    # prove the cascade works with synthetic headlines (detection is the easy part)
    demo = ["Trump says Intel will get major chips act funding",
            "Elon Musk tweets about Dogecoin again",
            "Fed signals rate cut at next FOMC meeting",
            "Nvidia unveils next-gen AI chips"]
    print("CASCADE DEMO (synthetic headlines):")
    for h in demo:
        for e in map_beneficiaries(h):
            print(f"  [{e['authority']}/{e['theme']}] {e['primary']} -> {e['secondary']} -> {e['etfs']} (sent {e['sentiment']:+d})")
    print()
    print(json.dumps(build_authority_events(sys.argv[1] if len(sys.argv) > 1 else "docs/data"), indent=2)[:400])
