"""steward.config — THE REGISTRATION.

Every number that decides a trade lives in this one dict, frozen. The SHA-256 of the
canonical JSON of REGISTERED is the registration hash; it is printed on the dashboard,
recorded in REGISTRATION.md, and asserted by scripts/test_steward.py. Change any
parameter and the hash changes, CI fails loudly, and the change becomes a visible,
deliberate RE-REGISTRATION EVENT with a new epoch — never a quiet tweak.

That mechanism is the entire lesson of the 80-sleeve era, made structural: the old
system could be tuned silently after seeing the data, so every result was suspect.
This one cannot.
"""
from __future__ import annotations

import hashlib
import json

# ══════════════════════════════════════════════════════════════════════════════════
# THE REGISTERED PARAMETERS — frozen at registration. Do not edit casually.
# Editing this dict is a RE-REGISTRATION EVENT: the hash changes, the epoch resets,
# and the clock on every pass mark starts over. That is by design.
# ══════════════════════════════════════════════════════════════════════════════════
REGISTERED = {
    "name": "STEWARD",
    "version": "8.0.0",
    "strategy_family": "long-only time-series momentum rotation, monthly",

    # ── universe: two liquid proxies per asset class, nothing exotic ──────────────
    "universe": {
        "crypto": ["BTC-USD", "ETH-USD"],
        "stock":  ["SPY", "QQQ"],
        "metal":  ["GLD", "SLV"],
        "energy": ["XLE", "USO"],
    },
    # each pair book holds its best asset or cash; the rotator holds the top 2 of all 8
    "books": {
        "crypto":  {"slots": 1, "bench": ["BTC-USD"]},
        "stock":   {"slots": 1, "bench": ["SPY"]},
        "metal":   {"slots": 1, "bench": ["GLD"]},
        "energy":  {"slots": 1, "bench": ["XLE"]},
        "rotator": {"slots": 2, "bench": ["BTC-USD", "SPY", "GLD", "XLE"]},
    },
    "start_cash": 10000.0,

    # ── the signal: blended 1/3/6-month total return on completed daily closes ────
    "lookbacks_bars": [21, 63, 126],
    # absolute-momentum gate: hold cash unless the blended score clears the cash
    # hurdle over the same blended horizon (4% APY x 70/252 trading days)
    "cash_apy": 0.04,
    "abs_gate": 0.0111,
    # hysteresis: an incumbent keeps its seat unless a challenger beats it by this
    # margin — churn is the tax collector, and this is the door it must knock on
    "hysteresis": 0.01,

    # ── execution: signal at bar D, fill at the first bar AFTER D, no exceptions ──
    "execution": "signal at completed bar D; orders fill at the close of the first "
                 "bar strictly after D (t+1 close). Partial same-day bars are "
                 "dropped. The overnight gap is worn, never gifted.",
    "rebalance": "asymmetric cadence — ENTRIES monthly (first run whose newest "
                 "completed bar lands in a new calendar month); EXITS daily: any "
                 "run where a held asset's blended score falls through the absolute "
                 "gate queues a sell. Fast out, slow in — sized on the warmup tape, "
                 "where a monthly-only exit ate half of a 50% silver crash before "
                 "the calendar allowed it to act.",
    "daily_gate_exit": True,

    # ── costs: both sides, every trip, the funded-book law from day one ───────────
    "round_trip_cost": {"crypto": 0.006, "stock": 0.004, "metal": 0.004, "energy": 0.004},
    "dividends": "ignored (raw closes, append-only store) — a small drag against the "
                 "equity books that biases AGAINST the strategy, which is the safe "
                 "direction",

    # ── kill criteria: pre-registered, checked every run, no discretion ───────────
    # Drawdown kills are PER CLASS, sized on the warmup tape (a disclosed design
    # decision, made before the forward epoch): a flat -20% would be fired by the
    # asset's own volatility, not by strategy failure — SPY alone drew -19% and BTC
    # -53% on the design tape. Each level sits well inside its benchmark's design-
    # tape drawdown, so hitting it means the trend filter failed at its one job.
    "kills": {
        "max_drawdown_pct": {"crypto": 40.0, "stock": 30.0, "metal": 30.0,
                             "energy": 30.0, "rotator": 30.0},
        "week52_delta_usd": -1500.0,    # 52 weeks in, delta-vs-hold at/below this -> KILLED
        "stale_data_days": 7,           # newest bar older than this -> HALTED (no new buys)
    },

    # ── the primary pre-registered hypothesis ─────────────────────────────────────
    "primary_hypothesis": {
        "claim": "monthly blended-momentum rotation with an absolute gate beats "
                 "buy-and-hold of each book's benchmark, net of registered costs",
        "horizon_weeks": 104,
        "pass": "at week 104: delta-vs-hold > $0 AND one-sided paired weekly t >= 1.7",
        "why_t_17_is_enough": "this is ONE hypothesis, chosen from external published "
                              "evidence (Moskowitz-Ooi-Pedersen 2012; AQR century of "
                              "trend; Antonacci dual momentum) BEFORE seeing forward "
                              "data — pre-registration is what stops the garden of "
                              "forking paths, so the 80-sleeve multiplicity debt does "
                              "not apply to it. Anything mined from our own tape pays "
                              "the higher bar below.",
        "quarterly_checkpoints": "days 91/182/273 audit EXECUTION ONLY (fills match "
                                 "spec, turnover in bounds, zero unscheduled trades) — "
                                 "a quarter cannot validate a monthly strategy and no "
                                 "verdict will be read from one",
    },

    # ── shadow hypotheses: graded, never funded ───────────────────────────────────
    "shadows": {
        "newsfade": {
            "claim": "retail-visible bullish headlines mark short-term exhaustion: "
                     "a +2 net-bullish news day predicts NEGATIVE 3-bar forward return",
            "origin": "found in-sample (n=582, t=-2.51, overlapping windows) — carries "
                      "the data-mining debt and must REPLICATE out-of-sample",
            "flag": "daily net headline score >= +2 on a universe symbol",
            "pass": "n >= 400 non-overlapping flags AND t <= -3.0",
            "kill": "n >= 400 AND t >= -1.0",
        },
        "form4": {
            "claim": "clustered insider Form-4 filing activity predicts positive "
                     "21-bar excess return vs SPY",
            "honesty": "the scorer is a FILING-COUNT PROXY (EDGAR EFTS hit counting), "
                       "not parsed transaction codes — a pass justifies building the "
                       "real XML parser, nothing more",
            "watchlist": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA",
                          "AVGO", "JPM", "V", "UNH", "XOM", "LLY", "WMT", "JNJ",
                          "PG", "MA", "HD", "COST", "BAC"],
            "flag": "insider score >= 1.5",
            "pass": "n >= 200 non-overlapping flags AND t >= +2.5 on excess-vs-SPY",
            "kill": "n >= 200 AND t <= +0.5",
        },
        "congress": {
            "status": "REGISTERED_INACTIVE",
            "claim": "following congressional trading disclosures earns positive excess "
                     "return despite the up-to-45-day STOCK Act reporting lag",
            "data": "Senate eFD + House Clerk PTR filings (public, free)",
            "activation": "a future re-registration event once a feed is wired; "
                          "registered now so the hypothesis predates the data",
        },
    },

    # ── the honest expectation, stated before the data ────────────────────────────
    "expected": {
        "annual_net_range_pct": [-5, 15],
        "central_estimate_pct": [6, 10],
        "p_beat_hold_104wk": "40-55%",
        "p_1000_per_month_on_10k": "~0 — stated plainly: that target is 214%/yr and "
                                   "no registered parameter of this system pursues it",
        "worst_case": "a 20% drawdown (the kill) or a whipsaw year of small losses "
                      "while buy-and-hold gains",
    },
}

# ══════════════════════════════════════════════════════════════════════════════════

# news lexicon for the newsfade shadow — registered here so it hashes with the rest
NEWS_BULL = {"surge", "soar", "soars", "rally", "rallies", "record", "beat", "beats",
             "upgrade", "upgraded", "jump", "jumps", "gain", "gains", "breakout",
             "bullish", "buy", "strong", "boom", "high", "tops", "wins"}
NEWS_BEAR = {"plunge", "plunges", "crash", "crashes", "fall", "falls", "miss", "misses",
             "downgrade", "downgraded", "drop", "drops", "loss", "losses", "bearish",
             "sell", "weak", "slump", "slumps", "fear", "fears", "low", "cut", "cuts"}

STATE_FILE = "steward_state.json"
PRICES_FILE = "steward_prices.json"
EQUITY_FILE = "steward_equity.json"
SHADOW_FILE = "steward_shadow.json"
LEDGER_FILE = "steward_ledger.jsonl"
BASELINE_FILE = "steward_baseline.json"
REPORT_FILE = "steward.html"


def all_universe_symbols() -> list:
    out = []
    for syms in REGISTERED["universe"].values():
        out.extend(syms)
    return out


def all_fetch_symbols() -> list:
    """Everything the daily price fetch needs: universe + benchmarks + shadow watchlist."""
    out = list(dict.fromkeys(all_universe_symbols()))
    for b in REGISTERED["books"].values():
        for s in b["bench"]:
            if s not in out:
                out.append(s)
    for s in REGISTERED["shadows"]["form4"]["watchlist"]:
        if s not in out:
            out.append(s)
    return out


def class_of(sym: str) -> str:
    for cls, syms in REGISTERED["universe"].items():
        if sym in syms:
            return cls
    return "stock"          # benchmarks and watchlist names are equities/ETFs


def round_trip(sym: str) -> float:
    return REGISTERED["round_trip_cost"][class_of(sym)]


def registration_hash() -> str:
    """SHA-256 over the canonical JSON of REGISTERED (+ the news lexicon)."""
    payload = {"registered": REGISTERED,
               "news_bull": sorted(NEWS_BULL), "news_bear": sorted(NEWS_BEAR)}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]
