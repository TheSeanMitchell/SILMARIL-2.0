"""
silmaril.execution.authority_catalyst — the reviewer's addition.

Not all news is equal. "positive article" is generic sentiment. But:
    "TRUMP mentioned INTC"
    "NVIDIA partnership announced"
    "ELON tweeted about <company>"
    "Fed signals rate cut"
are AUTHORITY events — a named, market-moving actor acting on a specific
name. These behave differently (sharper, faster moves) than ambient news and
deserve their own detection so the engine can weight them.

This scans each name's headlines for authority entities and tags the name
with an authority-catalyst score + which authority fired. Deterministic
keyword/entity matching — no LLM, fits the project's no-synthetic-analyst
rule. Writes docs/data/authority_catalyst.json AND returns a per-ticker map
the router can fold into ranking.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

VERSION = "authority-catalyst-1.0"

# authority entities → weight (how hard they move markets) and class.
# matched case-insensitively as whole words/phrases in headlines.
AUTHORITIES = {
    # people
    "trump": (1.00, "head_of_state"),
    "president trump": (1.00, "head_of_state"),
    "elon musk": (0.95, "elon"),
    "elon": (0.85, "elon"),
    "musk": (0.80, "elon"),
    "powell": (0.90, "fed"),
    "jerome powell": (0.90, "fed"),
    "federal reserve": (0.90, "fed"),
    "the fed": (0.80, "fed"),
    "fed signals": (0.85, "fed"),
    "rate cut": (0.75, "fed"),
    "rate hike": (0.75, "fed"),
    # mega-cap companies (partnership/endorsement moves smaller names)
    "nvidia": (0.90, "megacap_partner"),
    "microsoft": (0.80, "megacap_partner"),
    "amazon": (0.78, "megacap_partner"),
    "apple": (0.80, "megacap_partner"),
    "google": (0.78, "megacap_partner"),
    "meta": (0.75, "megacap_partner"),
    "openai": (0.85, "megacap_partner"),
    "tesla": (0.78, "megacap_partner"),
    # government / regulatory
    "white house": (0.85, "government"),
    "sec ": (0.75, "regulator"),
    "department of": (0.70, "government"),
    "executive order": (0.85, "government"),
    "tariff": (0.78, "government"),
    "sanction": (0.75, "government"),
    # corporate-action authority signals
    "partnership": (0.65, "partnership"),
    "acquisition": (0.70, "m_and_a"),
    "acquires": (0.70, "m_and_a"),
    "merger": (0.68, "m_and_a"),
    "buyout": (0.68, "m_and_a"),
    # analyst authority
    "upgrade": (0.60, "analyst"),
    "downgrade": (0.60, "analyst"),
    "price target": (0.55, "analyst"),
    "initiated": (0.50, "analyst"),
    "reiterated": (0.45, "analyst"),
}

# compile word-boundary patterns once
_PATTERNS = [(re.compile(r"\b" + re.escape(k) + r"\b", re.I), k, w, c)
             for k, (w, c) in AUTHORITIES.items()]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def _dump(path: Path, obj):
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


def _headline_text(h):
    if isinstance(h, dict):
        return str(h.get("title") or h.get("headline") or "")
    return str(h)


def detect_authority(headlines: List[Any]) -> Optional[Dict[str, Any]]:
    """Return the strongest authority catalyst found across a name's
    headlines, or None."""
    best_w = 0.0
    hits = []
    for h in (headlines or []):
        text = _headline_text(h)
        if not text:
            continue
        for pat, key, w, klass in _PATTERNS:
            if pat.search(text):
                hits.append({"authority": key, "class": klass, "weight": w,
                             "headline": text[:160]})
                if w > best_w:
                    best_w = w
    if not hits:
        return None
    # dedupe by authority, keep strongest first
    by_auth = {}
    for h in hits:
        a = h["authority"]
        if a not in by_auth or h["weight"] > by_auth[a]["weight"]:
            by_auth[a] = h
    ranked = sorted(by_auth.values(), key=lambda x: x["weight"], reverse=True)
    return {
        "authority_score": round(best_w, 3),
        "top_class": ranked[0]["class"],
        "hits": ranked[:5],
    }


def build_authority_catalyst(out_dir, debates=None) -> Dict[str, Any]:
    """Scan all debates' headlines for authority events. Writes the file and
    returns {ticker: {authority_score, top_class, hits}} for the router."""
    out = Path(out_dir)
    if debates is None:
        debates = (_load(out / "signals.json", {}) or {}).get("debates") or []

    tagged = {}
    for d in debates:
        t = d.get("ticker")
        det = detect_authority(d.get("recent_headlines"))
        if det:
            tagged[str(t).upper()] = det

    # rank the strongest authority catalysts right now
    ranked = sorted(
        ({"ticker": k, **v} for k, v in tagged.items()),
        key=lambda x: x["authority_score"], reverse=True)

    from collections import Counter
    class_hist = dict(Counter(v["top_class"] for v in tagged.values()))

    payload = {
        "version": VERSION,
        "generated_at": _now(),
        "summary": {
            "names_with_authority": len(tagged),
            "by_class": class_hist,
        },
        "ranked": ranked[:40],
        "note": ("Authority catalysts = a named market-moving actor (Trump, "
                 "Elon, Fed, a mega-cap partner, a regulator, an analyst) "
                 "acting on a specific name. These move differently than "
                 "ambient sentiment. authority_score (0-1) can boost a name's "
                 "ranking weight; top_class says which kind of authority."),
    }
    _dump(out / "authority_catalyst.json", payload)
    return tagged


if __name__ == "__main__":  # pragma: no cover
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/data")
    tagged = build_authority_catalyst(out)
    print(f"{len(tagged)} names with authority catalysts")
    for k, v in list(tagged.items())[:10]:
        print(f"  {k}: {v['authority_score']} ({v['top_class']})")
