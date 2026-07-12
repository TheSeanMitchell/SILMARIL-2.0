# 05 · WIRING MAP — producer → store → consumers (the anti-"wired-but-starved" registry)

Legend: lane P=pulse(every cycle) H=hourly D=deep(3×/day) W=weekly. Contracts layer validates
schema + these rows every cycle; any missing/stale producer is a NAMED red light.

| Store | Producer (module, lane) | Consumers |
|---|---|---|
| price_samples.json | ingestion, P | paper_sim, regimes, fingerprints, edge_capture, peak_rhythm, charts |
| ccxt_samples.json | ccxt_universe (waterfall, 5.1), H/D | paper_sim.load_all_samples, census, chart modal |
| metals_samples / energy_samples | metals_energy_feed (keyed), D | paper_sim, census |
| paper_book_*.json (×5) | paper_sim.live_step, P | validation, session_*, take-home, edge_capture, trade_quality |
| paper_sim_live.json | paper_sim, P | UI everything, gate_evidence, scorecard, utilization |
| HEATSHIELD.json | paper_sim comparison, P | UI, gate_evidence, **floor resolver (autotune, 5.1)** |
| champion_validation.json | champion_validation, P/H | election, split, Survival table, ChampTruth, ladder fallback, arena chips, scorecard |
| champion.json / champion_*.json | champion / champion_split, P | master gate, arena, timeline |
| CHAMPION_GOVERNANCE / TIMELINE | governance writers, H | ChampTruth, timeline panel, gate_evidence |
| REGIME_CLASSIFIER.json | regime engine, P | entries gate, UI, conductor context |
| UNIVERSE_CENSUS + CENSUS_ROSTER | census (content-age gate), P | funnel context, spine, M2 instrument |
| STORE_CONTRACTS.json | store_contracts, P | wiring audit UI, scorecard |
| INVARIANTS(+_STATE).json | invariants (incl INV10), P | spine, scorecard |
| CHAMPION_UTILIZATION.json | utilization, P | spine (CYCLES label) |
| CONDUCTOR_LEDGER.jsonl / _STATE | conductor_log C0, P | **conductor_c1 (5.1)**, spine |
| CONDUCTOR_C1.json | conductor_c1, P (5.1) | spine/Conductor panel |
| RESEARCH_OS.json | research_os, P | spine, roadmap |
| DAILY_BASELINE / AGGRESSION_LADDER / WEEKLY_SCORECARD / STOCK_PARITY_AUDIT / COMPLEXITY_LEDGER | labs, P | Movement V |
| REGIME_ACCURACY / TRADE_QUALITY / CALIBRATION | RA/TQ/calibration, H | Movement V, gate_evidence, scorecard |
| SESSION_TODAY / SESSION_ANATOMY | session_reconstruction / session_anatomy, P | Forensics |
| SCORECARD.json | scorecard (5.1 rewrite), P | Forensics headline grade |
| edge_capture_engine.json | edge_capture_engine (sane universe, 5.1), P | Forensics, scorecard, Research-OS pursuables |
| PEAK_RHYTHM.json | peak_rhythm (all industries, 5.1), H | System Brain |
| FEATURE_GATES_STATUS.json | gates writer + **gate_evidence overwrite (5.1)**, P | System Brain gates board |
| api_health.json | analytics api_health, D + **health_lights merge (keyed lanes), P** | Project Health / fallback depth |
| deep_heartbeat.json | analytics.yml stamps, D | contracts freshness, scorecard lane-liveness |
| MTF_REGIME.json | mtf_regime, P (5.1B) | paper_sim exits/throttle/override/sizing (next cycle), report card, UI ladder |
| REGIME_EXIT_AB.jsonl | paper_sim harvest/fee-clear exits, P (5.1B; append-only, wipe-proof) | conductor_report_card grading |
| CONDUCTOR_REPORT_CARD.json | conductor_report_card, P (5.1B) | SPINE, Conductor panel |
| opportunity_journal.json | opportunity_journal (sane universe + audit reasons + stuck, 5.1B), P | Forensics journal, Conductor learning |
| DECISION_TRACE / DAILY_JOURNAL / MASTER_ACCOUNT / BENCH_BOOKS / FINGERPRINTS | respective writers, P/H | UI + gate_evidence |

**Integration rule:** a new feature is not "done" until its row exists here AND in
`store_contracts` — that is what killed the wired-but-starved failure class.
