# SILMARIL 7.1.1 — "THE EVERYTHING CHART" · why you saw zero difference, and the fix

**Battery: 108/108 green.** Functionally rendered against YOUR 8:20 PM data before shipping: MOG-USD and DOGE-USD, the two names from your screenshots.

## THE STRAIGHT ANSWER: I instrumented the wrong chart.

Your dashboard has THREE chart systems. The one every ticker click actually opens is **`docs/silmaril_chart.js`** — its capture-phase click handler intercepts ALL ticker clicks site-wide. In 7.1.0 I wired the external overlays and the nine-layer graph into `silmaril_graph.js` + `drawChart()` — a path your clicks never reach. So the engine did the work and the modal you use displayed none of it. That is the whole story of "zero difference," and it was my miss: I audited slices of a 265KB file and never searched `docs/` for other chart implementations.

**The proof the engine side WAS running, from your own 8:20 PM backup:** `SOURCE_OVERLAY.json` — 229KB, 16 held/weighed names, real Coinbase + Kraken series, DOGE verdict AGREE · `CANON_MIGRATIONS.jsonl` — the DOGEUSDT re-key executed · movers journal — 4 real 48h movers (was "99.7% of 399 missed") · **FINGERPRINTS: 674/674 fitted** (your "jack it to 674" ask was already satisfied — it was just never drawn). The data existed; the door didn't open onto it.

## WHAT 7.1.1 SHIPS (one file + tripwire): `silmaril_chart.js` v3 — the modal itself becomes the Everything Chart

Every ticker click now opens, drawn ON the price with a full legend:

- **Outside venues overlaid** — Coinbase (orange) and Kraken (purple) dashed lines from SOURCE_OVERLAY, plus Yahoo for ETFs/metals/energy, with the time-aligned agreement chip in the header: `vs outside venues +0.041% AGREE · checked 12m ago`. Per-provider spreads in the side panel. Absent venue = absent line, never invented.
- **Peaks ▲ / troughs ▼ / floors / ceilings with test counts** — engine CHART_INTEL when fitted; otherwise the SAME swing math runs in-view on the SAME tape, labeled "view-detected". Every name shows structure now — no more blank rooms because the engine hadn't prioritized a symbol.
- **Heartbeat & the next peak** — median peak-to-peak rhythm, last peak (price + time), a purple vertical at the projected next peak with a live ETA ("next peak ~in 2.1h (rhythm 3.4h)").
- **Trajectory ladder** — 2h/4h/8h/12h/1D/2D/3D/1W chips straight from the tape (your MRVL/AMAT complaint: the multi-window read is now on every chart).
- **The fingerprint's own fit, drawn** — blue "fp buys X.XX% dip" and green "fp bounce +X.XX%" lines from its custom fit, plus reliability and the summary in the panel. All 674 fits are now visible.
- **Geometry gate chip** — TRADEABLE/UNTRADEABLE in the header, with "needs to win X% vs measured floor Y%" in the panel.
- **Kept:** entry/target/stop/live-mark, your real fills, Dr Strange projection, confidence card, OHLC panel, crosshair, timeframes.

## THE MOG "GLITCH" — named, not mystified

MOG is NOT a bug in our pipeline and NOT quarantine-worthy stale data: the venue feed reports it at only **2–3 representable sub-penny price levels ~22% apart** — the square wave IS the feed's tick size. Two fixes: (1) an amber **⚠ QUANTIZED FEED** banner on any chart where ≤6 price levels span the view, stating exactly that and that integrity rails exclude it from entries; (2) **honest sub-penny formatting** — axis labels now show `$0.0000001187`, never five rows of `$0.000000` (verified on your MOG tape).

## YOUR OTHER POINTS, DIRECTLY

- **"You removed the open positions bars for the sleeves."** No — byte-identical between your 5:40 PM and 8:20 PM backups: 6/6 `__posBar` + OPEN POSITIONS blocks present (sleeve modal lines ~1238/1251, portals ~1489/1526). What changed around them: marks now come from the canonical tape, so the bars have live data instead of freezing at entry. If a specific sleeve still renders without bars, name it and I'll trace that exact ledger.
- **"Do we have to run backfill universe?"** No. Backfill fills daily-candle history depth; it gates none of this. It also now runs automatically inside the daily lane at 08 UTC. Nothing to press.
- **Fingerprints "to 674 NOW"** — already there: 674/674 in your live FINGERPRINTS.json. 7.1.1's job was making them visible.

## INSTALL (2 files, drag-and-drop)

| file | path |
|---|---|
| `docs/silmaril_chart.js` | `docs/` |
| `scripts/selftest_5_1.py` | `scripts/` (adds tripwire T112) |
| `SILMARIL_7_1_1_CHART_REPORT.md` | repo root |

No reset. No engine change. Hard-refresh the dashboard (Ctrl/Cmd+Shift+R) after the Pages deploy (~1 min) — the modal is client-side, so the change is visible on the very next click.

One honesty caveat: the outside-venue layer covers the 16 held/weighed names the budgeted overlay scopes (by design — it refreshes top-of-hour for what matters now); every OTHER layer — structure, cadence, next-peak ETA, trajectory ladder, fingerprint fit, geometry, quantized-feed truth, sub-penny digits — renders for all 1,000+ names immediately.
