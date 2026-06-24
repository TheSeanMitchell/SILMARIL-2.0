# SILMARIL 2.5.3 — Health matrix FIXED + fallback framework + what to plug in

## First: your crypto feed was never down. The RED light was my bug.
Your health panel showed "🔴 Crypto prices (CCXT) no file yet" because my health
matrix looked for `ccxt_samples.json` (doesn't exist) and an `updated` field that your
files don't use. Your real crypto/stock prices live in `price_samples.json` —
**100% coverage, 627/627 priced, fresh to the minute.** Crypto "stopped trading"
because the Opportunity Audit shows **0 qualifying oversold setups this cycle** — the
system behaving correctly, not a disconnection. Nothing was broken.

## Health matrix rewritten to read the REAL source (api_health.json)
`health_matrix.py` now reads your authoritative `api_health.json` (the same data the
legacy page uses) plus a robust freshness check that falls back to file mtime and
recognises `last_recorded`. Result on your data:
  🟢 Prices 100% coverage · 🟢 News 188 sources · 🟢 Metals · 🟢 Energy · 🟢 Paper sim
  🟡 Broker LEGACY (20 Alpaca fractional-order errors/48h — real, see below)
Accurate lights. The only non-green is the Alpaca broker, which is a real issue.

## Unified health panel on the MAIN page (legacy richness + new style)
The footer panel now shows EVERYTHING: every feed light, data-source fallback depth per
need, files-fresh count, price coverage, news source count, cron pressure per provider,
domain clocks, storage. One glance, the whole pipeline.

## Fallback framework (silmaril/data_sources/multi_source.py)
Each data need now has an ordered provider chain. `fetch_with_fallback(need, symbol)`
tries each until one returns data, so a single provider outage falls through to the next
WITHIN THE SAME RUN — you never lose a feed for more than the fall-through time.
- **crypto_price**: CoinGecko → CryptoCompare → **Binance public (keyless, always on)**
  So crypto can NEVER fully go dark — the last link needs no key.
- **stock_price**: Finnhub → AlphaVantage → TwelveData → FMP
Add a key as a secret and it auto-joins the chain. No code change needed.

The health panel's "DATA-SOURCE FALLBACK DEPTH" row shows X/Y sources ready per need —
green when 2+ are configured (a fallback exists), so you can see at a glance where you're
single-threaded.

## The Alpaca broker YELLOW (real issue worth fixing)
`api_health.json` shows 20 errors/48h: `HTTP 422 fractional orders`. Alpaca is rejecting
fractional crypto orders on the LEGACY paper account. That's an Alpaca order-sizing issue
(round to whole units or use notional orders), separate from the internal sim. Flagging
it — it's the one genuinely non-green light.

================================================================================
## WHAT TO PLUG IN — secrets to add for full fallback depth (you asked)
================================================================================
The health matrix checks these EXACT env-var names. You already have several (Alpha
Vantage, FMP, Finnhub, OXR, EIA, plus marketaux/newsapi/twelve_data per your cron meter).
To get every chain to 2+ providers (no single point of failure), add the ones you're missing:

PRIORITY 1 — crypto fallback (only Binance-public right now):
  COINGECKO_API_KEY        (free demo tier — coingecko.com/api)
  CRYPTOCOMPARE_API_KEY    (free tier — min-api.cryptocompare.com)

PRIORITY 2 — metals fallback (only OpenExchangeRates right now):
  METALPRICE_API_KEY       (free — metalpriceapi.com)   OR
  METALS_DEV_API_KEY       (free 100/mo — metals.dev)

PRIORITY 3 — extra stock depth (optional, you may already have 2+):
  TIINGO_API_KEY           (free — tiingo.com)
  POLYGON_API_KEY          (free tier — polygon.io)

ALREADY EXPECTED (just confirm the secret NAMES match exactly):
  ALPHA_VANTAGE_API_KEY · FMP_API_KEY · FINNHUB_API_KEY · TWELVE_DATA_API_KEY
  OPENEXCHANGERATES_APP_ID · EIA_API_KEY · NEWSAPI_KEY · MARKETAUX_API_KEY
  FRED_API_KEY (macro) · ALPACA_API_KEY / ALPACA_SECRET_KEY (broker)

If your existing secrets use DIFFERENT names than the list above, tell me the names and
I'll map them — the health matrix and fallback chains key off these exact strings.

## Cron schedule for all-green
Your feeds are green at the current cadence. The only pressure is free-tier daily call
limits (your cron-pressure meter shows 0% today — lots of headroom). The 10-min crypto
cadence is fine. For metals/energy the free APIs are daily-ish, so those update slower by
design, not by failure. With fallback chains in place, even if one provider hits its daily
cap, the next in the chain carries that run.

## Honest 2.5.3 status
This session fixed the reliability/observability problem you raised (health accuracy +
unified panel + fallback framework). Still pending from full 2.5.3: Decision Trace Engine,
Learning Feedback Engine, Capital Router Explainer, Stock Sector Recovery. Those remain the
real remainder for the next pass.
