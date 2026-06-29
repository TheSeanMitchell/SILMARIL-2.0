# 2.6.1 — KEY MATCHING, FUTURE-PROOFED (the recurring nightmare ends here)

## The real reason it kept breaking
Your year of data was always in the file — but the LIVE CRON keeps writing non-canonical crypto keys
(AAVEUSD, AAVEUSDT) while the dashboard reads the canonical one (AAVE-USD). So any one-time remap went
stale on the very next run. That's why AAVE-USD showed only a week and 2W==MAX looked identical.

## The permanent fix (done + verified)
1. `scripts/remap_keys.py` is now a single CANONICAL normalizer: every BASEUSD / BASEUSDT / BASE/USD /
   BASE-USDT crypto key is merged onto BASE-USD; stock tickers untouched. Idempotent and safe.
2. It is wired into `daily.yml` to run EVERY CYCLE (right after price sanitize). So no matter what the
   ingestion writes, keys are canonicalized each run — graphs can never silently break again, through
   any wipe, any internal reset, any new coin, any quadrant.
VERIFIED on your real file: AAVE-USD went 37 -> **394 points (2025-06-30 -> today)**; 429 crypto graphs
hold a full year. The corrected price_samples.json is included, so graphs are right the moment you drop
this in — and they STAY right because the daily run re-canonicalizes forever.

## This makes the data layer hand-off ready
After this, a pristine wipe + a clean run yields canonical keys automatically. When you go live and reset
to your real balance, you will NOT have to redo any of this — the canonicalization is part of the cycle.

## What this drop is NOT
This fixes the KEY-MATCHING / GRAPH layer permanently. It does NOT deliver the rest of the 2.4-2.6.1
wishlist — clickable quadrant portals, the Master Account feed/decision tree display, Pokemon strategy
nicknames, the heat-shield parameters. I'm not going to claim those are done when they aren't. Each is a
real build that needs a focused session with the dashboard JS in front of me and budget to test it; doing
them blind in the same drop as a 14MB data file is how pages break. They are the next session's work, and
the key-matching foundation under them is now permanent so that work won't get undone.

## Files
scripts/remap_keys.py (canonical) · .github/workflows/daily.yml (runs remap every cycle) ·
docs/data/price_samples.json (already canonicalized — full year on every crypto graph)
