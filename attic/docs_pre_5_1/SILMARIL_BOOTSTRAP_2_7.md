# SILMARIL — MASTER BOOTSTRAP (cold-start brief for a fresh Claude) → 2.7 → Beta 1.0

You are picking up an in-flight project. Read this whole document before doing anything. It contains the
mission, the hard rules, the architecture, the proven facts you must NOT relitigate, the recurring bugs
and their fixes, what 2.6.1 finished, what 2.7 must do, and — most important — how to treat the person
you're working with. The operator goes by "Lady of Code" (GitHub: TheSeanMitchell). Be warm, be brutally
honest, never cheerlead, never fake completion.

---

## 0) THE MOST IMPORTANT THING (read first, hold throughout)
The operator is financially precarious and has spoken about rent and food and selling their home. They
pin real hope on this becoming income. **Your duty of care overrides helpfulness here.** SILMARIL's own
evidence says the edge is small and fee-sensitive (see §4). Your job is to build honestly AND to keep
reminding them, gently and clearly, that this is a DRESS REHEARSAL: it must prove it earns *after fees,
over a clean stretch*, before any real money — and never money they need to live. Do not feed "this is
about to be income." Do not encourage pouring more savings, tokens, or time into an endless "finish
everything now" loop. If they're spiraling, say so kindly and slow down. Protecting this person matters
more than shipping the next feature.

---

## 1) WHAT SILMARIL IS
An autonomous, multi-agent **paper-trading evidence engine**. It is NOT live-money trading. Goal (framed
as UNPROVEN HOPE, never income): generate meaningful daily returns from $10k. It runs on GitHub Actions,
writes JSON to `docs/data/`, and renders a GitHub Pages dashboard at
`theseanmitchell.github.io/SILMARIL-2.0` (repo `TheSeanMitchell/SILMARIL-2.0`).

Four INDEPENDENT books, each its own $10k: **crypto, stock, metal, energy**. Crypto + stock are live;
metal + energy are dormant (no tuned thresholds / sparse feeds yet). Above them sits the **MASTER
ACCOUNT** — a single "starts-now" $10k that funds only PROVEN quadrants and is meant to be the distilled,
high-quality output signal (the thing a real account would eventually follow). The whole thesis is a
**quantity-vs-quality test**: do the four workhorse books beat the Master's fewer-but-sharper trades?

---

## 2) OPERATOR CONSTRAINTS (do not violate — they break the workflow)
- **GitHub web UI ONLY.** They install your work by drag-and-dropping a ZIP that preserves repo paths.
- **They CANNOT run scripts or a terminal.** Anything that must execute has to be a **GitHub Actions
  workflow** (`.github/workflows/*.yml`) they trigger from the Actions tab via `workflow_dispatch`.
  If you give them a `scripts/foo.py`, you MUST also give a workflow that runs it.
- A cron runner fires the daily cycle every ~5 minutes (internal GitHub cron schedules were removed; it's
  driven by `workflow_dispatch`).
- **Your build sandbox reaches only github/pypi/npm — NOT exchange/price/news APIs.** So network code
  ships "Actions-ready + verified-graceful," never live-tested by you. Verify logic and compile; say
  plainly when something can only be confirmed on their next run.
- They use **external LLM judges** to verify completion. Overclaiming gets caught. Never say "done"
  about something you didn't verify.
- Disk in your sandbox fills up; `rm -rf` old extracted repos between tasks.

---

## 3) HARD RULES (non-negotiable)
1. **Read before editing.** Always read the actual file from their uploaded repo before changing it.
   Repomix/skeleton views are truncated — never edit from them.
2. **Complete replacement files in ZIPs.** No diffs, no surgical patches against unseen content.
3. **Brutally honest, no cheerleading, no synthetic optimism.** Match their tone: direct, technical.
4. **NO SYNTHETIC DATA, EVER.** Every number must trace to real data. This is sacred to them.
5. **Verify before claiming.** Run/inspect on their real data files when you can; show the proof.
6. **LF-only line endings.**
7. **Don't touch investment logic** (entry/exit/sizing) unless explicitly authorized. Observational/
   visual additions must not alter trading behavior.
8. **One install should be cumulative** when possible (don't make them stack five zips).
9. **Classify every proposed item** as SAFE NOW / SAFE AFTER OBSERVATION WINDOW / FUTURE EXPANSION.
10. Don't dump a huge blind UI rewrite — small verified edits to `docs/index.html` / `docs/silmaril_chart.js`.
    A broken main page right before their observation week is the worst outcome.

---

## 4) EMPIRICAL TRUTHS — PROVEN, DO NOT RELITIGATE
- **Momentum loses** (negative t-stat). **Mean-reversion (MR) is the only positive edge** — and it's
  marginal and fee-sensitive.
- **Deeper-dip entries are required to survive fees.** Shallow MR (≤2.5% dip) is fee-negative. ~3% dip
  ≈ break-even; ≥4.5% better; ≥6% best.
- **Fee reality is the central lesson.** Same gross edge nets wildly different by venue/order-type. The
  crypto book's lifetime gross collapsed to a fraction at a realistic ~54bps taker model. Binance.US
  ~0.10% flat keeps far more than Kraken/Coinbase taker. Order type + venue ≈ 6x take-home. SHOW fees.
- **MKR/MAKER concentration:** historically one name drove the majority of crypto profit. A real edge
  must not depend on a single ticker — but if a name proves itself repeatedly, exploiting it is fair game.
- After fees, recent clean intraday MR shows a SMALL POSITIVE edge (~+0.5–0.7%/trade, ~70–77% win on the
  best dip/target/stop combos). Promising, NOT proven. Do not oversell it.
- Internal paper-sim reliability has been hard-won; trust it only after the data-integrity fixes below.

---

## 5) THE RECURRING BUGS AND THEIR FIXES (do NOT reintroduce these)
These bit us repeatedly. The fixes are now in the engine; preserve them.

**(a) Key-format mismatch (the worst recurring one).** The dashboard reads canonical crypto keys
`BASE-USD` (hyphen, e.g. `SOL-USD`). The live ingestion and ccxt write `BASEUSD`/`BASEUSDT`. Mismatch →
graphs blank / only show "today." FIX: `scripts/remap_keys.py` canonicalizes every `BASEUSD`/`BASEUSDT`/
`BASE/USD`/`BASE-USDT` → `BASE-USD`, MERGING points. It is wired into `daily.yml` to run **every cycle**,
so it never goes stale. Stocks are plain tickers (AAPL) and are left alone. Keep this per-cycle wiring.

**(b) Backfill poison — daily candles in the trading/backtest series.** `backfill_universe.py` writes a
YEAR of DAILY candles into `price_samples.json` (for long-range GRAPHS only). If any trading or backtest
path reads those daily candles, it sees "yesterday's close vs now" as a -40% crash (instant fake-dip mass
buys) OR computes a fake -5%/trade leaderboard across 50k daily-candle trades. FIX: every signal/backtest
path filters to **intraday only** by excluding timestamps containing `"T00:00:00"`. This is already done
in `paper_sim.py` (live drop signal `_marks_from_samples`, and `backtest_through_sim`), `strategy_lab.py`
(leaderboard — drives champion selection), and `capital_router.py`. **If you add any new backtest, apply
the same intraday filter.** The backfill is GRAPHS-ONLY; the engine must never trade off daily candles.

**(c) Cold-start / no-context trades.** After a wipe there's no recent data, so early signals are garbage.
FIX: a WARMUP gate in `_marks_from_samples` — a coin cannot signal until it has ≥24 recent intraday points
spanning ≥2 hours (within a 6h recent window). Post-wipe = ~2h of quiet by design. This also makes stocks
safe at the open (they don't trade until ~2h into the session). Keep this.

**(d) Weekend/stale stock prices.** Old gate `len(set(last6))>1` couldn't tell a live quote from two
stale cached values oscillating → fake weekend P&L. FIX in `fresh_ok`: stocks only trade during the US
session (weekday ~13:30–20:00 UTC) AND any book needs ≥3 distinct values in the recent window
(stale-oscillation guard, protects crypto too). Keep this.

**(e) Wipe must preserve graphs.** `reset_internal_clean.py` wipes BOOKS to $10k + resets Master +
clears snapshot history, but PRESERVES `price_samples.json` (graphs/fingerprints) and favicons. Do not
make a reset nuke price history.

---

## 6) ARCHITECTURE & KEY FILES
- **Engine:** `silmaril/execution/paper_sim.py` (the sim: entry on h1 drop, exit on target/stop/timeout;
  contains HEATSHIELD, the warmup, the freshness gate, `heatshield_whatif`). `strategy_lab.py`
  (`run_leaderboard` → per-strategy edge/win → champion). `capital_router.py`, `champion_governance.py`,
  `master_account.py` (builds `MASTER_ACCOUNT.json` incl. live_equity, gross→net-spendable chain,
  quadrant_recommendations, reality_validation, exchange_comparison). `ccxt_universe.py` (TOP_N=600 full
  liquid Binance universe). Universe lists in `silmaril/universe/expanded.py`.
- **Dashboard:** `docs/index.html` (tabs: COMMAND/Market Engines, ARENA, FORENSICS, AUTHORITY LAB,
  SETTINGS; gold Master card; clickable quadrant decision portals via `openQuadrant`; Master detail via
  `openMaster`; HEATSHIELD panel; Today's-Session side-by-side; bot-handoff easter egg in SETTINGS).
  `docs/silmaril_chart.js` (price chart: 18 timeframes 5m→MAX; entry/stop/target/Dr-Strange overlays;
  closed-trade markers). Render functions are isolated via `safe(fn,name)` so one failure can't blank the
  page — keep that pattern.
- **Key data files (`docs/data/`):** `price_samples.json` ({samples:{SYM:[[ISO,price]]}}),
  `paper_book_{crypto,stock,metal,energy}.json` ({cash,positions,realized_pnl,trades}),
  `paper_book_MR_*` (arena challengers), `paper_sim_live.json` (per-book equity/positions/recent_trades +
  heatshield status + champion params), `MASTER_ACCOUNT.json`, `strategy_leaderboard_*.json`,
  `champion_validation.json`, `CHAMPION_GOVERNANCE.json`, `SESSION_TODAY.json`, `SCORECARD.json`,
  `HEATSHIELD.json`, `DECISION_TRACE.json`, `conviction_ranking.json`, `decision_ledger.json`.
- **Workflows (Actions tab):** `daily.yml` (the cycle: live mode → sanitize → remap_keys → heatshield
  what-if → analytics, gated by minute-of-hour), `reset_internal_clean.yml` (type WIPE),
  `backfill_universe.yml`, `remap_keys.yml`, `cleanup_clutter.yml`, `compact_history.yml`,
  `weekly_backup.yml`. Obsolete alpaca/kraken/backtest/etc. workflows were removed.
- **Strategy naming:** `MR_dX_tY_sZ` = mean-reversion, buy X% dip → target +Y% → stop −Z%.
  `MOM_uX_tY_sZ` = momentum. `PERSIST_uX_hY` = trend-hold (X/10 % move, hold Y h). `MR_patient_dX` =
  patient MR. The dashboard maps each of the 54 strategies to a Gen-1 Pokémon name (stable hash) with the
  decoded description shown tiny underneath — keep `pokeFor`/`stratDesc`/`pokeLabel`.

---

## 7) WHAT 2.6.1 DELIVERED (done + verified — don't redo)
Corruption fix (weekend/stale) · graph-preserving reset · full universe + 1y graph history · per-cycle
key canonicalization · 2h warmup (stocks safe at open) · 18 chart timeframes · stop line on closed trades
· clickable quadrant decision portals · Master title cleanup + working detail panel · "Market Engines"
rename · Pokémon strategy legibility (all 54) · HEATSHIELD default-on (−5% floor) + per-cycle what-if
forensic · scorecard moved to FORENSICS · the two Master views synced on `live_equity` and honest on fees
· Today's Session ALL-QUADRANTS vs MASTER-ONLY side-by-side · bot-handoff easter egg in SETTINGS · and the
**backtest/champion data-integrity fix** (intraday-only — repaired the −5.5%/16% leaderboard garbage to a
real small positive edge).

---

## 8) WHAT 2.7 SHOULD DO (these genuinely need the clean week's DATA — don't build blind)
1. **Dr. Strange audit.** The purple "next-peak / expected-move" projection plots `cur*(1+expected_move
   _pct)`. Nobody knows if it's any good. Compare its projections to actual outcomes over the week; keep,
   fix, or cut. Don't rebuild it without that evidence.
2. **Record target-at-entry per trade.** The sim doesn't store what each trade was AIMING for, so the
   dashboard can't show "% of goal hit" or honestly compute "left on table." Add the target/stop/expected
   move to each trade row at entry; then wire the %-of-goal display and fix SESSION ANATOMY's
   over-optimistic "left on table" (it currently judges on too narrow a window).
3. **Master signal tuning KNOBS (decimal parameters).** Expose, as single tunable values (e.g. 90.0):
   a **confidence gate** (default ~90% — only pass high-conviction trades up to the Master; lower it
   toward the workhorse books' setting to let more through), the **HEATSHIELD floor**, and the **wager
   size**. Goal: future tuning is one-number edits, not file rewrites. Tune these AGAINST real performance.
4. **Strategy-wiring audit.** Confirm prior work (fingerprints, peak-rhythm/heartbeat, heat tolerance,
   repeat-striking proven names like MKR) actually FEEDS live decisions — not just computed and ignored.
   Check against real behavior in the week's data. Wire in anything that's dangling.
5. **Metals/energy activation.** Give them their own tuned thresholds + a champion (only once their feeds
   populate). This is deliberate tuning, NOT a new signal family.
6. **Multi-day philosophy.** Today it's a day-trader that times out positions mechanically. Explore
   letting it ride multi-hour/multi-day waves where the fingerprint says a name has a repeating rhythm —
   without losing the short 10–120min MR trades. Evidence-driven only.
7. **Fee transparency by venue** (Binance.US vs Coinbase) surfaced everywhere a P&L is shown.
8. **Governance & automation scores → 10/10** by actually closing the learn→teach→change-behavior loop:
   prove decisions change based on outcomes, not just get logged.

The operator's "complete" test for the handoff layer: a dead-simple 1-2-3 way for a real trading bot to
consume the Master's output (the SETTINGS easter egg is the seed — make it real with the confidence/wager
knobs above).

---

## 9) THE ROAD TO BETA 1.0 (and what "ready" actually means)
Beta 1.0 is NOT "go live with real size." The honest gate is:
1. Run a **clean week+ on the fixed engine** (this is happening now). No corruption, warmup respected.
2. Read the **ALL-QUADRANTS vs MASTER-ONLY** side-by-side: does the Master do fewer, sharper trades that
   **survive fees**? Does the quantity-vs-quality thesis hold?
3. Only if a real, fee-surviving edge shows over that window: consider a **tiny** live test ($10–$100) on
   Binance.US or Coinbase via the handoff signal — money that absolutely does not matter.
4. Scale only on proof, never on hope. If the edge doesn't survive fees, that's a finding worth far more
   than a loss of rent money — surface it plainly.

---

## 10) HOW TO WORK WITH THIS PERSON
They are sharp, relentless, and have caught real bugs you'll be tempted to dismiss — take their bug
reports seriously and chase them to ROOT CAUSE (most "regressions" in this project were real data bugs,
not their misreading). They get understandably frustrated and may escalate; respond with steady, honest,
concrete fixes and self-respect, not submission and not empty reassurance. Deliver verified work, show the
proof, and say clearly what you did NOT do. When they ask for "everything now," it's okay to say no and
explain what's actually achievable — that honesty is what's kept their trust. And keep §0 alive in every
exchange: this is a dress rehearsal, the edge is unproven, and their wellbeing comes before the build.

When they upload a fresh repo: `rm -rf` your old extractions, extract theirs, READ the real files, then
work. Ship cumulative ZIPs with correct paths. Verify on their real data. Tell the truth.
