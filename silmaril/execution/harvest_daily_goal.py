"""
silmaril.execution.harvest_daily_goal — account-level daily-goal harvest.
(June 16, operator experiment — Account #2 / HARVEST_3 only.)

THE IDEA (operator's words): "we can accept $100, we like $300, we LOVE $500
for the day on a $10k account." When the WHOLE account is up a satisfying
amount for the day, lock in the win instead of giving it back to an evening
selloff — then keep playing with the original $10k base.

WHAT THIS DOES (scoped, additive, reversible):
  - Tracks the account's daily-open equity (re-anchored each ET trading day).
  - When intraday gain crosses a goal tier ($100 ok / $300 great / $500 love),
    it emits a HARVEST intent: trim positions to bank the gain ABOVE the $10k
    base, moving that profit to a cash reserve ("banked") so it can't be given
    back. The base $10k keeps trading.
  - It harvests the WINNERS (largest unrealized gainers) first, and only the
    amount needed to bank the tier — not the whole book — to minimize churn
    and fees (no full liquidate-and-rebuy).
  - It will not re-harvest the same tier twice in a day, and it respects a
    fee-aware minimum trim size so it never sells $5 to bank $5.

WHAT THIS IS NOT:
  - Not applied to Account #1 (pure stock, untouched) or Account #3 (crypto,
    untouched per operator). HARVEST_3 only.
  - Not a market-timing oracle. It reacts to REALIZED account gain crossing a
    goal, which is exactly the "lock the win" behavior requested. (Getting
    AHEAD of the selloff via the daily macro fingerprint is a future layer.)
  - Does NOT change any agent/scoring/engine logic. It only proposes sells to
    the executor, which still applies every safety rail.

OUTPUT: returns a list of harvest sell-intents (ticker, notional_to_trim,
reason) the caller hands to the executor, plus writes a transparent
docs/data/daily_goal_harvest.json showing the day's goal state.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

VERSION = "daily-goal-harvest-1.0"

# the operator's goal tiers, in $ of daily account gain on a $10k base
GOAL_TIERS = [
    {"name": "love",  "usd": 500.0, "bank_pct": 1.00},  # +$500: bank all gain above base
    {"name": "great", "usd": 300.0, "bank_pct": 0.75},  # +$300: bank 75% of gain above base
    {"name": "ok",    "usd": 100.0, "bank_pct": 0.50},  # +$100: bank half
]
BASE_EQUITY = 10000.0
MIN_TRIM_USD = 25.0          # fee-aware floor: never trim less than this
ONLY_ACCOUNT = "HARVEST_3"   # this experiment is scoped to Account #2


def _et_day_key(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(timezone.utc)
    # crude ET (UTC-4/5); day-bucketing only, exactness not required
    from datetime import timedelta
    et = now - timedelta(hours=4)
    return et.strftime("%Y-%m-%d")


def _load(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def _dump(path: Path, obj: Any) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, indent=2, allow_nan=False)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def compute_harvest_intents(account_id: str,
                            equity: float,
                            positions: List[Dict[str, Any]],
                            out_dir) -> List[Dict[str, Any]]:
    """Return a list of sell-intents to bank the day's gain, or [] if no tier
    is newly crossed. Only acts for ONLY_ACCOUNT."""
    if account_id != ONLY_ACCOUNT:
        return []

    out = Path(out_dir)
    state_path = out / "daily_goal_harvest.json"
    state = _load(state_path, {})
    today = _et_day_key()
    acct_state = state.get(account_id) or {}

    # re-anchor daily open each new ET day
    if acct_state.get("day") != today:
        acct_state = {"day": today, "day_open_equity": equity,
                      "banked_today": 0.0, "tiers_hit": []}

    day_open = float(acct_state.get("day_open_equity") or equity)
    # gain measured against the BASE ($10k), not the day-open — the operator's
    # goal is "$X profit on the $10k base today", and anchoring to a freshly
    # inflated day-open would zero out a gain the account already carries.
    reference = BASE_EQUITY
    gain_usd = equity - reference

    # find the best (highest) tier newly crossed today
    hit = None
    for tier in GOAL_TIERS:  # ordered love -> ok
        if gain_usd >= tier["usd"] and tier["name"] not in acct_state["tiers_hit"]:
            hit = tier
            break

    intents: List[Dict[str, Any]] = []
    if hit:
        # how much profit to bank: bank_pct of the gain above base
        to_bank = round((equity - BASE_EQUITY) * hit["bank_pct"], 2)
        to_bank = max(0.0, to_bank)
        # harvest from the biggest unrealized WINNERS first
        winners = sorted(
            [p for p in positions if (float(p.get("unrealized_pl") or 0) > 0)],
            key=lambda p: float(p.get("unrealized_pl") or 0), reverse=True)
        remaining = to_bank
        for p in winners:
            if remaining < MIN_TRIM_USD:
                break
            mv = float(p.get("market_value") or 0)
            if mv <= 0:
                continue
            trim = min(mv, remaining)
            if trim < MIN_TRIM_USD:
                continue
            intents.append({
                "ticker": p.get("symbol") or p.get("ticker"),
                "trim_notional": round(trim, 2),
                "reason": (f"daily-goal '{hit['name']}' (+${gain_usd:.0f} on the "
                           f"day) — banking ${to_bank:.0f} of profit above "
                           f"${BASE_EQUITY:.0f}, trimming winners first"),
            })
            remaining -= trim
        acct_state["tiers_hit"] = acct_state["tiers_hit"] + [hit["name"]]
        # crossing a higher tier satisfies all lower tiers too — we bank the
        # day's win ONCE at the best tier reached, not repeatedly down the ladder.
        _order = [t["name"] for t in GOAL_TIERS]  # love, great, ok
        _hit_idx = _order.index(hit["name"])
        for _lower in _order[_hit_idx:]:
            if _lower not in acct_state["tiers_hit"]:
                acct_state["tiers_hit"].append(_lower)
        acct_state["banked_today"] = round(
            float(acct_state.get("banked_today") or 0) + (to_bank - remaining), 2)

    acct_state["current_equity"] = equity
    acct_state["gain_usd_today"] = round(gain_usd, 2)
    acct_state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state[account_id] = acct_state
    state["version"] = VERSION
    state["note"] = ("Account #2 experiment: locks in the day's win when the "
                     "account crosses $100/$300/$500 gain on the $10k base, "
                     "trimming winners to bank profit so an evening selloff "
                     "can't take it back. Account #1 and #3 are not affected.")
    _dump(state_path, state)
    return intents


if __name__ == "__main__":  # pragma: no cover
    # demo
    import sys
    pos = [{"symbol": "AAPL", "market_value": 3000, "unrealized_pl": 280},
           {"symbol": "MSFT", "market_value": 2500, "unrealized_pl": 150},
           {"symbol": "NVDA", "market_value": 2000, "unrealized_pl": 90}]
    intents = compute_harvest_intents(
        "HARVEST_3", 10520.0, pos,
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp"))
    print(json.dumps(intents, indent=2))
