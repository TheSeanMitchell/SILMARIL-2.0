# SILMARIL 5.0 — participation fix (ALL industries trade) + Invariants Engine

Install by dragging these files over the repo (GitHub web UI), same as always. Nothing here
touches the hotfix you already installed; these are additive.

## Part 1 — WHY the stock / metal / energy books were idle (two real bugs, both fixed)

Every non-crypto book sat at 0 trades. It was not thresholds alone — it was two plumbing bugs
plus a strategy-type mismatch:

1. **Override-ordering bug (all books).** `regime_overrides` were applied *after* the candidate
   funnel was already built with the champion's own entry, so a *lowered* override entry could
   never actually add names. Even the stock override you had was a silent no-op. **Fixed:** the
   override is now resolved *before* candidate selection, and it can now also set `dir` and
   `max_hold_min` (not just entry/target/stop).

2. **`fresh_ok` gated metal/energy on US stock-market hours (metal/energy).** Commodities fell
   through to the equities-session check, so gold/silver/oil could only enter during the 6.5-hour
   NYSE window — wrong; they trade ~24/5. **Fixed:** metal/energy now gate on live-data
   freshness (like crypto); stock keeps its correct regular-session gate.

3. **Strategy-type mismatch.** The elected non-crypto champions are slow momentum/HOLD strategies
   (stock `HOLD_u1_t8` = buy +1% strength, +8% target, 480-min hold; metal `PERSIST_u25_h12` =
   buy +2.5%). Those almost never fire intraday and, with 8% targets, would never *close* a trade
   in a day — so no closed-trade data. **Fixed via the override surface** (below), not by touching
   the champions.

## Part 2 — Mean-reversion participation profiles (PARAM_CATALOG.regime_overrides)

Each non-crypto book now runs a **mean-reversion** profile (buy small dips) sized to that market's
real intraday range — the system's one proven edge, at native scale:

| book   | regimes            | entry (dip) | target |
|--------|--------------------|-------------|--------|
| stock  | SIDEWAYS / UPTREND | 0.7%        | 1.2% / 1.4% |
| metal  | SIDEWAYS / UPTREND | 0.4%        | 0.8% / 0.9% |
| energy | SIDEWAYS / UPTREND | 0.7%        | 1.3% / 1.4% |

Crypto keeps its June-30 profile. All targets clear the 0.2% fee floor; the deep `floor_min`
stops (8–10%) mean these sit through heat and mostly close on target — realized losses stay rare.
DOWNTREND stays safety-gated for crypto/stock by design. Every override is a knob you can retune,
and the forward record (plus Research-OS Q003) judges whether it actually pays.

**Proven end-to-end here:** with the fixes in place, metal, energy, and stock each open a real
position on a small dip where their momentum champions stayed idle; the empty-override path is
byte-for-byte unchanged (no regression).

## Part 3 — Invariants Engine (Law 11) — the next DoD rock

New `silmaril/execution/invariants.py`: nine per-cycle logical-safety checks that sit beside the
store contracts. Where contracts prove every store is *shaped* right, invariants prove the live
state is doing nothing *impossible*: no book cash negative/NaN, every open position carries a
stop+target, entry prices positive, no book over-allocated, champion params in (0,1], **no trade
ever entered on a synthetic daily candle** (the backfill-poisoning guard), GEKKO never in the
Master's funded set, realized P&L equals Σ closed trades, no equity runaway.

Any violation flips `INVARIANTS.json` red and names the exact offender. A consecutive-all-green
streak is tracked in `INVARIANTS_STATE.json` (survives wipes) toward the DoD clause *"contracts +
invariants green for 30 cycles."* Runs in the 5.0 spine (fast + full), wrapped so it can never
affect trading. Surfaced on the Command-tab 5.0 strip as the **INVARIANTS** row with the streak.

Verified: reads ALL GREEN on your live 3:40 PM data, and correctly goes RED (streak → 0) when a
missing stop / negative cash / synthetic-candle entry / accounting mismatch is injected.

## Verify after install
- Tomorrow during the session: the Command-tab **UNIVERSE FUNNEL** rows for stock/metal/energy go
  non-zero (seen → warm → candidates → bought), and OPEN POSITIONS populate. Metal/energy can also
  trade outside NYSE hours now.
- 5.0 strip shows **INVARIANTS ALL GREEN · green N/30** climbing each cycle.
- `SOURCE_BUDGET.json` (from the prior hotfix) stays near-untouched — participation adds no API load.

## Files
- `silmaril/execution/paper_sim.py` — override-ordering fix + metal/energy freshness gate
- `silmaril/execution/invariants.py` — NEW Invariants Engine
- `silmaril/cli.py` — invariants wired into the 5.0 spine
- `scripts/reset_internal_clean.py` — INVARIANTS.json rebuilds on wipe; INVARIANTS_STATE.json preserved
- `docs/data/PARAM_CATALOG.json` — mean-reversion participation profiles
- `docs/index.html` — INVARIANTS row on the 5.0 strip

## One honest caveat
Participation is not edge. These profiles guarantee the books *trade* at each market's native
scale; whether that trading is *profitable* is exactly what the forward record, the null books,
and the fee-honest engine now measure. If an asset class has no post-cost mean-reversion edge,
you'll see it in the realized P&L and the Δ-vs-NULL line — truthfully, and cheaply.
