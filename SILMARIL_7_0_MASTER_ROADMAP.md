# SILMARIL 7.0 — THE ACTIVATION · MASTER ROADMAP (6.1 → 7.0, EXECUTED)
**The final structural release. This document is both the expanded roadmap you asked for and its completion audit — every ✅ verified in this build: 358-file compile sweep, node-checked UI, 50-tripwire battery, every engine run live on your data with printed receipts.**

---

## 0 · THE EXECUTED MAP (6.1 → 7.0 in one release)

| mv | name | what shipped | receipt | tripwire |
|---|---|---|---|---|
| 6.1 | **THE GEOMETRY GATE** | p\* on every entry; stops CAP at 1.5×target (never widen — Law 21); Wilson evidence floor (own ∪ cluster prior, shrinkage stated); UNTRADEABLE verdicts with numbers; `GEOMETRY.json`; p\* chips on every position row | **93 TRADEABLE · 44 geo-locked · 83 evidence-short · 425 stand-down** on first contact | T44 |
| 6.2 | **THE STOP-LOSS LAB** | sleeve **G GEOMETRY SNIPER** (TRADEABLE-only, capped stops) vs sleeve **H PATIENT REVERT** (your thesis: proven-revert names, WIDE vol stop, 7-day hold) — clickable ledgers, racing every run | 24 sleeves live across 4 industries; stops BIND at entry | T17/T29 |
| 6.3 | **THE MAKER BOOK** | entries rest as post-only limits (`MAKER_PENDING.json`); FILL on touch at maker cost or EXPIRE with the miss logged — order type is most of the edge on 1–3% moves | REST/FILL/UNFILLED actions in the funnel | T46 |
| 6.4 | **GRADED CONFIDENCE** | every BUY stamps its prediction; every SELL closes the loop (`CALIBRATION_LEDGER.jsonl`); Brier + reliability deciles; **QUARANTINE strips gating authority** → Master falls back to raw evidence | UNPROVEN (n=0) honest at wipe | T47 |
| 6.5 | **THE GOVERNOR** | drawdown ladder ×1.0/×0.5/halt · daily-loss breaker · streak breaker · **ONE-FACTOR LAW** (crypto+GEKKO = one bet) — every wager in paper AND Master obeys | caught **crypto factor 100.2%/60%** live on first run → new adds refuse | T48 |
| 6.6 | **THE CELL TABLE** | class×regime×fit cells, expectancy ± CI; **SELF-ARMS** observe→gate on the first PROVEN cell and writes `_armed_at` — Law 29's reference implementation | 2 cells observing; armed path proven | T45 |
| 6.7 | **LEARNING PERMANENCE** | `archive_evicted()` gzips every eviction BEFORE any cap (discovery, Master ledgers wired); `DATA_LEDGER.json` audits size·cap·archived — **your "data leak" is closed by design** | archive already **2 files · 2.64 MB** from first pass; live 191.6 MB named store-by-store | T49 |
| 6.8 | **THE INTERROGATOR** | ~16 questions answered with evidence each cycle, incl. *"which belief has the least evidence and the most influence?"* → **TOWARD/AWAY-FROM-EDGE** verdict on BRAIN | first verdict: AWAY (9✓ 3~ 1✗) — the ✗ correctly names the over-cap factor | T50 |
| 6.9 | **MASTER v3 + DSR + KNIFE** | regime-conditional policy (in-regime proven sleeve leads, stand-down to global); geometry gate on picks; calibration teeth; sizer hand; **DSR** (Sharpe minus expected max of 316 nulls) on the champion; **FALLING-KNIFE FLOOR-CONFIRM** — in a DOWNTREND, no dip-buy until the last k prints hold above the window low (your July-17 mandate, literal) | DSR honest INSUFFICIENT; policy_src + gate_input written per verdict | T44/T48 |
| **7.0** | **THE ACTIVATION** | version 7.0 pinned everywhere (T9+verify); **GENESIS wipe** (registry-driven, learning resets, archives sacred); Constitution v2 (**Laws 21–30**, no-new-alpha retired → Law 28); workflows audited (2 one-shots retired to attic); battery **42 → 50**; 25/25 BRAIN signals; six new cockpit panels | **50/50 GREEN** | T51 |

## 1 · THE ACTIVATION CHECKMARKS (Law 29 — data flips knobs, never code)
After install, evolution is automatic and pre-registered:
1. **Edge cells**: first cell with n≥20 & CI_lower>0 → `edge_surface.mode` flips to `gate` (writes `_armed_at`). *Already implemented and self-arming.*
2. **Confidence authority**: `CALIBRATION.status` = CALIBRATED at n≥25 → the Master's gate input returns from evidence to confidence automatically (same code path, no change needed).
3. **Crash re-entry**: `CRASH_LEDGER` ≥ 20 resolved obs → flip `crash_lane.reentry` per its documented rule.
4. **Champion trust**: DSR verdict POSITIVE at n≥30 → the ATTRIBUTION label may carry weight again (display already wired).
5. **Live unlock**: the existing 90-day/100-trade lock (untouched) — every book + Master ≥ $10k across 90 unbroken days.
Nothing above requires code. That is what "final update" means.

## 2 · YOUR THREE CONCERNS, ANSWERED IN CODE
**"Bad day — every account red; MR shouldn't buy a collapsing market."** Three organs now stand between you and a repeat: the **falling-knife floor-confirm** (no dip-buy in DOWNTREND until a floor prints — your "watch multiple 10-min samples establish a bottom," verbatim), the **Governor's daily-loss breaker** (−2% of seed halts the day), and the **one-factor law** (a market-wide crypto collapse can no longer be bought ten times under ten names). Sleeve **H** exists precisely to test your "wait for the true bottom, then hold long" thesis with real ledger receipts.

**"Edge concentration looks wrong — one name is 101% of net."** It is mathematically correct and it IS the warning working: when the rest of the book nets −$1.02, the one winner's share of net exceeds 100% by construction (the panel even says so in its red banner). Post-genesis it starts clean; Law 27 governs when concentration is acceptable — *named, sized, survives the remove-the-top test.*

**"Sideways needs many variations."** Correct — regime sub-states (drift-up/drift-down/chop-tight/chop-wide by realized-vol tercile × trend sign) are the first data-driven refinement the Cell Table will surface on its own: cells are keyed by regime, so sub-state expectancy separates automatically as n grows. When cells prove a split, the regime classifier inherits it (knob, not code).

## 3 · BEYOND 7.0 (the only permitted work: capital, not code)
Seed $500 at the evidence gate → live/paper divergence monitor is the kill-switch → ×2 per 100 clean live trades capped by P(ruin)<1% → the harvest reserve is the artifact you show a funder. The Medallion standard, honestly: their moat is execution microstructure + thousands of small conditional edges + ferocious risk control. 7.0 gives you the honest miniature of all three — maker fills, the cell table, the Governor. Beat them by being *provable* at your scale; scale is capital's job, not code's.

## 4 · ONE HONEST PARAGRAPH
Nothing in this release manufactures profit. What it does is make every future dollar **attributable, every failure named the cycle it happens, and every graduation automatic**. Trade count will drop hard on day one — that is the sound of a system finally refusing unwinnable math. If the edge is real, the Interrogator's verdict will walk AWAY → TOWARD inside your 90 days and you will be able to prove it line by line; if it is not, you will know quickly, cheaply, and in writing — with every lesson archived, never lost. Either outcome honors four months of your work. Ship it Sunday. Let the tape talk.
