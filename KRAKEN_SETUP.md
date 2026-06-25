# KRAKEN — how to use it, what it unlocks, and the honest tradeoffs

## Short version
Kraken opens a **more real** experimental ground — specifically it gives you the ONE thing your
internal sim lacks: **real live bid/ask/spread (and order-book depth) with no keys, no account.**
That's the missing ingredient for a true Reality Audit. But the *Kraken CLI binary* is an awkward
fit for your GitHub-web-UI + Actions setup, so I wired the part that actually fits you instead.

## Two ways to use Kraken — and why I picked one
1. **Kraken CLI** (`curl … kraken-cli-installer.sh | sh`): installs a binary on a MACHINE and exposes
   an MCP server for AI agents. Great if you have a terminal / always-on box. But you run entirely
   through the GitHub web UI with no terminal, and the Actions runner is ephemeral (it resets every
   run), so installing a CLI there is fragile and buys little. **Not the right first step for you.**
2. **Kraken public REST API** (no keys): returns live best bid/ask, spread, and depth via plain HTTPS.
   Your Python ingestion already runs on the Actions runner, which CAN reach the internet. **This is
   the fit** — same real data, zero install, lives inside the system you already have.

## What I shipped (option 2)
- `silmaril/ingestion/kraken_spread.py` — pulls real bid/ask/spread from Kraken's public API for the
  symbols you trade, stdlib-only (zero new dependencies), fully defensive (partial/empty on any error,
  never blocks the cycle). Wired into the cycle **hourly** (minute < 10) so it adds no latency to most
  runs — important given your run-time worries.
- A **🐙 LIVE KRAKEN SPREAD** panel in Forensics that shows the live bid/ask/spread per symbol.

### Verifying it (important — I could NOT test it from here)
My build sandbox can only reach github/pypi/npm, NOT api.kraken.com, so this ships **unverified from
my side**. After you install it, the next top-of-hour Actions run will either populate
`KRAKEN_SPREAD.json` (panel fills with live spreads) or the run log will show "kraken spread skipped:
…". If the symbol coverage looks thin, the cause is Kraken's pair naming — the module maps via each
pair's `wsname` (e.g. "BTC/USD" → "BTC-USD"), which covers the majors; exotic names may need tuning.

## What this unlocks — the real Reality Audit
Right now your Reality Check applies a *documented fee model* (honest, but modeled). With real Kraken
spread captured per symbol, you can upgrade it to **measured** execution cost:
`live estimate = gross − fees − (real spread × notional) − modeled slippage`.
That turns "survives 87% (fee model)" into "survives X% (fees + real spread)" — a genuine reality
score built on measured data, not assumptions. That's the natural next build once spreads are flowing.

## Do you need more? Does it open a larger ground?
- **More real:** yes — measured spread/depth from a live venue beats mid-price sampling.
- **Larger universe:** Kraken lists a big USD spot universe; you can cross-check which of your 600+
  names actually quote on Kraken and how tight they are (the panel sorts by spread — tight = tradeable,
  wide = costly). That's a real-world tradeability filter you didn't have.
- **Live paper validation:** Kraken's CLI/futures demo can paper-trade against live prices. That's a
  separate, heavier integration (and needs the CLI or futures-demo account). Worth doing later to
  cross-validate signals, but the public-API spread capture is the high-value first step and it's done.

## On "no trades since 6:30 AM"
Most likely working as designed: your books only buy on a ≥3% drop and the trajectory filter rejects
weak setups. A calm overnight/morning tape where nothing breached the threshold = zero entries, which
is correct MR behavior (your Opportunity Audit already showed 0-of-628 cycles). The fix for the
*anxiety* is visibility: an "0 candidates because no asset dropped ≥3%" overnight line so silence is
explained rather than scary. That's a small, real, synthetic-free next build whenever you want it.
