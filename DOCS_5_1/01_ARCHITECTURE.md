# 01 · ARCHITECTURE — the machine's shape

## Layers (bottom → top)
1. **Feeds** — coingecko/freecryptoapi + ccxt waterfall (binanceus→kraken→coinbase, 5.1) for crypto;
   yfinance/alpaca/finnhub/AV/FMP/twelve_data for stock; yfinance+OXR+AV metals; yfinance+AV+tiingo
   energy; marketaux/newsapi/google-RSS news; Alpaca is **pricing-only** (`_broker_policy`).
2. **Ingestion & marks** — `price_samples.json` (+`ccxt_samples/metals_samples/energy_samples`);
   daily-backfill candles (`T00:00:00`) are filtered from every signal path.
3. **Books** — five trading books (`paper_book_{crypto,stock,metal,energy,aggressive}.json`) run by
   ONE exit/entry code path in `paper_sim.live_step`; GEKKO = fixed-knob aggressive probe (2%→2%/6%),
   fingerprint-fitting BYPASSED so it stays a control. Four nulls in `BENCH_BOOKS.json`
   (CASH/SPY/HODL/EQW) mark-only. Master (`MASTER_ACCOUNT.json`) WATCHES until the live-money bar.
4. **Governance** — `champion_validation` groups closed trades by ENTERING STRATEGY per book →
   survivability; `champion.py` elects crypto every cycle (sticky, ≥5 trades, 15-pt margin);
   `champion_split` flips non-crypto books to forward governance the moment they qualify.
5. **Verification & research** — contracts, invariants, census, utilization, RA/TQ/calibration,
   labs (baseline/ladder/weekly/parity/complexity), Research-OS, Conductor C0→C1, gate evidence,
   evidence scorecard.
6. **UI** — `docs/index.html` (GitHub Pages), single-file, renderer-per-panel, stores are the API.

## Lanes (GitHub Actions; ALL state writers share concurrency group `silmaril-state`)
| Lane | Trigger | Carries |
|---|---|---|
| PULSE `daily.yml` | external cron + in-repo `*/10` fallback | ingest→mark→decide→execute→verify + the full 5.1 spine |
| HOURLY `hourly.yml` | `:07` | arena compact, RA/TQ, governance, sanitize |
| ANALYTICS `analytics.yml` | 3×/day | deep suite; stamps `deep_heartbeat.json` start/finish |
| WEEKLY `weekly_backup.yml` | Sun | backup + weekly scorecard |
| SELFTEST `selftest.yml` | Mon + dispatch | regression battery (read-only) |
Push discipline: fetch → `rebase -X theirs` → push, retried; run_lock guards the live cycle.

## The stores contract
Every JSON store: atomic write (`atomic_io.write_json_atomic`), `generated_at` content stamp,
schema + producer→consumer row in `store_contracts` (freshness by CONTENT age — git checkout
resets mtimes, so mtime is never trusted). A dead producer = RED light with the store named.
