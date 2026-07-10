# INSTALL — SILMARIL 5.0 FINAL AUDIT (drag-and-drop, GitHub web UI)

Every file sits at its real repo path inside the ZIP. Drag each into the matching folder on
github.com (or drag the whole tree and let it overwrite). No terminal. All Python is
`py_compile`-clean, all YAML parses, and every fix was verified on your real July-9 data —
transcripts in `AUDIT_2026_07_10_FINAL.md`.

## FILES IN THIS INSTALLER

**Engine**
- `silmaril/cli.py` — the five evidence labs now run in the every-cycle spine (starvation
  impossible); the Alpaca bridge is gated by the real `_broker_policy` knob (off by default,
  per your pricing-only directive)
- `silmaril/execution/store_contracts.py` — five lab stores + deep heartbeat registered; new
  FRESHNESS layer: a store that stopped being written goes RED **by name**

**Config & data**
- `docs/data/PARAM_CATALOG.json` — your July-9 11:45 PM catalog + `_broker_policy` as a real
  object knob. **If you hand-edited any knob after the backup**, don't drop this file — instead
  just edit `_broker_policy` in yours to:
  `{"execution_enabled": false, "pricing_ok": true}`
- `docs/data/deep_heartbeat.json` — seed; arms the dead-lane alarm from minute one

**Workflows** (`.github/workflows/`)
- `analytics.yml` — the lane that silently died 2026-07-03, rebuilt unkillable: Python 3.11 +
  cache, heartbeat start/finish, every step failure-tolerated, rebase `-X theirs` retry push
- `daily.yml`, `hourly.yml` — push rebase upgraded to `-X theirs`
- `weekly_backup.yml` — push now retried
- `cleanup_5_0_final.yml` — **NEW** one-click purge of everything the audit proved dead

**Scripts**
- `scripts/cleanup_5_0_final.py` — the purge itself (code → attic reversibly; orphaned data →
  deleted; ledger printed)

**Root**
- `requirements.txt` — numpy dedupe
- `AUDIT_2026_07_10_FINAL.md` — the full audit record
- `DELETE_THESE_LEGACY_FILES.txt` — now a pointer to the one-click workflow
- `SILMARIL_5_0_BACKBONE.md` / `.xml` — final-audit addendum appended (roadmap pair, complete)
- `INSTALL_5_0_FINAL.md` — this file

## INSTALL ORDER
1. `silmaril/cli.py` + `silmaril/execution/store_contracts.py`
2. `docs/data/deep_heartbeat.json` (+ `PARAM_CATALOG.json`, or hand-edit the knob — see above)
3. All five `.github/workflows/*.yml` + `scripts/cleanup_5_0_final.py`
4. Root docs any time
5. Commit. Then Actions → **Cleanup 5.0 Final (one-time)** → Run workflow → type `CLEAN`.

## WHAT YOU SHOULD SEE
- **First pulse (≤10 min):** run log shows `daily baseline ✔ (spine)` … `complexity ledger ✔
  (spine)`, and `broker bridge: SKIPPED — _broker_policy.execution_enabled=false`. Five new
  stores appear in `docs/data/`. CONTRACTS row may show brief PENDING → GREEN.
- **First deep run (next :20 slot of 07/11/23 UTC):** `deep_heartbeat.json` gains
  `finished_at`; suite outputs move off their 2026-07-03 freeze.
- **If the deep lane ever dies again:** within ~30 h the CONTRACTS row on the Command tab goes
  RED with `deep_heartbeat.json … its producing lane is dead`. That one line is the whole point
  — a week-long silent death is no longer possible.
- **After cleanup:** repo ~25 MB lighter; root has no `cli.py` (it's in `attic/`, reversible).

## ROLLBACK
Code moves are reversible from `attic/` via the GitHub web UI. Workflow files: restore any
prior version from commit history. Nothing in this installer touches trade state, price
history, or long-memory stores.
