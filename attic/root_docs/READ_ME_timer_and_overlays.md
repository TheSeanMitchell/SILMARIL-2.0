# SILMARIL 2.5.4 — Timer/Edge-Capture overhaul + chart overlays that actually overlay

## 1. THE TIMER ANSWER YOU ASKED FOR (top priority) — TIMER_OPTIMIZATION.json + panel
New simulation replays EVERY closed trade under a grid of hold-timers (30m…12h, and NO timer),
taking the earliest of target-hit / stop-hit / timeout, then finds the timer that captures the
most edge per quadrant. On your real data:

- **CRYPTO (40 trades): optimal timer ≈ 30 min → +0.386%/trade vs 0.309% today (+0.077%).**
  The curve: 30m +0.386% (best) → decays → brief bump at 480m (+0.183%) → negative past 600m/none.
- **Primary leak: SOLD TOO LATE on 27 of 40 trades** (only 13 sold too early). Crypto MR bounces
  fast then fades — a SHORT timer takes the bounce; holding longer gives it back. That is the
  direct answer to "buy/sell too early or late": for crypto, we exit too LATE, and a ~30-min cap
  beats everything including no-timer.
- Stock/Metal/Energy: not enough closed trades to simulate yet (books mostly flat) — the engine
  is wired and will fill those quadrants independently as they trade. Each quadrant is evaluated
  and recommended on its OWN (localized), exactly as asked.

This is measurement/simulation — it RECOMMENDS the timer; it does not flip the live timer during
the 2.5.5 learning pause. When you un-pause, champion the recommended timer per book like any
other parameter. The leak breakdown tells you which lever: sold_too_late → shorten/cap; sold_too_
early → lengthen/remove; thesis_slow → it's entry/regime, not the timer.

## 2. CHART OVERLAYS — now actually drawn (this was the repeated miss)
The overlays were blank because **all four books are flat right now (0 open positions)** and the
chart only drew open-position lines. Fixed by consolidating everything into CHART_OVERLAYS.json
(56 symbols) and drawing it whether or not a position is open:
- **GOLD target line** — the cash-out-hope price (from the open position, or the last trade here).
- **Buy marker (▲)** at every past entry, **sell marker (▼ green/red)** at every past exit.
- **Dr Strange projection** — a purple dashed line + label to the Monte-Carlo expected price
  (direction + median % over 3 days, e.g. "DrStrange DOWN −1.77%").
- **Peak-rhythm next-peak** marker (bounce timing).
- Stats panel now has a **PREDICTIONS & SIGNALS** block: Dr Strange, Conviction (signal + how many
  agents back it), and the symbol's past-trade W/L record + last exit.

## 3. HOVER NOW WORKS ON PAST-TRADE ROWS (and everywhere)
The trade rows render the symbol as a bare text node after a "SELL/BUY" badge, so the old auto-
tagger (which skipped any cell with a child element) never caught it. The tagger now also wraps
ticker **text nodes**, so hovering/tapping a symbol in any recent-trades table — cockpit, legacy,
or the new front-page table — pops the chart.

## 4. FRONT PAGE now has trade history
Added a "RECENT TRADES — all books" panel to the main page (crypto + stock, 25 each), every symbol
hoverable/clickable for its chart, like the cockpit.

## 5. UI tweaks you asked for
- Header is now **SILMARIL 2.5.4**, bolder (weight 900), "· 4-QUADRANT LAB" removed. I will not
  touch the front header again unless you say so.
- Dark/Light button shrunk to a small 🌙 pinned to the top-right corner.

## Honest notes for your judges
- Overlays only appear for symbols that have a trade/position/prediction. A random coin with no
  history shows price only — correct, not a bug.
- Still a line chart (no candlesticks/volume) because the feed stores [time, price] only. Unchanged
  from last note: real candles need OHLCV capture in the sampler first (a 2.5.5 data task).
- Timer recommendation for non-crypto books is DATA-GATED until they accumulate trades.
