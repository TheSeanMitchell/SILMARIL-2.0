# SILMARIL 5.0 — RESCUE + NOTES APPLIED (2026-07-10 PM)
### Base: your July-9 11:45 PM working backup. Every change verified on your real July-10 data before packaging.

## THE BREAKAGE, OWNED PLAINLY
The 07-10 AM "final audit" installer contained a regression — mine. Its broker gate
(`if _HAS_ALPACA and _broker_exec:`) was placed on a block I believed was the Alpaca bridge.
That block is 818 lines and the **internal 4-book paper sim, champion updates, and split
leaderboards live inside it**. With `execution_enabled:false`, the gate switched off the entire
trading core in every lane: books froze at 11:12Z while tail analytics and the 5.0 spine kept
stamping — the "everything broken, daily does nothing" you saw. Your data was never touched:
every ledger, position, and price series is intact. This package is your July-9 base with the
core permanently un-hostaged (the region now always runs; only the single broker call
`run_all_harvest_accounts` is gated, at its call site) — plus your notes, applied.

## VERIFIED BEFORE SHIPPING (all on your real July-10 stores)
| # | Proof | Result |
|---|---|---|
| V1 | Full pipeline, broker knob OFF | paper_sim_live / champion / BENCH / CONTRACTS all stamp fresh; log shows `paper sim:` → spine labs → `run complete`; broker line reads "internal books unaffected". **The regression cannot recur.** |
| V2 | GEKKO exit fix, live_step on your positions | **6 sells fire at their OWN targets**: SOL +1.66%, BCH +5.30%, ETH +3.15%, ZEC +7.58%, AAVE +9.80%, WAVES +3.11% → **+$304.54 realized** that the bug was sitting on |
| V3 | Governance unfrozen | validation now emits strategy rows (crypto: MR_patient_d3, n=13, **survivability 81** — the 0/100 on Forensics dies); election grades real scores; stock book flips to `forward survivability (stock book)` governance |
| V4 | Checkout-proof freshness | heartbeat aged 31h under brand-new mtimes → `RED: its producing lane is dead` |
| V5 | Post-STOP cooldown | 10-min-ago STOP blocked from re-entry; 500-min-ago allowed (knob: 240m) |
| V6 | Universe lane | `ccxt_universe` imports with ccxt now in requirements — the broad crypto lane revives |

## YOUR NOTES → WHAT EACH GOT
**GEKKO buys-never-sells** → ROOT CAUSE: the exit loop filtered positions by book label
("aggressive") instead of universe class ("crypto"), skipping every GEKKO position forever.
Fixed (`asset_class(sym) != uc`). Proof: V2.

**BCH-USD / SUSHI-USD "hit target, not selling"** → Three findings. (1) Your crypto book DID
sell both at TAKE overnight: BCH +$30.42 (05:43Z), SUSHI +$26.00 (08:36Z) — its exit engine
works. (2) What you watched not selling were GEKKO's copies (the real bug, fixed above).
(3) The chart modal drew the CHAMPION's target line (+3%) instead of each position's own fitted
target (e.g. 5.5%) — that manufactured false "hit target" readings. Fixed: the modal now uses
the open position's own target/stop and says so. Also fixed a latent cousin: a held name whose
feed goes stale could previously never exit (marked at entry forever, timeouts off). Now it
marks from the last real print, fills only on a fresh one (≤45 min), and flags itself
`stale_price_min` — armed, honest, never zombie, never filling on fiction.

**"Fixes breaking / not applied to all / returning after wipes"** → the exit logic is one code
path for all five books (the GEKKO miss was the one filter above); the store-contracts layer
now freshness-checks by CONTENT timestamps, so anything that stops updating goes RED by name
even though git checkout makes every file look new (V4). That closes the whole
"silently stopped" class your notes keep hitting.

**Champion never rotates / "Lickitung forever" / Forensics survivability 0 / truth panel
loading** → ROOT CAUSE: champion_validation grouped closed trades by BOOK file, so its
"strategies" were literally `crypto/stock/metal` — and the election filters to real strategy
names, so it graded an EMPTY dict every cycle. It was structurally impossible for any champion
to rotate. Fixed: trades group by the strategy that ENTERED them (`champion_entry`), rows carry
`{book, strategy}`, the crypto election reads crypto rows, and non-crypto books now flip to
forward-survivability governance the moment they have qualifying live trades (your stock book
already qualifies). Proof: V3. Note on the DECISION TRACE confusion: Nightcrawler/Timon/
Electabuzz there are the per-position FITTED parameter variants (your "custom per trade" —
working as designed); `MR_patient_d3` is the governing champion that entered them. Both were
true; the store that reconciles them was the broken one.

**LDO-USD −$70.96 autopsy** → The trade: bought on a fitted 0.96% dip (target 5.5%, stop 6%),
price knifed, STOP honored but filled at −7.1% — the extra 1.1% is gap-through slippage across
a 10-minute cycle on a fast fall (honest, not a bug). The avoidable part: the book re-bought
LDO **24 minutes after** stopping out, into the same falling knife. New knob:
`reentry_cooldown.after_stop_min = 240` — a name that just hit its stop is barred from
re-entry for 4 hours, every book including GEKKO. Proof: V5.

**GEKKO vs crypto "no variation anymore"** → Correct observation: fingerprint fitting had
silently overridden GEKKO's fixed 2%→2%/6% knob profile (its LDO position carried a fitted
5.56% target). GEKKO now bypasses fingerprint fitting entirely and trades its own
`aggressive_book` knobs — the control probe is a control again.

**The accidental A/B (GEKKO +2.33% "beating" crypto +1.11%)** → judged against the Law-10 null:
**BENCH_HODL (just holding BTC/ETH) made +3.31% today. Nobody beat holding.** GEKKO's lead was
the bug forcing it to hold through an up-day — unrealized, exit-fees unpaid: accidental beta,
not alpha. Crypto's harvest ran Δ −2.20% vs holding on this day. That is exactly the
hold-vs-harvest question, and it's already a registered Research-OS question with the EXIT_LAB
(trailing exits) as the sanctioned vehicle — the "hybrid strategy brewing" you smelled, tested
properly instead of shipped on one lucky day.

**MKR-USD "fake numbers"** → Verdict: the trades are REAL — distinct, plausible prints
($1366.44 / $1311.71), canonical key only, no MKRUSD twin traded, no price-snapping (zero
duplicate-print pattern). What made it look fake: MKR has no intraday series in the CHART store,
so its trades floated on an empty chart. Two fixes: the modal now merges `ccxt_samples.json`,
and requirements now installs `ccxt` — which revives the `ccxt_universe` lane that has been
import-dead in production (V6). That lane is also the honest answer to…

**UNIVERSE FUNNEL "seen 90 — did we lose the universe?"** → Not lost: census shows 472 crypto
listed, 91 fresh in 24h — "seen 90" IS the fresh set; 381 names have daily history but no live
ticks because the non-ccxt sources only stream ~90 names. With ccxt installed, expect "seen" to
climb and `ccxt_samples.json` to appear. Metal 12 / Energy 6 similarly reflect feed breadth,
now auditable per-name in the census (which also never ran in Actions until today — its
self-gate used file mtime, which git checkout resets; fixed to content timestamps).

**"Fully automated, updates at all checkpoints — non-negotiable"** → delivered as machinery,
not promises: five evidence labs run in the every-cycle spine; every scheduled lane is
failure-tolerated with a heartbeat; store freshness is content-timestamp based (checkout-proof,
V4); pushes rebase `-X theirs` retried so no lane's output can be silently discarded.

**Master Account tab confusion** → by design: it's a production REHEARSAL — the proven book's
gross run through the full real-world cost stack (fees/spread/slippage/tax/withdrawal) to show
what you'd actually keep. The $10k never moving is correct: the Master does not trade before
the unlock. No change made.

**Queued next (named honestly, not silently dropped):** per-valuable 10-minute regime-shift
detector (new instrument — the per-trade custom FITTING you praised already exists; the live
shift ALERT per symbol is new work); SESSION ANATOMY starvation; DENIED-tab verification;
registry/Settings/Movement-V wording pass; heatshield auto-apply (its OBSERVE gate exists —
evidence 0/60, it earns control the standard way); external-cron migration for remaining lanes;
black-box completeness review. Sniper items, next pass, in that order.

## ONE HONEST CLOSE
The live-money bar is unchanged — 100 out-of-sample trades across 90 unbroken days — and one
green Thursday (HODL +3.3%) proves nothing about edge. What this package restores is the thing
that matters more: the engine runs, sells fire, governance grades real evidence, and anything
that dies says so out loud within a day.
