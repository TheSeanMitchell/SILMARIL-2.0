# SILMARIL — BEYOND 7.0 MASTER DIRECTIVE
## The spine for 8.0 · 9.0 · 10.0 · 11.0 · 12.0 — small installments, one at a time, each soaked and proven before the next

---

# PART I — HOW TO USE THIS DOCUMENT

This is the single source of direction from 7.0 forward. Hand ONE installment at a time to the coding session. Never hand two. Every installment below is sized for one session, one ZIP, one drag-and-drop install, and a 1–2 day soak before the next begins.

**The cadence (never violated):**
1. Hand the installment text (copy the whole numbered block) to the coding session with the latest FULL BACKUP zip.
2. The session follows the Standing Laws (Part II), ships one ZIP, and states exactly which soak checks to run.
3. Operator installs, runs the daily workflow twice manually, then leaves the cron running.
4. Soak 1–2 days (or the stated market condition, e.g. "one weekday open"). Walk the installment's SOAK CHECKLIST.
5. Every box green → next installment. Any box red → hand the red box back as the ONLY task ("fix this, nothing else").

**Version gates.** Do not begin 9.0 until every 8.x soak is green, and so on. Versions are themes; installments are the units of work. It is always correct to pause between installments — the engine collects data either way, and the 90-day clock (started 2026-07-20 05:12 UTC) runs regardless.

**What every installment must contain when handed back as a delivery:** complete files at repo paths, py_compile + node-check proof, the full selftest battery green on BOTH the full-data tree and a fresh post-genesis tree, the new tripwire(s) named, and the kill switch named.

---

# PART II — STANDING LAWS (copy into every coding session verbatim)

1. Read every file you will touch IN FULL before editing. Exact-text edits only; never regex across multi-line definitions.
2. Additive, never destructive. Nothing is removed without explicit operator intent.
3. Every bug fixed ships a selftest tripwire that would catch its regression. Tripwires live in `scripts/selftest_5_1.py`: define `def tNN_name():` using the `check("TNN …", ok, detail)` pattern, register in the runner tuple. Marker-based tripwires must be updated in the same delivery that changes the marker text (the T60 lesson).
4. Every behavioral change is knob-gated in `docs/data/PARAM_CATALOG.json` with a `_note` naming the kill (`mode: "off"`). New behaviors default to `shadow` (log only) unless this directive says otherwise.
5. No synthetic data in live modules. "I don't know yet" beats an invented number. Daily backfill candles (`"T00:00:00" in t`) never TRIGGER a signal; they may only VETO.
6. One canon per fact. Trades: `LEDGER.jsonl` (written only by the live cycle via `PaperBook._ledger`). Equity: `EQUITY_TRUTH.json`. Health: `api_health.json`. New stores register in `docs/data/STORE_REGISTRY.json` with a class (`LEDGER` / `LEARNING` / `STATE` / `DERIVED`) in the same delivery that creates them.
7. Atomic writes only: `write_json_atomic` from `silmaril/execution/atomic_io.py`. Append-only ledgers use plain append.
8. Delivery = complete-file ZIP at correct repo paths for GitHub web drag-and-drop. Include the battery result line in the final message. Max one honesty caveat per message; realized fee-paid P&L is the only score; $100–300/day is unproven hope, never income.

---

# PART III — INSTALLMENT 0 (SHIP FIRST · the audit hotfix · one session)

Three small items found in the 2026-07-20 audit. One ZIP.

**0.1 — Bench-books reset law (the vs-HODL ghost).**
Root cause with receipts: `silmaril/execution/bench_books.py` line 19 states the doctrine — nulls "start where the governed books started" — but `scripts/reset_internal_clean.py` never touches `BENCH_BOOKS.json` (class STATE, absent from both the delete list and the preserved list). Re-anchoring after a wipe is therefore ACCIDENTAL: on July 19 the anchors survived a genesis wipe and the spine showed a ghost `crypto−HODL: −22.15%` on a fresh $10k book; on July 20 the anchors happened to re-create (05:27) after the wipe (05:12) and the comparison is clean. Convert luck into law:
- In `scripts/reset_internal_clean.py`, in BOTH standard and genesis paths, delete `BENCH_BOOKS.json` (with a printed line: "deleted BENCH_BOOKS.json (nulls re-anchor with the fresh books — Law 10 comparisons share one inception)"). `bench_books.py` already rebuilds it on the next cycle at fresh $10k.
- Tripwire T69: reset script text contains `BENCH_BOOKS.json`; AND on the fresh-tree harness, if `BENCH_BOOKS.json` exists its `books.BENCH_CASH.created_at >= WIPE_MARKER.wiped_at`.

**0.2 — Sky News video swap (operator order).**
`docs/index.html` line ~872: replace exactly
`{t:'Sky News (24/7 live)',src:'w9uJg68CV4g'},` → `{t:'Sky News',src:'YDvsBbKfLPA'},   // operator swap: watch?v=YDvsBbKfLPA`
Verify the embed loads once deployed (some streams block embedding; if it 401s, report it, do not improvise a replacement).

**0.3 — Register the 7.0 river stores.**
`docs/data/STORE_REGISTRY.json` `stores` map gains: `"LAB_OUTCOMES.jsonl": "LEARNING"`, `"NEWS_TILT_AB.jsonl": "LEARNING"`, `"LAB_EVIDENCE.json": "DERIVED"`, `"NEWS_PULSE_STATUS.json": "DERIVED"`. Tripwire T70 asserts all four registered.

**SOAK CHECKLIST 0 (1 day):** after two live cycles past any quiet window: `LAB_EVIDENCE.json`, `NEWS_PULSE_STATUS.json` both HTTP 200 on Pages and < 30 min stale; run a STANDARD reset on a throwaway branch or accept on next real reset only — spine Δ-vs-null reads ~0.0% within one cycle of any future wipe; Sky News tile plays; battery 69/69.

---

# PART IV — 8.0 · THE PROOF RELEASE ("every number can defend itself")

Theme: consumption receipts and calibration teeth. 7.0 proved the wiring exists; 8.0 proves every subsystem measurably changes decisions, then lets evidence move capital in the smallest honest increments. **The questions 8.0 demands of the data:** Which modules actually change decisions? When we say 60%, do we win 60%? Does news pulse predict anything? Is one symbol carrying the book?

**8.1 — FLOW_PROOF ledger.**
Objective: every subsystem proves input → output → consumer every cycle.
Build: new module `silmaril/execution/flow_proof.py` with `record(module, inputs_read: list, outputs_written: list, consumers: list, influenced: int)` appending per-cycle rows into `FLOW_PROOF.json` (last 48h retained, per-module latest snapshot). Instrument these call sites first (one line each): paper_sim `_run_side` (per book), strategy_lab_abcd `build_strategy_lab`, master_account cycle, confidence engine builder, fingerprint fitter, bench_books, health_lights. `consumers` is declared (who reads my output), `influenced` is counted (decisions this cycle that read the value — e.g. candidates scored).
UI: SETTINGS "SYSTEM BRAIN" gains a FLOW column: 🟢 consumed this cycle · 🟡 produced/unconsumed 48h · 🔴 silent 48h.
Tripwire T71: store exists; ≥7 modules reporting; no module 🔴 on the full-data tree.
Kill: none needed (observation only). SOAK (2 days): zero 🔴 rows; if any module shows 🟡 two days running, that module's revive-or-retire becomes the next micro-task.

**8.2 — PANEL_PROVENANCE.**
Objective: no dashboard panel can silently read a stale or orphaned file again.
Build: in `docs/index.html`, wrap `jget` so every fetch records `{path, generated_at|null, ms}` into a global `window.__prov`; a new HEALTH sub-panel "PANEL PROVENANCE" lists every fetched store, its freshness vs the engine cycle (`paper_sim_live.json.generated_at` as the clock), red if > 2 cycles stale, gray if 404. Also emit the table into `PANEL_PROVENANCE.json`? No — UI-only is enough (engine must not depend on browser state); keep it client-side.
Tripwire T72: html contains the provenance renderer and the `jget` wrapper; count of `jget('data/` calls equals count captured (static grep parity).
SOAK (1 day): open the panel — zero red rows, zero gray rows except knowingly-conditional stores; any red row is the next micro-task.

**8.3 — Per-series chart meta.**
Objective: every chart states its own evidence (the NDSN/IR/PALL/GLD "looks fake" complaint becomes a permanent label).
Build: in the chart pipeline (`docs/silmaril_chart.js` series prep + `drawChart` in index.html), compute per-series `{intraday_n, backfill_n, span_h}`; render into `#mStats`: "N live prints · M daily candles · span Xh". When `intraday_n >= 6`, filter `T00:00:00` rows from the DRAWN line (doctrine); when `intraday_n == 0`, draw backfill dashed + label "daily candles only — intraday resumes at open".
Tripwire T73: markers present; no chart path draws mixed candles without the filter branch.
SOAK (1 weekday): open NDSN, GLD, a crypto — labels correct in all three states (live-only, mixed, backfill-only).

**8.4 — Δ-vs-null everywhere.**
Objective: Law 10 becomes a column, not a footnote.
Build: sleeves table, strategy survival leaderboard, champion panels, and quadrant portals each gain `Δnull` (crypto/GEKKO vs HODL, stock vs SPY, metal vs GLD-hold, energy vs flat-cash) computed from `BENCH_BOOKS.json` shared inception (guaranteed by 0.1). Sorting on the sleeves table defaults to Δnull.
Tripwire T74: the four renderers contain the Δnull column; sleeves sort key is delta_vs_hodl-family.
SOAK (1 day): spotlight sleeve == top of Δnull sort; portals show Δnull under each book.

**8.5 — Attribution monitor.**
Objective: institutionalize the MKR/183% lesson before any adaptive system trains on concentrated luck.
Build: new `silmaril/execution/attribution.py` reading `LEDGER.jsonl` → `ATTRIBUTION.json`: per-book rolling 30d {top symbol, its share of net P&L, herfindahl}; ALERT flag when any symbol > 50% of positive net. FORENSICS panel renders it; alert also lands one line on the spine.
Tripwire T75: store fresh each cycle; alert math verified on a synthetic ledger in the tripwire itself.
SOAK (2 days): numbers match a hand count of LEDGER rows.

**8.6 — Calibration teeth (shadow).**
Objective: CALIBRATION stops being a report and starts (shadow-)scaling wagers.
Build: in paper_sim sizing after `_conf` is final: read `CALIBRATION.json` reliability bins; compute `calib_mult` (over-promising bins shave toward 0.75×, under-promising toward 1.15×, clamp). Knob `calibration_teeth {mode: "shadow", floor:0.75, ceil:1.15}`; shadow logs `{sym, conf, calib_mult, wager_flat, wager_teeth}` to `CALIB_TEETH_AB.jsonl`; `mode:"on"` applies the mult. Kill: `mode:"off"`.
Tripwire T76: hook present; knob registered; AB file appends in shadow.
SOAK (2+ days, ≥20 shadowed rows): AB report says whether teeth would have helped; FLIP TO "on" ONLY when the shadow split is positive after fees over ≥50 rows — that flip is its own micro-installment with its own soak.

**8.7 — News-tilt weekly verdict.**
Objective: the 7.0 shadow log earns a written verdict instead of drifting.
Build: `silmaril/execution/news_tilt_report.py` (weekly lane): join `NEWS_TILT_AB.jsonl` candidates to eventual LEDGER outcomes → `NEWS_TILT_REPORT.json` {n, hot-vs-cold expectancy split, fee-adjusted verdict: PROMOTE / KEEP SHADOW / RETIRE}. BRAIN panel line renders the verdict.
Tripwire T77: report generated weekly; verdict field ∈ the three values.
SOAK (7 days): first report exists and is legible. Flipping `news_tilt.mode:"on"` is its own later micro-installment, only on PROMOTE.

**8.8 — Conductor C2, the first ε.**
Objective: the Conductor's best shadow policy gets 5% of GEKKO's wagers — the first evidence-earned autonomy.
Build: knob `conductor {c2_mode:"off"→"on", epsilon:0.05}`; when on, GEKKO applies the top C1 policy to a random ε-slice of its entries, tagging LEDGER rows `policy:"C2"`; report card compares C2 slice vs baseline with a pre-registered kill (C2 slice negative after 25 closes → auto-revert to off and say so on the spine).
Precondition: C1 ≥ 300 scored AND top policy uplift positive (both already true per spine history — re-verify at build time).
Tripwire T78: gating precondition coded, kill coded, tag written.
SOAK (until 25 C2 closes): report card verdict published either way.

**8.0 exit bar:** FLOW_PROOF fully green 7 straight days · provenance panel clean · every leaderboard carries Δnull · attribution live · teeth and news each hold a WRITTEN verdict · C2 either survives its kill or reverted with the receipt.

---

# PART V — 9.0 · THE RESILIENCE RELEASE ("the machine survives the world")

Theme: regime intelligence and unattended durability. **Questions 9.0 demands:** Does behavior change correctly at every open/close? Which strategy wins in WHICH regime? Can the machine run 14 days untouched and narrate every self-repair?

**9.1 — Market-calendar service.**
Build: `silmaril/execution/market_calendar.py` — one canonical `is_open(asset_class, ts)` + `next_open/next_close` covering NYSE sessions + half-days + holidays (static table, yearly maintenance note), metals 24/5 windows, energy settle, crypto 24/7. Replace every scattered market-closed heuristic in paper_sim and the UI readiness strings with calendar calls; "MARKET CLOSED — resumes Mon 06:30 PT" is computed, never guessed. Gold and energy arm at their TRUE opens.
Tripwire T79: module exists; paper_sim + readiness consume it; a holiday from the table returns closed.
SOAK: one full weekend→Monday transition — stock/metal/energy flip ARMED→TRADING-eligible at the right minute; screenshots kept.

**9.2 — Bootstrap ladder as capital limits.**
Build: per-book state machine OBSERVE → SHADOW → PROBE(25% size) → FULL, promoted purely by evidence counts (fit events + workshop outcomes + resolved closes), stored `BOOTSTRAP_LADDER.json`; paper_sim sizing multiplies by the ladder cap; readiness panel names the rung. Knob with kill (`ladder.mode:"off"` = FULL).
Tripwire T80: rung math unit-tested; sizing respects cap; UI shows rung.
SOAK (2 days post any future reset): books climb rungs visibly instead of jumping to full size.

**9.3 — Regime-conditional champions.**
Build: extend champion election to elect PER REGIME per book from `CHAMPION_FORWARD_LEDGER.jsonl` rows tagged with the regime at entry (start tagging now if absent); `CHAMPION_GOVERNANCE.json` gains a per-regime table; the active champion is the one matching the CURRENT regime, sticky margin unchanged. DOWN regime with no positive-survivability champion = stand down (that is a finding, not a failure).
Tripwire T81: regime tag on every new forward row; election filters by regime; governance table renders.
SOAK (3+ days): governance shows the per-regime table; no champion flip-flops.

**9.4 — Fallback waterfalls ≥2, enforced.**
Build: `api_health.key_groups` becomes a CONTRACT: any group with `providers_active < 2` turns the spine line YELLOW and (if it persists 3 cycles) files an ENGINE issue via the existing failure-issue step. No new providers wired here — enforcement only; wiring a missing provider is its own micro-task when it fires.
Tripwire T82: enforcement path unit-tested with a doctored health file.
SOAK: passive — first real single-provider dip produces the issue.

**9.5 — Self-heal ledger.**
Build: every automatic recovery already in the codebase (rebase-retry push, stale-lock reclaim, provider failover, oscillation quarantine release) appends `SELF_HEAL.jsonl` {t, kind, detail}; HEALTH panel lists the last 10. Silent recoveries hide rot.
Tripwire T83: all four call sites instrumented.
SOAK (2 days): at least the push-rebase kind appears (it fires routinely) and reads sensibly.

**9.6 — Weekly platform scorecard, auto-filed.**
Build: Sunday lane writes `WEEKLY_SCORECARD_<date>.json` + a rendered panel: trades, expectancy, Δ-vs-null per book, calibration Brier, uptime %, feed depth, tripwire streak, self-heals, and ONE sentence the engine writes about itself from a fixed honest template.
Tripwire T84: scorecard generated; all fields non-null or explicitly "insufficient".
SOAK: first Sunday.

**9.0 exit bar:** 14 unattended days, zero operator interventions · one clean weekend→Monday proof · per-regime champions each ≥ 25 forward trades in their home regime (this bar may take weeks — the clock is the point).

---

# PART VI — 10.0 · THE HANDOFF RELEASE ("rehearsal becomes real, or the verdict is published")

Theme: the live-money gate, executed exactly as written on day one. Nothing here adds alpha. **Questions 10.0 demands:** Would live books have filled our paper trades? What do venue fees really take? Is the edge PROVEN, UNPROVEN, or NEGATIVE — with intervals, not vibes?

**10.1 — The gate, mechanized.**
Build: `silmaril/execution/handoff_gate.py` computes every cycle: days_since_reset ≥ 90 AND out-of-sample forward trades ≥ 100 AND positive expectancy AFTER modeled live fees AND max drawdown within bound AND Δ-vs-null > 0 → `HANDOFF_GATE.json {unlocked: bool,每 factor}`. The Settings "Connect Binance.US" button reads ONLY this file. No override parameter exists in code.
Tripwire T85: gate math unit-tested; button gated on the file.
SOAK: panel shows the live countdown truthfully.

**10.2 — Venue shadow orders.**
Build: for 30 days pre-live, every Master decision also writes a venue-formatted order (Binance.US / Coinbase / Robinhood symbol mapping, lot size, min notional) to `VENUE_SHADOW.jsonl` via the existing `venue_universe` data; UNMAPPABLE names are flagged loudly (that list is gold — it prunes the tradeable universe honestly).
Tripwire T86: every Master open/close since enablement has a shadow row or an UNMAPPABLE flag.
SOAK (3 days): spot-check 5 rows against real venue symbol specs.

**10.3 — Capacity- and fee-aware sizing.**
Build: order-book snapshots (spread, top-depth) for held/candidate names each cycle (keyless public endpoints; Actions-only); wager capped so modeled slippage ≤ a knob; venue fee schedule replaces the flat friction model in REALITY CHECK. Paper fills exceeding displayed depth are tagged UNFILLABLE and excluded from the gate's forward count.
Tripwire T87: cap math tested; UNFILLABLE exclusion proven in the gate calc.
SOAK (2 days): REALITY CHECK "survives fees" recomputes under venue fees; note the delta.

**10.4 — The honest edge verdict page.**
Build: `EDGE_VERDICT.json` + panel: expectancy with bootstrap CI, Δ-vs-every-null, fee survival, regime dependence, concentration, sample sizes — verdict ∈ {PROVEN, UNPROVEN, NEGATIVE}. Regenerated weekly and at gate evaluation. If not PROVEN at day 90, the deliverable IS this page, published without spin, and the clock keeps running — that outcome is a success of the instrument.
Tripwire T88: verdict derivable only from stored evidence; no field hand-set.

**10.5 — First-capital protocol (builds only on PROVEN).**
Build: smallest viable stake config, hard daily loss breaker, auto-revert to paper on any breaker trip, vault discipline carried over (realized profit leaves the table on every winning close). Ships DISABLED behind the gate; enabling it is a human act after the gate unlocks, never automatic.
Tripwire T89: breaker + auto-revert unit-tested in simulation.

---

# PART VII — 11.0 · THE TAPE'S MEMORY ("the system learns its instruments deeply")

Theme: pattern depth — only now, on top of a proven measurement stack. **Questions 11.0 demands:** Does each name behave differently by regime? Do bounce rhythms decay? Does BTC lead the alts we trade? Which graveyard rejections were mistakes?

**11.1 — Fingerprint 2.0 (regime-conditional per-name profiles).** Split each name's dip/bounce fit by regime at sample time; entries use the profile matching the live regime; names whose profiles diverge strongly across regimes get flagged (they are two instruments wearing one ticker). Tripwire: profile store versioned; entries read the regime-matched fit. Soak: 2 days, spot-check three names' profiles against their charts.

**11.2 — Peak-rhythm 2.0 with decay.** Rhythm medians become exponentially-weighted with a half-life knob; a name whose rhythm broke (stale cycle) loses its rhythm bonus instead of trading on a dead beat. Tripwire: decay math unit-tested. Soak: rhythm ages visibly on the confidence card.

**11.3 — Cross-asset lead-lag.** Measure (report-only first) whether BTC/ETH moves lead the alt candidates by 1–3 cycles; publish `LEAD_LAG.json`; a later micro-installment may add a small entry-timing tilt, knob-gated, shadow-first. Tripwire: correlations computed on live prints only. Soak: report reads sanely across one volatile day.

**11.4 — Research OS auto-experiments.** The queued questions (Q001–Q007…) each get a machine-runnable experiment spec {hypothesis, data slice, metric, pass/fail}; the weekly lane executes one experiment and files the answer with evidence into the knowledge graph. Tripwire: one question resolved per week or blocked-reason stated. Soak: first resolved answer survives your reading.

**11.5 — Graveyard mining.** The counterfactual engine already prices what we did NOT do; 11.5 promotes it: rejection reasons whose would-have outcomes are persistently positive (e.g. a too-tight gate) generate a filed hypothesis into the Research OS queue automatically — the system asks for its own rule changes, with receipts, never applies them itself. Tripwire: hypothesis rows cite ≥ 30 graveyard samples. Soak: first auto-filed hypothesis is one you'd have written yourself.

---

# PART VIII — 12.0 · THE INSTITUTION ("outlives any session, any operator absence")

Theme: durability of the whole, not features. **Questions 12.0 demands:** Could this restore from ash? Could someone else run it? Do the books close like a firm's?

**12.1 — Audit-grade monthly statement.** Auto-generated per calendar month: opening/closing equity per book, realized/fees/vault sweep, trade count, Δ-vs-null, breaker events — one PDF-ready markdown, archived forever.
**12.2 — Disaster-recovery drill.** A scripted, operator-run drill: restore the repo from the newest archive into a scratch branch, run one cycle, prove parity (LEDGER hash, equity within cents). Filed as `DR_DRILL_<date>.json`. Quarterly.
**12.3 — Multi-venue arbitration.** When more than one venue can fill an order, choose by fee+liquidity score from the 10.3 snapshots; decision logged with the runner-up so the choice is auditable.
**12.4 — Capital ladder & compounding policy.** Written policy in-code: vault sweep percentages by equity band, when vault converts to withdrawn (live-mode only), max book size before splitting — so growth follows rules, not mood.
**12.5 — The succession pack.** One generated document + machine-readable system map: every store, every lane, every knob, every kill, the soak protocol, and how to hand an installment to a coding session — so the platform survives me, any future model, or a month of your absence. This directive is its seed.

---

# PART IX — THE 90-DAY COVENANT (in force NOW, alongside all of the above)

The clock started 2026-07-20 05:12 UTC. To protect it: NO resets (a reset restarts the 90 days — the gate reads days-since-reset); if a reset is ever truly forced, STANDARD mode only, never genesis. Weekly ritual (15 minutes, Sundays): read the scorecard (8.6+/9.6), the spine, LIVE-HANDOFF READINESS, and the newest EDGE numbers; file anything odd as the next micro-task. Let losing days stand — they are data; the nulls are the judge, not the day's color. Installments 0 through 8.5 are safe during collection (observation/labels); 8.6-on touch behavior only through shadow-first knobs with pre-registered kills, which is exactly what the covenant permits.

The bar has never moved: 100 out-of-sample forward trades across 90 unbroken days, fees on, beating the do-nothing nulls. Everything in this directive exists to make that verdict undeniable — whichever way it lands.
