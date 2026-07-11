# 04 · UI REFERENCE — panel → renderer → store (docs/index.html)

Boot: `load()` every 60s; 5.1 adds font-scale control (A−/A/A+, localStorage `silmarilZoom`,
body zoom .7–1.8) and Command reorder (Master → account buttons → LIVE POSITIONS; heuristic,
graceful no-op).

| Panel | Renderer | Store(s) |
|---|---|---|
| Live positions/trades (all books) | `renderTrades` + row builders | `paper_sim_live.json` — 5.1 rows: net-now, net-@-target, ⚑ AT TARGET only when mark≥target px; wager printed on trades |
| Master card / cost rehearsal | `renderMasterCard` | `MASTER_ACCOUNT.json` |
| Champion truth + CHALLENGER WATCH | `renderChampTruth` | `CHAMPION_GOVERNANCE.json`, `champion_validation.json`, rotation knobs |
| Quadrant leaderboards (+forward chip) | arena builder | `strategy_leaderboard_*`, `champion_*`, validation |
| Survival leaderboard | `#arenaBody` filler | `champion_validation.strategies` (book chip, 5.1) |
| Promotion ladder | ladder line | governance → validation fallback (5.1) |
| Scorecard | `renderScorecard` | `SCORECARD.json` (formula categories) |
| Session recorder / anatomy | `renderSession` / `renderAnatomy` | `SESSION_TODAY.json` / `SESSION_ANATOMY.json` |
| Reality / take-home / concentration / timeline / registry / heatshield / Kraken | respective renderers | same-named stores |
| Edge capture | edge panel | `edge_capture_engine.json` (sane universe + pursuable_missed) |
| Spine strip (census/contracts/invariants/utilization/conductor/research-OS/rotation/feeds) | spine builder | respective stores; UTILIZATION labeled CYCLES |
| Movement V | `renderMovementV` block | REGIME_ACCURACY / TRADE_QUALITY / CALIBRATION / RESEARCH_QUEUE / ECONOMIC_CLOCK / DAILY_BASELINE / AGGRESSION_LADDER / WEEKLY_SCORECARD / STOCK_PARITY_AUDIT / COMPLEXITY_LEDGER |
| System brain health matrix + gates | `renderBrain` | live payload, `FEATURE_GATES_STATUS.json` (real evidence, 5.1), PEAK_RHYTHM (all industries) |
| Project health / fallback depth | health matrix builder | `api_health.json` (+`key_groups` from health_lights, tolerant text until first beat) |
| News wall + headlines | news builders | `YT_FEEDS` (Schwab→stable 24/7 swap) + authority stores (direct `url` links) |

Rule of the house: a panel with nothing honest to say prints "insufficient/accruing" — never a fake number.
