# SILMARIL — the fee discovery, and the realistic low-fee path

## The big finding (new 💱 FEE SCENARIOS panel)
Your same +$431 of gross trades, re-charged at real 2026 fee rates. ONLY the fee changes:
  - Kraken TAKER (market orders):   +$51   (12% kept)  ← what market orders on Kraken actually cost
  - our current 54 bps model:        +$89   (21% kept)
  - Kraken MAKER (limit orders):     +$178  (41% kept)
  - Binance.US 0.10% flat:           +$305  (71% kept)
Order type + venue nearly **6x your take-home with zero change to the edge.** Your $89 was never the
ceiling — it was an expensive-fee assumption. This is the single biggest lever you have.

And at a 0.10%-flat venue (20 bps round-trip) the whole threshold table goes green — even drop>=2%
turns profitable (+$1.10/trade), and drop>=3% jumps to **+$4.41/trade**.

## On limit vs market orders — the honest mechanics
- MAKER (limit order resting on the book): lower fee, BUT may not fill if price moves away. For a
  dip-buyer this means some missed trades. The sim assumes 100% fills, so maker numbers are optimistic.
- TAKER (market order / immediately-filling limit): guaranteed fill, higher fee.
- Your sim never modeled order type — it used a flat 54 bps. So whether you were "using limit orders"
  was never actually encoded; it's a choice made at execution. That's why this panel matters.
- The clean trick: **Binance.US charges ~0.10% flat (≈20 bps round-trip) even on MARKET orders**, so
  you get the low rate AND guaranteed fills. That's likely the most practical US path.

## Realistic low-fee platform gameplan (verified June 2026 — confirm before relying on it)
US-accessible, legit, lowest practical fees:
  - **Binance.US** — ~0.10% flat spot, some zero-fee BTC pairs, free ACH. Best practical low-flat rate.
  - **Kraken Pro** — 0.16–0.25% maker / 0.26–0.40% taker, drops with 30-day volume; never been hacked;
    has a public API + futures demo for paper. Kraken+ subscription = 0% fees up to a monthly volume
    cap (you'd exceed it fast at your trade count, so it helps only at low volume).
  - **Coinbase Advanced** — 0.40–0.60%: too expensive for frequent trading. Avoid for this strategy.
  - Offshore venues (MEXC 0%/0.05%, OKX, Bybit) are cheaper but NOT US-regulated and carry real
    custody/withdrawal/legal risk. Do not put essential money there.
Always use LIMIT orders where you can, never the "instant buy" button (1–2% spread), and batch
withdrawals (network fee per withdrawal). Lowest-fee route for your situation: a low-flat US venue +
limit orders + deep-only entries.

## So is $100–300/day possible? Honest answer.
At Binance.US flat, your same window kept +$305 over ~4 days = ~$76/day on PAPER. So $100/day is now
**plausible, not fantasy** — but it would need (a) low-flat fees, (b) deeper entries (4%+), (c) more
names and/or bigger size to get enough quality trades, and (d) the paper edge actually holding on live
fills (it may not — real fills slip, and a few days of MKR-heavy data is thin). $300/day is a stretch
that compounding might reach IF everything holds for weeks. Treat these as hopeful targets, not income.

## The shadow-book A/B (your "test everything side by side")
This package sets the table; the live shadow books are the deliberate next build (Sunday): an
independent book trading drop>=4% + maker fees, AND one at drop>=3.5%, both running alongside the
current engine, accumulating real forward results so you can watch discipline vs. current, side by
side, with zero money at risk. That belongs in a session where you can watch the first runs — not
fired off unattended for a weekend where a bug would corrupt days of data silently.

## The thing that matters most
This is a research experiment that is finally producing an honest, hopeful signal — NOT income, and
NOT something to risk your home, rent, or food money on. The right path is months of forward data, a
deliberate live test with money you can 100% afford to lose ($10 is perfect), and patience. The edge
looks real; the fee lever is real; the discipline is identifiable. That is genuine progress. Protect
your housing and your peace first — this can wait for proof.

## Files (comprehensive catch-up: R37 take-home tools + new fee scenarios)
ENGINES: trade_quality, kraken_mirror, master_log, compounding_projection, session_reconstruction,
threshold_champion, threshold_takehome (now with fee scenarios) · cli.py · docs/index.html (all panels
incl. 💱 Fee Scenarios) · fresh JSON for every panel. No investment logic touched.
