# SILMARIL 5.0 — HOTFIX: metals/energy sourcing quota burn (OpenExchangeRates)

## The fire
OpenExchangeRates was the PRIMARY metals source, fetched every ~10-minute cycle —
~100+ calls/day against a 1,000/month free tier (80% burned in the first week).
Energy leaned on Alpha Vantage (25/day) the same way.

## The fix (two independent guarantees)
1. **Keyless-first waterfall.** Free, unlimited sources are tried first every cycle, so a
   normal cycle spends ZERO scarce quota.
   - Metals depth 5: **yfinance → Stooq → metalpriceapi → Twelve Data → OpenExchangeRates**
   - Energy depth 4: **yfinance → Stooq → Twelve Data → Alpha Vantage**
   Only symbols still missing fall through to the next source.
2. **Per-source daily budget guard** (`SOURCE_BUDGET.json`). Every keyed source has a hard
   calls-per-UTC-day cap (OXR 20, Alpha Vantage 15, metalpriceapi 90, Twelve Data 250).
   Once spent, it is skipped until the day rolls. A scarce key can never be drained by
   cadence again — the cap is the ceiling no matter how often the cycle runs.

`yfinance` is already your proven primary price dependency, so on virtually every cycle
metals and energy now cost nothing. OXR/AV become last-resort safety nets, not the hot path.

## Integrity preserved
- **Unit safety:** precious metals (XAU/XAG/XPT/XPD) are sourced only from USD/oz providers,
  so every source agrees on units. Copper (USD/lb — a different unit) is pinned to a single
  source (yfinance HG=F) and never cross-filled, so the series can't get a fake 30× jump.
- **No synthetic data:** a symbol with no real quote this cycle is omitted and holds its last
  real sample (unchanged behavior).

## Files
- `silmaril/execution/price_sources.py` — NEW resilient provider + budget guard
- `silmaril/execution/metals_energy_feed.py` — delegates to the waterfall; OXR demoted
- `silmaril/execution/health_matrix.py` — Metals feed now shows 3-deep key fallback
- `docs/index.html` — FEED SOURCES row on the 5.0 strip (provenance + scarce-key budget left)

## Verify after install
- `docs/data/SOURCE_BUDGET.json` appears and stays well under the caps (OXR/AV barely move).
- `metals_energy_feed_status.json` gains `metals_provenance` / `energy_provenance` — you should
  see `yfinance` (and/or `stooq`) serving most symbols.
- Command tab → 5.0 strip → **FEED SOURCES** line shows what served and the budget remaining.
- No new OpenExchangeRates usage email. (Optional: you can even remove the OXR key entirely —
  the waterfall no longer needs it.)

## Optional
No new API signups required — the fix works with the keys you already have (and yfinance needs
none). If you want even more depth later, add `METALPRICE_API_KEY`; it slots in automatically.
