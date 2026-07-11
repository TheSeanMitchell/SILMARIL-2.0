# 07 · REGRESSION PROTECTION — every incident is now a tripwire

**The rule:** a bug is not fixed until something automated fails if it returns.
Battery: `scripts/selftest_5_1.py` (local + weekly `selftest.yml`, read-only). Runtime rails:
invariants (every cycle) + store-contracts freshness (every cycle).

| Historical incident | Permanent tripwire |
|---|---|
| 2026-07-10: broker gate enclosed 818 lines incl. the paper sim — engine dark in every lane | **T1** AST guard: `live_step` import may never sit under a `_HAS_ALPACA`/`_broker_exec` conditional |
| GEKKO bought-never-sold (exit loop filtered by book label) | **T2** fixture: over-target aggressive position MUST sell |
| Stale-feed zombie / fills on fiction | **T3**: 6h-old print → no fill, position stays open + flagged `stale_price_min` |
| Champion frozen forever (validation grouped by BOOK) | **T4**: rows must be strategies, never book names |
| LDO −$70.96 re-buy of the same knife 24 min after STOP | **T5** cooldown semantics (240m) |
| Census/freshness blind in Actions (git resets mtimes) | **T6** content-age beats fresh mtime → RED |
| Recurring weekend/market-hours entries | **T7** + runtime **INV10**: weekend stock BUY = FAIL |
| Fee-honesty silently dropped in a refactor | **T8** veto-presence check |
| Any lane silently dying (the July-3 deep-lane death) | contracts freshness caps + `deep_heartbeat` finish stamp → named RED ≤1 day |
| Position missing `cost` nuking a whole book side | hardened `.get("cost", MIN_COST)` (fraction-correct) |

**Update discipline:** every future bug fix ships WITH its test in the same drop, or it isn't done.
