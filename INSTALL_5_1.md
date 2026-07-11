# INSTALL — SILMARIL 5.1 FINALITY (drag-and-drop, no wipe required)

## ORDER (GitHub web UI, commit after each group)
1. `silmaril/execution/` — paper_sim.py · ccxt_universe.py · edge_capture_engine.py ·
   peak_rhythm.py · invariants.py · scorecard.py · **health_lights.py · gate_evidence.py ·
   conductor_c1.py** (new)
2. `silmaril/cli.py` (spine additions)
3. `docs/index.html`
4. `docs/data/PARAM_CATALOG.json` — this file = your July-11 catalog + `heatshield_autotune`.
   If you hand-tuned knobs since, instead add ONLY that object (value inside this file).
5. `scripts/` — selftest_5_1.py · cleanup_5_1_docs.py; `.github/workflows/` — selftest.yml ·
   cleanup_5_1_docs.yml
6. Root docs — README.md (overwrites) · DOCS_5_1/ (11 files) · NOTES_5_1_LEDGER.md · this file
7. Optional now / anytime: run **cleanup_5_1_docs** workflow with `confirm=ATTIC` to sweep the
   24 legacy root docs into `attic/docs_pre_5_1/` (nothing deleted — additive philosophy)

## FIRST CYCLES — what you'll see
- Header **SILMARIL 5.1**; A−/A/A+ top-right; Master → buttons → LIVE POSITIONS ordering
- Position rows: `net now · net @ target`; ⚑ AT TARGET only when price truly crosses
- Spine log: `health lights ✔ … gate evidence ✔ … conductor C1 ✔ … scorecard …`
- Fallback depth turns real on the first daily/hourly cycle; gates show live tallies
- Next hourly/deep: `ccxt universe: N fresh pairs from binanceus` → funnel "seen" climbs,
  `ccxt_samples.json` appears, MKR-class charts fill (first success may take one lane pass)
- Monday 03:45 UTC: selftest lane reports **8 pass** (or run it on demand from Actions)

## ROLLBACK
Every file has a July-11 twin in your backup; the catalog change is one added key. Cleanup is
reversible (attic keeps everything).
