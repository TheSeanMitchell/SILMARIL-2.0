"""ladder.config — THE REGISTRATION of SILMARIL 9 ("The Ladder").

Every number that decides a trade lives in REGISTERED. Its SHA-256 (first 16 hex) is the
registration hash, printed on the page and checked by scripts/test_ladder.py against
REGISTRATION_9.md. Changing any number changes the hash, the test fails, and the change
has to be a deliberate, visible re-registration — never a quiet tweak after seeing data.

The ladder, bottom to top:
  SLEEVES            four per category: HOLD (the do-nothing twin), TREND, MOMENTUM, VOLTARGET
  CATEGORY ACCOUNTS  crypto / stock / metal / energy — each holds the average of its three
                     working sleeves (a committee, not a popularity contest)
  MASTER             holds the two category accounts whose own track records are rising
                     fastest, only while they beat T-bills; otherwise cash

Frozen 8 November 2026, before the history replay was run for the first time.
"""
from __future__ import annotations

import hashlib
import json

REGISTERED = {
    "name": "SILMARIL 9 - THE LADDER",
    "version": "9.0.0",
    "registered_on": "2026-11-08",
    # first NYSE close of the forward experiment; every forward account opens here
    "epoch_date": "2026-11-09",
    "start_cash": 10000.0,

    # ── universe ─────────────────────────────────────────────────────────────────
    "categories": {
        "crypto": ["BTC-USD", "ETH-USD"],
        "stock": ["SPY", "QQQ"],
        "metal": ["GLD", "SLV"],
        "energy": ["XLE", "USO"],
    },
    # idle money is never idle: it sits in 1-3 month T-bills (total return)
    "cash_symbol": "BIL",
    "calendar_symbol": "SPY",          # NYSE trading days are the clock for everyone
    "price_basis": "adjusted close (splits + dividends) — total return for every holding "
                   "and every benchmark alike",

    # ── execution ────────────────────────────────────────────────────────────────
    "execution": "decided on closes up to day D-1, filled at the close of day D. Every leg "
                 "of a rebalance fills on the same day. Fees are charged on both sides.",
    "round_trip_cost": {"crypto": 0.008, "etf": 0.001, "cash": 0.0},
    "min_trade_frac": 0.01,           # trades smaller than 1% of the account are skipped

    # ── the sleeves ──────────────────────────────────────────────────────────────
    "sleeves": {
        "HOLD": "50/50 of the category's two assets, bought on day one, never traded again",
        "TREND": "monthly: each asset holds its half while its close is above its 200-day "
                 "average, otherwise that half sits in T-bills (Faber 2007)",
        "MOMENTUM": "monthly: hold the ONE asset with the best blended 1/3/6-month return if "
                    "it beats T-bills over the same windows, else T-bills; checked daily for a "
                    "fast exit (Moskowitz-Ooi-Pedersen 2012; Antonacci 2014)",
        "VOLTARGET": "monthly: 50/50 basket scaled so its recent volatility is about 15% a "
                     "year, the rest in T-bills; re-sized only when the size moves by more "
                     "than 10 points (Moreira-Muir 2017)",
    },
    "sma_days": 200,
    "momentum_lookbacks": [21, 63, 126],
    "hysteresis": 0.01,
    "vol_window": 63,
    "vol_target": 0.15,
    "vol_band": 0.10,
    "warmup_bars": 253,

    # ── the category account ─────────────────────────────────────────────────────
    "account_rule": "equal average of the TREND, MOMENTUM and VOLTARGET sleeve targets; "
                    "re-balanced whenever any sleeve changes its target",

    # ── the master ───────────────────────────────────────────────────────────────
    "master_rule": "monthly: score each category account's own equity curve by its blended "
                   "1/3/6-month return; hold the top 2 that beat T-bills, half each, "
                   "mirroring that account's holdings; a held account that falls below "
                   "T-bills is dropped the next day; empty seats sit in T-bills",
    "master_slots": 2,

    # ── what is NOT here, on purpose ─────────────────────────────────────────────
    "no_halts_without_a_way_back": "there is no drawdown kill or governor that can lock the "
                                   "system out forever. Risk control lives inside the rules "
                                   "(trend, momentum and volatility exits), which re-enter "
                                   "on their own. A stale price feed pauses decisions and "
                                   "resumes them automatically when data returns.",
    "stale_data_days": 5,

    # ── the verdict, stated before the data ──────────────────────────────────────
    "verdict": {
        "horizon_weeks": 104,
        "pass": "MASTER beats the equal-weight hold of all 8 assets after costs, with a "
                "smaller worst drawdown",
        "checkpoints": "every 13 weeks the page reports progress; no verdict is read before "
                       "week 104",
    },
}


def all_symbols() -> list:
    out = []
    for syms in REGISTERED["categories"].values():
        out.extend(syms)
    out.append(REGISTERED["cash_symbol"])
    return out


def category_of(sym: str) -> str:
    for cat, syms in REGISTERED["categories"].items():
        if sym in syms:
            return cat
    return "cash" if sym == REGISTERED["cash_symbol"] else "stock"


def round_trip(sym: str) -> float:
    rt = REGISTERED["round_trip_cost"]
    if sym == REGISTERED["cash_symbol"]:
        return rt["cash"]
    return rt["crypto"] if sym.endswith("-USD") else rt["etf"]


def registration_hash() -> str:
    blob = json.dumps(REGISTERED, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]
