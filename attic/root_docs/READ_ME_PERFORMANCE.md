# SILMARIL — daytime run-speed overhaul (FINAL)

This session was solely about runtime. I profiled the real cycle and fixed the actual sinks, plus
removed the internal cron so it only runs when YOUR external runner triggers it.

## 1. Removed GitHub's internal schedule (part of the stacking)
`daily.yml` had THREE internal `cron:` schedules (every-15-min weekdays, pre-market, daily off-hours).
Those fired on top of your external cron runner — extra runs piling into the queue. **Removed all of
them.** The workflow now runs ONLY on `workflow_dispatch` (the "Run workflow" button or your external
runner hitting the dispatch API). One trigger = one run. No more GitHub-scheduled runs stacking.

## 2. Parallelized the news fetch — the multi-minute sink
`fetch_news_bulk` looped ~180 tickers **sequentially**, each a network RSS parse + delay. That was the
bulk of your 22 minutes (and exactly your "marketaux/newsapi 98%" clue). Now it uses an **8-worker
thread pool** — each fetch is independent and network-bound, so this cuts the news stage ~8× (minutes
→ well under a minute). Per-ticker failures stay isolated; output shape is identical (verified with a
mocked run). Prices were NOT the problem — `yf.download(threads=True)` already batches them.

## 3. Heavy forensics now run at most ONCE PER HOUR (deterministic)
I had piled many read-only audit engines into the live cycle over our sessions; they ran EVERY cycle.
Profiled worst offenders: regime_observer **9.3s**, split-leaderboards **4.0s**, leaderboard 1.2s,
threshold-champion, session-anatomy, timer-opt, exit-forensics, opportunity-audit. **~18–19s/cycle.**

Because the workflow is on-demand now, a wall-clock gate would be unreliable, so the gate is a small
**committed timestamp file** (`docs/data/_forensics_last.json`): forensics run only if >45 min since
they last ran, regardless of when you trigger. The **trade-critical path always runs every cycle** —
price/news ingestion, champion selection + split, capital router, paper-sim execution, snapshots.
Gated cleanly (`= fn(out) if _HOURLY else {}`); log shows "[perf] skipping heavy forensics this cycle
(ran < 45 min ago)". Kraken's hourly spread pull uses the same gate.

## Honest note on the number
My sandbox can't reach the price/news APIs, so I **could not measure wall-clock** — only the logic and
the ~18s engine savings are verified. The news 8× is a strong, standard win but its exact effect
depends on live latency. **Check the next few runs' duration in Actions.** Expectation: news minutes →
<1 min + ~18s from gating should bring runs well under your 9-minute target. If still over, next levers:
parallelize the fresh-quote overlay, trim the news ticker cap at peak, or split a lean trade-only
workflow from an hourly forensics one.

## "Crypto and stocks finding trades at the same time" — not an hour-block
Crypto trades 24/7 in the engine. The clustering was almost certainly the **cycle cadence**: when runs
were 22 min and stacking, entries only got evaluated when a cycle finally completed, so fills landed
together at cycle boundaries. Faster, non-stacked cycles should de-cluster this.

## Kraken — installed and wired; here's why it's not visible yet
`kraken_spread.py` is wired into the cycle, gated to the hourly flag so it never slows normal runs. It
populates `KRAKEN_SPREAD.json` + the 🐙 panel only on the hourly cycle AND only if it reached
api.kraken.com. Confirm via a forensics-cycle log line: "kraken spread: N symbols quoted" (working) or
"kraken spread skipped: …" (unreachable / symbol map needs a tune). I couldn't test it from here.

## Changed files
- `.github/workflows/daily.yml` — removed internal cron schedules (workflow_dispatch only).
- `silmaril/ingestion/news.py` — parallel bulk news fetch (8 workers).
- `silmaril/cli.py` — heavy forensics gated to ≤ once/hour via committed timestamp; Kraken aligned.
