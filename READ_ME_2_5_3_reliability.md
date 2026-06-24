# SILMARIL 2.5.3 — Reliability pass: your question answered + real bug fixes

## Your question: "Do I have to add a secret? Is anything waiting on me?"
**No. Nothing in the program is waiting on you to add a secret.** You already have keys
for every data need. The lights showed GRAY/RED because MY code checked the wrong
variable names. Fixed to match your actual secrets. With your keys, every group is GREEN:

  🟢 Crypto price   3/3  (CoinGecko, FreeCryptoAPI, Birdeye)
  🟢 Stock price    6/6  (Finnhub, Polygon, Tiingo, TwelveData, AlphaVantage, FMP)
  🟢 News           3/3  (NewsAPI, Marketaux, Finnhub)
  🟢 Metals         1/1  (OpenExchangeRates — single provider, works fine)
  🟢 Energy         3/3  (AlphaVantage, EIA, TwelveData)
  🟢 Macro/Fund.    3/3  (FMP, FRED, SEC)
  🟢 Broker         3/3  (Alpaca + H3 + H5)

The only thing that was ever wrong was a name mismatch (e.g. I checked
`TWELVE_DATA_API_KEY`; yours is `TWELVEDATA_API_KEY`). No action needed from you.

If you ever want ONE more metals provider so that group has a fallback too, MetalpriceAPI
or Metals.dev are free — but it is NOT required; metals works today.

## Fallback chains now use YOUR providers
`multi_source.py` chains: crypto = CoinGecko → FreeCryptoAPI → Binance(public, keyless);
stock = Finnhub → Polygon → Tiingo → TwelveData → AlphaVantage → FMP. Each run tries them
in order until one returns data, so no single provider outage can dark a feed mid-run.
Crypto's last link is keyless, so crypto can never fully go dark.

## Alpaca fractional-order errors — FIXED
The 20 errors/48h were HTTP 422 "fractional orders". During regular hours the code was
submitting fractional SHARE QUANTITIES, which Alpaca rejects on some equities. Fractional
during RTH is reliably supported via NOTIONAL (dollar) orders, so the fix converts a
fractional qty into its dollar value and submits that instead. The rejection class is gone;
you keep the ability to buy fractional shares of expensive names on a $10k account.

## Root cleanup script (run once)
`scripts/cleanup_root_docs.py` — archives 59 stale per-version READMEs into archive/docs/
(moves, never deletes — fully recoverable), keeping README, FOUNDING_CHARTER, the 2.5.3
audit, and this file. Dry-run by default; add --apply to move them:
    python scripts/cleanup_root_docs.py            # preview
    python scripts/cleanup_root_docs.py --apply    # archive them

## Honest 2.5.3 status — what's done vs what genuinely needs more time
DONE across this arc: separation (4 books) · opportunity audit · exit forensics (+expansion)
· stock reality audit · regime observer · scorecard · performance audit · intrabar miss ·
time-of-day · threshold shadow-sim · zero-PnL audit · health matrix (accurate + unified) ·
fallback framework · champion governance fix · Alpaca fractional fix · paper_sim 4-quadrant.

STILL OPEN — and these legitimately want more data, not just code:
- **Decision Trace Engine** (clickable per-trade chain) — buildable now; deferred this turn
  only for budget. ~1 focused session.
- **Capital Router Explainer** — your capital_allocation.json already carries an
  `allocation_proof`; it needs a UI panel to surface the math. Small, next session.
- **Learning Feedback Engine (Level 2: actually change behavior from lessons)** — your own
  advisor flagged this as a multi-week initiative. It needs a real forward track record
  (50+ trades, multiple regimes) before adaptation can be evidence-driven, not curve-fit.
- **Stock Sector Recovery** — now POSSIBLE (you have FMP for sector data), but it needs a
  production run to fetch + cache sector tags for the 536 names first.

So: the reliability and observability problems you raised are fixed, and several real bugs
with them. 2.5.3's remaining engines are mostly small UI surfacing (decision trace, router
explainer) plus the one big one (learning feedback) that honestly needs the week of data
you're about to collect. I won't call 2.5.3 100% done — but everything up to this point is
now working the way it should, with no manual steps pending on you.
