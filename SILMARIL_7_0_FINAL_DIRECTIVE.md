# SILMARIL 7.0 — FINAL ASSEMBLY DIRECTIVE · THE CLOSED LOOP

### Operator ruling: this IS the completion of 7.0 — no new version number. Supersedes and fully absorbs the 7.1 Reconciliation Directive. Hand any executing session THIS file only.
### One sentence: 7.0-FINAL is the release where every loop closes — every number reconciles to one owner, every learning system survives a reset, every subsystem is provably in the decision path or honestly stamped out of it, and the edge-search machinery that already exists is finally allowed to run.

---

## ⚑ LANDED LEDGER — SHIPPED AND PROVEN IN THE 7.0 FINAL WIRE ZIP (2026-07-19)

The following items from this directive are ALREADY CODED, TESTED, AND DELIVERED. Do not redo them; verify them (their tripwires are in the battery, now 60 tests, 60/60 green on both the full-data tree and a fresh post-genesis tree):

- **R2 dup-BUY guard** (`buy()` refuses held names) + belt-and-suspenders in the buy loop — T55. The exact SOLUSDT/STRK/VETUSD dup rows are now flagged as `legacy_pre_epoch` by reconciliation and archive out at reset.
- **R1 one book of record**: `LEDGER.jsonl`, single writer inside the live PaperBook (backtests physically cannot write canon) — T55.
- **R1 Master mirror law** (`master_brain.mirror_canon:"auto"`): the Master opens ONLY positions a real book holds (tagged `mirrors`), force-closes on `BOOK_CLOSED (canon mirror)` when the book exits, and records `ACCEPT-WAIT` verdicts otherwise — T56, plus a live functional test.
- **R3 honest Master tail**: closed round-trips + genuinely-open BUYs only; orphan SELLs impossible — T56.
- **R4/R5**: reconciliation extended (epoch-scoped dup check, mirror-law check) and **`EQUITY_TRUTH.json`** emitted every cycle (total · Δ vs $60k start · open-committed) — T61. Ran green against the real July-18 data.
- **V1/V2 the vault**: `CHAMPION_FORWARD_LEDGER.jsonl` appended on every close (the election can finally accumulate across resets — the "Lickitung forever" root cause); CALIBRATION removed from the standard-reset delete list; the preserved-forever roster reclassed LEARNING so the post-wipe DERIVED sweep can never kill it; **archive-first reset** that REFUSES to run if archiving fails (Law 26) — T57/T58, proven by a scripted reset rehearsal.
- **Genesis interlock**: burning the library now requires typing `GENESIS-BURN-THE-LIBRARY`; `WIPE` alone = standard (learning kept).
- **T2 maturity gate** (`maturity {mode:auto, min_fit_events:12}`): fitted-book entries require ≥N fingerprint dip-events or ≥3 resolved bounce-tries on tape (tape evidence survives resets); GEKKO exempt by doctrine — T60.
- **H1** files-map hoisted to module scope — the Governor / Interrogator / Calibration / Data-Ledger "loading" bug is dead. **H2**: all 46 empty catches now report through a visible RENDER-FAULTS strip (broken ≠ pending, forever). JS parse-verified.
- **U2 venue truth**: `scripts/venue_universe.py` + `venue_universe.yml` (daily, keyless, in Actions where egress is open) → `VENUE_UNIVERSE.json`; wired into the Master's venue gate. Parsers unit-tested on real payload shapes.
- **Workflow law (operator directive, in full)**: all 13 workflows verified — every lane owns its OWN concurrency group (nothing can queue behind, delay, or displace another workflow), `cancel-in-progress: false` everywhere, daily stays on the */10 cron, selftest now daily + on every push, verify_install weekly, one-shots stamped MANUAL BY DESIGN with reasons, every commit step pull-rebases with retries, and daily/hourly/analytics/selftest file their own 🔴 ENGINE RED issue on failure — T59.
- **Battery grown 53 → 60** (T55–T61), green on both trees.

**STILL OPEN from this directive** (the next sessions' work, in order): Tier 1 VIEWS layer (H3) · headline Δ-vs-null promotion (H4) · exit-grade renames (H5) · provenance footers (H6) · Tier 4 bootstrap-ladder states + market-calendar messaging (T1/T4) · Tier 5 FLOW_PROOF + W1–W12 closures · Tier 6 edge engine (calibration teeth in sizing, attribution monitor, Δ-null leaderboard columns, Conductor C2 wiring) · Tier 7 health-chain four-link fix + fallback waterfalls · Tier 8 inventory verdicts · the Final Exam.

---

## 0. TO THE EXECUTING SESSION — READ BEFORE YOU TOUCH ANYTHING

You are picking up SILMARIL (repo `TheSeanMitchell/SILMARIL-2.0`) after the 7.0 build, a genesis wipe (2026-07-17 15:23 UTC), and a disappointing two-day post-wipe run. This directive was produced from a **direct read of the July-18 5PM full repo backup** — 365 Python modules, ~300 data stores, a 1,667-line dashboard, 12 workflows, a 53-tripwire selftest battery. Every finding carries a `file:line` receipt. Line numbers are from that backup; **verify each receipt against the current tree before editing** (files may have shifted).

This is a multi-session directive. It is ordered so that each phase leaves the tree green and shippable. Do the phases **in order**. Do not skip ahead to the exciting parts; the exciting parts only mean something once the boring parts are true.

### Standing doctrine — non-negotiable, applies to every change in every phase:
- **Read the whole file before editing it.** The historic "landed but didn't" failures came from inferring structure from skeletons. No exceptions, even for files you think you know.
- **Additive, never destructive.** Extend; never remove working systems without explicit intent. Retirement = move to `attic/` with a dated note, never silent deletion.
- **Exact-text `str_replace` only.** Never regex a multi-line definition.
- **Every diagnosed bug ships a selftest tripwire** that would catch its regression. The battery (currently **53** tripwires, `scripts/selftest_5_1.py`) only grows.
- **Build-verify-package:** `py_compile` every touched `.py`, JS-parse `docs/index.html`, run the full selftest on BOTH a fresh-install tree and a full-data tree, THEN package a complete-file ZIP at correct repo paths with a `present_files` manifest. The operator deploys by GitHub web drag-and-drop only.
- **Realized, broker-confirmed P&L is the only score.** Everything else is instrumentation.
- **No synthetic data in live modules. Ever.** After a wipe the correct output is "insufficient evidence," never a fabricated number.
- **Every new behavior is knob-gated in `PARAM_CATALOG.json` with a named, pre-registered kill switch.** Nothing autonomous ships without an off switch and a kill criterion written down BEFORE it runs.
- **Fail loud.** A subsystem that fails silently is worse than one that doesn't exist. This release ends silent failure as a class (see Tier 1 and Tier 7 — silent failure is how the health panel itself has been lying for 31 hours).
- **Brutal honesty, no cheerleading.** $100–300/day is unproven hope, never income. The live-money bar is unchanged: **100 out-of-sample trades surviving the gate across 90 unbroken days.** Nothing in this directive moves that bar.

### The reframe:
7.0's failure was not an alpha failure. The machine contradicts itself (three parallel simulations shown as one account), hides its own failures (46 empty catch blocks; the health panel reading a 31-hour-stale file), and amnesia-wipes its own learning (genesis reset + forward records that live inside the books it flattens). **7.0-FINAL's job is to close every one of those loops so the machine can be trusted to run itself — and then to switch on the edge-search loop that was already built and never enabled.** No new alpha families. No new subsystems that aren't closures of existing ones.

---

## 1. WHAT A PROFESSIONAL WOULD DO WITH 40 LIFETIMES OF TAPE — THE DESIGN CREED

Every decision in this directive traces to one of these ten rules. When in doubt during execution, pick the option that satisfies more of them.

1. **One book of record.** Every fill is written once, by one writer, to one canonical ledger. Every other view derives from it and can be diffed against it mechanically. A shop where the blotter and the P&L disagree is not a shop.
2. **Knowledge is capital — never delete it.** Positions are disposable; observations are not. A pro who liquidates the book does not burn the research library. State (cash, positions) and Knowledge (fingerprints, outcomes, calibration, forward records) live in different vaults with different rules.
3. **Evidence before risk.** No name trades without a minimum count of resolved observations on that name. "I don't know yet" is the default posture, especially after any reset. The machine earns the right to trade each symbol.
4. **Attribution before adaptation.** Know exactly which names, strategies, hours, and regimes the P&L came from before letting anything adapt. (The MKR lesson: one symbol was once 183% of net profit. A machine that adapts to unattributed P&L adapts to noise.)
5. **The null is the opponent** (Law 10). The scoreboard is delta versus doing-nothing (HODL/SPY/CASH), per book and per strategy — not raw realized green. Realized +$46.77 while 22 points behind HODL is a loss, and the dashboard's headline must say so.
6. **Fees at the gate, not the postmortem.** An entry that cannot clear round-trip friction at its own fitted target is not a candidate. (The fingerprint system already fits fee-clearing targets for 223/434 names — make that the gate everywhere.)
7. **Calibration has teeth.** If the machine says 34% and wins 20%, the machine is lying to itself; sizing must haircut by measured calibration, and the Brier record must survive resets.
8. **Pre-registered kills.** Every adaptive behavior states, before it runs, the evidence that will turn it off. The report card, not enthusiasm, decides what stays.
9. **Search, don't hope.** Edge is found by running controlled counterfactual experiments on your own tape (the Conductor ladder C0→C1→C2 — already built, one rung from live) — not by adding indicators.
10. **The machine says why, in writing, every time.** Every buy, skip, hold, exit, and promotion carries a one-line reason from named evidence. If a panel can't name its file, its consumers, and its last influence on a decision, it is decoration and must say so on its face.

---

## 2. TIER 0 — ONE BOOK OF RECORD (reconciliation; nothing downstream matters until numbers agree)

### R1 — There is no canonical trade ledger; the Master runs a PARALLEL simulation.
**Receipt:** `silmaril/execution/master_account.py:72` `build_master_account()` loads `paper_sim_live.json` for context (line 79) but runs its **own** `_buy`/`_sell` (lines 118, 142) appending to its **own** `book["trades"]` (133, 155), emitting `recent_trades` (353). Proof from live data: the Master bought MOG-USD/DYDX-USD/GALA-USD while the crypto book bought SOL/ZEC/VET/DYM/STRK — same cycles, disjoint trades. The "one real account" (−4.9%) and the "profitable crypto book" (+$46.77) never had to agree because they are different books.

**Fix:** Introduce **`LEDGER.jsonl`** — append-only, one row per fill, one writer (the paper-sim recorder), schema: `{t, book, sym, side, qty, px, fee, trade_id, cycle_id, strategy, reason}`. Every book's `trades` array becomes a derived view of it. The **Master consumes canon**: its rows must be a distilled, tagged subset of real book fills (`mirrors: {book, trade_id}`), never independent fills. If a true watching-only shadow book is wanted, every shadow row still derives from a canon fill.

**Tripwires:** (T-CANON-1) every `MASTER_ACCOUNT.json → recent_trades` row maps to a canon `trade_id`; (T-CANON-2) Master never holds a position no book holds; (T-CANON-3) per book, `sum(canon fills) == book cash+positions` to the cent.

### R2 — Duplicate BUY rows (recorder bug, receipts).
**Receipt:** `docs/data/paper_book_crypto.json` logs SOLUSDT (t=`2026-07-17T18:44:32.394161`) and STRK-USD (t=`21:31:10.707891`) each **twice with identical microsecond timestamps**; `paper_book_aggressive.json` double-logs VETUSD and STRK-USD. Cause: `paper_sim.py` `PaperBook.buy()` (line 446) has **no already-held guard**; the candidate loop checks `sym in positions` only on the maker-rest branch (1216), so a name filled from a resting maker order (1046) re-enters the market-buy path (1229) in the same cycle. This inflates trade counts, corrupts win-rate denominators and the per-symbol history the sizer reads (1174), and creates phantom "open" trades — the direct cause of "GEKKO shows 4 open but LIVE POSITIONS shows 0."

**Fix:** (a) `buy()` refuses if `sym in self.positions`; (b) dedupe candidates against `positions` and `_pend` before the loop; (c) a maker-fill and a market-buy may never touch the same symbol in one cycle. **Tripwire (T-CANON-4):** no two rows anywhere share `(sym, side, t)`.

### R3 — The Master's "3 nonsensical trades" is a DISPLAY bug.
**Receipt:** `master_account.py:361` `live_trades_tail = reversed(book["trades"][-3:])` — the Command tab renders the last three raw rows (currently SELL DYDX / SELL GALA / BUY LCID), i.e. two SELLs whose matching BUYs scrolled off plus one open BUY. The underlying 10-row `recent_trades` is fully matched. **Fix:** render matched round-trips or clearly labeled OPEN/CLOSED positions from canon. Never an arbitrary N-row tail that breaks pairing.

### R4 — Cross-view reconciliation, proven every cycle.
LIVE POSITIONS, RECENT TRADES, ALL-CHARTS-EYESHOT, the Markets portfolio, and OPEN-TRADE TRUTH each recompute from whatever file is nearest. **Receipt for the worst case:** the OPEN-TRADE TRUTH strip printed "$0 committed across 0 open trades" while the books held seven positions — its reader is pointed at the wrong store. After R1 they reconcile by construction; **prove it**: a RECONCILIATION panel + engine job that, every cycle, asserts open-count, committed-$, and realized-P&L match across every view and canon, RED on any mismatch. Normalize the symbol field to `sym` everywhere (some panels read `symbol`). **Tripwire (T-CANON-5):** reconciliation status GREEN, and OPEN-TRADE TRUTH's committed-$ equals canon's open-position sum.

### R5 — There is exactly ONE equity number.
The engine computes, each cycle, `EQUITY_TRUTH.json`: per-book mark-to-market, Master, total, deltas vs each null — from canon + current marks only. Every panel that shows money reads THIS file. No panel computes equity again, ever. (This is the general form of the bot's one good technical question — "list every place the UI recomputes instead of reading canon" — answered by making recomputation structurally impossible; see Tier 1 VIEWS.)

---

## 3. TIER 1 — THE DASHBOARD BECOMES A DUMB, HONEST RENDERER (VIEWS + fail-loud)

### H1 — Four "loading" panels, ONE scoping bug (likely a one-line fix).
**Receipt:** `const files = {…}` is declared **inside `renderBrain()`** at `docs/index.html:880`; `renderQuestions` (1146), `renderSizerStrip` (1156), `renderCalibration` (1162), `renderDataLedger` (1167) reference `files.*` **outside that scope** → `ReferenceError` → swallowed by empty `catch(e){}` → the literal `loading…` forever. These are exactly the four panels the operator flagged broken: 🧠 INTERROGATOR, 🛡️ GOVERNOR (sizer strip), 🎯 CALIBRATION, 🗄️ DATA LEDGER. Their data files (`QUESTIONS.json`, `SIZER.json`, `CALIBRATION.json`, `DATA_LEDGER.json`) all exist and are populated. **Fix:** hoist the `files` map to module scope; grep every `files.` reference resolves.

### H2 — 46 empty `catch(e){}` blocks make BROKEN look like PENDING.
**Receipt:** `docs/index.html` has 46 empty catches of 58 total. **Fix (pattern, applied to every render):** every catch writes a visible, distinct state into its own panel — `⚠ render error: <panel> · <message>` vs `⏳ first cycle pending · needs <file>` — never bare `loading…`. After this lands, every remaining "broken" panel the operator listed (Decision Flow, Session Anatomy, Timer/Edge-capture sim, Opportunity Audit, Threshold shadow, Drop-threshold shadow, Survival Leaderboard, Promotion Ladder, Live-Handoff Readiness, System Brain) self-declares as pending-data or a named error you then fix. **Tripwire (T-UI-1):** zero occurrences of an empty catch body in `docs/index.html`; selftest greps for it.

### H3 — VIEWS: the engine precomputes every panel; the UI computes NOTHING.
This is the eternal fix for the whole "panels disagree" class. New engine stage writes `docs/data/views/VIEW_<panel>.json` for every money- or count-bearing panel, derived **only** from canon (`LEDGER.jsonl`, `EQUITY_TRUTH.json`) and the owning store. The dashboard renders views verbatim. **Tripwire (T-UI-2):** a views-vs-canon differ runs in selftest — any drift is a red build. The UI can no longer be wrong on its own; it can only be late.

### H4 — One progress metric, and it's the honest one.
**Receipts:** `COMPOUNDING_PROJECTION.json` shows `current_equity: 10046.77` (crypto realized-only, fees netted) while true four-book equity was ~$38,048 against a $40,000 start; `SESSION_TODAY.json` shows "+$44.39 today" beside −$1,952 total; the operator's own spine already prints the most honest number in the system: **`Δ vs NULL crypto−HODL: −22.15%`** (Law 10). **Fix:** the headline everywhere is **Total Equity (all books + Master) and Δ vs nulls**, from `EQUITY_TRUTH.json`; realized-net-of-fees is the second line and never renders without equity beside it; the compounding projection is whole-system net-of-fees or is stamped `crypto book · realized-only · excludes open drawdown — NOT the portfolio`. Its 'honest_note' already says this; the headline must match its own note.

### H5 — Exit-grade taxonomy is mislabeled and scared the operator.
**Receipt:** `silmaril/execution/exit_forensics.py:108` — "CATASTROPHIC" means post-exit **leak ≥ 4%** (the name kept RUNNING ≥4% after we sold). Both "catastrophic" crypto exits were **wins sold too early**, not disasters; the operator read "2 catastrophic" as blowups. **Fix:** rename grades to `GOOD / EARLY / VERY_EARLY / LATE(-loss)`, always render realized sign next to the grade, and keep the leak number. Leak is the system's single best exit-improvement signal (avg 5.1% left on the table) — Tier 6 consumes it.

### H6 — Every panel carries a provenance footer.
One shared renderer stamps each panel: `source: <file> · written by <module> · age <n>m · consumers: <list or DISPLAY-ONLY>`. This is the bot's Evidence/Consumers idea made mechanical, and it permanently answers "is this wired or is it bloat?" panel by panel.

---

## 4. TIER 2 — THE UNIVERSE MADE TRUE (the question asked a thousand times, closed forever)

### U1 — What the universe actually is today (receipts).
The crypto universe is a **hardcoded static list**: `silmaril/universe/expanded.py:263` `CRYPTO_TOP_100` (101 coins) + `TOKENS_LOWER_CAP` (builder at 466). It is **not** a live pull from Binance.US, Coinbase, or Robinhood. Of it, **91** have fresh yfinance `-USD` data → the census "crypto 91 listed / 100% fresh." The funnel's "seen 344" merges a **404-symbol ccxt/Kraken USDT tape** (`ccxt_samples.json`; `paper_sim.py:323`, canonicalization 1518–1533); the extra ~250 are USDT ghost pairs correctly filtered "stale/ghost — can't fill" — exactly the OPPORTUNITY JOURNAL's +40% "missed movers" (DOODUSDT, XECUSDT, 1MWOJAK…). **They are not on the operator's venues. The journal is currently a list of regret for trades that never existed.**

### U2 — VENUE TRUTH (run inside GitHub Actions; the coding sandbox proxy blocks these domains).
New Actions job (daily, keyless): fetch Binance.US `exchangeInfo`, Coinbase Exchange `products`, Robinhood's crypto list → canonicalize to `-USD` → write **`VENUE_UNIVERSE.json`** `{sym: {binanceus, coinbase, robinhood, min_notional, status}}` with a fetched-at stamp and a 7-day staleness alarm. **Tradeable = (has fresh price data) ∩ (listed on ≥1 operator venue)**. The funnel's "seen" becomes venue-listed reality; the journal reports only venue-tradeable misses (ghosts move to a collapsed "off-venue movers" footnote). The stock universe already scans 923 names — apply the same venue stamp via Robinhood/Alpaca listability so "seen 524" is also venue-true.

### U3 — Operator decision to surface (don't guess): full venue union (~hundreds of names, incl. thin low-caps) vs deliberate top-N-by-liquidity. Recommendation: **venue union, then a liquidity floor** (spread + depth from the fee/spread stores) so entries fire only where fills are real. Wire ONE choice end-to-end and label it on the funnel.

---

## 5. TIER 3 — THE KNOWLEDGE VAULT (learning that survives every reset — the amnesia bug, killed)

**The good news the operator doesn't know:** a learning-preserving reset ALREADY EXISTS. **Receipt:** `.github/workflows/reset_internal_clean.yml` takes `wipe_mode: standard | genesis` — "standard = books/sleeves/master reset, **learning kept** · genesis = learning resets too (archives are sacred) — Law 30," and genesis deletes exactly the stores classed LEARNING in `docs/data/STORE_REGISTRY.json`. The July-17 wipe was run in **genesis** mode (`WIPE_MARKER.json → mode: genesis`). The instinct "should we be doing a NON-genesis wipe?" is correct, and the button is already on the workflow.

**The bad news, with receipts — the vault leaks even in standard mode:**
- **V1:** `STORE_REGISTRY.json` classes 289 stores (215 DERIVED / 48 STATE / **18 LEARNING** / 8 LEDGER), but `GRAVEYARD.json`, `REPORT_CARD.json`, `CONDUCTOR.json`, and `UNIVERSAL_CARDS.json` are **unregistered**, and `CALIBRATION.json` is classed DERIVED — worse, `scripts/reset_internal_clean.py:41` **deletes CALIBRATION.json even in standard mode.** The machine's memory of "when I said X% I actually won Y%" dies in every reset. Calibration history is learning, full stop.
- **V2 — the Lickitung root cause survives standard reset:** the champion forward record is **derived from closed trades inside `paper_book_*.json`** (`champion_validation.json`: only 2 strategies, n=2 each, survivability 0 "insufficient closed trades"), and every reset flattens the books → forward evidence returns to ~0 → the ≥5-forward-trade election can never complete → the seed default `MR_patient_d3` stays champion forever. The Pokémon evolution cannot fire because its evidence is burned before it accumulates.
- **V3:** `snapshot_history.jsonl` is cleared on reset with **no archive step** — a Law 26 violation ("archived, never discarded") in the reset path itself.

**Fixes:**
1. **`CHAMPION_FORWARD_LEDGER.jsonl`** — append-only LEARNING store; every closed trade appends `{strategy, book, sym, entry_t, exit_t, pct, fees, regime, outcome}`. The election reads THIS ledger, never the books. Forward records now accumulate across every reset, and rotation can finally happen on evidence. Label the two leaderboards unambiguously: **HYPOTHESIS (backtest)** — currently `MR_d1_t2_s12` "Scarlet Witch," +38.9%/34 backtested — vs **CHAMPION (forward-proven)** — `MR_patient_d3` "Lickitung," elected by survivability. Different strategies, different criteria; the UI showing both unlabeled is why it "appears broken."
2. **Registry completion + reclassification:** register every store on disk (tripwire T-VAULT-1: no unregistered store); move `CALIBRATION.json`, `GRAVEYARD.json`, `REPORT_CARD.json`, conductor ledgers, `UNIVERSAL_CARDS`/`CONFIDENCE_CARDS` observation histories, and the new forward ledger to LEARNING; remove CALIBRATION from the standard-reset delete list.
3. **Archive-first reset:** before any reset touches a LEDGER/LEARNING store, copy it to `archive/<ISO-date>/` in the same commit (Law 26 made mechanical). Tripwire T-VAULT-2: reset refuses to run if the archive step is missing.
4. **Asymmetric confirmations:** standard reset keeps `WIPE` confirm; **genesis requires typing `GENESIS-BURN-THE-LIBRARY`** and prints, in the workflow summary, exactly which learning stores it is about to destroy. Genesis should feel like what it is.
5. **RESET REHEARSAL (scripted drill, shipped as a workflow):** snapshot → standard reset on a scratch copy → assert all LEARNING+LEDGER stores byte-identical → assert bootstrap enters OBSERVE (Tier 5) → assert mature names re-arm from preserved evidence. The drill is the proof the vault holds; run it before the operator's next real reset.
6. **KNOWLEDGE RESTORE one-shot:** a dispatch workflow that re-imports LEARNING stores from a dated backup ZIP path — because the operator's July-18 full backup already contains everything the genesis wipe burned. Nothing from before the wipe is actually lost; it's sitting in the backup waiting for this tool.

---

## 6. TIER 4 — TRUTHFUL TIME (post-reset behavior, market calendars, maturity)

### T1 — The post-wipe window is QUIET, not LEARNING (why it "went dumb instantly").
**Receipt:** `paper_sim.py:190` `QUIET_AFTER_WIPE_MIN = 120.0` — trades are suppressed for 2 hours and **no evidence gate follows**. `WIPE_MARKER.json` wiped 15:23; the Master bought WDC at 17:37 (~2h10m later) on backtest-seeded priors with zero forward evidence, and lost. The system did exactly what it was coded to do; the code just doesn't match the doctrine ("a scientific recording system that records data for the purpose of making better decisions").

**Fix — the BOOTSTRAP LADDER (per book, states rendered on every book header):**
`OBSERVE` (no entries; accumulating resolved observations) → `EVIDENCE-GATED` (entries only on names whose maturity clears the gate) → `FULL` (normal operation). After a **standard** reset with a preserved vault, mature names re-arm immediately — the ladder is fast because knowledge survived. After a **genesis** wipe, OBSERVE lasts until real maturity exists — days, and that is correct and the UI says so proudly: "OBSERVE — earning the right to trade · 14/25 names mature."

### T2 — Confidence MATURITY (the single best idea in the other bot's notes, grounded and enforced).
Per-name gate: a symbol is tradeable only when its record shows **≥ N resolved observations** (knob `maturity.min_resolved`, suggest 10) including **≥ W wins** (suggest 3), with age ≥ A days. Every confidence surface renders maturity inline: `EOS 34% · 17 obs · 3W/2L · 4d · LOW`. The Universal Confidence Card (27 fields) gains four: `obs_resolved, wins, losses, first_seen`. The Master gate already reads cards (`master_account.py:78`, top-percentile cut at 284) — add maturity as a hard pre-filter before the percentile, so the gate literally cannot select an immature name. **Tripwire (T-MAT-1):** no entry row in canon for a name below maturity while the knob is on.

### T3 — Floor-confirm in EVERY regime (stop catching falling rocks).
**Receipt:** `paper_sim.py:1112–1130` — the falling-knife floor check ("last k prints hold above the window low") engages only when `_regime` starts `DOWN`. Current regime SIDEWAYS → a name printing lower every 10-minute sample still gets dip-bought. **Fix:** per-name floor-confirm independent of book regime, knob-gated (`entries.floor_confirm_all_regimes`), with the floor state shown on the candidate row ("floor printed 3/3 ✓" / "still falling ✗ — waiting").

### T4 — Market calendars: CLOSED is not WARMING.
**Receipt:** `metals_samples.json` / `energy_samples.json` hold ~1,500 points spanning ~20 days (the feeds are rich and wired), but the warmup gate (`paper_sim.py:361–430`, `_WARM_KNOB {min_points:8, min_span_h:1.5}` within 6h) can't be satisfied on a weekend because COMEX/NYMEX/NYSE **don't print** — so books display "warmup needs ~2h," which is false. Honest answer to "if we can trade it in the real world we can trade it here": on a weekend you largely cannot trade spot metals/energy/stocks in the real world either; crypto is 24/7 and correctly did trade. **Fix:** per-book session state machine from `ECONOMIC_CLOCK.json` — `MARKET_CLOSED (resumes Mon 06:30 PT) / WARMING_UP (n of 8 prints) / ARMED / TRADING` — and FIRST-TRADE READINESS renders the true state. **Tripwire (T-TIME-1):** a book never renders WARMING while its venue calendar says closed.

### T5 — Locked capital is a surfaced decision, not a silent default.
**Receipt:** `paper_sim.py` `TIMEOUT_EXIT = False` — a position that never hits target or stop sits forever (SOL, DYM currently). By design for patient MR, but it's invisible. **Fix:** render locked-capital $ and age per book; put the tradeoff to the operator as a knob (`exits.max_hold_days`, default off) rather than changing behavior silently. If enabled, exits tag `TIMEOUT` distinctly so exit forensics can judge whether the timeout is saving or costing (it already grades this).

---

## 7. TIER 5 — CLOSE EVERY LOOP (wire what's starved, prove what's wired, stamp what's decoration)

The audit found the operator's fear is **half** right. Several doubted systems ARE wired into decisions — the problem is they never show it. Others produce output nobody consumes. This tier ends the ambiguity permanently with **FLOW_PROOF**, then closes each named loop.

### FP0 — FLOW_PROOF: consumption receipts, every cycle (the eternal wired-but-starved killer).
Every producer stamps its output `_meta: {cycle_id, produced_at, producer, schema_v}`. Every consumer appends to `CONSUMPTION_LOG.jsonl`: `{cycle_id, consumer, source_file, source_cycle}`. A REQUIRED-CHAINS list (~15 chains below) is verified each cycle by the wiring auditor; the WIRING panel upgrades from "file fresh" to "**consumed this cycle by <N> named consumers**"; any required chain unconsumed for 3 cycles goes RED on HEALTH. Consumers assert expected keys exist and fail LOUD to HEALTH on schema mismatch — the historic field-name-mismatch class ends here. **Tripwire (T-FLOW-1):** all required chains consumed within the last 3 cycles on the full-data tree.

### The loop-by-loop closures (each = verify receipt → wire or stamp → FLOW_PROOF chain → tripwire):

**W1 — Confidence cards → Master gate: WIRED (prove it visibly).** Receipt: `master_account.py:78` loads `CONFIDENCE_CARDS.json`; percentile gate at 284–315; line 189 already falls "back to raw evidence percentile until confidence re-earns its calibration." Add: maturity pre-filter (T2), and the panel line "consumed by: Master gate · this cycle's cut 0.303 · selected EOS, INJ."

**W2 — Confidence → live sizing: WIRED (prove it visibly).** Receipt: `paper_sim.py:1183–1189` `_ce_map → _conf → _mult` sets the wager multiplier (1180: "prefer the UNIFIED confidence engine — blends peak rhythm, phase…"). Panel shows "sizing consumer: <sym> wager ×<n> this cycle."

**W3 — Fingerprints → entries: WIRED (make it the law it claims to be).** Receipt: `paper_sim.py:877–1103` — per-name fitted dip/target/stop (`_fits.get(sym)` at 1101), a fingerprint red-tape exception at 958, degenerate-fit guard near 1103. 223/434 names carry fee-clearing fits. Closures: (a) unfitted names fall back to the champion **and the row says so** ("fallback: champion params — no fit yet"); (b) the drop×bounce matrix and threshold sweep become the fingerprint's **refresh inputs** — when a cell with n≥25 fee-cleared expectancy beats the current fit, promote it to CANDIDATE-FIT, shadow it 25 resolved observations, then adopt (knob `fingerprint.matrix_promotion`, kill: shadow underperforms current fit). The sweeps stop being wall art and become the per-name parameter search.

**W4 — Peak rhythm → holds: HALF-WIRED (close it).** Receipt: `PEAK_RHYTHM.json` loads at `paper_sim.py:648` and feeds the confidence blend (1180), but `max_hold_min` comes from champion params (672–676; per-name override plumbing exists at 874). Close: per-name expected-hold = f(median cycle, e.g. 2× median, clamped) via the 874 override path, knob `holds.rhythm_native`, kill: rhythm-holds' realized capture < champion-hold baseline over 50 closes (edge-capture sim already measures this).

**W5 — Time-of-day → entries: NOT CONSUMED by any trade path (receipt: zero references in `paper_sim.py`/`master_account.py`).** Decision, not assumption: either wire as a knob-gated entry-window weight (`entries.tod_weight`, kill pre-registered) **or stamp the panel DISPLAY-ONLY**. Recommendation: wire it — POWER_HOUR is measured evidence and the creed says concentrate where the edge is measured — but only through the Conductor's shadow scoring first (Tier 6), so it earns its way in like everything else.

**W6 — Dr. Strange: correctly gated at observe (say so).** Receipt: `feature_gates.py:26–28` `{"mode":"observe","min_samples":50, evidence_file: DR_STRANGE_TRIAL.json}`. Panel must display its gate state and samples-to-graduation instead of looking mysteriously idle.

**W7 — MTF ladder → gates: verify the consumer.** `mtf_regime.py` writes; `brain_wiring.py` references. Confirm a real decision consumer (veto/boost) or stamp DISPLAY-ONLY; if wiring, Conductor-shadow first, same as W5.

**W8 — Graveyard/counterfactuals → policy: WIRED TO NOTHING actionable yet.** Receipt: DISCOVERY computes would-have outcomes for every rejection ("not_selected n=242 avg would-have −0.55%" — the machine's rejections are currently BEATING its selections' counterfactual, i.e., the filter is adding value; say that out loud on the panel). Closure: a weekly `POLICY_REPORT.json` distilling graveyard + counterfactual + exit-leak into ranked policy hypotheses, consumed by the Conductor (Tier 6) as its experiment queue. Learning-from-what-we-did-NOT-do finally feeds something.

**W9 — Exit leak → exit policy.** avg 5.1% post-exit leak with HELD_GAIN dominating exits = documented money left on tables. Feed leak-by-name into the rhythm-hold calc (W4) and into the sweep as a "later-target" hypothesis lane. Never auto-change exits without the Conductor shadow first.

**W10 — Regime classifier → everything it should touch.** The classifier has earned trust (85.7–100% graded per book). Consumers to verify/close: floor-confirm (T3 makes it per-name anyway), aggression ladder, champion-per-regime election (elect and record champions **per regime**, from the forward ledger, so SIDEWAYS-champion ≠ DOWNTREND-champion; knob-gated).

**W11 — Sleeves A–G report to the same judge.** Sleeve G (Geometry Sniper) is bleeding; nobody wrote its kill criterion. Every sleeve gets a report-card row with a pre-registered kill (e.g., G: −5% cumulative vs sleeve C over 50 trades → auto-bench to shadow). The card, not sentiment, benches a sleeve. Also fix the sleeve modal's missing close button (operator gets stuck) and the janky hover-chart (make it click-to-open; a modal that traps the operator twice in one tab is a UI bug class, add T-UI-3: every modal has a close path).

**W12 — News/Authority: research-division stamp.** It never trades (doctrine). Panel shows "RESEARCH ONLY — consumed by: Research OS" and its source health honestly (the "no sources this cycle" yellow is a real RSS fetch issue in the keyless lane — route feedparser through the daily keyed lane or record why empty).

---

## 8. TIER 6 — THE EDGE ENGINE (turn on the search machinery you already built)

**Plain words first:** no directive can conjure edge, and a 34/35 day proves volatility was harvestable that day, not that expectancy is positive. What a directive CAN do is close the search loop so that if a repeatable edge exists in this universe at these fee levels, the machine will find it, prove it forward, size it by calibration, and kill it the moment it decays. That loop is mostly BUILT. It has never been allowed to complete.

### E1 — The Conductor ladder: C0 → C1 → **C2** (the last mile).
**Receipts:** `CONDUCTOR_STATE.json`: 807/300 decisions logged, rung "C0 — logging only"; C1 shadow-scoring live in the spine (`cli.py:3591`, conductor_c1) with policies scored (P0 status-quo −0.6bps · P1 sit-out-downtrend −1.03bps · P2 sideways-only −1.05bps — none currently beats status quo, which is itself an honest, useful answer). C2 was pre-designed: "tiny ε on GEKKO after C1 shows positive uplift — never automatic."
**Directive:** wire C2 exactly as pre-designed, knob `conductor.c2` (default off) with `epsilon` (suggest 0.05 = 5% of GEKKO entries follow the current best challenger policy), eligibility only when C1 shows positive uplift with CI clear of zero, and the pre-registered kill: uplift ≤ 0 after 50 policy-influenced closes → auto-off + report-card entry. The experiment queue comes from W8's POLICY_REPORT. This is the engine's only sanctioned path for behavior to change itself: **hypothesis → C1 shadow → C2 ε-trial on GEKKO → report card → promote or kill.** Everything in W5/W7/W9/W10 that wants to change behavior enters through this door.

### E2 — Calibration with TEETH (and a memory).
CALIBRATION.json survives resets now (Tier 3). Closure: per-bucket reliability (when we say 30–40%, we win X%) feeds a **sizing haircut**: multiplier × min(1, observed/stated), knob `sizing.calibration_teeth`, kill pre-registered. The Master's line-189 fallback becomes principled: calibration below threshold → gate uses raw evidence percentile and the panel says why.

### E3 — Attribution, always on.
`ATTRIBUTION.json` each cycle from canon: P&L share by name / strategy / sleeve / hour / regime; concentration flag when any name >50% of a book's net (the MKR lesson as a standing tripwire, T-EDGE-1). Adaptive systems (E1, W3b) read attribution and refuse to adapt toward a single-name artifact.

### E4 — The scoreboard is Δ-vs-null, per strategy.
Survival leaderboard and champion panels add the only column that matters: delta vs the matching null over the same window (crypto vs HODL, stock vs SPY). A strategy that's green but loses to its null ranks below one that's flat and beats it. Law 10, mechanized.

### E5 — MKR/corrupt-feed verification.
EDGE CAPTURE shows "MKR +14.2% available, 0% captured" — before anyone chases it, verify the 5.11 two-print + oscillation quarantine is actually suppressing MKR's known stale-flip (~1365↔1229) and that its "available edge" isn't the phantom band. Receipts or it isn't edge.

---

## 9. TIER 7 — REDUNDANCY, SELF-HEALTH, AUTOPILOT (the machine minds itself)

### A1 — The health panel has been lying about the thing it exists to report (full receipt chain — fix all four links).
1. UI reads **`HEALTH_MATRIX.json`** (`docs/index.html:1272`) — which is **31+ hours stale** (`generated_at 2026-07-17T15:57` vs fresh api_health at 7/18 23:52). The FALLBACK-DEPTH zeros the operator sees are a frozen snapshot from a keyless run at wipe-time.
2. TWO writers produce `key_groups`: `health_matrix.py:90–97` (env-secret names only, keyless providers not counted) and `health_lights.py` — which was **built in 5.1 specifically to fix this exact bug** (its own docstring says so) and counts keyless providers correctly.
3. `health_lights` runs in the every-cycle spine (`cli.py:3589`) yet its block is **absent from fresh api_health.json** → it is failing silently every cycle inside the spine's try/except (the empty-catch disease, engine-side).
4. `analytics.yml` carries **zero secrets** (grep: 0 `secrets.` refs) and the reset workflow carries none — any key_groups computed in those lanes reads an empty environment by construction.
**Fix:** ONE owner (`health_lights`, keyless-aware) → merged into `api_health.json`; UI reads that; retire health_matrix's key_groups (attic); un-silence the spine loop (each spine-addition failure writes a visible line into HEALTH: "health_lights FAILED: <err>"); add a **SECRETS AUDIT** line computed in the keyed daily step ("repo secrets present: n/17 — [names missing]") because every-group-zero is also consistent with **no repo secrets being configured at all** — an operator action item to check in Settings→Secrets, which code cannot see. Then go further than "configured": a daily one-ping **WORKS test** per provider records configured vs actually-answering. **Tripwires:** T-AUTO-1 HEALTH_MATRIX age < 2 cycles or panel reads api_health; T-AUTO-2 key_groups present in fresh api_health; T-AUTO-3 zero silent spine failures (spine writes a pass/fail roster each cycle).

### A2 — Fallback depth ≥2 for every feed, for real.
Per feed group, a keyless-first waterfall with ≥2 working providers (crypto price: yfinance + ccxt/kraken + coingecko; stock: yfinance + finnhub/fmp/av/tiingo/polygon as keyed extras; metals yfinance×5 + OXR; energy yfinance×3 + EIA; news: google_rss + edgar + keyed extras; broker: alpaca). Cross-source disagreement >X% → quarantine the outlier (extends the 5.11 oscillation defense to the source level). Scarce keys stay budgeted (OXR/AV caps already exist — keep them).

### A3 — Workflow audit (12 files inventoried; close the gaps).
Exists and correct: shared `concurrency: silmaril-state` on all state-mutating workflows; daily `*/10` as fallback cadence behind the external pinger; hourly `:07` heavy lane; analytics 3×/day WIDE; backfill 08:10; weekly_backup Sun 00:00; selftest Mon 03:45; verify_install; one-shots (cleanup_5_11, integrity_backfill, remap_keys, compact_history); reset with wipe_mode.
Close: (a) **selftest on every push AND daily**, not weekly — a red battery should never wait six days to be seen; (b) a **FAILURE→ISSUE** step on daily/hourly/analytics (on job failure or selftest red, open/refresh a pinned GitHub issue titled `🔴 ENGINE RED — <date>` with the failing roster; the repo becomes self-reporting); (c) give **analytics.yml the same env block** as daily (A1.4) or explicitly mark it keyless-by-design in-file; (d) an **Actions-cron liveness** line on HEALTH (last daily-lane commit age; if >30m, "cadence degraded — check external pinger + Actions"); (e) weekly_backup verifies the archive/ dir is included (Tier 3's Law 26 output must be in the backup).

### A4 — Self-heal rules (bounded, boring, written down).
Stale feed → promote next provider in the waterfall + HEALTH line. Selftest red → sizer RED (entries halt; exits/positions stay live — the plumbing exists: `paper_sim.py:1066`) + issue. Store unparseable → restore from last archive copy + quarantine the corrupt file (never regenerate synthetically). Every self-heal action logs to `SELF_HEAL_LEDGER.jsonl`. No self-heal ever fabricates data or closes positions.

### A5 — AUTOPILOT definition (what "handles itself" means, in writing on the HEALTH tab).
Green autopilot = external pinger or fallback cron firing ≤15m; all required FLOW chains consumed; reconciliation GREEN; selftest green; feeds ≥1 working source each with fallback armed; books in their correct calendar states; vault intact (registry complete, archives current). Any breach = named RED line + issue. The operator should be able to leave for a week and read one page on return.

---

## 10. TIER 8 — NOTHING WASTED (the full inventory; every buried system claimed)

Build `SUBSYSTEM_INVENTORY.json` + a HEALTH sub-panel: one row per subsystem, columns `{produces, consumers(proof from CONSUMPTION_LOG), influence(last decision changed), verdict}`. Verdict ∈ **WIRED** (proof attached) / **DISPLAY-ONLY** (stamped on its panel, honest decoration) / **ATTIC** (moved, dated, reversible). Seed rows — the executor fills verdicts with receipts, no guessing:

Canon ledger · Equity truth · Views layer · Master gate (cards, Law 18) · Confidence engine · Universal cards (+maturity) · Fingerprints (+matrix promotion) · Drop×bounce matrix · Threshold sweep · Peak rhythm · Time-of-day · MTF ladder · Regime classifier · Champion election + forward ledger · Parameter-champion registry · Strategy lab sleeves A–G · Survival leaderboard · Promotion ladder · Champion timeline · Dr. Strange (+gate state) · Conductor C0/C1/C2 · Report card · Discovery/Graveyard/Counterfactuals → POLICY_REPORT · Exit forensics (+renamed grades) · Edge capture · Opportunity journal (venue-true) · Decision trace · Session anatomy · Black-box recorder · Calibration (+teeth) · Attribution · Sizer/Governor · Geometry gate · Heatshield/breakers · Nulls (CASH/SPY/QQQ/HODL/EQW) · Census/freshness · Wiring audit (+FLOW_PROOF) · Health lights · Economic clock · Daily baseline · Research OS · Question engine (Interrogator) · Unknown-unknowns · Complexity ledger · Data ledger/retention · Store registry · Selftest battery · Self-heal ledger · Authority/news (research-only) · Venue universe · Alpaca multi-account (H3/H5) · Weekly scorecard · Aggression ladder · Compounding projection (relabeled) · Live-handoff readiness (90-day bar).

Rules: the **Complexity ledger** enforces that 7.0-FINAL ends with **net module count ≤ start** (closures and attic moves, not growth). Anything verdict-less at ship time is itself a red tripwire (T-INV-1). This is how "let NOTHING buried go to waste" becomes checkable instead of aspirational.

---

## 11. THE PROMISE, ANSWERED HONESTLY (read this section to the operator verbatim)

You asked for the update that finds the edge and finishes the commitment. Here is the truth the receipts support, with no cheerleading and no despair:

**What this directive delivers:** a machine that cannot contradict itself (one ledger, one equity, dumb UI), cannot lose its memory (the vault + forward ledger), cannot trade without evidence (maturity + bootstrap ladder), cannot hide a dead subsystem (FLOW_PROOF + inventory), cannot fail silently (fail-loud everywhere, including the health system that was itself failing silently), and — for the first time — is **allowed to search for its own edge** through the only honest door: Conductor C1 shadow → C2 ε-trial → report card → promote or kill, fed by the graveyard's counterfactuals, sized by calibration with teeth, scored only against the null.

**What no directive can deliver:** edge itself. A 34/35 day is what a mean-reversion book looks like when volatility cooperates; the same book was −22% against HODL over the honest window. Renaissance's Medallion — the ceiling you named — ran ~66% gross in its best years on decades of research, thousands of signals, and execution advantages a retail paper stack cannot have; rent from $10k needs ~1–3% **per day**, which compounds past anything in recorded market history. The system's own doctrine already says this ("$100–300/day is an unproven hope, never income") and its own gate already knows the only way to find out: **100 out-of-sample trades across 90 unbroken days, forward, against the null, fees on.** 7.0-FINAL's job is to make that experiment finally runnable without resets destroying it — so the machine itself can tell you, with receipts, whether the edge you believe in is real. If it is, this loop finds and keeps it. If it is not, this loop proves that too, and that answer — before real money — is the whole reason SILMARIL was built as a dress rehearsal.

**Go-live now?** No. Same three reasons as before, now with fixes scheduled: numbers don't reconcile (Tier 0), the only honest metric is negative (Law 10 headline, Tier 1), and no forward record has ever survived to maturity (Tier 3). The Binance.US connect button stays locked behind the bar the system already enforces. **Immediate practical call for this weekend:** do **NOT** genesis again — run the reset workflow in **standard** mode (learning kept) tonight, accept that under current code the calibration/forward records still leak (Tier 3 fixes that; your July-18 backup preserves today's knowledge for the restore tool), and let the clean week start Sunday night into Monday exactly as you planned.

---

## 12. EXECUTION PLAN — phased for multiple sessions, each phase ships green

| Phase | Tier(s) | Scope (size) | Gate to proceed |
|---|---|---|---|
| **P0** | 0 | R2 dup-guard · R3 tail fix · `LEDGER.jsonl` + Master-consumes-canon · R5 EQUITY_TRUTH (L) | T-CANON-1..5 green; books replay to the cent |
| **P1** | 1 | H1 hoist · H2 fail-loud all catches · H3 VIEWS layer · H4 headline · H5 grades · H6 provenance footers (L) | T-UI-1..2 green; zero bare "loading" |
| **P2** | 3 | Vault: forward ledger · registry completion · archive-first · asymmetric confirms · reset rehearsal · restore tool (M) | rehearsal drill passes byte-identical |
| **P3** | 4 | Bootstrap ladder · maturity gate · floor-confirm all regimes · calendar states · locked-capital surface (M) | T-MAT-1, T-TIME-1 green |
| **P4** | 2 | VENUE_UNIVERSE Actions job · tradeable intersection · journal venue-true · U3 decision surfaced (M) | VENUE_UNIVERSE fresh in Actions |
| **P5** | 5 | FLOW_PROOF + required chains · W1–W12 closures/stamps (L — may split 5a/5b) | T-FLOW-1 green; inventory verdicts started |
| **P6** | 6 | E2 calibration teeth · E3 attribution · E4 Δ-null columns · E5 MKR verify · E1 **C2** wiring (off by default) (M) | C2 ships gated-off with kill registered |
| **P7** | 7 | A1 health chain (4 links) · A2 waterfalls · A3 workflow gaps · A4 self-heal · A5 autopilot page (M) | T-AUTO-1..3 green; failure→issue tested |
| **P8** | 8+11 | Inventory verdicts complete · attic moves · complexity ledger check · FINAL EXAM below (S) | T-INV-1 green; exam checklist signed |

Every phase: read-before-edit → exact-text edits → new tripwires → `py_compile` + JS parse → **full 53(+new) battery on fresh AND full trees** → ZIP at repo paths → operator drag-and-drop. Every behavioral knob defaults OFF with its kill criterion written into `PARAM_CATALOG.json` at ship time.

**FINAL EXAM (P8, before declaring 7.0-FINAL done):** reconciliation GREEN 7 consecutive days · views==canon differ clean · reset rehearsal passes · bootstrap ladder observed live (standard reset → mature names re-arm) · all required FLOW chains consumed · zero silent failures for a week (spine roster clean) · health panel shows true provider depth with ≥2 sources per feed or a named plan · venue universe fresh · headline reads Δ-vs-null · C1 report current and C2 still off pending positive uplift · live-handoff bar untouched and its clock finally, actually, running.

---

## 13. SUCCESS CRITERIA (7.0-FINAL is done only if every line is mechanically checkable and checked)

- One canonical ledger; every money panel derives from `EQUITY_TRUTH.json`; the UI computes nothing and can only be late, never wrong.
- No two fills share `(sym, side, t)`; Master ⊆ books; OPEN-TRADE TRUTH equals canon.
- No bare `loading…` anywhere; broken ≠ pending, forever; every panel carries provenance.
- A standard reset preserves fingerprints, observations, calibration, graveyard, and the champion **forward ledger** — proven by the scripted rehearsal, and Law 26 archives written in the same commit.
- After any reset, books climb OBSERVE → EVIDENCE-GATED → FULL, and no immature name ever fills while the gate is on.
- "Seen" means venue-listed; the journal mourns only trades that could have existed.
- Every subsystem in the inventory holds a receipts-backed verdict; required FLOW chains are consumed every cycle; the wired-but-starved class is dead.
- The health system reports true provider depth from ONE owner, and nothing in the spine can fail without a visible line.
- The champion can rotate because forward evidence accumulates across resets; hypothesis and champion are labeled as different things; sleeves live under pre-registered kills.
- The edge-search door is open and guarded: C1 scores continuously, C2 exists behind a default-off knob with a registered kill, calibration haircuts sizing, attribution stands watch, and the null sits atop every leaderboard.
- The live-money bar is exactly where it was: **100 out-of-sample trades, 90 unbroken days, forward, fees on, against the null** — and for the first time, nothing in the machine can accidentally reset that clock.

*7.0-FINAL is the release where every loop closes and the machine earns the right to be left alone. Whether the edge is real is the experiment it finally gets to run honestly — and either answer, proven, is the finish line we set out for.*
