# WORKFLOW SPEED — what was slow, what changed, what's left

## Your diagnostic questions, answered
- **Is repo storage (375 MB) the problem?** Partly YES — but not the disk usage itself. The killer was
  `fetch-depth: 0` in checkout, which **clones the entire 375 MB history every run**. On a big repo that
  is minutes of pure git transfer before any code runs. **Fixed:** changed to `fetch-depth: 1` (shallow).
  Also run the existing **Compact Git History** workflow periodically to shrink history — safe between
  cycles, never mid-run.
- **Is API riding too hard?** YES, contributing. marketaux/newsapi at ~98% means the news fetch is doing
  a polite 0.4s sleep PER ticker across ~180 tickers — that alone is ~70s of sleeping, sequential, every
  run. **Fixed (partial):** cut polite_delay 0.4 → 0.15s. The real fix is parallelizing those fetches
  (below). You are not in danger of crossing the limit; you're just paying latency for being sequential.

## What changed in daily.yml (all in this delivery)
1. **Shallow checkout** (`fetch-depth: 1`, was 0) — biggest single win on a 375 MB repo.
2. **Heavy analytics gated to top-of-hour** — `sanitize_history`, `analytics.suite`, and `brag_sheet`
   now run only when the minute < 15 (once/hour) instead of every 15 min. They summarise data that barely
   moves intra-hour, so this is free time back on 3 of every 4 session runs. The TRADE cycle still runs
   every time.
3. **Shallow-safe commit** — the old `git pull --rebase origin main` can't work on a depth-1 clone; now it
   pushes and, only if rejected, fetches just the tip and rebases.
4. **news polite_delay 0.4 → 0.15s.**

Expected effect: the dense session runs should drop well under the 15-min cadence, so they **stop stacking**.
The stacking you saw (45 min between updates) is the concurrency queue: with `cancel-in-progress: false`,
a 30-min run forces the next two 15-min ticks to wait behind it. Faster runs = no queue.

## The next big lever if it's STILL slow (needs a code change, flagged not done)
**Parallelize the per-ticker fetches** in `silmaril/ingestion/news.py::fetch_news_bulk` (and the price
pulls). They're sequential today. A `concurrent.futures.ThreadPoolExecutor(max_workers=8)` over the ticker
list would cut the network-bound portion ~8x. This is the single highest-value remaining optimization, but
it touches the ingestion path, so it should be done carefully with the no-synthetic-data rule in mind and
verified on a real Actions run.

## Should you separate workflows / move off GitHub Actions?
- **Separating** the heavy analysis into its own less-frequent workflow is reasonable and the gating above
  is a lighter version of that. If you want true separation: keep `daily.yml` as a lean trade-only cycle
  every 15 min, and add an `analytics.yml` on `cron: '5 * * * *'` (hourly) that runs the suite. Both share
  the `silmaril-state` concurrency group so they never write at once.
- **Moving off Actions:** if you ever need guaranteed sub-15-min cycles, a tiny always-on host (a $5/mo VPS
  or a scheduled cloud function) running the same `python -m silmaril --live` on a real cron would be far
  more predictable than Actions' best-effort scheduler. Not required yet, but that's the path if the pops
  keep getting missed.
