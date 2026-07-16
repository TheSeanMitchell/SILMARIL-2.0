# SILMARIL 5.3 — THE HAIL MARY · THE EVIDENCE ENGINE
**The final structural build. What follows is the unified directive (docs #1–#5 rolled into one), improved with extreme prejudice, and its completion audit — because a checklist you can't audit is a wish.**
*Authored + executed 2026-07-15/16 against the 11 AM backup. Every ✅ below was verified live in this build: compile sweep, node-check, 41-tripwire battery, and each engine run on your real data with printed receipts.*

---

## 0 · THE CHECKLIST (Table of Contents = the audit surface)

| # | Movement | Ships | Status |
|---|---|---|---|
| HM-1 | **Truth in Accounting** — gross≠net forever; exit reasons READ, never re-derived; verdicts proven | paper_sim · session_reconstruction · session_anatomy | ✅ T30 |
| HM-2 | **Clean Room** — STORE_REGISTRY (289 stores classified) · lab honors the wipe · card derives from books | STORE_REGISTRY.json · strategy_lab · conductor_report_card | ✅ T32 |
| HM-3 | **Resurrect the Dead** — percentile gates (lab D/E/F + Master) · starved components exposed | strategy_lab · master_account · confidence_engine | ✅ T31 |
| HM-4 | **The Venue Layer** — declared fees (Binance.US/Coinbase One/Robinhood) · live listings · Universe Truth Test · capped slippage · roster auto-expansion | venues.py · VENUES.json · VENUE_REALITY.json · ccxt_universe union | ✅ T33 |
| HM-5 | **The Master Brain** — shadow book · evidence-gated picks · ⚡strike-on-shift · USD reserve · policy auto-rotation · every verdict in writing | master_account.py (rewritten) · MASTER_LEDGER · MASTER_DECISION_LEDGER.jsonl | ✅ T36 |
| HM-6 | **The Evidence Layer** — 5-layer tree on all 1,050 cards (market·strategy·symbol·execution·evidence) + Wilson CI + fit_state | confidence_engine | ✅ (T28 extends) |
| HM-7 | **Discovery** — Opportunity Graveyard (+24h/+7d resolution) · Counterfactual engine (never/limit/held+4h/half) | discovery.py · DISCOVERY.json · 2 jsonl ledgers | ✅ T42 |
| HM-8 | **Verified-Crash Lane** — confirmed giant steps = REAL events: logged, cooled-off, learned-from | momentum_chain · CRASH_LEDGER.jsonl · paper_sim gate | ✅ T37 |
| HM-9 | **Reconciliation** — books == card == session, every cycle, out loud | reconciliation.py · RECONCILIATION.json | ✅ T38 (ALL GREEN 7/7) |
| HM-10 | **Champion Honesty** — ATTRIBUTION role on the panel · Hold-timer tells the rhythm truth | index.html · parameter_registry | ✅ T39 |
| HM-11 | **Fit Quality Floor** — DEGENERATE fingerprints never act; every card states FITTED/VOL-NATIVE/DEGENERATE | paper_sim · confidence_engine | ✅ T40 |
| HM-12 | **90-Day Protocol** — readiness ALWAYS a number (0/100 · N/90 from cycle zero) | index.html | ✅ T41 |
| UI | Master Brain panel · Discovery panel · sleeve click-through ledgers · harvest columns · MASTER-FOLLOWS policy chips · chart never dead-ends (the T fix) · 19/19 BRAIN signals | index.html · brain_wiring | ✅ node PASS |
| KNOBS | venue_layer · master_brain · crash_lane · discovery — each with `_what` + pre-registered KILL | PARAM_CATALOG.json | ✅ |
| TESTS | Battery **29 → 41** (T30–T42), all install-safe | selftest_5_1.py | ✅ **41/41** |

---

## 1 · WHAT THE BUILD *FOUND* WHILE BUILDING (new receipts, this session)

**R-A · Reconciliation caught wipe residue on its maiden run.** The report card's cumulative read **$2,235.01** while Σ(all books) = **$681.21** — a $1,553.80 accumulator that survived the 07-14 wipe. Root-caused (the card summed its own persisted `realized_pnl` chain), fixed (Law 17: the card now DERIVES from the books every cycle), and now **7/7 checks GREEN, cumulative = books = verified = $681.21.** The instrument justified its existence in its first sixty seconds.

**R-B · The ONDO saga is closed in every store.** `SESSION_ANATOMY` now reads: `ONDO-USD TAKE → CAPTURED_WELL` · `NEAR-USD TAKE → CAPTURED_WELL`. A perfect target fill can never again be branded "SOLD TOO EARLY" — T30 proves the identity (`100.0% of goal · 0.000 left · fee on its own line · gross 3.000`) on every battery run, forever.

**R-C · The Universe Truth Test answered on first contact:** union 275 venue-listed names, **55 venue-listed names we weren't tracking** (now auto-joining the wide fetch via EXTRA_TICKERS), and **$60.86 of $534.86 realized ($11.4%) was earned on names your venues don't list.** Not fatal — but now it's a *number on a dashboard* instead of a hope.

**R-D · The Master made the first decisions of its life** — shadow-opened positions, closed its first trade, wrote accept/reject verdicts with reasons for all four books, and the golden card now shows equity · USD reserve · SHADOW-TRADING. The 0/90-forever era is over.

**R-E · The Evidence Layer is immediately, usefully harsh:** ONDO — execution 1.00 (listed on all three venues), symbol 0.80, but **evidence 0.035** (fp_n=0, book_n=2, no rhythm). It also exposed **six** starved confidence components (my 5.2 audit found three). Percentile gates make the compressed scale harmless; the starved list makes it visible.

---

## 2 · THE DESIGN LAWS 5.3 ADDS (permanent)
- **Law 16 — Gross never meets Net.** Every crossing percentage carries its basis; a perfect fill reads 100%.
- **Law 17 — Facts are read from their source of truth.** Re-derivation is how HELD_GAIN lied; it is banned.
- **Law 18 — Gates are percentiles of the live distribution.** An unreachable gate is a hidden untested hypothesis.
- **Law 19 — Evidence outranks value.** Every card answers *how proven* before *how good* (fp_n · book_n · Wilson CI · freshness · venues).
- **Law 20 — The not-done is data.** Rejections resolve forward; trades spawn counterfactuals; the Master learns policy.

## 3 · THE 5.3 NOTES, IMPROVED WITH PREJUDICE (what I changed and why)
The other agent's Evidence-Engine philosophy was right; its mechanics didn't know this machine. Improvements executed: **(1)** its 12-layer waterfall became five *measured* layers wired into the existing card (no parallel architecture to rot); **(2)** its 10-alternate counterfactual became four *deterministic* alternates computable from the recorded tape (no synthetic prices — Law 7); **(3)** its "Master as allocator with its own AI-like brain" became a *shadow book with a written ledger* — allocation follows evidence it can cite, and rotation follows the lab's closable leaders you asked for; **(4)** its promotion ladder collapsed into the one bar that matters (100 OOS trades · 90 unbroken days · every book + Master ≥ $10k · beats the nulls · survives concentration and venue tests) because eleven stages nobody audits is ceremony; **(5)** its "automatic executive briefs" were deferred as decoration — the BRAIN, SPINE, and the new panels *are* the brief, live, every cycle.

## 4 · WHAT DID **NOT** SHIP (named, so nothing leaks back in silently)
Live order placement (the 90-day lock is untouched; connectors remain the next-phase dry-run task) · equities-venue selection (documented decision, not code) · crash re-entry (knob exists, OFF until CRASH_LEDGER ≥ 20 obs) · closed-loop phase-3 re-decide (reconciliation shipped; the re-decide pass waits for one clean week under the new instruments) · executive brief generator. **Freeze after this:** the only permitted changes in the 90-day window are P0 correctness fixes that ship with a tripwire.

## 5 · THE 90-DAY PROTOCOL (operator runbook)
**Install** (drag-drop, workflows paused) → **run one daily** (stores regenerate; expect battery **41/41**) → **internal wipe** (the lab, the Master, and every STATE store now provably reset — T32) → **enable the 10-minute runner** → **do not touch it.** Watch: RECONCILIATION stays green; MASTER LEDGER fills with reasons; the Graveyard resolves; readiness counts N/90 from the wipe. The bar is unchanged and now *computable*.

## 6 · ONE HONEST PARAGRAPH
5.3 does not manufacture an edge — it makes an edge **impossible to fake and impossible to miss**. The fee model can't drift 3× anymore; a perfect fill can't be shamed; a dead sleeve can't hide; the Master can't coast on a zero-length record; the wipe can't leave ghosts; and everything the system *declines* now testifies. If the next 90 days show daily compounding, you'll be able to prove it line by line. If they don't, you'll know that too — quickly, cheaply, and in writing. That is the whole release, and it is enough.
