# 08 · DATA ROADMAP — feeds, keys, tokens, expansion order

## Current feeds (2-deep fallback goal per group; live depth on the dashboard via health_lights)
Crypto: coingecko + freecryptoapi + **ccxt waterfall (binanceus→kraken→coinbase, 5.1)** — the
waterfall is what grows "seen 90" toward the full liquid universe and feeds MKR-class charts.
Stock: yfinance + alpaca(pricing) + finnhub/AV/FMP/twelve_data. Metals: yfinance+OXR+AV (OXR/AV
budget-capped, never drained). Energy: yfinance+AV+tiingo. News: marketaux+newsapi+google-RSS.
Macro: FRED (keyed) when BOOK_RATES admission begins.

## Cron token (the expiring-PAT problem, solved once)
GitHub → Settings → Developer settings → **Fine-grained personal access tokens** → Generate:
Resource owner = your account · Repository access = ONLY `SILMARIL-2.0` · Permissions: Actions
**Read and write** (Contents not required for `workflow_dispatch`) · **Expiration: No expiration**.
Put the token in the cron-runner's Authorization header (`Bearer <token>`), endpoint
`POST /repos/<owner>/SILMARIL-2.0/actions/workflows/daily.yml/dispatches` body `{"ref":"main"}`.
Never expires; revoke/rotate from the same page if ever leaked. The in-repo `*/10` fallback keeps
the pulse alive regardless.

## Expansion order (admission-gated, Part-III law; no dates)
1. ccxt waterfall breadth → census fresh% up → fingerprints toward full coverage (in flight now).
2. FRED spine (macro fingerprint) → BOOK_RATES M0–M2.
3. BOOK_ROTATION (index/ETF monthly momentum) to M3 — the calm-money null-beater test.
4. CFTC COT weekly + funding/OI observe cards. 5. FX stays M0–M1 until a real bid/ask practice feed.
Every source enters OBSERVE, feeds a named module, and gets a contracts row before it can matter.
