"""steward.form4 — SEC EDGAR Form 4 filing-activity score.

Ported from silmaril/ingestion/form4.py (the one module of the 348 that earned a
seat in the replacement). HONESTY NOTE carried forward from the original and now
stated louder: this scores the COUNT of Form 4 filings referencing a ticker via
EDGAR full-text search — it does NOT parse transaction codes, so it cannot tell
an open-market buy from a sale or an option exercise. It is a cheap proxy on
trial. If the shadow hypothesis passes its registered bar, the reward is building
the real XML parser; until then this earns nothing but a grade.

SEC requires a User-Agent with contact info: set SEC_USER_AGENT_EMAIL in GitHub
secrets (any real mailbox satisfies them).
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List

_BASE_URL = "https://efts.sec.gov/LATEST/search-index"
_USER_AGENT = os.environ.get("SEC_USER_AGENT_EMAIL", "steward-research contact@example.com")
_HEADERS = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
_CACHE_TTL = 3600
_cache: Dict[str, tuple] = {}


def get_insider_buy_score(ticker: str) -> float:
    """Filing-activity score for the last 30 days. 0.0 on any error — a research
    signal that fails to fetch is a 0, never a crash."""
    hit = _cache.get(ticker)
    if hit and (time.time() - hit[1]) < _CACHE_TTL:
        return hit[0]
    try:
        import requests
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        params = {"q": f'"{ticker}"', "dateRange": "custom",
                  "startdt": cutoff, "forms": "4"}
        resp = requests.get(_BASE_URL, params=params, headers=_HEADERS, timeout=10)
        if resp.status_code != 200:
            _cache[ticker] = (0.0, time.time())
            return 0.0
        hits = resp.json().get("hits", {}).get("hits", [])
        score = _score_hits(ticker, hits)
        _cache[ticker] = (score, time.time())
        return score
    except Exception:
        return 0.0


def _score_hits(ticker: str, hits: List[dict]) -> float:
    score = 0.0
    for h in hits:
        try:
            name = (h.get("_source", {}).get("entity_name", "") or "").upper()
            if ticker.upper() in name or name.startswith(ticker[:3].upper()):
                score += 0.5
        except Exception:
            continue
    return min(3.0, max(0.0, round(score, 2)))
