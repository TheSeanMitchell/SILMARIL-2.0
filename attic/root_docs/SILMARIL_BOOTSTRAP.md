# SILMARIL — AGENT BOOTSTRAP / HANDOFF (read this first)

You are continuing work on SILMARIL with its operator ("Lady of Code"). This file is the full
context so you don't have to relearn it. Read it before doing anything.

## WHAT SILMARIL IS
An autonomous multi-agent **paper-trading EVIDENCE engine** — branded "SILMARIL 2.5.4". It is NOT
a money-maker yet; it is a research platform that collects honest evidence about whether a tradeable
edge exists. The aspirational goal is $100–300/day from $10k, but that is an UNPROVEN hope — never
treat it as income. $10k is a hard ceiling per book.

- Repo: github.com/TheSeanMitchell/SILMARIL-2.0  ·  Live: theseanmitchell.github.io/SILMARIL-2.0
- Runs on **GitHub Actions cron** (~15-min cadence during market hours), writes JSON to
  `docs/data/`, rendered by a **GitHub Pages** dashboard (`docs/index.html` + `docs/silmaril_chart.js`).
- **Four independent books** — crypto, stock, metal, energy — each with its OWN arena, champion, and
  $10k. They are NEVER pooled; "combined equity" is only a display SUM. Crypto + stock are live;
  metal/energy are data-gated until their feeds fill.

## HARD RULES (the operator enforces these and will catch violations)
1. **Read before editing.** Never write a replacement from a skeleton — read the actual current file.
2. **Additive, never destructive.** No synthetic/fake data, ever. No LLMs in analyst layers.
3. **Complete replacement files** in drag-and-drop **zips preserving repo paths**. The operator uses
   the **GitHub web UI only** — no terminal, no diffs, no surgical patches. LF line endings only.
4. **Brutally honest, non-cheerleading.** Rate subsystems COMPLETE/PARTIAL/PLACEHOLDER/UNVERIFIED with
   evidence. "Permanently observational / no demonstrated edge" is an ACCEPTABLE outcome. The operator
   uses external judges; overclaiming fails them. NEVER stamp something done without verifying against
   the real repo (file exists, wired, output fresh, render call present).
5. **Verify before claiming.** Two recurring failure patterns to actively guard against:
   - "**Defined but never called**" — a render fn written in HTML but never invoked. grep-verify every
     render fn appears as `safe(()=>renderX())` in BOTH `docs/index.html` and `docs/cockpit.html`.
   - "**Wired but starved**" — a module integrated but receiving no data due to field-name mismatch.
     Trace the full data chain, not just the integration point.
6. **Build sandbox can't reach price/news APIs** (only github/pypi/npm). GitHub Actions CAN. So build
   data-fetch code Actions-ready and verify graceful no-key behavior; don't expect live data locally.
7. **No new alpha signals / strategy families.** The project is in EVIDENCE + LEARNING mode, not
   signal-hunting. Harden/validate/explain what exists.

## EMPIRICAL TRUTHS (proven from real data — don't relitigate)
- **Momentum loses; mean-reversion (MR) is the only positive edge** — marginal, regime-dependent.
- Crypto MR works in oversold/bear; **stock MR has lost in every observed regime** (stocks keep
  falling; crypto bounces). ~92% of the crypto universe are stale "ghosts" excluded by a freshness filter.
- **Exit problem:** trades end on TIMEOUT, not target. Timer simulation says crypto's optimal hold is
  **~30 min** (+0.386%/trade vs 0.309% actual). Leak breakdown: **sold-too-late 27 vs too-early 13** —
  crypto bounces fast then fades, so a short hold captures more.
- **Drop×Bounce champion (real data):** accuracy champion (safe/downtrend) = drop 4.0% → target 1.0%
  (67.9% hit); expectancy champion (aggressive/uptrend) = drop 4.5% → target 4.5% (+0.418%/trade,
  11.6% hit). Deeper drops = better entries. This CONFIRMS the operator's thesis: less aggressive
  targets on downtrends = higher success; aggressive on uptrends = higher yield.
- Peak rhythm: BTC peaks ~every 169 min, ETH ~165 min.

## CURRENT STATE — 2.5.4 IS COMPLETE (measurement/explainability/champion-rotation/projection)
Engines (all in `silmaril/execution/`, each emits a JSON to `docs/data/`, wired in `cli.py` ~line
2274 block, surfaced on a dashboard panel):
- **Champion governance** (champion.py selects by forward survivability; CHAMPION_GOVERNANCE.json),
  champion truth panel.
- **Measurement suite:** opportunity_audit, exit_forensics, decision_trace, time_of_day, intrabar_audit,
  zero_pnl_audit, scorecard, health_matrix (reads api_health.json), capital_router_explainer, sector_recovery.
- **2.5.4 additions:** timer_optimization (TIMER_OPTIMIZATION.json), threshold_champion (drop×bounce
  1.0–6.0% grid → champion drop + champion bounce + combo), regime_classifier (per-book UP/SIDEWAYS/DOWN),
  peak_rhythm, chart_overlays (CHART_OVERLAYS.json — consolidates closed trades + open pos + dr_strange +
  conviction per symbol), parameter_registry (PARAMETER_REGISTRY.json — **8 champion parameters, all green:
  Strategy, Drop, Bounce, Drop×Bounce combo, Hold-timer, Regime, Peak-rhythm, Time-of-day**),
  compounding_projection (1d…1y, honest decay caveats), daily_journal (human-voice brag sheet).
- **Chart** (`docs/silmaril_chart.js`, injected in index/paper_sim/cockpit/legacy): custom line chart with
  time axis, crosshair, timeframe tabs, **trend label badge (UPTREND/DOWNTREND/SIDEWAYS + slope%)**, a
  **legend**, and overlays = champion entry/target(GOLD cash-out line)/stop + buy▲/sell▼ markers +
  Dr Strange projection + next-peak. Hover/tap works on EVERY symbol incl. trade-row text nodes.
  Front page shows all 4 quadrants in OPEN POSITIONS + RECENT TRADES with exact timestamps.
  HONEST LIMIT: still a LINE chart — candlesticks need OHLCV capture in the sampler first (price_samples
  stores [ISO_ts, price] only).

## OPEN 2.5.5 WORK (correctly data-gated — do NOT fake these)
- **Closed learning loop** (lesson → change behavior → measure → keep/reject). Every engine RECOMMENDS;
  none auto-flips live params yet. This is the heart of 2.5.5 and needs weeks of forward data.
- **Champion-of-champions A/B optimizer** — tests every parameter COMBINATION per book each run and proves
  the current combo is best, with an A/B "are we helping or hurting" test. Needs forward data across
  different regimes to mean anything. The per-parameter champions all exist; the cross-product optimizer
  does not.
- **Adaptive mid-trade exits + stop-point champion** (incl. no-stop) — exits are currently FIXED at entry.
- **Regime→trading coupling** (regime classified but doesn't yet set target aggression) and **news→trading
  coupling** (authority engine reports e.g. Hormuz/crude but doesn't gate trades).
- **Non-crypto champions** — data-gated until stock/metal/energy trade.
- **Parameter-audit candidates not yet championed:** stop-loss %, position size/deployment %, max-hold cap,
  entry-confirmation lookback, freshness window, per-regime target multiplier, news-veto, exposure cap.
  Each slots into parameter_registry.py with one reader once it has evidence.

## DATA SOURCES / SECRETS (operator's exact GitHub secret names — all configured, no action needed)
ALPACA_API_KEY/_H3/_H5, ALPACA_API_SECRET/_H3/_H5, ALPHA_VANTAGE_API_KEY, BIRDEYE_API_KEY,
COINGECKO_API_KEY, EIA_API_KEY, FINNHUB_API_KEY, FMP_API_KEY, FRED_API_KEY, FREECRYPTOAPI_API_KEY,
MARKETAUX_API_KEY, NEWSAPI_KEY, OPENEXCHANGERATES_APP_ID, POLYGON_API_KEY, SEC_USER_AGENT_EMAIL,
TIINGO_API_KEY, TWELVEDATA_API_KEY (no underscore). Fallback chains (multi_source.py): crypto =
CoinGecko→FreeCryptoAPI→Binance(keyless); stock = Finnhub→Polygon→Tiingo→TwelveData→AlphaVantage→FMP.

## WORKFLOW / PERFORMANCE (just optimized — see WORKFLOW_SPEED_NOTES.md)
- `daily.yml` is the ONE scheduled trading cadence. Just changed: **shallow checkout (fetch-depth 1)**,
  heavy analytics **gated to top-of-hour**, **shallow-safe commit**, news polite_delay 0.4→0.15s.
- Repo ~375MB. Run `Compact Git History` periodically (safe between cycles). `cleanup_workflows.py`
  archives the 17 stale one-off workflows.
- The remaining big lever if still slow: **parallelize the per-ticker news/price fetches** (thread pool)
  in silmaril/ingestion/news.py — it's currently sequential over ~180 tickers.

## HOW TO WORK WITH THE OPERATOR
Emotionally invested, values brutal honesty over false completion, repeatedly (accurately) catches
overclaiming. Wants every measured parameter turned into a rotating-champion that auto-grows (registry
built for this). Keep responses warm but direct: lead with what shipped + honest what-isn't. Deliver
drag-and-drop zips. Never claim done without grep-verifying render calls and checking the real repo.
