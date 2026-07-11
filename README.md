# SILMARIL 5.1 — deterministic paper-trading research platform
### The root orientation document. Read this file and `DOCS_5_1/` before touching anything; together they replace every legacy directive/audit/install doc (all moved to `attic/docs_pre_5_1/`).

**What this is:** a multi-book internal paper simulation (crypto · stock · metal · energy · GEKKO
probe + 4 benchmark nulls + one WATCHING Master account) that hunts for a real, fee-surviving
trading edge and refuses to lie about whether it has found one. Deterministic, explainable,
evidence-governed. **What it is not:** income. The $100–300/day figure is an unproven hope priced
at zero. **Live-money unlock (untouchable):** 100 out-of-sample trades surviving the gate across
90 unbroken days.

**Prime doctrine:** Evidence Growth ≥ Feature Growth · realized P&L is the only score ·
every claim Verified/Rejected forward · no synthetic data (test vectors excepted) ·
nothing unproven touches a decision (experimental gates) · every book judged Δ-vs-null ·
root-cause before fix · every squashed bug becomes a permanent tripwire (`scripts/selftest_5_1.py`).

## TABLE OF CONTENTS
| Doc | What it answers |
|---|---|
| `README.md` (this file) | identity, doctrine, and the tab-by-tab UI↔engine checklist |
| `DOCS_5_1/01_ARCHITECTURE.md` | layers, lanes, books, stores — the machine's shape |
| `DOCS_5_1/02_PHILOSOPHY.md` | the Laws (1–16 condensed), gates, nulls, honesty rules |
| `DOCS_5_1/03_ENGINE_PIPELINE.md` | one cycle, step by step, module by module |
| `DOCS_5_1/04_UI_REFERENCE.md` | every panel → renderer function → store |
| `DOCS_5_1/05_WIRING_MAP.md` | producer→consumer table for every store |
| `DOCS_5_1/06_FEATURE_INVENTORY.md` | every feature: COMPLETE / OBSERVE-GATED / RETIRED |
| `DOCS_5_1/07_REGRESSION_PROTECTION.md` | incident → permanent tripwire mapping |
| `DOCS_5_1/08_DATA_ROADMAP.md` | feeds, keys, cron-token guidance, expansion order |
| `DOCS_5_1/09_OPTIMIZATION_ROADMAP.md` | evidence-gated next steps (nothing by date) |
| `DOCS_5_1/10_PRODUCTION_CHECKLIST.md` | the road to live money, prerequisite by prerequisite |
| `NOTES_5_1_LEDGER.md` | every 5.1 operator note → what was done about it |
| `INSTALL_5_1.md` | drag-and-drop install order + first-cycle expectations |

## THE TAB-BY-TAB CHECKLIST — UI element ↔ engine source (audit 2026-07-11; all lanes live)

### ① COMMAND
| UI element | Engine source (store ← writer, lane) | Status |
|---|---|---|
| ★ MASTER ACCOUNT (golden, top) | `MASTER_ACCOUNT.json` ← cli master gate, every cycle | WATCHING by design — trades only after the live-money bar; the cost-stack table is a production REHEARSAL of the proven book's gross |
| Five account buttons + LIVE POSITIONS | `paper_sim_live.json` ← `paper_sim.live_step`, every cycle | 5.1: reordered directly beneath Master (boot JS, graceful no-op); rows now show **net now vs net @ target** + ⚑ AT TARGET only when price ≥ target price |
| LIVE REGIME (⚡ shift watch) | `REGIME_CLASSIFIER.json` ← regime engine, every cycle | per-book; per-VALUABLE 10-min shift detector is Queued (see 09) |
| DENIED THIS CYCLE | `paper_sim_live.json.funnel.rejections` | empty = no vetoes fired that cycle (working, not broken) |
| FIRST-TRADE READINESS / MASTER ACCEPT-REJECT | `MASTER_ACCOUNT.json.decision_log_tail` | fills as gate evaluates |
| WIRING AUDIT | `STORE_CONTRACTS.json` ← `store_contracts`, every cycle | content-timestamp freshness (checkout-proof) |
| UNIVERSE FUNNEL | `paper_sim_live.json.funnel` | "seen" = names with FRESH ticks; census names every exclusion; ccxt waterfall (5.1) grows it |
| SILMARIL 5.1 — SPINE panel | census/contracts/invariants/utilization/conductor/research-OS/bench stores | UTILIZATION `dep n/m` = **cycles**, labeled so in 5.1 |
| FINGERPRINTS coverage | `FINGERPRINTS.json` ← fingerprint engine, hourly | grows as feed breadth grows |
| PROJECT HEALTH / FALLBACK DEPTH | `api_health.json` ← analytics suite **+ 5.1 `health_lights` (keyed lanes)** | key-group zeros fixed: depth computed where the keys actually live |
| Quick log | `DAILY_JOURNAL.json` ← journal writer, cycle | honest by construction |

### ② ARENA
| UI element | Engine source | Status |
|---|---|---|
| CHAMPION TRUTH PANEL | `CHAMPION_GOVERNANCE.json` + `champion_validation.json` | 5.1 adds **CHALLENGER WATCH**: incumbent vs top challenger, gap vs switch-margin, replacement proximity per book |
| QUADRANT LEADERBOARDS | `strategy_leaderboard_{book}.json` + `champion_{book}.json` | backtest labeled **hypothesis**; 5.1 adds live **forward: surv · n** chip; election runs every cycle on forward survivability (rescue fix) |
| STRATEGY SURVIVAL LEADERBOARD | `champion_validation.json.strategies` → `#arenaBody` | populated post-rescue (rows are strategies, never books); 5.1 adds book chip |
| PROMOTION LADDER | governance ladder, validation fallback (5.1) | Sandbox→Incubation(10)→Candidate(25)→Production(50)→Verified(100) |

### ③ FORENSICS
| UI element | Engine source | Status |
|---|---|---|
| PROJECT SCORECARD | `SCORECARD.json` ← `scorecard.py` **(5.1 full rewrite)** | 7 categories, each a printed FORMULA on a named store — auditable, never flattery |
| TODAY'S SESSION (black box) | `SESSION_TODAY.json` ← `session_reconstruction`, cycle | alive post-rescue; resets midnight Vegas; all books |
| SESSION ANATOMY | `SESSION_ANATOMY.json` ← `session_anatomy`, cycle | alive post-rescue |
| REALITY CHECK | `REALITY_CHECK.json` | live-fee survival of the proven book |
| DAILY TAKE-HOME | realized per-day minus documented fees | dollars scale with WAGER (a $1.62 win on a $48 wager is +3.7%, not a $1000 risk — rows print the wager) |
| EDGE CAPTURE | `edge_capture_engine.json` **(5.1 sane universe)** | canonical + fresh ≤24h + one-listing-per-base + \|move\|≤50% — the TON +23824% ghost era is over; emits `pursuable_missed` |
| CRYPTO EDGE CONCENTRATION | `CRYPTO_CONCENTRATION.json` | twin-safe since canonical-key law |
| CHAMPION TIMELINE | `CHAMPION_TIMELINE.json` | rotation is live post-rescue; timeline moves when evidence does |
| PARAMETER-CHAMPION REGISTRY | `PARAMETER_REGISTRY.json` | **decision-driving** (fingerprint fits feed entries/exits), not decoration |
| HEATSHIELD | `HEATSHIELD.json` ← paper_sim | **5.1: ACTIONABLE** — floor resolver applies the measured winner when n≥60 (knob `heatshield_autotune`, clamped, reversible); gate shows WEIGHTED only while genuinely applied |

### ④ SILMARIL NEWS
| UI element | Engine source | Status |
|---|---|---|
| Video wall | `YT_FEEDS` in index.html | dead Schwab stream replaced (5.1) with a stable 24/7 broadcaster |
| Headlines + tags | authority/news stores ← feedparser lane | 5.1: anchors link the **direct article URL** when the store carries it |
| Influence on trading | `NEWS_TRIAL_STATUS.json` + gates board | OBSERVE until the 90-day trial proves hit-rate > coin-flip — research only, never trades |

### ⑤ SETTINGS / SYSTEM BRAIN
| UI element | Engine source | Status |
|---|---|---|
| HEALTH MATRIX | live payload + per-store ages | Peak rhythm now **all industries** (5.1, bounded per class) |
| TUNABLE KNOBS | `PARAM_CATALOG.json` (edit → commit → next cycle) | 5.1 adds `heatshield_autotune`; `reentry_cooldown`, `_broker_policy` from rescue |
| EXPERIMENTAL GATES | `FEATURE_GATES_STATUS.json` ← **5.1 `gate_evidence`** | evidence counts are REAL tallies from named stores; the eternal 0/60 era is over |
| MOVEMENT V | RA/TQ/CALIBRATION/RESEARCH_QUEUE/ECONOMIC_CLOCK + five labs | writers alive post-rescue; rows fill as evidence accrues ("insufficient" is honesty, not breakage) |
| CONDUCTOR | `CONDUCTOR_STATE.json` + **`CONDUCTOR_C1.json` (5.1)** | C0 logging → C1 shadow scoring live (gate 300); C2/C3 evidence-locked (see 02/09) |

## OPERATIONS IN ONE PARAGRAPH
Lanes: PULSE (external cron + `*/10` fallback → daily.yml, the trade cycle) · HOURLY (`:07`, heavy pass)
· ANALYTICS (3×/day deep, heartbeat-stamped) · WEEKLY (backup/scorecard) · SELFTEST (Mon, regression
battery). All state-writers share the `silmaril-state` concurrency group; pushes rebase `-X theirs`
with retries. Every store write is atomic; freshness is judged by CONTENT timestamps because git
checkout resets mtimes. If any lane dies, `STORE_CONTRACTS.json` goes RED and names it within a day.
Cron token: use a **fine-grained PAT with no expiration** (repo-scoped, Actions:write) so the
external pinger never lapses — full steps in `DOCS_5_1/08`.
