# SILMARIL 4.0 — THE FINAL DIRECTIVE
## Verification, Aggression, and the Machine That Cannot Lie to Itself
### The keystone document. Compounds — removes nothing from — the 3.0 Master Directive (Phases 0–23), the Movement V Addendum (24–28), the 4.0 Completion Backbone (Laws 1–8, Movements VI–VIII), and the operator's full note set (`Silmaril_4_0_Notes.txt`, incorporated VERBATIM by reference as first-class law).

---

## THE ONE OBJECTIVE (from the Notes, now canon)

> **Make it impossible for the engine to lie. Not intentionally — statistically.**

3.0 was Governance. **4.0 is Verification.** Profit is a consequence; truth comes first. Every
subsystem exists to strengthen one of the **Four Pillars** — Understanding, Prediction,
Execution, Evolution — and every claim anywhere in SILMARIL must eventually be **Verified or
Rejected** by forward evidence (the Truth Engine doctrine). Nothing optimizes for looking
intelligent; everything optimizes for being correct.

## THE MOVEMENTS, RENAMED (per the Notes — this alone changes the philosophy)
**I Verification · II Market Intelligence · III Adaptive Trading · IV Knowledge Evolution ·
V Portfolio Cognition · VI Scientific Discovery · VII Self-Audit.**
The Notes' Master Improvement Backlog (Movements I–XXI: Data Integrity → Global Market
Cognition, ~300 items) is adopted wholesale as the research roadmap; the note file ships beside
this directive and binds any future agent.

---

# WHAT THIS FINAL PASS EXECUTED (July 6 — built, compiled, smoke-proven on the real repo)

### 1. THE UNFREEZE — root cause found and killed
The paralysis was never parameter overload. **Cycle cadence had degraded to ~50–66-minute
gaps** (external pinger), so the warmup gate could mathematically never fill → 0 entry-warm →
0 candidates → 0/90 master → frozen champion. Fixes, all live:
- **Cadence-proof warmup**: knob-driven (`PARAM_CATALOG.warmup`, default **8 pts & ≥1.5h
  span**) — the ~2h-context principle preserved, starvation impossible. Smoke: 630/630
  entry-warm on the real July-6 stream.
- **In-repo fallback schedule** (`*/10`) in daily.yml — the harvest never again depends on one
  external service being configured correctly; run_lock + the shared concurrency queue make
  overlap with the pinger harmless.
- **Cadence watchdog**: every cycle computes observed median gap from its own ledger and prints
  it on the ENGINE PULSE with an explicit warning above 20m. Degradation can never again be
  silent.

### 2. THE JUNE-30 TRUTH — reconstructed, and reintroduced as governed knobs
The 33/35-win, +21.66% day (`paper_book_crypto.json`, June-30 repo) was **real mechanics, not
magic**: 5-minute data density × 2% dip entries × ~1–2% targets × ten concurrent shots — rapid
small wins, several closing the same minute. None of it was exotic; all of it is now dialable:
- `regime_overrides.crypto.SIDEWAYS = {entry 2%, target 2%}` (+UPTREND entry 2%) — **the
  June-30 profile lives on the main book**, judged by the forward record, with today's
  fee-honest engine auto-vetoing anything that can't clear round-trip costs.
- The remaining ingredient — density — returns with the cadence fixes above.

### 3. 🦎 GEKKO — the aggressive probe (the operator's fifth account, delivered)
A **separate, independent $10k paper book** on the crypto universe named **GEKKO** ("greed, for
lack of a better word") — professional shorthand for exactly what it is. Doctrine:
- **Same rails, lower bar**: integrity quarantine, knife veto, heatshield floor, and fee-honesty
  all bind; entries at 2% dips → 2% targets, soft regime gate (observes-with-conviction in
  DOWNTREND instead of hard-blocking).
- **Absolutely Master-isolated**: never funded, never mirrored, excluded from champion
  governance (smoke-verified: master ledger books = crypto/stock/metal/energy only).
- **Dual purpose**: harvest the low-hanging fruit the governed books skip, AND manufacture the
  forward evidence (trade-quality cards, calibration pairs, fee reality at thin margins) that
  Verification needs — the Notes' "Observation Priority" idea given a body.
- Fully knob-controlled (`aggressive_book`: enabled/name/entry/target/stop); wiped on reset;
  auto-recreates at $10k. **Smoke: GEKKO took its first position on its first cycle**, exactly
  where the 3% governed book found nothing.

### 4. MOVEMENT I (VERIFICATION) — first two engines LIVE
- **Regime Accuracy Audit** (`regime_accuracy.py`, hourly): every regime call graded against
  the market 24h later (median book move, ±1% bands); per-book accuracy% + confusion counts;
  honest below 5 graded. *The classifier now earns trust instead of assuming it* — Notes #1.
- **Trade Quality Engine** (`trade_quality.py`, hourly, GEKKO included): every closed trade gets
  a report card — entry vs local low, exit vs local high, % of the available move captured.
  **Proven on today's real trades**: YFI captured 44.8% and 48.6%; BONK's card exposed the
  knife (entry 3.15% below the local low; the floor did its job) — Notes #11.
- **Master confidence decomposed** (Notes #6): every ledger row now carries
  `confidence_parts` — the REAL formula inputs (survivability / win% / closed trades /
  net-after-fees). Verified live: `win 66.7 · trades 3 · net −$15.21`. No mystery; the
  multi-factor board (trend/liquidity/fingerprint/…) earns components only as each signal
  proves out.
- **Gates-influence stamp**: every cycle the payload states plainly whether ANY experimental
  gate influenced trading (today: "all observe, weight 0") — Notes Cat-A #4 transparency.

### 5. UI TRUTH-PAIRING (per the operator's only sanctioned "superficial" work)
GEKKO position/trade tables + funnel row + doctrine banner; dynamic warmup rule (the stale
"0/24" is dead); cadence + gates on the ENGINE PULSE; Regime-Accuracy and Trade-Quality rows on
the Movement-V strip. Every new capability is visible the moment it breathes.

---

# THE REMAINING 4.0 BUILD (for the successor, in execution order)
All prior obligations stand; evidence sources are already accruing.
1. **Movement I completion**: prediction-vs-outcome ledger for EVERY forecast (regime durations,
   expected moves, master expectations) → calibration curves per subsystem (Notes XX); False-
   Positive tracker (how often did confidence-X lose); Drift Monitor (monthly edge/expectancy/
   fees/turnover deltas — Notes #17); deterministic-replay self-audit (Notes XIII).
2. **Statistical Edge Discipline** (Backbone Movement VI, unchanged and binding): luck baseline
   printed on every 316-way board; multi-window consistency for "trusted"; walk-forward-only
   promotion; edge-decay flags; 2× friction bar; **point-in-time universe snapshots start
   immediately** (every day without them is unrecoverable survivorship bias).
3. **Adaptive Trading**: per-asset parameter hypotheses (the Notes' "ETH best pullback 2.3%")
   grown from GEKKO+book forward trades — Parameter Evolution objects (current/tested/
   confidence/next-candidate) replacing bare knobs.
4. **Market Intelligence**: probability-distribution regimes (trend%/confidence/transition risk/
   expected duration — Notes Cat-A #1 card, verbatim target); regime topology + combos
   transition table (≥30 occurrences) feeding gated confidence boosts.
5. **Knowledge Evolution / Truth Engine**: every claim in the system registered → Verified/
   Rejected with evidence counts; counterfactual engine (Universes A–E per trade); Opportunity-
   Cost engine ("what SHOULD I have done").
6. **Portfolio Cognition**: fingerprints → behavioral identities; Market Weather traded by the
   Master while books trade assets; Market Memory analogs ("92% similar to State #37" — the
   June-30 forensic state is the first entry).
7. **Self-Audit forever**: the cycle-level questions from the Notes ("what froze? what stopped
   learning? which hypotheses never graduate?") as a standing panel.

**Prepare-for-years clause** (Notes, verbatim spirit): every store append-only or wipe-proof,
every change in the Evolution Ledger, nothing temporary, everything cumulative.

## DEFINITION OF DONE (4.0) — unchanged where it matters
Every Movement-I surface live-and-honest · Laws 1–8 grep-verifiable · promotion only ever by
forward evidence · the live-money unlock remains exactly **100 out-of-sample trades surviving
the gate over 90 unbroken days** — enthusiasm never opens that door; evidence does.

## THE HONEST CLOSE
No architecture can guarantee a persistent post-cost edge exists — the Notes say it, and it is
law here too. What THIS machine now guarantees is rarer: **whatever the July–October record
says, you will be able to believe it.** The governed books measure the edge honestly; GEKKO
hunts it greedily inside the same rails; and the Verification layer grades every claim either
of them makes. If the edge is real, this system will find it, prove it, and compound it. If it
isn't, you'll know truthfully, cheaply, and first. That is what four months of this work
bought — a machine that refuses to lie to the person who built it.
