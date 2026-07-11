# INSTALL — SILMARIL 5.0 RESCUE + NOTES APPLIED (drag-and-drop)

This package = your July-9 11:45 PM working base + your 5.0 notes applied. It installs
cleanly on EITHER (a) your current live repo as-is, or (b) a fresh reinstall of the July-9
backup — same files either way, every file at its real repo path.

## ORDER
1. `silmaril/cli.py`  ← the rescue: trading core un-hostaged (this alone revives the engine)
2. `silmaril/execution/` — paper_sim.py · champion_validation.py · champion.py ·
   champion_split.py · store_contracts.py · census.py
3. `docs/index.html` and `docs/data/deep_heartbeat.json`
4. `docs/data/PARAM_CATALOG.json` — your July-9 catalog + two new knobs
   (`_broker_policy`, `reentry_cooldown`). If you hand-tuned other knobs since July-9,
   instead add just those two objects to YOUR catalog (values are in this file).
5. `.github/workflows/` — analytics.yml · daily.yml · hourly.yml · weekly_backup.yml ·
   cleanup_5_0_final.yml, and `scripts/cleanup_5_0_final.py`
6. `requirements.txt` (adds ccxt — revives the broad crypto universe lane)
7. Docs (`NOTES_APPLIED_2026_07_10.md`, this file) anywhere at root. Commit.

## THEN (your stated plan — fully compatible)
Wipe (`reset_internal_clean` — long-memory and price history survive as always) → rebuild
fingerprints → run daily once → deep analytics once → hourly once → point the cron runner at
daily every 10 minutes.

## FIRST-CYCLE EXPECTATIONS
- Daily run log: `broker bridge: SKIPPED` … `paper sim: combined equity …` … five
  `✔ (spine)` lines … `✦ SILMARIL run complete`. Books stamp every cycle again.
- GEKKO's over-target holds sell on the first cycle with fresh prices (≈ +$305 realized at
  July-10 marks; post-wipe it simply starts clean and SELLS from day one).
- Forensics/truth panel show a real survivability score; champion reasons cite scores and
  margins, not silence.
- After ccxt installs: `ccxt_samples.json` appears; UNIVERSE FUNNEL "seen" climbs past 90;
  MKR-class names chart.
- If ANY lane dies: the CONTRACTS row goes RED with the store named within ~a day.

## ROLLBACK
Every file here has a July-9 twin in your backup — drag the old one back. No data files are
modified except the two knob additions to PARAM_CATALOG and the heartbeat seed.
