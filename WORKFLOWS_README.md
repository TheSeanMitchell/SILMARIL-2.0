# WORKFLOWS — table of contents & operating manual (5.1B)
### Read this before editing ANY workflow file. Every state-writing lane shares the `silmaril-state` concurrency group; two writers can never race, but a careless edit here can starve a store and flip a red light. The wiring audit (`STORE_CONTRACTS.json`) will name the dead lane within a day — this page tells you what you broke.

## THE TABLE
| File | Purpose | Trigger(s) | Internal timer (UTC) | Writes / owns | Depends on | Edit safety |
|---|---|---|---|---|---|---|
| `daily.yml` | **THE PULSE** — ingest → mark → decide → execute → verify + full 5.1 spine (MTF ladder, health lights, gate evidence, C1, report card) | external cron (primary) + fallback schedule + dispatch | `*/10` fallback | every trading store: books, paper_sim_live, HEATSHIELD, MTF_REGIME, REGIME_EXIT_AB, CONDUCTOR_*, journal, contracts, invariants… | secrets env block (all `*_API_KEY`) | SAFE to change cron minutes only. NEVER add steps between checkout and the engine run; NEVER remove `concurrency` or `run_lock` |
| `hourly.yml` | heavy pass: arena compact, RA/TQ, governance, sanitize | schedule + dispatch | `:07` (off the congested :00) | leaderboards, champion_validation, governance, RA/TQ | daily's stores | keep `:07` stagger; safe to retime ±minutes |
| `analytics.yml` | deep suite: WIDE arena, api_health, fee scenarios, sweeps | schedule + dispatch | `7:20 · 11:20 · 23:20` | api_health (merged with key_groups), deep stores, `deep_heartbeat` | keyed secrets | keep off market-open hour (13:30–14:30 UTC); retime freely otherwise |
| `backfill_universe.yml` | nightly gap-fill: daily candles + census backstop, **entire universe, all industries** (crypto incl. ccxt waterfall, stock, metal, energy) | schedule + dispatch | `8:10` (dead zone) | price history backfill, fingerprint fuel | feeds | safe; keep in the dead zone |
| `weekly_backup.yml` | repo snapshot + weekly scorecard | schedule + dispatch | Sun `0:00` | backup artifact, WEEKLY_SCORECARD | — | safe |
| `selftest.yml` | 14-tripwire regression battery (READ-ONLY) | schedule + dispatch | Mon `3:45` | nothing (prints only) | — | always safe; run on demand after any install |
| `verify_install.yml` | one-click whole-truth marker audit (asserts version **5.1** + every 5.1B marker) | dispatch only | — | nothing | — | update markers when you ship features |
| `cleanup_5_1_docs.yml` | attic legacy root docs (confirm=ATTIC) | dispatch only | — | moves files to `attic/` | — | one-time tool |
| `reset_internal_clean` (script, run via dispatch lane if present) | the WIPE — resets books to $10k, preserves ALL long-memory (`EVOLUTION_LEDGER · RESEARCH_OS · CONDUCTOR_LEDGER · REGIME_EXIT_AB · CENSUS_ROSTER …`) | manual | — | books, sim state | — | 5.1B-verified: preserve list includes every new store |

### Maintenance lanes (dispatch-only — nothing runs these on a timer)
| File | Purpose | Safety |
|---|---|---|
| `reset_internal_clean.yml` | THE WIPE (books → $10k; long-memory + price history preserved incl. `REGIME_EXIT_AB` and the Conductor ledgers — 5.1B-verified) | confirm-gated; run only when you mean it |
| `backfill_universe.yml` | (also listed above) after a wipe, this + the pulse rebuild fingerprints for the ENTIRE universe, all industries — metals/energy fit FIRST under the 5.1B class quotas | safe |
| `compact_history.yml` | history compaction (repo-size discipline) | keeps the knob-governed windows; never touches long-memory stores |
| `remap_keys.yml` | canonical-key remapper (twin dedupe) | safe; concurrency-guarded |
| `cleanup_clutter.yml` / `cleanup_root.yml` / `cleanup_5_0_final.yml` / `cleanup_5_1_docs.yml` | historical tidy-up tools, confirm-gated | one-time tools; harmless to leave |

## PEAK-HOURS RULE
Never schedule heavy lanes inside **13:00–15:00 UTC** (NYSE open window) or **:00** of any hour (GitHub cron congestion). The stagger above already respects both.

## GOING EXTERNAL-CRON-ONLY (the operator's standing wish — now one switch)
Every scheduled job above carries `if: github.event_name != 'schedule' || vars.EXTERNAL_CRON_ONLY != 'true'`.
1. Set up the external runner per `CRON_SETUP.md` (root) — endpoints + eternal fine-grained PAT.
2. Repo → Settings → Secrets and variables → **Variables** → New: `EXTERNAL_CRON_ONLY` = `true`.
3. Done: every internal timer becomes a 2-second no-op skip; zero overlap, zero GitHub-attention competition. Delete the variable (or set `false`) to restore internal timers instantly — nothing is ever removed from the files.
