# SILMARIL — THE MASTER ROADMAP · 7.0 → 8.0 → 9.0 → 10.0

### The finish line has never moved: 100 out-of-sample trades surviving the gate across 90 unbroken days, forward, fees on, beating the do-nothing nulls — then, and only then, the Binance.US connect unlocks. Everything below serves that bar. $100–300/day remains an unproven hope, never income.

---

## WHERE 7.0 ENDS (the baseline this roadmap builds on — all shipped, all tripwired)

7.0 closed the trust layer: one canon ledger (LEDGER.jsonl) that only the live cycle can write; the Master as a strict mirror of book-held names with vaulted, non-spendable harvest on every winning sell; archive-first resets with learning stores that survive standard mode; the ONE-UNIVERSE river (sleeves trade the books' own candidate stream, every sleeve close flows back as maturity evidence, the champion sleeve steers Master policy and gets the gold spotlight on both tabs); the trajectory veto (multi-window free-fall may not fill without a printed floor — every book, GEKKO included); news in the decision path (shadow A/B on every sized candidate, one knob from live tilt); the modal contract; readiness panels that state the real funnel reason; and a health panel that reads the authoritative, cycle-fresh file. 67 tripwires green on both the full-data and fresh post-genesis trees.

What 7.0 does NOT claim: proven edge. The books have a handful of closed trades. The system is a clean instrument now; the instrument has not yet earned the verdict.

---

## 8.0 — THE PROOF RELEASE ("every number can defend itself")

Theme: consumption receipts and calibration teeth. 7.0 proved the wiring exists; 8.0 proves every subsystem measurably changes decisions, and starts letting evidence move capital in the smallest honest increments.

1. **FLOW_PROOF ledger.** Every cycle, every subsystem emits `{inputs_read, outputs_written, consumers_confirmed, decisions_influenced}` into FLOW_PROOF.json. A tripwire fails if any live module goes two days with zero confirmed consumers — dead code gets named, then retired or revived, never left ambiguous.
2. **PANEL_PROVENANCE.** Every dashboard panel registers `{panel, source_file, writer, generated_at, reads_canon}`; a HEALTH sub-panel renders it. A panel reading a file staler than the engine's cycle is a red light, not a surprise. This makes the July health-panel class of bug (fresh truth in one file, frozen lie in another) structurally impossible.
3. **Per-series chart meta.** Every chart states its own evidence: `N intraday prints · M daily backfill candles · span` — the NDSN/IR/PALL/GLD "looks fake" complaint becomes a label, permanently. Backfill candles render visually distinct from live prints.
4. **Calibration teeth in sizing.** CALIBRATION.json (Brier/reliability) stops being a report and starts scaling wagers: names where stated confidence historically over-promises get shaved; names that under-promise get their full size. Knob-gated (`calibration_teeth.mode: shadow→on`), pre-registered kill, A/B logged against flat sizing.
5. **Conductor C2 — the first ε.** C0 logged 800+ decisions; C1 shadow-scored policies. C2 puts a tiny ε (5% of GEKKO's wagers only) behind the best-scoring policy, only after C1 shows positive uplift across ≥300 scored decisions. Never automatic beyond GEKKO; the report card, not enthusiasm, decides if it stays.
6. **News tilt goes live-eligible.** The 7.0 shadow log (NEWS_TILT_AB.jsonl) gets a weekly A/B report: candidates with hot/positive pulse vs cold, realized outcomes. If the split clears fees over ≥50 shadowed candidates, flip `news_tilt.mode: on` (capped ±10% conviction tilt). If not, the knob stays shadow and the report says so out loud.
7. **Δ-vs-null everywhere.** Every leaderboard row (sleeves, strategies, champions) carries its Δ against the matching null (HODL/SPY/CASH) as a first-class column. Law 10 stops being a footnote.
8. **Attribution monitor.** Rolling per-symbol P&L concentration with an alarm when any single name exceeds 50% of net profit (the MKR/183% lesson institutionalized) — concentration is surfaced before adaptive systems train on it.

Exit bar for 8.0: FLOW_PROOF green for every live module for 7 straight days; calibration teeth and news tilt each carry a written A/B verdict; C2's ε either survives its kill criterion or is rolled back with the receipt published.

---

## 9.0 — THE RESILIENCE RELEASE ("the machine survives the world")

Theme: regime intelligence and unattended durability. 8.0 made decisions defensible; 9.0 makes the platform survive Mondays, outages, and regime flips without an operator touching it.

1. **Regime-conditional champions.** Each book elects a champion PER REGIME (UP/SIDEWAYS/DOWN), from forward survivability within that regime only. The 7.0 trajectory veto becomes one instrument in a regime playbook: SIDEWAYS runs mean-reversion; confirmed UP unlocks the HOLD family; DOWN stands down or requires double floor confirmation.
2. **Bootstrap ladder.** A wiped or new book walks named states — OBSERVE → SHADOW → PROBE (quarter-size) → FULL — with promotion by evidence count, not time. The readiness panel already speaks this language; 9.0 makes the states real capital limits.
3. **Market-calendar service.** One canonical calendar (NYSE/NASDAQ sessions, half-days, holidays, metals 24/5 windows, energy settles, crypto 24/7) consumed by every gate and every panel. "MARKET CLOSED — resumes Mon 06:30 PT" comes from the calendar, never from a heuristic; gold and energy arm themselves at their true opens.
4. **Fallback waterfalls ≥2, enforced.** Every feed group (crypto price, stock price, news, metals, energy, macro, broker marks) must hold ≥2 live providers; a group at 1 goes YELLOW on the spine and files an ENGINE issue. The 7.0 key_groups panel becomes a contract, not a report.
5. **Self-heal ledger.** Every automatic recovery (rebased push, reclaimed lock, provider failover, quarantine release) writes SELF_HEAL.jsonl. Silent recoveries hide rot; a healing machine that narrates its healing can be trusted alone for a week.
6. **Weekly platform scorecard, auto-filed.** Every Sunday the engine grades itself (trades, Δ-vs-null, calibration, uptime, feed depth, tripwire streak) into a dated report the operator can read in two minutes.

Exit bar for 9.0: 14 unattended days with zero operator interventions; every book demonstrates correct behavior across at least one full weekend→Monday transition; regime-conditional champions carry ≥25 forward trades each in their home regime.

---

## 10.0 — THE HANDOFF RELEASE ("rehearsal becomes real, or the verdict is published")

Theme: the live-money gate, executed exactly as written on day one. Nothing in 10.0 adds alpha; 10.0 is the honest bridge.

1. **The gate, mechanized.** The Binance.US connect stays LOCKED until BOTH hold: ≥90 days since last reset AND 100 out-of-sample forward trades with positive expectancy after modeled live fees, healthy drawdown, and Δ-vs-null > 0. The engine computes this every cycle; no human override path exists in code.
2. **Capacity- and fee-aware sizing.** Live order books (spread, depth) bound wager size per name; modeled friction is replaced by venue-quoted fees. Paper fills that live books couldn't absorb are flagged UNFILLABLE and excluded from the record.
3. **Venue rehearsal in shadow.** For 30 days before any real order, every Master decision is mirrored as a venue-formatted order (Binance.US/Coinbase/Robinhood syntax) into VENUE_SHADOW.jsonl — proving the translation layer against real symbols, lot sizes, and minimums with zero dollars at risk.
4. **The honest edge verdict.** At gate-evaluation time the engine publishes one page: expectancy with confidence interval, Δ-vs-every-null, fee survival, regime dependence, concentration — and a one-line verdict: PROVEN EDGE / UNPROVEN / NEGATIVE. If the verdict is not PROVEN, 10.0's deliverable is that page, published without spin, and the clock keeps running. That outcome is a success of the instrument, not a failure of the project.
5. **First-capital protocol (only on PROVEN).** Smallest viable stake, hard daily loss breaker, auto-revert to paper on any breaker trip, and the vault discipline carried over: realized profit leaves the table on every winning close.

---

## STANDING LAWS ACROSS ALL VERSIONS

Read before edit, in full. Exact-text edits only. Additive, never destructive. Every bug ships a tripwire; the battery runs green on full AND fresh trees before any package. Every behavioral change is knob-gated with a pre-registered kill. No synthetic data in live modules — "I don't know yet" beats an invented number. Realized, fee-paid P&L is the only score. One honesty caveat per report, and this is the roadmap's: everything above is scaffolding around an edge that is still small, fee-sensitive, and unproven — the roadmap's job is to make the verdict undeniable, whichever way it lands.
