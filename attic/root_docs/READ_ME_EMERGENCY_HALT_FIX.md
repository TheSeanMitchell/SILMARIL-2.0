# SILMARIL — EMERGENCY FIX: "sold everything and stopped trading"

This drop fixes the showstopper from the 2AM deploy and answers the roadmap
question straight. Three files, drag-and-drop at their repo paths. All compile
clean; the deadlock fix is proven on your live 6:20 data.

---

## What actually happened (traced in the 6:20 repo, not guessed)

Two events in sequence, both confirmed in `alpaca_h3_state.json` / `hard_stops.json`:

**1. It sold everything.** The consensus engine flipped `STRONG_SELL` across
crypto, and the exit ladder's consensus-flip layer dumped every position at once
(XTZ closed −$9.18, plus XRP/SUSHI/SOL). That is a *broad reversal* signal
overriding positions — the opposite of your golden law ("exit when OUR position
turns, not on a full reversal").

**2. It stopped — a halt DEADLOCK.** Those realized losses pushed #2 to −3.28%
and #3 to −3.24% (and −6.11% weekly) on the day. That tripped the hard-stop in
`silmaril/risk/hard_stops.py` (`DAILY_HALT_PCT = 3%`), which set
`plans_to_iterate = []` and blocked **all** opens. To un-halt, the rule needs a
**+1.5% rebound from the halt low** — but the book was now **100% cash**, so
equity is static, so it can *never* rebound, so the halt *never lifts*. The
engine was permanently frozen in cash. `last_cycle_summary.composite_halt: true`,
`orch_objective: "RECOVER_FROM_DRAWDOWN"` — the orchestrator literally wanted to
recover but the halt wouldn't let it trade. #3 was worse: the **weekly** halt
needs +2.5% and wouldn't clear for days.

This is a real design flaw, not a market problem: **any −3% day permanently
stops a 24/7 cash account.** It surfaced now because removing the grocery
harvest (which used to bank tiny gains constantly and kept the book churning
near $10k) means a reversal now hits unbanked positions and crosses −3% in one
move.

---

## The fixes

### 1. `alpaca_paper.py` — break the halt deadlock (the "stopped" fix)
The halt is now split:
- **CATASTROPHE** (cohort −4% safe-mode, or an explicit policy kill-switch) →
  still a **full block**. Systemic, hands-off.
- **DRAWDOWN-ONLY** (this account's own daily/weekly hard-stop) → **RECOVERY
  MODE**: it keeps trading, but only the **3 strongest fresh-GREEN names**
  (recovery probes), so the account can move, rebound, and lift its own halt
  instead of deadlocking in cash.

Proven on your live 6:20 candidates: from 39 admitted names it selects 3 probes
(MOG +9.1%, OMC +7.0%, NWS +3.0% on the 10-min read). **Safety proven too:** if
the whole market were red, it selects **zero** — recovery mode never catches a
falling knife, it only probes names that are genuinely rising right now. The
normal tradability + market-hours + fresh gates still apply on top, so only
tradeable, in-session, rising names actually fill.

### 2. `alpaca_paper.py` — consensus defers to momentum (the "sold everything" fix)
A `STRONG_SELL` consensus no longer dumps a position whose **own fast tape is
still green and in profit**. That broad-signal mass-dump is what sent #2/#3 to
cash all at once and into the halt. A still-green winner is now left to the
momentum exit (which sells it when ITS tape actually rolls); a fading or losing
position still honors the consensus sell. This is the same golden-law principle
as the entry gate, applied to the exit.

### 3. `edge_capture.py` + `docs/index.html` — the ceiling counter you asked for
The edge panel now shows two honest numbers instead of one:
- **held-only edge** (what we banked on names we held): ~5.8%.
- **reachable edge** (of the opportunity Alpaca can even reach, what % we bank,
  counting tradeable runners we *missed* as 0): **~2.2%** — the real number to
  drive toward 100% before migration.
- **Alpaca-reachable: ~64.7%** of the big-mover opportunity. **53 of the biggest
  movers are off-limits on Alpaca** — that 35% is locked behind migration no
  matter how good the logic gets.

---

## Are we done with the 2.1 roadmap? No — here's the honest status.

**Done and live:** §6 entry gate (nosedive fix), grocery harvest removed from the
live path, momentum exit is the primary sell brain, buy-side debuggability (entry
gate panel), and now the halt-deadlock fix + consensus-defer + the ceiling
counter.

**Not done (still 2.1, pre-migration):**
- **Prove the spine drives edge UP over cycles.** This is the big one and it
  *cannot* be finished in a single drop — the edge metric is computed off
  accumulated fill history, so it only climbs as post-fix trades replace the old
  ones. The fixes are structurally correct; they need live cycles to show. Watch
  **reachable edge** (2.2% today) as the scoreboard.
- Authority-catalyst tiering and the attention-lifecycle layer (roadmap items
  3–4) — allowed but untouched; lower priority than getting edge up.
- Per your note, the **full grocery purge + leaderboard removal is deferred to a
  later update** (not in this drop, as you asked).

---

## The hard truth, since you're at a decision point

You said: fix it today or abandon Alpaca, then GitHub. The **"stopped trading" is
fixed** — the engine will trade again and can't deadlock on a routine drawdown.

But be clear-eyed about the rest: the crypto accounts have been *losing* for days
($10k → ~9.5k → ~9.3k), and even on Alpaca's reachable universe we bank only
~2.2% of the opportunity. **That 2.2% is a logic problem, and it follows you to
any broker.** Abandoning Alpaca recovers the 35% off-limits names but does
nothing for the 2.2% — you'd just have a bigger universe to lose on. Abandoning
GitHub doesn't help either; the cron cadence limits timing precision, but it is
not why the book is red. The entry gate + exit rewrite + these two fixes attack
the 2.2% directly — but they need a few clean cycles to prove. **The order that
actually wins is unchanged: get reachable edge climbing on Alpaca first, prove
it, then migrate to add the 35%.** Migrating before the logic works just scales
the bleed.

## How to verify
- `python3 -m py_compile` clean on both files; dashboard JS passes `node --check`.
- Recovery-probe proof: 3 probes from real candidates; 0 in a red market.
- After deploy, the next crypto cycle should show `RECOVERY MODE: N probe(s)` in
  the log instead of `OPEN halted`, and the accounts should start moving again.
