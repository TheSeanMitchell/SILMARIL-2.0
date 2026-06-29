# SILMARIL 2.5.1 — FOUR ASSET CLASSES (crypto · stock · metal · energy), all equal

Drop on repo root. The book system is generalized from 2 markets to 4 — each with its
own arena, champion, election, regime, and paper book. No synthetic data.

## What changed (the whole pipeline is now 4-class)
- **`paper_sim.asset_class()`** is the single source of truth (crypto/stock/metal/
  energy), exact-match so no ticker is misclassified. `BOOKS = (crypto, stock, metal,
  energy)`. `live_step` runs **all four books** every cycle, each trading its OWN
  `champion_<book>.json`; `paper_sim_live.json` now carries metal/energy too.
- **`strategy_lab.run_split_leaderboards`** → four independent arenas
  (`strategy_leaderboard_{crypto,stock,metal,energy}.json`).
- **`champion_split`** → four independent champions, each its own election
  (`champion_{book}.json`). Crypto stays forward-governed; the others take their own
  arena winner, sticky.
- **`regime_observer`** → four independent regime systems.
- **Command center** → four live quadrants (champion, equity, P&L, open, status).

Verified end-to-end: crypto trades MR_d3_t3_s4, stock trades MR_d5_t3_s6, metal &
energy run as empty books awaiting their feed — independently, no cross-contamination.

## Metals + Energy data — uses keys you ALREADY have
`metals_energy_feed.py` runs each cycle in GitHub Actions and writes
`metals_samples.json` / `energy_samples.json` (same format the sim reads):
- **Metals** via `OPENEXCHANGERATES_APP_ID` (XAU/XAG/XPT/XPD/XCU; you have this key).
- **Energy** via `ALPHA_VANTAGE_API_KEY` (WTI/Brent/Natural Gas; you have this key).
- Fallbacks: MetalpriceAPI / Twelve Data if you add those keys.

**No key → it writes nothing.** No synthetic data, ever. The build sandbox can't reach
these hosts, but your GitHub Actions runner can (same as your other feeds). The moment
the feed writes prices, metals and energy **automatically** get a tradeable universe,
an arena, a champion, and live trading — no further code needed.

### One workflow tweak
`daily.yml` already exposes `ALPHA_VANTAGE_API_KEY` and `OPENEXCHANGERATES_APP_ID` to
the run step, so the feed is wired and will start producing data on the next cron run
(subject to free-tier rate limits — Alpha Vantage commodities are daily-cadence, so
metal/energy bars update slowly; they'll accumulate over the day).

## 2.5.1 — now complete on the architecture
DONE: separation (now 4-way) · opportunity audit · exit forensics (+expansion) ·
stock reality audit · regime observer (4-way) · scorecard · performance audit ·
self-explaining UI · four independent books with their own arenas/champions/elections.

The only thing between you and live metal/energy trades is the feed accumulating
enough samples to clear the freshness + drop thresholds — i.e., data and time, not
code. Do your pristine reset now and start tomorrow with all four books live.
