"""
US equity market calendar — so the engine KNOWS when stock/metal/energy books have a live market and never
burns cron time, API quota, or judgment on days nothing can trade. Crypto ignores this (24/7).

Holidays are listed explicitly per year (authoritative, auditable). Add future years by extending the dicts —
one file, no code changes (same philosophy as PARAM_CATALOG.json).
"""
from datetime import datetime, date, time, timezone, timedelta

# Full-close NYSE holidays
HOLIDAYS = {
    2026: ["2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
           "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"],
    2027: ["2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
           "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24"],
}
# Early closes (13:00 ET)
HALF_DAYS = {
    2026: ["2026-07-02", "2026-11-27", "2026-12-24"],
    2027: ["2027-11-26"],
}

def _et_now():
    # ET = UTC-4 (EDT) Mar-Nov, UTC-5 otherwise; exact DST bounds matter little at the day level,
    # but the session close check uses the summer offset during Apr-Oct which covers all 2026 half-days.
    now = datetime.now(timezone.utc)
    offset = 4 if 3 <= now.month <= 10 else 5
    return now - timedelta(hours=offset)

def equity_day_status(dt=None):
    """('OPEN'|'HALF'|'CLOSED', reason). Day-level only — intraday session windows are enforced elsewhere."""
    et = dt or _et_now()
    d = et.date()
    iso = d.isoformat()
    if d.weekday() >= 5:
        return "CLOSED", "weekend"
    if iso in HOLIDAYS.get(d.year, []):
        return "CLOSED", "NYSE holiday"
    if iso in HALF_DAYS.get(d.year, []):
        return "HALF", "half day — 1:00 PM ET close"
    return "OPEN", "regular session"

def equity_session_live(dt=None):
    """True only while the NYSE session is actually running (9:30 ET to 16:00, or 13:00 on half days)."""
    et = dt or _et_now()
    status, _ = equity_day_status(et)
    if status == "CLOSED":
        return False
    close = time(13, 0) if status == "HALF" else time(16, 0)
    return time(9, 30) <= et.time() <= close
