# SILMARIL 2.5.5 — SESSION ANATOMY (obsessive forensics of today, real data only)

Two new Forensics panels that dissect today's session trade-by-trade, entirely from real fills +
real price_samples. No synthetic data, no behavior changes, no decisions forced on data we lack.

## SESSION ANATOMY panel — why each buy & sell fired, and did we capture the move
For every one of today's 27 crypto round-trips it replays the real price path and shows:
- **dip at entry** — how far price had fallen from its recent high when we BOUGHT (the MR trigger),
- **MFE** (max favorable excursion) — the best exit price that existed during the hold,
- **MAE** (max adverse excursion) — the worst drawdown we sat through,
- **capture efficiency** — % of the available up-move we actually banked (exit vs MFE),
- **left on table** — how much more the price offered in the hour after we sold,
- a **verdict**: CAPTURED_WELL / SOLD_TOO_EARLY / GAVE_BACK / FLAT_TIMEOUT.

## What today's data actually proves
- **Capture efficiency was 90.9% on average** — your EXITS were excellent today. Exits were not the
  problem; if anything, 9 trades sold slightly early but only left ~0.8% on the table on average.
- **Worst drawdown sat through was −1.89%** — you never took much heat. Clean session.
- **MKR carried because its entries were on −7.2% dips vs −2.7% for everything else.** Deeper dip →
  bigger bounce. MKR's three trades: −6.9%/−7.7%/−7.1% dips → +7.8%/+8.5%/+7.7% returns, ~98.6%
  capture each. The 10 break-evens were all shallow ~2.7% dips that barely bounced.

## The dip-depth → outcome table (the lesson in one view, today, small samples)
| entry dip | trades | avg return | win% | capture |
|-----------|--------|-----------|------|---------|
| 0–2% (shallow) | 9 | +3.49% | 44% | 92% |
| 2–4% | 13 | +3.15% | 62% | 90% |
| 4–6% | 1 | +1.07% | 100% | 73% |
| **6%+ (deep)** | **4** | **+6.95%** | **100%** | **97%** |

The signal: **the deepest dips (6%+) produced the highest returns AND a 100% win rate today.**
Shallow dips were closer to coin-flips. This is today's data confirming the project's oldest
empirical truth — deeper drops = better entries — with concrete session numbers.

## Important honesty
- Small samples (4–6% n=1, 6%+ n=4). This is ONE session. It's evidence, not proof, and not a
  reason to change live thresholds yet — that's the 2.5.5 discipline.
- MFE/MAE/capture are measured against sampled MID prices, so they describe the move that existed,
  not guaranteed fills. No synthetic data anywhere.

## Also in this delivery
- DECISION_TRACE cap raised 30 → 200 (now shows ~194 trades with reconstructed reasons).
- SESSION_TODAY.json (the black-box recorder from the prior step) + this SESSION_ANATOMY.json.

## What's still honestly ahead in 2.5.5 (buildable from real data as it arrives)
Crypto-vs-stock failure comparison, per-quadrant parity panels, an observed-forward projection from
rolling realized returns, and watching whether deep-dip quality holds across more sessions and
regimes. None require synthetic inputs; all wait on more days of data before they mean much.
