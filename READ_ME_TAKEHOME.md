# SILMARIL — Take-Home After Fees + Threshold Sweep (the "cut the fat" tools)

Two new Forensics panels, both honest, both answering: how do we trade fewer and more profitable trades?

## 💰 DAILY TAKE-HOME (last 7 days) — real, reconciles to your Reality Check
Per Vegas-midnight day (you said keep midnight — kept), from the actual book: gross, the documented
54 bps/round-trip fee bill, and net kept. Right now it reads:
  - Jun 23: gross -$11.80 · fees -$96.15 · **NET -$107.95** (18 trips)  ← a losing day, fees made it worse
  - Jun 24: gross +$314.73 · fees -$172.92 · **NET +$141.81** (36 trips) ← good day, but 36 trips cost $173
  - Jun 25: gross +$128.69 · fees -$73.46 · **NET +$55.23** (17 trips)
Sum = **+$89.09** — exactly your lifetime Reality Check number. The panels agree. And the lesson is
right there: the 36-trip day paid the biggest fee bill. Fewer trips would keep more.

## 🎯 THRESHOLD SWEEP — measured proof of "fewer, deeper, profitable"
Simulated over REAL price history (top-45 crypto names, same engine as the drop×bounce champion — real
prices, no fabricated trades). For each threshold: how many trades fire, and net take-home PER TRADE
after fees. Every trade must clear **0.54%** just to pay fees, so:

DROP TRIGGER (bounce held at the live 3%):
  - drop≥2.0% → 1456 trades, **-$2.30/trade (LOSES)**
  - drop≥2.5% → 891 trades, **-$0.78/trade (LOSES)**
  - drop≥3.0% → 553 trades, **+$1.01/trade** ← your current setting, just barely profitable
  - drop≥4.0% → 195 trades, **+$1.91/trade**
  - drop≥4.5% → 96 trades, **+$3.09/trade**
  - drop≥6.0% → 11 trades, **+$7.82/trade** ← far fewer, far richer

BOUNCE TARGET (drop held 3%): small targets (1–2%) lose after fees; 2.5%+ clears; bigger targets earn
more per trade at lower hit rate. The faded rows in the panel are the money-losers — the fat to cut.

**The verdict, in your own data:** shallow dips are not just coin-flips — after fees they LOSE money.
Your 3% trigger sits right on the break-even line. Pushing deeper (4–6%) multiplies net-per-trade. This
is the single clearest lever you have, and now you can watch it every day.

## On your trajectory question — honest answer
You asked if bounce estimates are being auto-adjusted by trajectory over the last day/week/month.
**Not yet.** The sweep evaluates bounce targets against actual forward price paths, and the champion
engines RECOMMEND the best drop/bounce, but nothing yet auto-tunes the LIVE bounce target from rolling
trajectory. That auto-tuning IS the judge-mode step we mapped — gather 1–2 weeks, add it as a shadow
champion, A/B it, promote only if it beats the incumbent. This sweep is the dial you'll watch to know
it's working.

## Files
NEW: silmaril/execution/threshold_takehome.py · WIRED: silmaril/cli.py (hourly) ·
UI: docs/index.html (💰 Daily Take-Home + 🎯 Threshold Sweep) · FRESH: docs/data/THRESHOLD_TAKEHOME.json
No investment logic touched — all observational.
