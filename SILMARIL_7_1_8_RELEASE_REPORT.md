# SILMARIL 7.1.8 — "THE RATIO BENCH"
### WDAY answered, the fake peaks found, three new sleeves built on the one number nobody measured.

**Battery: 121/121** on the full tree, a reset tree, and a simulated install over your July 29 backup. Click path 9/9.

---

## 1 · WDAY — not a bug, but the display was lying to you

`WDAY  $152.30 → $168.01  +10.32%  target $158.39` and no sell.

From the sleeve state: `stock:E · WDAY · peak_chg: 0.1162`. It reached **+11.62%**, the 7.1.6 trail armed, and it is riding at +10.32%. The trail exits on a 25% give-back — it would sell around +8.7%. **It did not ignore the target; it promoted the target to a trailing exit and is currently earning 2.6× what the +4% target would have paid.**

But you were right that something is wrong: **the bar still shows the original $158.39 target as the exit line.** Once a trail arms, that number is no longer the exit, so the panel reads "target hit, why no sell?" The display should show the trail level. That's a UI lie about a correct decision, and it cost you a night of doubt.

## 2 · The "missed targets" were FAKE PEAKS — a new instance of the sawtooth

Your instinct — *"every reason for selling low is hitting, every reason for selling high is being ignored"* — sent me to audit every position. Three positions (BAT-USD in sleeves A, B, C) reported **crossed target, no trail, now underwater.** That looked exactly like the bug you described.

It wasn't a missed sell. **The peak never happened.**

```
price_samples.json  BAT-USD   570 real prints, irregular timestamps,  ZERO grid rows
ccxt_samples.json   BATUSDT   299 rows on an exact 5-minute grid, containing 0.07120
ccxt_samples.json   BATUSD    299 rows, newest print dated 2023-06-27  ← three years dead
```

BAT's real tape never exceeded its +5% target. The admitted feed sat ~5.4% higher, and its stuck value (0.07120) is *above* the target (0.07093) — manufacturing a "+5.40% peak" that my own audit reported as a crossed target.

**Why it got in:** my 7.1.6 gap-fill rule admitted an alternate feed only where the reference had no print within **7 minutes**. But we sample every **10–20 minutes** and ccxt arrives on a **5-minute** grid — so every single grid row landed "in a gap" and was admitted. The fix was correct in principle and useless in practice because I hardcoded a tolerance smaller than our own heartbeat.

**Now:** the tolerance is derived from the reference series' **own median cadence** (×1.25), so a second feed can only ever speak for moments we genuinely cannot see. Plus a **DEAD_SERIES** rejection for any spelling whose newest print is >14 days old.

**Result:** BAT-USD → 570 rows, 0 grid rows. Universe-wide: 248 FROZEN + **82 DEAD** + 1 unverifiable rejected. Re-auditing every open position on clean data: **8 crossed-target positions, all 8 riding with trails armed, ZERO true misses.** Tripwire T122 extended.

## 3 · THE RATIO BENCH — three new sleeves

You asked me to take the geometry finding and build. Here it is. One equation drives all three:

> **required win rate = stop ÷ (target + stop)**

Every existing sleeve inherits a **blanket 6% stop** while its target is measured per name. H PATIENT REVERT aims ~0.78% against 6%, so it needs **88.5%** to break even. It delivers **88.6%**. The sleeve isn't broken — the ratio is, and the stop is the one number nobody ever measured.

Verified on your own tape:

| name | target | 6% default → required WR | **measured stop** → required WR | ratio |
|---|---|---|---|---|
| MKR-USD | 3.60% | 66.7% | **1.84% → 41.2%** | 1.95:1 |
| STRK-USD | 6.00% | 53.3% | **10.00% → 65.0%** | 0.60:1 → **refused** |

MKR goes from needing two wins in three to needing **two in five**, on identical trades. STRK measures a 10% adverse excursion, so its 6% stop was being hit by design — the gate now refuses it instead of pretending.

### **L — TOLLBOOTH** · arithmetic first
Stop **measured** from the name's own 75th-percentile adverse excursion. Requires target/stop ≥ **1.6** (caps required WR at ~38%) *and* demands the name's measured bounce reliability beat that requirement by 8 points. Small, frequent, **vaulted**. Collects a modest toll many times with the maths on its side, instead of winning 9 in 10 for nothing.

### **M — FLOOR ARTIST** · the first sleeve the graph actually drives
Buys only within 1.5% **above** a floor the tape has tested **≥3 times**; stop sits 0.6% **below** that floor (the level's natural invalidation point — which is what makes it tight *and* honest); target is the nearest ceiling tested ≥2×. **Both legs read off real structure, so the ratio is a property of the setup rather than a guess.** Calibrated on your tape: **25 of 200 names** present a qualifying setup — selective, not silent.

### **N — CEILING SWEEP** · your own idea, implemented
Your words: *"is there a way to sweep profits when they don't hit their GOAL, but it would be profitable to take the new ceiling as it is established?"* Yes. N exits on **structure**: when price reaches a ceiling tested ≥2× **and** the last two cycles failed to make a new high, it banks the profit — provided the fill clears fees with real margin. It also sweeps a profitable position whose cadence says its peak has passed. **It never sweeps a loss** — the stop still owns the downside. That's your WTI question, answered in code.

All three are registered on **all four books**, knob-gated, and every refusal is written to `SLEEVE_VETOES.json` with its arithmetic stated (`"measured stop 10.00% against a 6.00% target pays only 0.60:1, below the 1.60:1 this sleeve requires"`). **Tripwire T125** asserts measured stops are real and bounded, unpayable shapes are refused *with reasons*, floors are support, sweeps never take a loss, and non-bench sleeves pass through untouched.

*Two bugs I hit building this, both caught by running it rather than reading it:* a missing `timedelta` import made `_structure_levels` return "no structure" for every name behind a bare `except: pass` (that silent swallow is now loud), and my first floor filter accepted levels **above** price — broken support — producing negative risk and ratios like 26,855,763:1.

## 4 · YOUR HISTORY QUESTION — and the number that settles it

You asked whether a year of backfill is worth it. **It is the single biggest constraint on everything above**, and here is the measurement:

```
live intraday coverage:  12 days (2026-07-18 → 07-29)
measured stop available:  15 of 193 fingerprinted names
too little history:       178 names — 92%
```

The ratio bench needs ≥8 completed dip→resolve excursions per name to measure a stop. It has that for **8%** of your universe. With a year it would have it for nearly all — and the same is true of floors, ceilings, heartbeat, cadence and trajectory, all of which get sharper with more tested levels.

**And I found what was capping it.** `scripts/prune_data.py`:

```python
keep = int(cat.get("intraday_keep_per_symbol", 2000))
```

At ~10-minute sampling, 2,000 prints is **about fourteen days**. The prune was trimming your tape back to two weeks every run. Dailies were untouched (good), but the *intraday* depth every measurement needs was being thrown away. **Raised to 20,000 (~5 months).** History is the asset.

**My recommendation on backfill:** yes, do it — daily candles for a full year on the whole roster, and hourly where the source allows. It won't help intraday dip-excursion measurement much (daily bars can't show a 0.5% intraday dip), but it will transform floors, ceilings, trajectory and regime. The intraday depth now accumulates on its own instead of being pruned away.

## 5 · DATA LEDGER — checked, and it is honest

`live 300 stores · 82.36 MB — archive 3 files · 7.179 MB (gzip)`. The law reads *"history is compressed into archive/*.jsonl.gz, never discarded"*, and the prune leaves daily candles alone. The one destructive edge was the intraday cap above, now fixed. **No evidence of a destructive cycle eating your learning.**

## 6 · MAKER/TAKER — the honest answer

Fees are modelled from venue tables and applied on every fill via `round_trip_cost`, and the geometry gate includes cost in the required-win-rate calculation — so cost is accounted for at every step. **But we do not model queue position, so we cannot claim maker rebates we haven't earned.** A resting limit *would* usually be a maker fill; a stop is always a taker. The current model charges a blended round trip, which is conservative for your targets and correct for your stops. Closing that gap properly needs `VENUE_SHADOW` (order book depth + queue), which is still the honest remaining distance to live.

## 7 · UNIVERSE NARROWING — audited

654/1074 feeds tradeable. The exclusions are 60 FROZEN + 43 QUANTIZED + 40 COARSE + 276 UNKNOWN (still gathering prints). **The geometry rules are not what's narrowing you** — dead and low-resolution feeds are, plus names that simply haven't accumulated enough prints yet. That last group shrinks on its own now that retention is fixed.

---

## INSTALL (4 files + report)

```
silmaril/execution/canon_keys.py          silmaril/execution/strategy_lab_abcd.py
scripts/prune_data.py                     scripts/selftest_5_1.py
SILMARIL_7_1_8_RELEASE_REPORT.md  (root)
```

No reset. The three new sleeves start trading as soon as candidates appear; watch `SLEEVE_VETOES.json` for `ratio gate —` lines to see them refusing shapes that cannot pay.

## THE HONESTY CAVEAT

I cannot promise these three sleeves make money. L, M and N are hypotheses — what I *can* say is that they are the first sleeves in this system whose arithmetic is measured rather than assumed, and that they will refuse a trade the maths forbids instead of taking it and losing slowly. Given the whole workshop has been running an 88.5% break-even bar without knowing it, that alone is a different game.

The fake-peak bug was mine, twice: once for hardcoding a tolerance smaller than our own sampling interval, and once for letting a three-year-dead series stay a merge candidate. Both now have tripwires that reproduce them.
