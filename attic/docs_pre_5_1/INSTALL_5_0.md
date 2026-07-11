# INSTALL — SILMARIL 5.0 (drag-and-drop, GitHub web UI)

Every file below sits at its real repo path inside the ZIP. Drag each into the matching folder on
github.com (or drag the whole tree in and let it overwrite). No terminal required. All files are
`py_compile` / `node --check` / YAML-JSON clean and smoke-run on your real data.

## FILES IN THIS INSTALLER

**New engine modules** (`silmaril/execution/`)
- `bench_books.py` — Null Layer: 4 strategy-free $10k baseline books (Law 10)
- `store_contracts.py` — schema + producer/consumer registry; kills wired-but-starved (Law 12)
- `census.py` — universe roll-call + new-listing detector
- `utilization.py` — DEPLOYED/ARMED/BLOCKED/STARVED per book/cycle (Law 16)
- `conductor_log.py` — Conductor rung C0 (context ledger, zero behavior change)
- `research_os.py` — Research OS v1 (questions · debt · negative knowledge · decaying beliefs)

**Patched engine**
- `silmaril/cli.py` — runs the 5.0 spine each cycle (wrapped; fast + full)
- `silmaril/execution/champion.py` — `provisional` provenance (Law 9) + live rotation knobs
- `silmaril/execution/champion_validation.py` — canonical tiers 10/25/50 + `production_verified`

**Workflows** (`.github/workflows/`)
- `daily.yml` — pulse is now ALWAYS the fast trade cycle
- `hourly.yml` — **NEW**: heavy pass on cron `:07` (the lane split)
- `backfill_universe.yml`, `remap_keys.yml`, `reset_internal_clean.yml`, `cleanup_clutter.yml`,
  `cleanup_root.yml`, `weekly_backup.yml` — joined the `silmaril-state` concurrency group

**Config & scripts**
- `docs/data/PARAM_CATALOG.json` — new `bench_books`, `champion_rotation`, `_broker_policy` knobs
- `scripts/reset_internal_clean.py` — wipes derived 5.0 views, preserves long-memory stores

**Dashboard**
- `docs/index.html` — SILMARIL 5.0 header · fixed click-through · 🦎 GEKKO card · PROVISIONAL badge
  · 5.0 Phase-A strip (nulls / census / contracts / utilization / conductor / research OS)

**Docs (root)**
- `SILMARIL_5_0_BACKBONE.md` / `.xml` — the roadmap pair
- `AUDIT_2026_07_07_INSTALLER.md` — what this pass found and fixed
- `SILMARIL_5_0_SCALE_GUIDE.md` — moving off GitHub Actions to real infra
- `INSTALL_5_0.md` — this file

## INSTALL ORDER (safe either way, but this avoids a red cycle in between)
1. `silmaril/execution/` new modules + patched `champion*.py`, then `silmaril/cli.py`.
2. `docs/data/PARAM_CATALOG.json` and `scripts/reset_internal_clean.py`.
3. All `.github/workflows/*.yml` (including new `hourly.yml`).
4. `docs/index.html`.
5. Root docs (any time).

Commit. The next pulse runs the spine; `hourly.yml` fires at the next `:07`.

## WHAT YOU SHOULD SEE ON THE FIRST FEW CYCLES
- **Command tab, new "SILMARIL 5.0 — PHASE-A SPINE" strip:** NULLS marking (CASH/SPY/HODL/EQW),
  a Δ-vs-NULL line, CENSUS counts, CONTRACTS verdict (expect GREEN, a few PENDING on brand-new
  stores for the first write), UTILIZATION per book, CONDUCTOR `n/300`, RESEARCH OS summary with
  the highest-value next question, and the live ROTATION KNOBS.
- **A 🦎 GEKKO card** in the quadrant row showing its real open positions; clicking any quadrant or
  the GEKKO card now opens its detail modal (the click-through is restored).
- **Champion panel:** a red **PROVISIONAL** badge while the incumbent holds without forward
  evidence, with the plain-words rotation trigger. This is correct and honest — it clears itself
  the moment a strategy books its minimum live trades.
- Census may report a large "new ≤14d" count on the very first run (the long-memory roster is
  seeding); it settles to true new listings after a day.

## VERIFY IT'S ALIVE (Settings → api_health / the new stores)
New files that should appear in `docs/data/` within a cycle or two: `BENCH_BOOKS.json`,
`UNIVERSE_CENSUS.json`, `CENSUS_ROSTER.json`, `CHAMPION_UTILIZATION.json`, `CONDUCTOR_LEDGER.jsonl`,
`CONDUCTOR_STATE.json`, `RESEARCH_OS.json`, `STORE_CONTRACTS.json`. If `STORE_CONTRACTS.json` reads
`ALL GREEN`, every module is not just wired but actually fed.

## TUNING ROTATION (the thing you wanted to push)
In `PARAM_CATALOG.json → champion_rotation`, lower `min_trades` and `switch_margin` to rotate
faster. Defaults (`5`, `15`) reproduce prior behavior exactly. Watch Research-OS **Q002** — it
grades whether faster rotation actually improves realized P&L before you trust it. The election
runs every cycle for all books; you are turning a dial, not editing code.
