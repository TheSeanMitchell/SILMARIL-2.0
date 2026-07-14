# NOTES 5.1 LEDGER — every operator note → what was done (2026-07-11)
Legend: **FIXED** engine/UI change in this drop · **PROVEN-OK** investigated, engine exonerated with receipts · **SHIPPED** new capability · **QUEUED** named in 09 with its gate.

| # | Note (raw + prompts) | Disposition |
|---|---|---|
| 1 | Font scaling desktop/mobile | **SHIPPED** — A−/A/A+ control, whole-UI zoom .7–1.8, persisted |
| 2 | PYTH/STRK "hit goal, didn't sell" | **PROVEN-OK + FIXED(UI)** — marks were BELOW target price (PYTH 0.0485<0.05057; STRK 0.030743<0.031372); the row compared GROSS-now vs NET-at-target. Rows now print net-now vs net-@-target and ⚑ AT TARGET only when price ≥ target price. Runtime tripwires T2/T3 + scorecard Exit-integrity watch this forever |
| 3 | THETA $1.62 / INJ $1.26 "barely clears fees on $1000" | **PROVEN-OK** — realized +3.70% / +2.66% on ~$48 wagers (not $1000); trade rows print the wager. Fee-clearance stays enforced (`min_takehome_usd`, T8) |
| 4 | GEKKO offloads, crypto holds — is the faceoff fair? | **PROVEN-OK** — both books run the same healed exit path; GEKKO's fixed 2% targets simply fill sooner than crypto's larger fitted targets. Comparison is now trustworthy; Δ-vs-HODL is the referee |
| 5 | Market-hours bug keeps returning | **SHIPPED** — INV10 runtime invariant + selftest T7; weekend stock BUY = named FAIL |
| 6 | Cron token expires | **DOCUMENTED** — no-expiration fine-grained PAT recipe in DOCS_5_1/08 |
| 7 | Future-proof every swatted bug | **SHIPPED** — `selftest_5_1.py` (8 tripwires incl. the T1 AST core-hostage guard) + weekly lane; doctrine: fix ships with its test |
| 8 | Universe capped at 90 / want full Binance.US | **FIXED** — ccxt lane had erred silently forever (binance.com HTTP 451 geo-block on US runners); 5.1 waterfall binanceus→kraken→coinbase, USD+USDT quotes, honest error trail in-store. "seen" grows as the lane lands; census names every exclusion |
| 9 | "dep 42/43 — capped to 43 valuables?" | **PROVEN-OK + FIXED(UI)** — 43 = CYCLES in the window, not symbols; labeled |
| 10 | Fingerprints → prediction, every valuable | **PARTIAL + QUEUED** — coverage grows with feed breadth (ccxt); peak-rhythm now ALL industries; per-valuable 10-min shift alert is Queued #1 with its grade-then-gate plan |
| 11 | Conductor / Master Brain finish | **SHIPPED** — C1 shadow scoring live (honest matched-subset method, gate 300, kill criteria pre-registered); C2/C3 evidence-locked; Master stays WATCHING until the bar (by your own directive) |
| 12 | Arena: champion never rotates / survival + ladder empty / transparency | **FIXED** — rotation was structurally frozen (rescue root cause); Survival populates from strategy rows (+book chip); ladder falls back to validation; CHALLENGER WATCH shows gap-to-flip per book; backtest labeled hypothesis + live forward chip |
| 13 | Scorecard feels like flattery | **SHIPPED** — full rewrite: 7 categories, each a printed formula on a named store |
| 14 | Session recorder / anatomy broken | **PROVEN-OK** — writers were core-hostaged pre-rescue; both stamp every cycle now; wiring rows guard them |
| 15 | Edge capture 0.05% / TON +23824% ghosts | **FIXED** — sane-universe denominator (canonical, fresh ≤24h, deduped, \|move\|≤50%), wager-aware capture, `pursuable_missed` feed for Research-OS |
| 16 | Heatshield: make learning actionable | **SHIPPED** — floor resolver applies the measured winner (n≥60, clamp 4–10%, knob-reversible); gate reads WEIGHTED only while genuinely applied |
| 17 | News: stale videos, direct links, transparency | **FIXED** — dead stream swapped for a stable 24/7 broadcaster; headlines link the article URL when present; influence stays OBSERVE-gated with real trial counts |
| 18 | Gates never fill / System Brain complete | **FIXED** — `gate_evidence` writes REAL tallies from named stores every cycle |
| 19 | Fallback depth all 0/N | **FIXED** — root cause: key-groups computed only in the keyless lane; `health_lights` now computes depth in the keyed lanes every cycle |
| 20 | Movement V unfinished | **PROVEN-OK + COMPLETE** — all row sources alive post-rescue; "insufficient (needs ≥N)" is the honest state until evidence lands |
| 21 | Command hierarchy: buttons + LIVE POSITIONS under Master | **SHIPPED** — boot reorder (graceful no-op if markup shifts) |
| 22 | Replace all root docs; future models orient instantly | **SHIPPED** — README checklist + DOCS_5_1/01–10 + this ledger; 24 legacy docs attic'd by `cleanup_5_1_docs` (confirm-gated) |
| 23 | Header → SILMARIL 5.1 | **SHIPPED** — title, spine, all version strings |
| 24 | Avoid future wipes | **SUPPORTED** — nothing in this drop requires a wipe; install is additive; long-memory stores untouched |
