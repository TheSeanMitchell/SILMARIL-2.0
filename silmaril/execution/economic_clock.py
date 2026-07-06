"""
ECONOMIC CLOCK (Movement V, Phase 26) — context, never signal. Zero direct authority.
Deterministic session + cadence context so any subsystem CAN condition on "what clock the world is
on" — whether conditioning helps is itself a hypothesis that must earn promotion.
"""
import json, calendar
from datetime import datetime, timezone
from pathlib import Path
from .market_calendar import equity_day_status, equity_session_live

def build_economic_clock(out_dir):
    out = Path(out_dir)
    now = datetime.now(timezone.utc)
    st, why = equity_day_status()
    dim = calendar.monthrange(now.year, now.month)[1]
    flags = []
    if dim - now.day <= 2: flags.append("month_end_window")
    if now.month in (3, 6, 9, 12) and dim - now.day <= 3: flags.append("quarter_end_window")
    if now.month == 12 and now.day >= 20: flags.append("year_end_tax_loss_window")
    if now.month in (7, 8): flags.append("summer_liquidity")
    payload = {"generated_at": now.isoformat(),
               "sessions": {"crypto": "24/7 OPEN",
                             "equities": ("OPEN" if equity_session_live() else st) + " — " + why,
                             "metals": "24/5 spot", "energy": "daily settle"},
               "context_flags": flags,
               "not_wired": "Fed/CPI/earnings calendars need a schedule feed — honest gap, future pass",
               "authority": "ZERO — context only (Law 6); conditioning on any flag is a promotable hypothesis"}
    (out / "ECONOMIC_CLOCK.json").write_text(json.dumps(payload, indent=1))
    return payload
