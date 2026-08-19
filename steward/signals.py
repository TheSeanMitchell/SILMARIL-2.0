"""steward.signals — blended time-series momentum, and nothing else.

score(sym) = mean of 21/63/126-bar total returns, computed on completed closes
up to and including the signal bar. The absolute gate compares that score to the
cash hurdle: below it, cash IS the position. The hysteresis margin keeps an
incumbent seated against a marginal challenger, because every swap costs a round
trip and churn was the quiet killer of the last system.

There is no second signal. The whole point of this design is that one honest,
century-tested signal with pre-registered pass marks beats eighty clever ones
graded after the fact.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .config import REGISTERED


def momentum_score(rows: List, asof: str) -> Optional[float]:
    """Blended momentum on closes with date <= asof. None when history is short."""
    px = [r[1] for r in rows if r[0] <= asof]
    if not px:
        return None
    rets = []
    for lb in REGISTERED["lookbacks_bars"]:
        if len(px) <= lb:
            return None                     # not enough history — no score, no trade
        past = px[-1 - lb]
        if past <= 0:
            return None
        rets.append(px[-1] / past - 1.0)
    return sum(rets) / len(rets)


def choose(current: List[str], scores: Dict[str, float], slots: int) -> List[str]:
    """The registered seat-selection rule, shared by every book and the backtest.

    * eligible = symbols whose score clears the absolute gate
    * an incumbent keeps its seat while eligible and within `hysteresis` of the
      slot cutoff — it is evicted only by a decisively better challenger
    * open seats go to the best eligible non-holders; unfilled seats are cash
    """
    gate = REGISTERED["abs_gate"]
    margin = REGISTERED["hysteresis"]
    eligible = {s: v for s, v in scores.items() if v is not None and v > gate}
    ranked = sorted(eligible, key=lambda s: -eligible[s])
    cutoff = eligible[ranked[slots - 1]] if len(ranked) >= slots else None

    target: List[str] = []
    for s in current:                       # incumbents first, in held order
        if s in eligible and (cutoff is None or eligible[s] >= cutoff - margin):
            target.append(s)
    for s in ranked:
        if len(target) >= slots:
            break
        if s not in target:
            target.append(s)
    return target[:slots]
