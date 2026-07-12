# 03 · ENGINE PIPELINE — one PULSE cycle, in order

1. **run_lock** acquire (stale auto-reclaim) → **ingest** feeds → append `price_samples.json`
   (+ ccxt/metals/energy stores). Backfill `T00:00:00` candles never enter signal paths.
2. **Marks & warmup** — per-symbol marks; entry-warm = ≥8 pts & ≥1.5h span (knob `warmup`).
3. **Regimes** — per-book slope/breadth → SIDEWAYS/UP/DOWN + advice + ⚡shift watch.
4. **Candidates** — per-book dip scan (fingerprint-fitted per-valuable entries/targets where fitted;
   GEKKO uses its fixed knobs) → **veto stack**: integrity ceiling · knife veto · regime gate ·
   fee-honesty (`min_takehome_usd` net-clear) · post-STOP `reentry_cooldown` (240m) · caps.
5. **Entries** — sized by ladder fracs; every position carries entry/target/stop/cost(fraction)/
   wager/champion; funnel records seen→warm→candidates→bought + named rejections.
6. **Exits** — ONE loop, all five books, filtered by UNIVERSE CLASS (the GEKKO fix): TAKE at target
   (fresh price required — stale feeds mark-from-last-real, fill only on fresh ≤45m, flag
   `stale_price_min`), TAKE_LIMIT high-water fills at limit, then **5.1B: REGIME_FLIP_HARVEST** (book fast-red + net-now ≥ 0 → bank it, A/B-logged)
   and **FEE_CLEAR_TIME** (age > 36h + net-now ≥ 0 → free the capital), then STOP at
   `max(p_stop, floor)` (heatshield-autotune resolution); underwater ≥72h gets `stuck` flagged.
7. **Persist** — books + `paper_sim_live.json` (funnel, positions incl `exp_net_usd`, trades incl
   `wager_usd`), HEATSHIELD comparison (+`autotune_applied` stamp).
8. **Governance** — validation (by strategy, per book) → election (crypto) → split (all books) →
   governance/timeline stores.
9. **SPINE (every cycle, each module wrapped — none can break a trade run):** bench nulls · census
   (content-age self-gate) · store contracts · invariants (incl INV10 market-hours) · utilization ·
   conductor C0 log · research OS · five labs (baseline/ladder/weekly/parity/complexity) · session
   reconstruction + anatomy · decision trace · journal · **5.1:** health_lights · gate_evidence · conductor C1 · evidence scorecard ·
   **5.1B:** mtf_regime (the 15m→30d ladder the NEXT cycle's exits/sizing consume) ·
   conductor_report_card (harvest/sizing A/Bs, stuck capital, realized tally).
10. **Broker bridge** — the ONLY gated call (`run_all_harvest_accounts` behind `_broker_policy`),
    gated at its CALL SITE. The core can never be enclosed again (selftest T1 enforces by AST).
11. Commit/push (`-X theirs`, retried) → run_lock release → `✦ SILMARIL run complete`.
