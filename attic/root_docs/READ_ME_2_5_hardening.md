# SILMARIL 2.5 — Workflow Hardening + Cockpit Landing

Drop on the repo root, overwriting. All Python compiles. Disaster-recovery work
skipped per your call (you'll keep manual backups). This is workflow hardening +
making the 2.5 cockpit the front door.

## Workflow hardening (the part you cared about)

**1. No two state workflows can run at once.** All 16 state-mutating workflows now
share one GitHub concurrency group (`silmaril-state`, cancel-in-progress: false):
daily, backfill_history, compact_history, reset, reset_10k, full_reset,
pristine_reset, reset_alpaca_grocery_to_truth, heal_starting_balance, risk_unfreeze,
wipe_for_alpha_2_1, migrate_alpha_3_0, sweep_switch, train_from_backtest, reflection,
senate. GitHub now serializes them — a reset can no longer fire while daily is
mid-write; it queues. Read-only workflows (backtest, diagnose, correlation, stress)
were left alone.

**2. Atomic writes.** New `silmaril/execution/atomic_io.py::write_json_atomic()`
writes to a temp file, fsyncs, then `os.replace` (atomic). Wired into the four
deploy-critical writers — champion, strategy_lab (leaderboard), champion_validation,
capital_router. A run killed mid-write can no longer leave a torn/corrupt
leaderboard or champion file; readers see either the old or the new, never half.

**3. Run lock.** `run_lock()` guards the live cycle in `cli.main()`: if a fresh
`run.lock` exists the run skips itself ("skipping to avoid double-write"); stale
locks (>30 min, i.e. a crashed run) auto-reclaim so nothing wedges. Belt-and-
suspenders with the concurrency group; demo runs are unlocked.

Net: duplicate cron overlap, concurrent execution, and partial/torn writes are now
all closed off. The one related bug still open is the `hold: 44` vs
`max_hold_min: 240` config mismatch (flagged last session) — that's a logic fix, not
a concurrency fix, and it's the next thing to clean up.

## 2.5 UI

`docs/index.html` is now the black-and-white retro cockpit (was saved as
`legacy_dashboard.html`, still reachable from the nav). Opening the site now lands on
SILMARIL 2.5: champion survival + 10/25/50/100 milestones, open positions with full
exit plans (target/stop/timeout — the JTO fix), the interval equity chart, and the
arena survival table.

## Honest status

Done now: workflow hardening (concurrency + atomic + lock), cockpit as landing,
2.5 branding on the main view. Not done: converting every *secondary* page
(paper_sim, lifecycle, leaderboard) to the B&W theme — mechanical, next pass, lift
the cockpit `<style>` into a shared `silmaril.css`. And the `hold`/`max_hold_min`
logic fix. Neither blocks the waiting period.

You can relax into the wait now: the system is serialized, its writes are atomic,
the front door is 2.5, and every open position shows exactly what it will sell at.
The job from here is time — let the champion stack trades toward 25 → 50 → 100.
