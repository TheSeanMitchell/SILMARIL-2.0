"""silmaril.execution.sizer — 7.0 THE GOVERNOR'S HAND (ladder · breakers · one-factor law).

Bet size is where compounding is created or destroyed. This module computes, every
cycle, the ONE multiplier and the ONE permission every entry must obey:

  DRAWDOWN LADDER (pre-registered, no discretion — Law 24):
    GREEN  (dd > -3%)      mult 1.00 · compound
    AMBER  (-3% .. -6%)    mult 0.50 · harvest-all mode (wins vault, base holds)
    RED    (dd <= -6%)     mult 0.00 · entries halt · review required

  CIRCUIT BREAKERS:
    daily loss     — realized today < -daily_loss_pct of seed → halt until tomorrow
    losing streak  — >= streak_n consecutive losses (all books) → AMBER floor

  THE ONE-FACTOR LAW: crypto ≈ one bet (BTC beta ~0.8). Aggregate open crypto+GEKKO
    notional above factor_cap_pct of their combined equity → additional entries in
    that factor SKIP with the reason written down.

Emits SIZER.json. paper_sim and the Master consume it every run.
KILL: sizer.mode:"off" → mult 1.0, no halts (the pre-7.0 world).
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .atomic_io import write_json_atomic

SEED_TOTAL = 50000.0   # 5 books × $10k


def _now():
    return datetime.now(timezone.utc)


def _load(out: Path, name: str, default=None):
    try:
        return json.loads((out / name).read_text())
    except Exception:
        return default if default is not None else {}


def build_sizer(out_dir) -> Dict[str, Any]:
    out = Path(out_dir)
    kb = (_load(out, "PARAM_CATALOG.json").get("sizer") or {})
    on = str(kb.get("mode", "auto")).lower() == "auto"
    amber_at = float(kb.get("amber_dd_pct", -3.0))
    red_at = float(kb.get("red_dd_pct", -6.0))
    daily_stop = float(kb.get("daily_loss_pct", -2.0))
    streak_n = int(kb.get("streak_n", 5))
    factor_cap = float(kb.get("factor_cap_pct", 60.0))

    st = _load(out, "SIZER.json", {})
    today = _now().date().isoformat()
    realized_today, streak, last = 0.0, 0, []
    equity_total, crypto_eq, crypto_open = 0.0, 0.0, 0.0
    live = _load(out, "paper_sim_live.json")
    for bk in ("crypto", "stock", "metal", "energy", "aggressive"):
        d = _load(out, f"paper_book_{bk}.json")
        sells = [t for t in d.get("trades") or [] if t.get("side") == "SELL"]
        realized_today += sum(float(t.get("pnl") or 0) for t in sells
                              if str(t.get("t", ""))[:10] == today)
        last += [(t.get("t"), float(t.get("pnl") or 0)) for t in sells]
        eq = ((live.get(bk) or {}).get("equity")
              or (10000.0 + float(d.get("realized_pnl") or 0)))
        equity_total += float(eq)
        if bk in ("crypto", "aggressive"):
            crypto_eq += float(eq)
            for p in (live.get(bk) or {}).get("positions") or []:
                crypto_open += float(p.get("wager_usd") or p.get("in_usd") or 0)
    for _, pnl in sorted(last)[-streak_n:][::-1]:
        if pnl < 0:
            streak += 1
        else:
            break
    peak = max(float(st.get("peak", SEED_TOTAL)), equity_total, SEED_TOTAL)
    dd = (equity_total / peak - 1.0) * 100 if peak else 0.0
    breakers = []
    if realized_today <= daily_stop / 100.0 * SEED_TOTAL:
        breakers.append(f"daily loss {realized_today:.2f} ≤ {daily_stop}% of seed — entries halt today")
    if streak >= streak_n:
        breakers.append(f"{streak} consecutive losses — AMBER floor")
    state = "GREEN" if dd > amber_at else ("AMBER" if dd > red_at else "RED")
    if breakers and state == "GREEN":
        state = "AMBER"
    if any("halt today" in b for b in breakers):
        state = "RED"
    mult = {"GREEN": 1.0, "AMBER": 0.5, "RED": 0.0}[state] if on else 1.0
    factor_used_pct = round(100.0 * crypto_open / crypto_eq, 1) if crypto_eq else 0.0
    payload = {"generated_at": _now().isoformat(), "mode": "auto" if on else "off",
               "state": state, "mult": mult, "dd_pct": round(dd, 2),
               "peak": round(peak, 2), "equity_total": round(equity_total, 2),
               "realized_today": round(realized_today, 2), "streak_losses": streak,
               "breakers": breakers,
               "factor": {"crypto_open_usd": round(crypto_open, 2),
                          "crypto_equity": round(crypto_eq, 2),
                          "used_pct": factor_used_pct, "cap_pct": factor_cap,
                          "over": factor_used_pct >= factor_cap},
               "harvest_mode": state != "GREEN",
               "ladder": {"GREEN": ">-3% · ×1.00 compound",
                          "AMBER": "-3..-6% · ×0.50 harvest-all",
                          "RED": "≤-6% or breaker · ×0.00 halt"},
               "what": ("the pre-registered hand on every wager: drawdown ladder, daily-loss "
                        "and streak breakers, and the one-factor law (crypto = one bet). "
                        "Law 24: no discretion, no exceptions, in writing.")}
    write_json_atomic(out / "SIZER.json", payload)
    return {"summary": f"sizer: {state} ×{mult} · dd {round(dd,2)}% · today ${round(realized_today,2)} "
                       f"· factor {factor_used_pct}%/{factor_cap}%"
                       + (f" · BREAKER {breakers[0]}" if breakers else "")}
