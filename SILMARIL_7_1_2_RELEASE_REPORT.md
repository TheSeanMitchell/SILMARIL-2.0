# SILMARIL 7.1.2 — "PRICE TRUTH" · the square waves, the unreal $200, and the sketchy leaderboards were ONE disease with FOUR causes

**Battery: 111/111 green** on the full tree, on a genuinely reset tree, and on a simulated install over your 11 PM backup. Every fix below was measured against YOUR real tape before packaging, not reasoned about.

**No reset needed. Do not reset.** Every fix is code-side; your fresh 05:04 UTC clock keeps running.

---

## THE HEADLINE: the biggest cause was my own 7.1.0 bug, and your eyes caught what my tests missed

7.1.0's one-key law unioned every spelling of a symbol on the assumption that `DOGEUSDT` and `DOGE-USD` are the same asset at the same price. On your tape that assumption was **false for 271 of 358 overlapping ccxt keys**:

| canonical | primary tape | ccxt spelling | conflict |
|---|---|---|---|
| APT-USD | $0.000131 | APTUSD $4.376 | **33,000×** |
| ARB-USD | $0.000757 | ARBUSD $1.130 | 1,492× |
| YFI-USD | $2,087 | YFIUSD $6,235 | 3.0× |
| ENJ-USD | $0.0271 | ENJUSD $0.2842 | 10.5× |
| LDO-USD | $0.371 | LDOUSD $1.842 | 5.0× |

Blending those made the tape **alternate between price scales at adjacent timestamps**. That single bug produced every symptom you reported:

- **"Graph looks the same for ENJ, YFI, LDO, XTZ, BF-B, BRK-B"** — they all became square waves. Measured repeat-rate damage: LDO 38%→58%, ENJ 2%→42%, YFI 17%→48%, XTZ 15%→46%.
- **The LDO dossier's "regular 144m cycle · RHYTHM-TRADEABLE (sideways+predictable)"** — peak detection dutifully found "peaks" in a scale oscillation and reported a heartbeat.
- **"Account sold it for a profit of $200. That didn't seem real."** It wasn't. A book marking against a series that jumps between price scales can book a windfall that never existed.

You were right on every count, and the reset was the correct call.

---

## FOUR FIXES, EACH WITH A TRIPWIRE

### 1 · THE SCALE-GUARDED UNION (`canon_keys.py`) — tripwire T113
A spelling now joins a canonical series **only** if an outside venue or a **time-aligned** price check (same moments, ≤30 min apart, within 5%) proves it is the same asset at the same scale. Everything else is rejected with a named reason and journaled — never blended, never silently dropped. Measured on your data: 298 rejections (245 `FROZEN_SERIES`, 50 `UNVERIFIABLE_NO_OVERLAP`, 3 `SCALE_CONFLICT`). Verified same-scale feeds still union normally, so DOGE gained real depth (624→923 prints) and BTC (625→924). **The square waves are gone.**

### 2 · THE PRICE TRUTH GATE (new `price_truth.py`) — tripwire T114
Your question was the hard one: *"Is there a way to safely remove the issue without blocking out real things we can actually invest in?"* Yes — by making the test **resolution, never price magnitude**. Each cycle every feed is graded on one question: *can this feed even express the move our strategy needs?* If the smallest price step the venue reports is coarser than the edge we're chasing, every "dip" on that name is the tick size, not the market.

Grades: **OK** (usable) · **COARSE** (real but too blocky) · **QUANTIZED** (the shape is the tick size) · **FROZEN** (a dead feed wearing a price) · **DISPUTED** (real venues disagree with us).

Only OK tapes may be **traded, fitted, or scored in the arena**. Measured on your universe: 650 tradeable, 148 quarantined, and critically —

- MOG-USD → **QUANTIZED** (3 levels, 10.6% tick vs 6% needed) → blocked
- APT-USD → **FROZEN** (1 price across 625 prints) → blocked
- **BF-B, BRK-B, GLD, SLV, GDX, USO, UNG, BNO → all OK and fully tradeable.** Equity-class names are measured on **regular-session prints only**, so an ETF flat over a closed weekend is never quarantined. A closed market is the calendar, not a broken feed.
- A sub-penny coin with a fine tick stays tradeable — the gate is asserted against false positives, not just false negatives.

Nothing is thrown away: excluded names keep collecting tape and are **re-graded every cycle**, so a feed that improves re-enters on its own. Knob `price_truth` · KILL `mode:"off"`.

### 3 · THE SURVIVORSHIP LAW (`strategy_lab.py`) — tripwire T115
You called the quadrant leaderboards "sketch." They were, and this one was pre-existing. `TIMEOUT_EXIT` is False, so a trade that hit neither target nor stop walked to the end of the window and then `if oc is None: break` **discarded it**. The arena counted only trades that *resolved* — and on a drifting tape a +5% target resolves constantly while a −12% stop almost never does, so the survivors were overwhelmingly winners.

| stock arena, same tape | before | after |
|---|---|---|
| best strategy | MR_d1_t5_s12 | **MR_d4_t3_s12** |
| win rate | 99.0% | **54.1%** |
| mean net/trade | +5.588% | **+0.612%** |

Unresolved positions are now marked to the last real price and counted, exactly as a live book carries them, and reported separately (`resolved` vs `open_marks`) so a mark can never be mistaken for a fill. **Note the champion changed** — the bias wasn't just inflating scores, it was electing the wrong strategy.

### 4 · THE SESSION-CONTINUITY LAW (`strategy_lab.py`) — tripwire T115
`_bt_one` walks a bare price list and treats index adjacency as continuous time, so an equity trade opened at 3pm Monday could "exit" into Tuesday's opening gap — a move no intraday strategy could ever have captured. Series are now cut at gaps >90 min and each segment backtested alone. Crypto is 24/7 and rarely segments (there it only splits genuine feed outages, also correct). 633 names segmented on your tape.

### Bonus: a latent contradiction closed
The reset script preserved `VENUE_UNIVERSE.json` while the registry classed it DERIVED — so the tripwire called the preserved copy a stale lie on every fresh tree. Reclassed LEARNING, and the reset now **rebuilds the store registry on the way out** so that class of self-contradiction can't recur.

---

## WHERE YOU'LL SEE IT

- **Chart modal** — the feed grade is a header chip and an amber banner carrying the authoritative verdict (the same grade that decides whether the engine will trade the name), plus "EXCLUDED from entries and from fitting until the feed improves."
- **Symbol dossier** — on an untrusted feed the rhythm, next-peak ETA and bounce likelihood are **struck out** behind a FEED banner instead of printing confident numbers. LDO can no longer claim a 144m cycle read off a square wave.
- **Quadrant leaderboards** — carry `feeds_excluded`, `names_segmented`, `resolved` vs `open_marks`, and both laws in plain text.
- **PROJECT HEALTH** — now reports feed truth: `650/1074 tapes tradeable · quarantined 148 (59 frozen, 53 quantized, 36 coarse)`. A cockpit reporting "feeds active" while a third of the tape is broken is the panel that let this through.

## INSTALL (11 files, drag-and-drop, exact paths)

```
silmaril/execution/price_truth.py      (NEW)    silmaril/execution/canon_keys.py
silmaril/execution/paper_sim.py                 silmaril/execution/strategy_lab.py
silmaril/execution/strategy_lab_abcd.py         silmaril/execution/store_registry.py
silmaril/cli.py                                 docs/index.html
docs/silmaril_chart.js                          scripts/selftest_5_1.py
scripts/reset_internal_clean.py                 SILMARIL_7_1_2_RELEASE_REPORT.md (root)
```
Hard-refresh the dashboard after the Pages deploy. **One expected note:** your very first `selftest` run may show T32 amber because `PRICE_TRUTH.json` and `brag.json` aren't in the store registry yet — the registry self-heals on the first cycle and T32 goes green (verified: 111/111 immediately after one registry rebuild).

## WEEK-READINESS CHECK (run against your tree, with 7.1.2 installed)

| check | state |
|---|---|
| scheduled live writers | **`daily.yml` only** — no lane can overwrite another |
| feed grading | 650/1074 tradeable, 148 quarantined, 276 still gathering prints |
| pyramid arming | crypto correctly `OBSERVE — workshop must promote a sleeve`; others market-closed |
| fingerprint hygiene | 424 untrustworthy names excluded, **zero leakage** into fitted cards |
| data budget | 77 MB total / 22.8 MB price samples; compaction + prune wired into the daily lane |
| tripwires | 111/111 on full, reset, and installed trees |

Expect the books to stay quiet at first — that's the arming gate, not a fault. What should move day over day: `price truth` counts (UNKNOWN falling as prints accumulate), sleeve closes, then the first PROMOTED sleeve arming its book.

## THE HONESTY CAVEAT

This release makes the week of collection **trustworthy, not profitable.** Every number that looked too good has now come down to something believable — stock's best strategy went from +5.59%/trade to +0.61%, which after fees is thin and may not survive contact with more data. That is the point: you now have an instrument that reports small honest edges instead of large fake ones. The 100-trade / 90-unbroken-day bar has not moved, and nothing here is evidence of edge.

Thank you for catching the scale-blend by eye when my own tests were green. That is the failure mode I can't self-detect, and it saved the week.
