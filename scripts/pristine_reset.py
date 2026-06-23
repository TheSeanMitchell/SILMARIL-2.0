#!/usr/bin/env python3
"""
scripts/pristine_reset.py — wipe account state to a clean baseline.

Use when starting an account fresh: a paper re-baseline, OR (the real goal)
when cutting ONE account over to a live-money account and you want nothing
from the paper run carried over.

It zeroes ONLY the trading-state files for the selected account(s):
positions, orders, realized P&L, savings/vault, harvest ledgers, the deal
journal entry, the duel row, and the hard-stop anchor. It does NOT touch
agents, scoring, signals, fingerprints, or any learning — those are
account-agnostic and stay intact.

ALWAYS pair with the matching action in the Alpaca dashboard:
  - paper re-baseline: reset that paper account to the baseline amount
  - live cutover: open/fund the live account, put its keys in GitHub
    secrets, and (separately) make that account's endpoint live

Usage (run in Actions or locally):
    python scripts/pristine_reset.py --accounts all
    python scripts/pristine_reset.py --accounts HARVEST_5
    python scripts/pristine_reset.py --accounts LEGACY,HARVEST_3 --baseline 10000
"""
from __future__ import annotations
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DATA = Path("docs/data")

# account_id -> its state file
STATE_FILES = {
    "LEGACY": "alpaca_paper_state.json",
    "HARVEST_3": "alpaca_h3_state.json",
    "HARVEST_5": "alpaca_h5_state.json",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _load(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def _save(p, obj):
    Path(p).write_text(json.dumps(obj, indent=2))


def reset_account_state(account_id: str, baseline: float):
    """Reset one account's main state file to a clean baseline, preserving
    only identity/config fields (label, mode, env wiring)."""
    fn = STATE_FILES.get(account_id)
    if not fn:
        print(f"  ! unknown account {account_id}, skipping")
        return
    p = DATA / fn
    old = _load(p, {})
    # keep only identity/config; wipe all trading history
    fresh = {
        "version": old.get("version"),
        "enabled": old.get("enabled", True),
        "account": {"equity": baseline, "cash": baseline,
                    "buying_power": baseline},
        "principal_target": baseline,
        "savings": 0.0,
        "realized_savings": 0.0,
        "savings_vault": 0.0,
        "lifetime_realized_wins": 0.0,
        "lifetime_realized_losses": 0.0,
        "position_meta": {},
        "positions_snapshot": [],
        "orders": [],
        "orders_placed": 0,
        "errors": [],
        "account_id": account_id,
        "mode": old.get("mode", "consensus"),
        "label": old.get("label", account_id),
        "min_harvest_gain_pct": old.get("min_harvest_gain_pct", 0.0),
        "configured": old.get("configured", True),
        "trading_capital": baseline,
        "genesis_at": _now(),
        "reason": f"pristine reset to ${baseline:.0f} baseline",
        "cycle_intents": [],
        "tickers_traded_this_cycle": [],
        "recent_alpaca_tickers": [],
    }
    _save(p, fresh)
    print(f"  ✓ {account_id}: state wiped to ${baseline:.0f} ({fn})")


def reset_shared_ledgers(accounts, baseline):
    """Clear the per-account entries from the shared ledger/journal files."""
    # hard_stops: re-anchor the reset accounts, clear any halt
    hs = _load(DATA / "hard_stops.json", {})
    if isinstance(hs.get("accounts"), dict):
        for a in accounts:
            hs["accounts"][a] = {
                "daily_open_equity": baseline, "current_equity": baseline,
                "daily_open_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "daily_halted": False, "weekly_halted": False,
                "daily_low_since_halt": 0.0, "weekly_low_since_halt": 0.0,
                "reason": "pristine reset",
            }
    if isinstance(hs.get("system"), dict):
        hs["system"]["cohort_safe_mode"] = False
        hs["system"]["cohort_halted"] = False
    _save(DATA / "hard_stops.json", hs)
    print("  ✓ hard_stops.json: anchors reset, halts cleared")

    # deal_journal: drop entries for reset accounts (or all if 'all')
    dj = _load(DATA / "deal_journal.json", {})
    if isinstance(dj, dict):
        dj["deals"] = [d for d in (dj.get("deals") or [])
                       if d.get("account") not in accounts]
        dj["deals_count"] = len(dj["deals"])
        _save(DATA / "deal_journal.json", dj)
        print("  ✓ deal_journal.json: reset-account deals cleared")

    # duel: clear the board so it rebuilds clean next run
    duel = _load(DATA / "duel.json", {})
    if isinstance(duel, dict):
        duel["board"] = [b for b in (duel.get("board") or [])
                         if b.get("account") not in accounts]
        _save(DATA / "duel.json", duel)
        print("  ✓ duel.json: reset-account rows cleared")

    # harvest ledgers: clear reset-account harvest history
    for fname in ("harvest_accounts.json", "harvest_truth.json",
                  "verified_harvest_ledger.json", "daily_goal_harvest.json"):
        fp = DATA / fname
        if not fp.exists():
            continue
        d = _load(fp, {})
        if isinstance(d, dict):
            for a in accounts:
                d.pop(a, None)
            _save(fp, d)
    print("  ✓ harvest ledgers: reset-account entries cleared")


def reset_paper_books(baseline: float):
    """2.5.1 — reset the FOUR internal paper-trading books (crypto/stock/metal/energy)
    AND the per-strategy arena books to a clean baseline, and rewrite the live cockpit
    summary so all four quadrants show a fresh $baseline immediately. This is what
    'pristine' must mean for the internal lab, not just the Alpaca-style ledgers."""
    clean = lambda: {"cash": baseline, "realized_pnl": 0.0, "positions": {},
                     "trades": [], "updated_at": _now()}
    n = 0
    for p in DATA.glob("paper_book_*.json"):
        _save(p, clean()); n += 1
    print(f"  ✓ paper books: {n} reset to ${baseline:.0f} (crypto/stock/metal/energy + arena)")
    # rewrite the live summary so the UI shows four clean $baseline books at once
    book = lambda: {"equity": baseline, "cash": baseline, "realized_pnl": 0.0,
                    "return_pct": 0.0, "open_positions": 0, "positions": [], "recent_trades": []}
    live = {"generated_at": _now(), "start_cash_each": baseline,
            "champion_crypto": None, "champion_stock": None,
            "champion_metal": None, "champion_energy": None,
            "crypto": book(), "stock": book(), "metal": book(), "energy": book(),
            "combined_equity": round(baseline * 4, 2), "combined_realized_pnl": 0.0,
            "note": "Pristine reset — four independent books at a clean baseline."}
    _save(DATA / "paper_sim_live.json", live)
    print(f"  ✓ paper_sim_live.json: four books reset to ${baseline:.0f} each")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounts", default="all",
                    help="'all' or comma list: LEGACY,HARVEST_3,HARVEST_5")
    ap.add_argument("--baseline", type=float, default=10000.0)
    a = ap.parse_args()
    accts = (list(STATE_FILES.keys()) if a.accounts.strip().lower() == "all"
             else [x.strip() for x in a.accounts.split(",") if x.strip()])
    print(f"PRISTINE RESET → {accts} @ ${a.baseline:.0f}")
    for acct in accts:
        reset_account_state(acct, a.baseline)
    reset_shared_ledgers(accts, a.baseline)
    reset_paper_books(a.baseline)
    print("DONE. Pair this with the matching Alpaca dashboard reset/funding.")
    print("Next engine run starts these account(s) clean.")
