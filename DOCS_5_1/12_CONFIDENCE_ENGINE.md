# 12 · THE CONFIDENCE ENGINE — every predictive signal, one number

**The gap it closed:** conviction sizing used to blend three inputs. Meanwhile the system computed a huge
arsenal of prediction signals that fed *nothing that traded* — most importantly **peak rhythm** (the
timing-between-peaks backbone). The confidence engine fuses them all.

## What it fuses (`confidence_engine.py` → `CONFIDENCE_ENGINE.json`, every cycle)
**5.1 FINAL — wired to NINE signals, every predictive metric the platform measures:**
| Signal | Source | Contribution | Weight |
|---|---|---|---|
| bounce reliability | fingerprint | how often this name's dips recover | 22% |
| rhythm regularity | peak_rhythm | is the high→low cycle predictable? | 16% |
| rhythm phase | peak_rhythm | near a trough (buy) or peak (avoid)? | 12% |
| MTF confluence | mtf_regime | multi-timeframe agreement | 12% |
| dip extension | fingerprint | deeper than the name's typical dip? | 10% |
| **timing alignment** | **timing_fingerprint** | is NOW this name's measured best-buy window? | 10% |
| **momentum exhaustion** | **momentum_chain** | is the downward run slowing (MR-ready)? | 8% |
| **conviction backing** | **conviction_ranking** | the independent multi-signal ranker's score | 6% |
| trend alignment | fingerprint | multi-timeframe trend tailwind | 4% |

The bolded three are new in 5.1 FINAL — the brain now reads timing fingerprints (per-symbol
time-of-day probability curves), momentum chains (multi-window momentum with exhaustion detection),
and the independent conviction ranker, so the confidence number reflects *everything* we measure.

Output per symbol: a blended 0-1 **confidence** score + the **component breakdown** (so the UI shows *why*),
plus a dedicated **rhythm-tradeability** score.

## The rhythm-tradeability score (your sideways-volatile theory, operationalized)
Flags names that are **reliably oscillating in a predictable band** — sideways, real amplitude, regular peak
spacing, not in a strong directional trend. This is the exact "constant predictable peak↔trough rhythm"
profile your theory targets. High scorers are the D-sleeve sniper's hunting ground and gold/metal's eventual
bread and butter. Shown as "RHYTHM-TRADEABLE LEADERS" in the MARKETS/STRATEGY tabs.

## Where it feeds
- **Conviction sizing** — the blended score now sizes wagers (replacing the 3-factor blend when available).
- **The D-sleeve** — only names above the confidence gate get sniped.

## Honest guardrail
This is measurement + blending. **Whether high confidence actually wins more is graded forward** (report
card / gates), never assumed. Ghost-amplitude prices (>15% "swings") are rejected so twins/glitches can't
inflate a rhythm score. Each component earns its weight by predicting — or loses it.
