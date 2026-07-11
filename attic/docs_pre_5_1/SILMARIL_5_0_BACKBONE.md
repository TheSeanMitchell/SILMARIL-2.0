# SILMARIL 5.0 — THE EXPANSION BACKBONE
## Allocation & Generalization — the machine that knows where to look
### Keystone document. Compounds — removes nothing from — the 3.0 Master Directive, the Movement V Addendum, the 4.0 Completion Backbone (Laws 1–8), the 4.0 Final Directive, and `Silmaril_4_0_Notes.txt` (Movements I–XXI, verbatim first-class law). Pairs with `SILMARIL_5_0_BACKBONE.xml` and `AUDIT_2026_07_06_PRE_5_0.md`.

---

## THE ONE OBJECTIVE OF 5.0

> **2.x Hardened. 3.0 Governed. 4.0 Verified. 5.0 ALLOCATES AND GENERALIZES:
> prove the edge, then prove it travels — and never spend a feature where evidence hasn't paid for it.**

3.0 answered *who may trade*. 4.0 answered *is it true*. 5.0 answers the two questions that
remain: **where should the next dollar of capital and attention go** (Allocation), and **does
the method survive outside the room it was born in** (Generalization). Every market, family,
signal, and meta-policy in this document enters through a numbered admission gate and is
measured against a null twin. Nothing is granted; everything is earned forward.

**The Prime Constraint, formalized:** Evidence Growth ≥ Feature Growth. Every workstream below
carries an **evidence gate** — a count of forward samples, clean cycles, or logged decisions —
and its next stage does not ship until the gate fills. The gates ARE the schedule. No dates
are promised anywhere in this document; cycle-counts and sample-counts are.

**The header rule:** the dashboard keeps its current header until every box in the 5.0
Definition of Done is checked. The golden **SILMARIL 5.0** header is the last commit of the
version, not the first. All UI work beyond truth-pairing (a number exists → it is visible)
is deferred until then (P7/P8/P9/P10 ride behind the flip).

---

# PART 0 — STATE OF THE REPO (July 6, 2026 backup — full findings in AUDIT_2026_07_06_PRE_5_0.md)

Verdict in one line: **the 4.0 machine landed and compiles clean; the system's scarcest
resource is forward evidence, not features.** All 316 arena strategies present; warmup knobs,
GEKKO, June-30 profile, RA/TQ engines, run_lock, atomic writes, backfill filters, `*/10`
fallback cron — all verified in code. Three defects found and **fixed in this drop**
(concurrency gaps on six workflows, tier-threshold drift 8/15/30 → canonical 10/25/50 + a
`production_verified` flag at 100, and unlabeled post-wipe champion provenance — the incumbent
now stamps `provisional: true` until forward evidence exists). Two structural truths drive the
5.0 ordering: **(1)** every book sits at $10k/0 trades post-wipe — Verification is starving;
**(2)** stock and energy are structurally quiet and metal has never purchased — the method has
not yet been *translated* to those rooms, only copied into them.

**The section that needs the most work, ranked:** ① Evidence Flow (per-market parameter
parity so every book trades — P6 generalized), ② Store Contracts (kill the wired-but-starved
failure class permanently), ③ the Null Layer (so every result is judged against doing
nothing). Those three are Phase 5.0-A/B for exactly that reason.

---

# PART 0.5 — EXECUTED IN THE 5.0 INSTALLER (July 7, 2026 — built, compiled, smoke-proven on the real repo)

This backbone is a multi-month roadmap gated by evidence, not dates. The FIRST installer
(this ZIP) lands Phase-A whole and fixes the three defects the audit found. Everything here
was `py_compile`/`node --check` clean and smoke-run against the real `docs/data` stores.

**Fully materialized this pass (the groundwork the rest stands on):**

1. **The Null Layer is live (Law 10, Part II).** `bench_books.py` runs four strategy-free $10k
   books — BENCH_CASH (accrues a knob APY), BENCH_SPY (buy-and-hold), BENCH_HODL (50/50 BTC-ETH),
   BENCH_EQW (equal-weight fresh-crypto basket frozen at creation, point-in-time). Marks come
   ONLY from real ingested samples; a leg with no real price waits, labeled, rather than
   inventing one. They re-baseline after any wipe and are excluded from the Master and from
   championship by construction. Smoke: all four initialized and marking on the real feed.

2. **"Wired-but-starved" has a named kill switch (Law 12, Part VI).** `store_contracts.py`
   validates nine core stores against declared field schemas AND checks eleven producer→consumer
   contract rows every cycle. Smoke: **ALL GREEN, zero red.** A new integration is not "done"
   until its schema + contract rows exist here.

3. **The Census Engine is live (Part VI).** `census.py` publishes a per-quadrant roll-call
   (listed / fresh-24h / stale / backfill-only / %fresh) so the "~92% ghosts" are auditable as
   the freshness filter doing its job — not silent loss. Long-memory `CENSUS_ROSTER.json`
   remembers first-seen forever and a **new-listing detector** surfaces anything ≤14 days old
   into a 14-day OBSERVE quarantine. Smoke: crypto 472 listed / 19.3% fresh; stock 1159 / 44.7%;
   metal 10 / 90%; energy 16 / 50%.

4. **Utilization is measured (Law 16, Part IX).** `utilization.py` stamps every book every cycle
   DEPLOYED / ARMED / BLOCKED_REGIME / STARVED with a 30-day rollup. Smoke matched live exactly:
   crypto DEPLOYED, GEKKO DEPLOYED, stock/metal/energy ARMED. ARMED-forever is now a public
   finding, not background noise.

5. **The Conductor exists at rung C0 (Part V).** `conductor_log.py` writes an append-only,
   wipe-surviving `CONDUCTOR_LEDGER.jsonl` — per-cycle context (per-book regime/champion/open/
   cash/equity + session + freshness), action `status_quo`, propensity 1.0 — plus a lifetime
   counter toward the C1 gate (300 decisions). **Zero behavior change**; this is the honest
   substrate every later counterfactual policy needs.

6. **The Research Operating System is live at v1 (the Part-2 notes, given a body).** `research_os.py`
   is the layer ABOVE the engines: a QUESTION REGISTRY whose evidence tallies from real stores
   (RESEARCH_DEBT = the gap), permanent NEGATIVE KNOWLEDGE (things proven NOT to work),
   BELIEFS THAT DECAY (last-confirmed + retest flags), four-way KNOWN_TRUE/KNOWN_FALSE/UNKNOWN/
   CHANGING classification, a computed UNKNOWN-UNKNOWNS panel (least-tested market, stalest
   belief, biggest evidence gap), and META-RESEARCH priorities ranked by expected information
   gain. Long-memory; survives wipes. Smoke: 7 questions open, debt 298 observations, top-value
   next question auto-selected (the GEKKO June-30 profile, already accruing 7/35 from real trades).

**The three audit defects — fixed:**

- **Cold-start champion dishonesty (the exact issue in the brief).** `champion.py` now stamps
  `provisional` + `evidence_basis` on every election. When the incumbent holds after a wipe
  with no qualifying forward evidence, the dashboard shows a red **PROVISIONAL** badge and states
  in plain words that it rotates the moment any strategy books its minimum live trades (Law 9).
  Smoke confirmed the current MR_patient_d3 is correctly flagged provisional. The illusion is dead.
- **Champion rotation is now a live dial (directly serves "exploit rotation on a faster scale").**
  New `PARAM_CATALOG.champion_rotation {min_trades, switch_margin}` feeds the anti-flip-flop gates.
  Defaults reproduce 2.18 behavior exactly; lower both to accelerate rotation as evidence lands —
  and Research-OS **Q002** grades whether faster actually pays before you trust it. The election
  already runs every cycle for all books; speed is no longer a code edit.
- **Tier drift corrected.** `champion_validation.py` tiers restored to the canonical
  Sandbox→Incubation(10)→Candidate(25)→Production(50) with a separate `production_verified` flag
  at n≥100, so no UI consumer of the four tier names breaks.

**Reliability & the long-requested workflow split:**

- **Lane split delivered.** The pulse (`daily.yml`) is now ALWAYS the fast trade cycle — nothing
  heavy rides the 10-minute lane again. A new **`hourly.yml`** (cron `:07`, off the congested top
  of the hour) carries the heavy pass (arena/RA/TQ/governance/sanitize/brag); WIDE/deep stays in
  `analytics.yml` (3×/day). This is the split that was asked for repeatedly and never landed.
- **Concurrency completed.** All state-mutating workflows now share the `silmaril-state` group
  (6 were missing it), so no two writers race regardless of trigger.
- **The 5.0 spine is wrapped per-module** in `cli.py` and runs in both fast and full cycles; any
  single module failing logs a warning and can never break a trade run. All writes are atomic.

**Header + policy (operator directives, 2026-07-07):**

- The masthead now reads **SILMARIL 5.0** (cosmetic flip authorized by the operator). The
  substantive gate is unchanged: the live-money unlock is still **100 out-of-sample trades over 90
  unbroken days** — the header moving early opens no doors the evidence hasn't.
- **Alpaca is pricing-only** henceforth (`_broker_policy` in PARAM_CATALOG). No new feature depends
  on it for execution.
- **Per-quadrant independent trading engines** (the brief's "own schedule/universe/system"): the
  correct first step is the lane split plus session-gated per-book clocks (already present), NOT
  parallel workflows — `silmaril-state` deliberately serializes state writes to keep the ledgers
  race-free. Full per-quadrant lanes are staged in Part VI once each book has its own store
  namespace; forcing them now would reintroduce the write races Law 12 just closed.

# PART I — THE LAWS OF 5.0 (Laws 9–16; Laws 1–8 stand untouched)

- **Law 9 — Provenance.** Every governing artifact (champion, gate weight, parameter, regime
  call) carries an `evidence_basis` field: *forward*, *backtest*, or *provisional*. Nothing
  provisional may be displayed, logged, or reasoned about as if it were forward-proven.
  (First enforcement shipped in this drop: `champion.json.provisional`.)
- **Law 10 — The Null Twin.** No active book exists without a named benchmark null (Part II).
  Every scorecard line is Δ-vs-null, never raw P&L alone. Beating zero is not beating anything.
- **Law 11 — Admission.** No market, instrument class, or strategy family touches a governed
  book except by climbing the M0–M5 / F0–F4 ladders (Parts III–IV). Enthusiasm has no rung.
- **Law 12 — Contracts.** Every JSON store has a schema; every producer→consumer field pair is
  registered; the cycle validates both and a failure is a red light, not a silent starve.
- **Law 13 — Cost Truth Per Venue.** Each venue/asset class carries its own measured
  round-trip cost model (spread + fee + slippage proxy); the 2× friction bar is applied with
  the venue's own number, never crypto's.
- **Law 14 — Attention Budget.** API calls, runner minutes, and repo bytes are allocated
  resources with per-lane budgets and a monthly audit line. A feature that starves the pulse
  of rate-limit headroom is a regression.
- **Law 15 — Pre-Registered Death.** Every experiment declares its kill criterion (sample size
  + threshold) *before* it starts logging. An experiment that cannot die is not an experiment.
- **Law 16 — Utilization Is Measured.** Idle capital is a cost with a number on it (Part IX).
  A champion that is armed but never deployed is a finding, not a neutral state.

---

# PART II — W1: THE NULL LAYER (benchmark books) — cheapest honesty ever purchased

Four strategy-free $10k books that only mark to market. No entries logic, no exits logic, no
champion, excluded from Master and from championship exactly like GEKKO. They are the floor
of every claim the system will ever make.

| Book | Holds | Marks | Answers |
|---|---|---|---|
| `BENCH_CASH` | BIL (T-bill ETF) — or FRED 3-mo yield accrual if pre-market data is simpler | daily | "What if the $10k just earned the risk-free rate?" — the hurdle every book must clear |
| `BENCH_SPY` | SPY buy-and-hold | daily | the null for the stock book and every equity family |
| `BENCH_HODL` | 50/50 BTC/ETH, no rebalance | per-cycle | the null for crypto + GEKKO — MR must beat *holding* |
| `BENCH_EQW` | equal-weight of the book's own tradable universe, monthly rebalance | daily | "was the alpha selection, or just exposure to the universe?" |

Implementation is deliberately trivial: one module (`bench_books.py`), one store
(`bench_books.json`), marks from feeds already ingested, wiped and auto-recreated on reset
like GEKKO. The Opportunity-Cost engine from the 4.0 backlog wires directly to these instead
of hypotheticals. **Evidence gate to call W1 done:** 30 consecutive cycles of valid marks on
all four, Δ-vs-null line rendered on each governed book's existing scorecard row (truth-pairing
only — no new UI surface).

---

# PART III — W2: NEW MARKETS — THE ADMISSION PROTOCOL (M0–M5)

The operator's instinct is correct and now law: skepticism first. Stock, energy, and metal
prove that *copying* the crypto profile into a new room produces silence, not edge. Every
candidate market climbs this ladder; a market may live at M2 forever and that is a success
(a truth learned cheaply).

- **M0 — Data feasibility.** ≥2 independent price sources; bid/ask or a defensible spread
  model; point-in-time capture from day one; sessions/calendar mapped into the clock module.
- **M1 — Cost truth.** Venue round-trip model written and adversarially reviewed against
  Law 13; the target sizes the market can actually offer must clear 2× that friction on paper
  arithmetic *before any book exists*.
- **M2 — Census.** Universe enumerated (Part VI census engine), liquidity tiers assigned,
  exclusions named. Volatility fingerprint measured: what does a "dip" even mean here (see
  translation table below).
- **M3 — Observe book.** A GEKKO-class isolated $10k book with market-native parameters.
  Never Master-funded, never champion-eligible. Gate to M4: ≥25 closed forward trades AND
  trade-quality cards produced AND Δ-vs-null computed.
- **M4 — Arena admission.** Market gets its own quadrant leaderboard; families compete under
  Movement-VI statistical discipline (luck baseline, walk-forward only, multi-window).
- **M5 — Governed book.** Master-eligible under the standard 90-gate. Same live-money bar as
  everything else; no exceptions.

### The parameter-translation table (why the rooms went quiet — and the fix)
A 3% intraday dip is a Tuesday in crypto, a monthly event in SPY, and a quarter's move in
EURUSD. Admission REQUIRES restating the MR profile in units of each market's own measured
daily volatility (entry ≈ 1.5–2.5σ of the market's intraday distribution, target ≈ 1–1.5σ,
stop ≈ 3σ), then letting the arena breed around that seed. This retroactively defines the
**5.0-B parity labs** for the rooms we already own: stock (dips 0.7–1.5%), metal (0.4–1.0%),
energy (0.8–2.0%) — the generalization of backlog item P6 to every quiet book.

### Candidate dossiers (priority order)

**C1 — INDEX / ETF ROTATION BOOK (`BOOK_ROTATION`) — the "dedicated index & ETF investor."**
Universe: SPY, QQQ, IWM, EFA, EEM, TLT, IEF, GLD, DBC + the 11 SPDR sectors. Family:
time-series + cross-sectional momentum at the 3–12 month horizon (weekly decision, monthly
rebalance, absolute filter: an asset must sit above its 10-month MA or its sleeve parks in
BIL). This is the single best-documented, retail-accessible, low-turnover family in the
public literature, it runs perfectly on a daily cron lane, and it is the direct answer to
"what would $10k do in calmer instruments beside our volatile books." Costs are near-zero
(liquid ETFs, monthly turnover). Null twin: `BENCH_SPY`. Note the honest asymmetry with our
crypto finding: *intraday* momentum lost (t = −14) in our universe; *multi-month cross-asset*
momentum is a different animal at a different timescale and gets its own trial, not a free
pass. Enters at M3 immediately (all data already flows through Alpaca/yfinance).

**C2 — RATES & BONDS BOOK (`BOOK_RATES`).** Instruments: TLT, IEF, SHY, LQD, HYG, TIP —
bond exposure via ETFs, tradable on the paper broker today. Dual value: (a) a slow MR/trend
book in the least-crypto-like room we can buy, the strongest possible generalization test;
(b) the macro spine — FRED 2s10s slope, 3-mo yield, and CPI prints become fingerprint inputs
for *every* book's regime context. Evidence accrues slowly by nature; the gate counts trades,
not days, so slowness is honest, not fatal. Enters at M0→M2 in 5.0-C (FRED wiring), M3 after.

**C3 — FX MAJORS (the operator's global-currency question) — admitted to M0–M1 ONLY, with
the honest math attached.** The good news: majors are the cheapest venue on earth
(EURUSD spread ≈ 0.6–1.2 pips ≈ 0.006–0.012%; round trip roughly an order cheaper than
crypto). The hard news: daily ranges of 0.3–0.8% mean the entire strategy lives at 0.2–0.5%
pullbacks and 0.15–0.4% targets — a regime our engine has never traded, where cost modeling
and fill realism decide everything. **M0 blocker, stated plainly:** we do not currently have
a real bid/ask FX feed; mid-rate APIs (exchangerate.host, ECB) are fine for census and regime
work but ILLEGAL for fills under the no-synthetic-data law. The unlock is a free practice
account API from a major FX broker (real streaming bid/ask, real paper fills) — that account
is the M3 gate. Sessions (Asia/London/NY) and the weekend close extend the calendar module.
No leverage, ever, at any rung. FX does not advance past M1 until C1 and C2 have produced
their first 25-trade cards — breadth is earned in order.

**C4 — BROAD COMMODITIES (DBC and singles like CORN/WEAT) — M0 dossier only in 5.0.**
Overlap rule: anything already inside metal/energy books is deduped, never double-owned.

**C5 — INTERNATIONAL INDICES (EWJ, EEM, FXI) and C6 — REITs (VNQ):** parked at M0. Both are
one census run away from readiness but add breadth without new mechanics — they wait until
the Conductor (Part V) can actually allocate across what we already have.

**REJECTED for 5.0, each with its one-line reason:** options (nonlinear risk our
verification layer can't yet grade), leveraged/inverse ETFs (decay is a structural tax on
exactly our holding pattern), VIX products (roll costs + regime jumps; observe-only research
at most), individual bonds (no venue access), futures (margin mechanics out of scope),
penny/OTC equities (integrity quarantine would eat the universe), live FX (see C3), anything
requiring shorting (deferred until long-only edge is proven — walk before hedging).

---

# PART IV — W3: STRATEGY GENERALIZATION — the momentum answer, and the Family Admission Protocol

**Why the engine never saw Intel, Monster, or SanDisk:** it is a dip-buyer. A stock in a
persistent uptrend never prints the qualifying dip, so the engine is *structurally blind to
strength* — not broken, specialized. The fix is not to bend MR; it is to admit a second
species and let the arena judge it.

### F0–F4 Family Admission Protocol (mirrors M0–M5, binds every new species forever)
F0 hypothesis registered with pre-death criterion (Law 15) → F1 grid seeded into the arena
(luck baseline printed on the widened board; multi-window; walk-forward only; 2× venue
friction) → F2 forward sleeves (paper books, exactly like today's MR sleeves) → F3 tier
climb on the canonical 10/25/50/100 ladder → F4 champion-eligible in its quadrant.

### Families admitted to F0/F1 in 5.0
- **`TREND_RS` — cross-sectional relative strength (equities).** Weekly: rank the liquid
  stock universe by 12-month-minus-1-month return; hold the top decile; exit on 10-week-MA
  break or 15% trailing stop; hard regime gate SPY > 200-day MA else flat. This is the
  buyer-of-strength the stock book lacks and the direct answer to the Monster/Intel/SanDisk
  question.
- **`EXIT_LAB` — exit engineering on the *existing* MR family.** Our trade-quality cards
  already measure capture%. Variants: trailing stops (fixed % and ATR-scaled), regime-flip
  exits, partial scale-outs at 1× target. Same entries, different deaths — the cheapest new
  evidence in the whole program because every open position feeds it.
- **`BREAKOUT_HOLD` (F0 registration only).** Donchian-style strength entries for crypto —
  registered, seeded, and left to prove itself against the luck line before anyone gets excited.
- **`VOL_SIZED` (modifier, not family).** Position size ∝ 1/σ of the symbol — enters as an
  observe gate on existing books, graduating by the standard evidence thresholds.

### "Selling at the peak," said honestly
No subsystem in this program will ever be asked to *predict a top* — that claim would fail
the Truth Engine on contact. The testable forms of the operator's instinct are: trailing
structures (EXIT_LAB), **per-symbol regime tags** (the book-level regime engine, run at symbol
granularity, so MNST can read UPTREND while the book reads SIDEWAYS — the tag routes the
symbol to the right family and flips positions to defensive exits when the tag dies), and
volume/velocity climax flags (observe-only cards attached to trades, graded later by RA-style
24h hindsight). Detection-with-lag, measured by capture% — never prophecy.

### The earnings blackout (stock-book safety with a hypothesis inside)
No new stock entries within N days before a scheduled earnings print (calendar already
available on keyed providers); positions held through earnings get a flag. Ships as an
observe gate: after ≥40 flagged events we learn whether earnings gaps were tax or fuel —
either answer is profit in evidence.

---

# PART V — W4: THE CONDUCTOR — the higher strategy engine, game theory kept honest

The operator asked for "higher game theories… a strategy engine that uses proven theories to
play at certain moments of the lifecycle or fingerprint." Here is that engine, built so it
cannot become astrology.

**The object:** a meta-policy over context → deployment. Context vector per cycle per book:
`(regime probabilities, fingerprint id, session bucket, volatility percentile, cadence
health, freshness, days-since-wipe)`. Action space: `(which eligible champion or cabinet
weighting, which aggression rung, or SIT OUT)`. The Conductor never invents signals — it only
chooses among things that individually passed their own gates.

**The ladder (each rung has a pre-registered death):**
- **C0 — Log the status quo.** Every cycle, record context + the action the current rules
  took + (later) the outcome, with propensity 1.0, into `CONDUCTOR_LEDGER.jsonl`
  (append-only, wipe-proof). Zero behavior change. Gate: 300 logged decisions with outcomes.
- **C1 — Shadow policies.** Candidate policies ("deploy rung-3 only in SIDEWAYS+vol<40th",
  "cabinet of top-3 survivors weighted by score") are scored counterfactually against the log
  where overlap allows. Pure math, zero trades.
- **C2 — ε-exploration on GEKKO only.** A small ε of GEKKO's cycles take the shadow-best
  action, propensity-logged, so off-policy estimates stop being fantasy. GEKKO's isolation is
  exactly why it exists.
- **C3 — Gated influence.** The Conductor joins the experimental-gates table like every other
  gate: OBSERVE → weighted, only past its evidence threshold (n ≥ 300 decisions, CI-positive
  uplift vs status quo). It earns weight the same way news_signals must.

**The game theory, translated into things that can be graded:** *mixed strategies* — a
champion **cabinet** (top-K by survivability, capital in sleeves, weights ∝ forward score) as
insurance against nonstationarity, run as an A/B against the single champion it would
replace; *regret minimization* — cabinet weights update Exp3-style but only across
gate-cleared members; *the Kelly law* — all sizing anywhere is capped at ¼-Kelly computed
from forward expectancy/variance, a constitutional ceiling, not a knob; *the option value of
waiting* — SIT OUT is a first-class action whose value is now measurable because Part II
gives cash a yield and Part IX gives idleness a price; *know your adversary* — our opponent
is not other traders, it is our own cost line and our own failure modes, which is why Law 13
and the invariants engine are listed under strategy, not plumbing.

---

# PART V-B — THE RESEARCH OPERATING SYSTEM (scientific curiosity, from the operator's Part-2 notes)

The Part-2 notes named the real next leap: not another algorithm, but the layer that knows **what
questions to ask.** The pipeline is inverted so trading sits near the bottom and knowledge above it:

> Market → Observations → **Questions → Hypotheses → Experiments → Evidence → Knowledge** → Trading
> decisions → Allocation → Portfolio → Compounding.

**Shipped now (v1, `research_os.py`, `RESEARCH_OS.json`, long-memory):**
- **Question Registry + Research Debt.** Every open question carries evidence-have (auto-tallied from
  real stores), evidence-needed, blocked-by, information-value, and a computed debt/priority. Seven
  seeded from the program's real open questions (does the champion beat HODL; does faster rotation
  pay; do stock-tuned thresholds wake the idle book; is the classifier better than a coin flip; does
  the June-30 profile survive fees; does FX's fee edge hold on a real feed; is the warmup enough).
- **Negative Knowledge** (permanent): momentum loses here (t = −14); lifecycle carries no edge; stale
  daily windows buy nosedives; one external pinger is not a cadence source. Each with its evidence.
- **Beliefs with decay:** last-confirmed + retest-after; stale beliefs flip `retest_required`.
- **Four-way classification** (KNOWN_TRUE / KNOWN_FALSE / UNKNOWN / CHANGING) on every item.
- **Unknown-Unknowns panel** computed live (least-tested market, stalest belief, biggest evidence gap).
- **Meta-Research priorities** = expected information gain; the roadmap writes itself from evidence,
  not intuition.

**Roadmapped (v2→, evidence-gated, in this backbone's spirit — nothing synthetic, everything cumulative):**
- **Information-Value scoring engine:** rank *experiments* (not just questions) by expected profit-
  impact per observation — "should this regime even exist?" outranks "5.0% vs 5.2% stop" automatically.
- **Decision Replay page (Part VI ties in):** freeze the engine exactly as it existed at a chosen second
  — every input, score, vote, threshold, rejected trade, confidence, regime — and re-run it. The
  deterministic core already makes this achievable; v2 gives it a UI.
- **Auto-question generation:** each answered question spawns its successors ("crypto momentum only when
  energy breadth expands?") as first-class rows once the combos-transition table (Part IV) has ≥30 obs.
- **Belief-decay automation:** retests scheduled and executed automatically when a belief goes stale,
  closing the loop from "expired" to "re-confirmed or overturned."
- **Dedicated Unknown-Unknown page** (P8 command-center tab): most-expensive assumption, weakest model,
  most-overfit model, least-tested regime, largest unexplained win/loss — the standing research map.

This is the discipline the notes asked for: the engine stops only tuning and starts **discovering what it
does not yet know**, and every subsystem still answers to the same three tests — better observations,
better decisions, better long-term compounded expectancy — or it is complexity, not leverage.

# PART VI — W5: THE DATA & SIGNAL SPINE

### New sources (each enters as OBSERVE feeding a named module; nothing touches a decision ungated)
| Source | What | Cadence | Cost | First consumer |
|---|---|---|---|---|
| FRED | yields, 2s10s, CPI, unemployment | daily | free | macro fingerprint; `BOOK_RATES` regime |
| Treasury FiscalData | official yield curve | daily | free | FRED fallback (2-deep rule) |
| CFTC COT | futures positioning (metals/energy/FX) | weekly | free | sentiment fingerprint cards for the two quietest books |
| ccxt funding rates + open interest | perp funding, OI | per-cycle | free | crypto MR context — hypothesis: negative funding + dip → better MR odds; observe gate, n≥60 |
| DefiLlama | TVL, stablecoin flows | daily | free | crypto regime context |
| Earnings calendars (existing keyed providers) | print dates | daily | keyed | earnings blackout (Part IV) |
| Economic calendar (existing) | FOMC/CPI timestamps | daily | keyed | rates/FX event blackouts |
| exchangerate.host / ECB | FX mids | hourly | free | FX census + regime ONLY (never fills) |
| FX broker practice API | real bid/ask + paper fills | streaming | free acct | the C3/M3 unlock |
| Stooq | EOD equities backup | daily | free | stock price 2-deep fallback |

### STORE CONTRACTS — the named kill of "wired-but-starved"
The most common silent failure in this program's history is a module correctly integrated but
starved by a field-name mismatch. 5.0 makes that class of bug **structurally impossible to
miss**: a `schemas/` directory with one JSON-schema per store; `validate_stores.py` runs
every cycle and every store failing schema flips a red STORE light with the failing field
named; `CONTRACT_REGISTRY.json` maps every producer→consumer field dependency
(e.g. `paper_sim_live.positions[].sym → trade_quality`), and the validator asserts each
consumer's read-paths exist in the producer's latest output. A new integration is not "done"
until its contract row exists. **Evidence gate:** 30 consecutive cycles all-green after
initial red-light triage.

### The Census Engine — "are we missing valuables?"
Daily `UNIVERSE_CENSUS.json` per venue: **listed** (full exchange enumeration via ccxt
markets / broker asset list) vs **tracked** vs **warm** vs **excluded-by-named-reason**
(freshness, liquidity tier, spread, integrity twin, step-ceiling). The 92%-stale-ghosts truth
becomes an auditable table instead of a memory: every exclusion has a reason string, so
"excluded correctly" and "missing wrongly" are finally different colors. New listings enter a
14-day auto-observe quarantine before eligibility; delistings are handled, not orphaned;
cross-venue twins keep the canonical-key law. The census is also the M2 instrument for every
candidate market in Part III.

**Point-in-time snapshots** (Backbone VI, already law) are restated here as the spine's first
duty — every day without them remains unrecoverable survivorship bias.

---

# PART VII — W6: RELIABILITY, OPS & TESTING

### Cron truth and the lane table
GitHub cron is best-effort and congested at :00; the pulse's defense-in-depth stands
(external pinger primary, in-repo `*/10` fallback, run_lock, watchdog). 5.0 adds **lanes with
staggered minutes** so heavy analytics never contend with the pulse:

| Lane | Schedule (UTC, staggered off :00) | Contents |
|---|---|---|
| PULSE | pinger + `*/10` fallback | ingest → mark → decide → execute → verify (unchanged monolith — splitting it is rejected as risk without payoff) |
| HOURLY | `:07` | arena compact, RA, TQ, governance, validator |
| DAILY-PRE | `08:10` (exists) + `13:10` | backfill guard, census, remap, prune, **P11 baseline snapshot** (SPY/QQQ/VIX/BTC/ETH/SOL/DXY/GOLD/OIL + champion/arena state → `DAILY_BASELINE.json`) |
| DAILY-POST | `21:40` | stock settle, rotation-book mark, scorecard append |
| WEEKLY | Sun `02:15` | COT ingest, **P14 platform scorecard**, rotation rebalance decision, backup (exists) |
| MONTHLY | first Sat `03:30` | drift monitor, deterministic-replay audit, attention-budget report (Law 14) |

All lanes share `silmaril-state` concurrency (the six missing declarations are fixed in this
drop) — the queue, not luck, prevents state races.

### The Invariants Engine (`invariants.py`, every cycle; any failure = red light + named line)
cash + Σposition-value == equity ± ε per book · no negative cash · no duplicate open per
(book, symbol) · ledger timestamps monotonic · zero `T00:00:00` candles in any signal path ·
freshness ceilings honored · all stores schema-valid · book count == expected · GEKKO and
bench books absent from the Master ledger · champion `provisional` flag consistent with
validation n.

### The test battery (Movement VII given teeth)
**Deterministic replay** — a frozen fixture day replays to byte-identical decisions (seeded;
Notes XIII). **Liar drills** — quarterly, inject one known-false claim (a doctored trade, a
fake regime call) into a scratch copy; the Truth Engine/validators must catch it or the drill
fails and that gap is the next sprint. **Chaos drills** — kill one feed in scratch; quarantine
+ fallback-depth must hold. **Promotion audit** — an independent second implementation
recomputes survivability from raw trades and must match `champion_validation` (a checksum on
the most consequential number in the system). **CI workflow** — `py_compile` all + `node
--check` + `validate_stores` on fixtures for every push (the doctrine "compile before
shipping," automated).

---

# PART VIII — W7: THE LEARNING LOOP (4.0 Movement-I completion lives inside 5.0)

Unchanged obligations, now sequenced with gates: prediction-vs-outcome ledger for every
forecast → **calibration curves** per subsystem (gate: 100 graded predictions each) ·
**False-Positive tracker** (how often did confidence-X lose) · **Drift Monitor** (monthly
edge/expectancy/fees/turnover deltas) · **Parameter Evolution objects**
(current/tested/confidence/next-candidate) replacing bare knobs, grown from GEKKO + sleeve
forward trades · **Opportunity-Cost engine** wired to the Part-II nulls so "what should I
have done" always has a priced answer. The Truth Engine's registry (every claim →
Verified/Rejected with evidence counts) is the roof over all of it; counterfactual Universes
A–E per trade complete the floor.

---

# PART IX — W8: UTILIZATION & SIZING — "never underutilize the champions"

- **`CHAMPION_UTILIZATION.json`** per book per day: % of cycles ARMED / BLOCKED (reason
  named) / STARVED (warmup/data) / DEPLOYED, plus minutes-to-first-qualifying-dip. A champion
  armed 100% and deployed 0% for a week is a parity-lab summons (Part III translation table),
  not background noise.
- **The idle-capital line** on every scorecard: `equity × BENCH_CASH daily yield × idle
  fraction` — Law 16's number. Patience stays a virtue only while it out-earns its price.
- **The Aggression Ladder lab (P12, unchanged, now housed here):** the same champion at
  10/20/30/40/50% deployment in parallel observe sleeves; compare forward Sharpe/DD/capture;
  the ladder's winner is a *candidate* for the Conductor's action space, nothing more.
- **P3 explainability** completes here: per-position rank, expected return, and every
  rejected candidate's named reason — the deployment decision fully glass-boxed.

---

# PART X — PHASES, COVERAGE, DEFINITION OF DONE

### Phases (gates, not dates)
- **5.0-A — NULLS & CONTRACTS.** Bench books · schemas + validator + contract registry ·
  invariants engine · utilization metric · this drop's three fixes deployed. *Gate: 30
  all-green cycles; Δ-vs-null on every book row.*
- **5.0-B — PARITY & FLOW.** Volatility-translated parameter labs for stock/metal/energy
  (P6 generalized) · per-symbol regime tags · earnings blackout (observe) · EXIT_LAB seeded.
  *Gate: every governed book ≥10 forward closed trades OR a census-named structural blocker.*
- **5.0-C — NEW ROOMS.** `BOOK_ROTATION` to M3 · FRED spine + `BOOK_RATES` to M2 · census
  engine live for all venues · FX M0–M1 dossier written. *Gate: rotation logs 8 weekly
  decisions; rates census + cost model reviewed.*
- **5.0-D — SPECIES & CONDUCTOR.** `TREND_RS` through F1 with luck baseline ·
  Conductor C0→C1 · aggression ladder running. *Gate: 300 propensity-logged decisions;
  TREND_RS beats its luck line in walk-forward or dies on schedule.*
- **5.0-E — INFLUENCE.** First gates cross observe→weighted strictly by their standing
  evidence thresholds · Conductor C2 on GEKKO · FX to M3 only if the practice-account feed is
  real. *Gate: any one gate legitimately weighted, with its uplift CI printed.*
- **Header flip:** last commit after the DoD below is 100%.

### Coverage matrix — every ask in the operator's brief → its home
global currency exchange → III·C3 | index-fund & ETF investor → III·C1 | bonds/secure sleeve
→ III·C2 + II | momentum stocks / sell-the-peak → IV | higher game theory / strategy engine →
V | new APIs & signal quality → VI | file splitting & cron reliability → VII lanes |
self-improvement & learning → VIII | optimization & testing methods → VII battery + VIII |
missing-valuables sweep → VI census | every-market-with-edge vision → III protocol (the
repeatable machine for entering *any* room) | champion utilization by minute/regime/
fingerprint → IX + V | most-neglected-section verdict → Part 0 | bugs caught now →
AUDIT doc + this drop's fixes.

### DEFINITION OF DONE (5.0)
Null layer marking and displayed on every book · contracts + invariants green 30 cycles ·
every governed book trading or census-excused · one new market at M3 with 25 carded trades ·
one new family through F1 judgment (promoted or killed — either counts) · Conductor C1
scoring real logs · utilization + idle-cost lines live · Laws 9–16 grep-verifiable · **the
live-money unlock unchanged and untouchable: 100 out-of-sample trades surviving the gate
across 90 unbroken days.**

## THE HONEST CLOSE
One caveat, stated once: nothing in this backbone — not FX, not rotation, not the Conductor —
guarantees a post-cost edge exists in any of these rooms; the $100–300/day figure remains an
unproven hope and is priced here at exactly zero. What 5.0 guarantees is the same thing 4.0
did, extended to every door we might ever open: **wherever this machine looks next, the
record it brings back can be believed** — and it will always know, to the dollar, whether
looking was better than sitting still.

---

# FINAL AUDIT ADDENDUM — 2026-07-10 (the completion pass)

The 5.0 Master Directive's closing order — *verify every system landed, is wired, is fed, and
works* — was executed against the July-9 11:45 PM full backup. Full record with verification
transcripts: `AUDIT_2026_07_10_FINAL.md`. The short version:

**Phase-A spine: VERIFIED COMPLETE.** All seven modules run clean on real data; contracts and
invariants ALL GREEN; dashboard 63/63 fetches resolved; click-through, PROVISIONAL badge, GEKKO
card, hold→max_hold_min contract — all confirmed live.

**Two real bugs found, root-caused, fixed:**
1. *The deep-analytics lane died silently 2026-07-03* (an unfailure-tolerated step skipped
   everything after it, including commit), starving all five evidence labs for a week — the
   wired-but-starved pattern at the workflow layer. Fixed four ways: labs moved into the
   every-cycle spine; the lane rebuilt unkillable (pinned 3.11, every step tolerated); a
   heartbeat store freshness-monitored by contracts; and a new FRESHNESS layer in
   `store_contracts` that turns *any* store that stops being written into a named RED.
2. *`_broker_policy` was prose* — the retired Alpaca bridge still executed in every pulse. Now
   a real gate, default off, re-armable by knob.

**New law earned by this pass (Law 17 — LANES):** *a lane is not alive because its cron exists;
it is alive because its heartbeat is fresh.* Every scheduled lane must stamp a
freshness-monitored store, and no lane's main step may be capable of silently cancelling its
own commit. The July-3 death is the proof case.

Dead code atticked, orphaned data deleted (one-click workflow), pushes race-proofed across all
lanes. Phase-A is closed; the harvest runs unattended. Phases B+ (new rooms, Conductor rungs,
Research-OS v2) proceed exactly as written above — on evidence, never enthusiasm.
