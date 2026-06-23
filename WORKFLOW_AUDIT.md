# WORKFLOW_AUDIT.md — SILMARIL 2.5 (Alpha 2.18 P4)

Audit of GitHub Actions workflows for concurrency, duplicate execution, and write
safety. Hardening implemented in the prior session; this documents the state.

## Can daily / backfill / compaction / reset run simultaneously?

**No — not anymore.** All 16 state-mutating workflows share one GitHub concurrency
group, `silmaril-state` (`cancel-in-progress: false`). GitHub serializes any run in
this group, so a reset cannot start while `daily` is mid-write — it queues. This
directly closes the overlap risk the directive names.

Covered (shared group): daily, backfill_history, compact_history, reset, reset_10k,
full_reset, pristine_reset, reset_alpaca_grocery_to_truth, heal_starting_balance,
risk_unfreeze, wipe_for_alpha_2_1, migrate_alpha_3_0, sweep_switch,
train_from_backtest, reflection, senate.

Left independent (read-only, safe to overlap): backtest, diagnose, diagnose_alpaca,
correlation_check, stress_test.

## Write safety

- **Atomic writes:** `silmaril/execution/atomic_io.py::write_json_atomic()` writes
  to a temp file, fsyncs, then `os.replace` (atomic on POSIX). Wired into the
  deploy-critical writers: champion, strategy_lab (leaderboard), champion_validation,
  capital_router, and CHAMPION_GOVERNANCE. A run killed mid-write cannot leave a
  torn/corrupt file — readers see old or new, never half.
- **Run lock:** `run_lock()` guards the live cycle in `cli.main()`. A second live
  run aborts if a fresh `run.lock` exists; stale locks (>30 min, i.e. a crashed run)
  auto-reclaim so nothing wedges.

## Status vs directive

| Requirement | Status |
|---|---|
| No concurrent execution | ✅ shared concurrency group |
| No overlapping cron | ✅ same group serializes crons |
| No duplicate processing | ✅ group + run lock |
| No corrupted state writes | ✅ atomic writes on critical files |
| Workflow locks | ✅ run.lock + GH concurrency |
| Atomic writes | ✅ (critical paths; remaining JSON writers can adopt the helper incrementally) |
| Recovery checkpoints | ◻️ deferred (you opted to rely on manual backups) |

## Remaining (low priority, your call to skip DR)

- Extend `write_json_atomic` to the remaining non-critical JSON writers (mechanical).
- Reconcile the `hold`/`max_hold_min` config mismatch (logic bug, flagged separately).
- Disaster-recovery simulation (RECOVERY_MATRIX) — deliberately deferred; you keep
  regular full backups, which covers the same risk more simply.
