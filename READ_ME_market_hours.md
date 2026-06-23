# Market Hours on Each Quadrant

Each quadrant now shows when that asset class is active:

**CRYPTO · 24/5**
- Always trading (except Sun-Mon midnight UTC flip). Updates every cycle.

**STOCKS · 9:30-16:00 ET**
- NYSE market hours. Shows countdown ("opens in 45min", "OPEN NOW", or "closed · after hours").

**METALS · 24/5 spot**
- Gold/Silver/Platinum always quoted as spot prices. Updates every 10-15min (your cron cadence).

**ENERGY · daily 4:15 PM ET**
- Energy commodities (WTI/Brent/Natural Gas) update once daily from Alpha Vantage free tier.
- Next update typically 4:15 PM ET when the daily bar closes.

Hover over the status line for a tooltip with details (when it goes live, when next update is, etc.).

As soon as prices come in for metals/energy (first 1-2 cycles for metals, first trading day for energy),
the quadrants will show equity and open positions. The champions will stay None until the strategy
has enough samples to clear the freshness filter and drop threshold.
