# SILMARIL 7.0.2 — THE CANONICAL MERGE
*Diagnosed against your July-17 11 AM tree. Battery **53/53**.*

## THUMBS UP — with one real bug found and killed. Here is the honest status of every claim.

### ✅ The 7.0.1 patch installed correctly
Isolation ✓ · stale-sweep ✓ · parameter_registry repair ✓ · census fix ✓ · T52+T53 ✓ · SPINE header reads 7.0 ✓.
**Proof it worked:** `THRESHOLD_TAKEHOME`, `KRAKEN_SPREAD`, `MASTER_LOG`, `SESSION_ANATOMY` all wrote fresh at **17:58 today** — those four builders were DEAD before the cascade repair. They are your "unregistered stores" selftest failure: the fix resurrected them faster than my hand-built registry could track.

### ✅ Every workflow is VALID and correctly scheduled
```
daily.yml       */10 * * * *   ✓   hourly.yml    7 * * * *      ✓
analytics.yml   20 7 * * *     ✓   backfill      10 8 * * *     ✓
selftest.yml    45 3 * * 1     ✓   + 6 manual-dispatch ✓
```
Nothing is disconnected. Nothing is lost.

### ✅ Every universe is feeding
`marks_health: marked=886 · entry_warm=886 · state=OK` — the quiet window is over, the engine is awake.
`crypto seen=344 · stock seen=524 · metal seen=12 · energy seen=6` · **engine merges 1,037 symbols.**

### ✅ The 4-minute run — arithmetic, not breakage
| | datapoints | run |
|---|---|---|
| July 16 (weeks of tape) | ~414,000 | 12 min |
| now (2× genesis) | 129,765 | 4 min |
Fixed overhead (checkout·deps·fetch·commit) is ~3 min of that. **The run is short because the tape is young — you genesis-wiped twice (10:38, then again 15:23, destroying 4h47m of fresh history).** It lengthens every day history accumulates.

### 🔴 THE REAL BUG — and it was hiding behind the wipes
**`paper_sim.py` line 1518 threw away your entire crypto tape at the fingerprint gate:**
```python
if _cl == "crypto" and "-" not in _s:
    continue      # canonical-crypto only
```
ccxt keys are `BTCUSDT` / `BTCUSD`, not `BTC-USD`. That rule **discarded 404 symbols × ~300 candles = 121,069 datapoints of real history, every cycle.**

Invisible for months — `price_samples` had weeks of canonical depth, so nobody noticed the ccxt tape was redundant. **Genesis exposed it:** canonical keys reset to ~14 prints, ALL the remaining depth sat in the keys we were skipping → **0 crypto fingerprints → 0 geometry rows → 0 crypto trades**, and no amount of waiting fixes it faster than 17 hours of unbroken cycles.

**Fixed (7.0.2):** non-canonical crypto is now CANONICALIZED and its history UNIONED onto the canonical key — the same rule `scripts/remap_keys.py` already uses. Fingerprints only; marks and entries untouched. **T54** fails the battery if the ccxt tape is ever orphaned again.

### The result, measured on your tree, right now
```
FINGERPRINTS   8 → 245 tracked · 99 fitted   (crypto 0 → 237 fittable)
GEOMETRY       0 → 10 TRADEABLE · 39 geo-locked · 18 evidence-short · 178 stand-down
INTERROGATOR   TOWARD-EDGE · 10✓ 3~ 0✗
BRAIN          25/25 wired+fresh
BATTERY        53/53
```
Most winnable right now: **ANT-USD** (needs 20.6%, proven floor 62.5%) · **FTM-USD** (30.1% vs 62.5%) · **RNDR-USD** (50.0% vs 62.5%).

### ✅ Also fixed: the registry now self-heals
`STORE_REGISTRY.json` was a hand-built snapshot that went stale the moment a builder was resurrected. It is now **rebuilt BY RULE every cycle** (`store_registry.py`, first in the spine), so a new store can never be "unregistered" again. T32 now demands **total** coverage.

## ⚠️ THE ONE THING THAT WILL HURT YOU: stop running GENESIS
Every genesis destroys `price_samples` — your hard-won tape. You have run it **twice in 5 hours.** Crypto fingerprints now fit from the ccxt candles immediately, but **stock** fingerprints fit only from the live tape and need ~100 prints ≈ **17 hours of unbroken 10-min cycles.** Every genesis restarts that clock at zero. **Install this, then leave it alone.** The system heals by accumulating history; it cannot heal while being reset.
