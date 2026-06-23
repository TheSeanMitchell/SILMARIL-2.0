# ALPACA BOOTSTRAP & RUNBOOK — read this before touching accounts

This file exists because the SAME class of bug kept recurring whenever we
reset accounts, re-keyed, or added an account. Every fix we've made is
documented here so it does NOT repeat. If orders ever stop, work this list
top to bottom — the cause is almost always one of these, all already fixed
in code but listed so you can verify fast.

═══════════════════════════════════════════════════════════════
## HOW ORDERS FLOW (the mental model)
═══════════════════════════════════════════════════════════════
1. The engine builds a "leaned-in" hotlist (conviction × momentum²).
2. Router → per-account plans: #1 stocks, #2 & #3 crypto.
3. Each account's executor (execute_consensus_signals) applies safety rails,
   then sends orders to Alpaca.
4. Crypto: symbol "BTC/USD", market, time_in_force gtc, 24/7.
   Stocks: limit/market, time_in_force day, ONLY during market hours.
5. Account state (positions, orders, P&L) is written to its own JSON file:
   #1 alpaca_paper_state.json · #2 alpaca_h3_state.json · #3 alpaca_h5_state.json

═══════════════════════════════════════════════════════════════
## THE RECURRING BUGS — ALL FIXED, listed so they never come back
═══════════════════════════════════════════════════════════════

### BUG 1 — "no orders at all" after a reset (the -90% cohort halt)
CAUSE: resetting an Alpaca account to a new balance while the risk system
still held the OLD daily-open → it computed a fake huge daily loss → tripped
the DAILY HALT → cohort_safe_mode froze ALL accounts.
FIX (in hard_stops.py): the daily-open anchor self-heals — if it's the
legacy $100k value or >3× current equity, it re-anchors to current and clears
the halt. So a reset can never again read as a crash.
VERIFY: docs/data/hard_stops.json shows each account daily_open ≈ its real
equity and daily_halted=false; system.cohort_safe_mode=false.

### BUG 2 — "no orders" because the executor CRASHED
CAUSE: a sector-lookup was passed as a function where a dict was required →
TypeError mid-cycle → zero orders, no clear error.
FIX (in alpaca_paper.py): crypto sectoring builds a proper DICT.
VERIFY: a manual run logs "opened=N" per account with no traceback.

### BUG 3 — crypto stops after stock-market hours
CAUSE: a global market-closed gate refused ALL order submission off-hours,
including crypto (which trades 24/7).
FIX: crypto symbols bypass the market-closed gate; stocks still wait for
regular hours.
VERIFY: crypto orders appear with timestamps after 20:00 UTC / on weekends.

### BUG 4 — crypto buys silently blocked once ~3 held
CAUSE: all crypto collapsed to sector "Unknown" → tripped the max-per-sector
concentration cap → new crypto buys blocked even with cash free.
FIX: in the valuables accounts, each coin gets its own sector key.
VERIFY: the book fills past 3 coins; cash deploys.

### BUG 5 — the SAME name ordered repeatedly with no fill (the LDO pile)
CAUSE: (a) crypto orders that didn't fill instantly stayed "open" and the
next cycle stacked ANOTHER order on the same name; (b) the stale-order
cleanup waited 2 hours, so duplicates piled up.
FIX (in alpaca_paper.py): a duplicate-order guard skips any name that
already has a live open order; crypto stale-cancel window cut to 15 min
(stocks keep 2 hours).
VERIFY: order sheet shows at most one open order per name; unfilled crypto
clears within ~15 min.

### BUG 6 — crypto un-tradeable in an account
CAUSE: a hardcoded _SKIP_ASSET_CLASSES={"crypto","token"} blocked crypto
everywhere; and the equity-only mission gate blocked -USD names.
FIX: both gates are account-aware — crypto trades in the valuables accounts
(#2, #3), stays blocked in the stock account (#1).
VERIFY: #2/#3 hold -USD names; #1 holds only equities.

═══════════════════════════════════════════════════════════════
## ADDING OR RESETTING AN ACCOUNT — the safe procedure
═══════════════════════════════════════════════════════════════
PAPER RE-BASELINE or LIVE CUTOVER, do this EXACT order:
1. Pause the cron (cron-job.org → disable the job).
2. In Alpaca: reset/fund the account to its baseline.
3. In GitHub → Settings → Secrets and variables → Actions: set/replace that
   account's key pair:
     #1: ALPACA_API_KEY / ALPACA_API_SECRET
     #2: ALPACA_API_KEY_H3 / ALPACA_API_SECRET_H3
     #3: ALPACA_API_KEY_H5 / ALPACA_API_SECRET_H5
   (Keep ALPACA_BASE_URL = https://paper-api.alpaca.markets for paper.)
4. Actions → "Pristine Reset" → that account (or "all"). This wipes the
   stale state files so no old positions/halt/P&L carry over. (BUG 1's heal
   also covers you, but the pristine reset is the clean path.)
5. Actions → "Daily Run" (manual) ONCE. Confirm in Alpaca that orders
   appear and the state file shows last_run set.
6. Re-enable the cron.

### LIVE-MONEY CUTOVER — the one extra thing
The base URL is currently global (paper). To take ONE account live while the
others stay paper, the endpoint must be made per-account (live account →
https://api.alpaca.markets). That's a code change to do DELIBERATELY before
any real money moves — it is NOT automatic. Everything else (keys, reset) is
the same as above.

═══════════════════════════════════════════════════════════════
## IF ORDERS STOP — 60-SECOND TRIAGE
═══════════════════════════════════════════════════════════════
1. Did daily.yml actually run? repo → Actions → is there a recent green run?
   If red/none → the cron or a workflow error, not the trading code.
2. Open the account's state file. last_run recent? reason="Live — configured"?
   If reason is a halt → check hard_stops.json (BUG 1).
3. Orders piling unfilled on one name? → BUG 5 (now auto-handled; should clear
   in 15 min).
4. Crypto silent but cash free? → BUG 4 (now fixed).
5. Crypto silent after hours? → BUG 3 (now fixed).
6. Nothing at all + no error? → likely a crash (BUG 2); run a manual daily
   and read the Actions log for a traceback.
Almost every past outage was one of the six above. They're all fixed in
code now; this list is for fast verification, not re-fixing.
