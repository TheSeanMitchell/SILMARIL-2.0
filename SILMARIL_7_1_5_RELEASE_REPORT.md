# SILMARIL 7.1.5 — "THE RAILS THE SLEEVES NEVER GOT"
### Why G and H are losing, gold trading on a Sunday, a doctrine you can read like a book, and a worksheet that ends in a decision.

**Battery: 117/117** on the full tree, a genuinely reset tree, and a simulated install over your 11 AM backup. Click path 9/9. Sleeve engine and veto ledger verified running on your real data.

---

## THE HEADLINE: the sleeves have been running with no safety rails

I put the two engines side by side. This is the whole explanation for G and H:

| rail | funded books | sleeves (before today) |
|---|---|---|
| re-entry cooldown | 4 references | **0** |
| trajectory veto | 11 references | **0** |
| market calendar | yes | added 7.1.4, gated per *book* — wrong for both |

Six releases of hard-won safety rails existed **only in the funded books**. The workshop has been trading without them the entire time.

### G GEOMETRY SNIPER — 4 closed, 0% win, every one a STOP
The ledger shows the mechanism, and it is not subtle:

```
SELL XTZ-USD   STOP  08:47:54   →   BUY XTZ-USD   08:47:54    (the same second)
SELL TURBO-USD STOP  12:18:42   →   BUY TURBO-USD 12:18:42    (the same second)
SELL XMR-USD   STOP  17:31:23   →   BUY XMR-USD   17:31:23    (the same second)
```

It stopped out and **instantly re-bought the identical falling name**, over and over. XTZ stopped it twice. That is not a bad strategy — it is a strategy with no cooldown, feeding itself into a knife.

### H PATIENT REVERT — 2 closed, 0% win, both STOPs
Both on names in confirmed downtrends: XTZ (peaks FALLING, −1.6% 1D / −2.2% 2D / −2.2% 3D) and TURBO. **Mean reversion wants oversold-in-a-RANGE.** Bought in free-fall it is simply early, every time. Your own chart of XTZ said "Peak trajectory FALLING" in red — the exact signal that should have vetoed the trade, drawn on screen and consulted by nothing.

### The fix — three rails, mirroring what the books already do (T121)
1. **Re-entry cooldown.** 180 minutes after any close; **360 after a stop-out**. This alone breaks G's loop.
2. **Trajectory veto.** Down across every window **and** peaks stepping down ⇒ no entry. This is the **first time a graph-derived read gates a decision** rather than decorating one. Deliberately a *veto*, not a signal: a veto can only prevent a trade the system was already taking, so it cannot invent a new loss. Knob `respect_trajectory` · kill available.
3. **Per-symbol market calendar** (below).

**And every refusal is now written down** — `SLEEVE_VETOES.json` records what each sleeve declined and which rail stopped it, because *"quiet by correct design"* and *"actually broken"* look identical from outside until the workshop states its reasons.

---

## GOLD AND METALS — yes, and here is the correct answer

You asked whether metals can trade now. Two things had to be true, and I checked both.

**First, what our metal book actually holds:** `metals_samples.json` = **XAG, XAU, XCU, XPD, XPT** — *spot metals, not ETFs*. That matters enormously, because 7.1.4 gated the whole book off on weekends as if it held GLD. Spot metal never closed the way an equity does; we were silencing instruments that were trading fine.

**Second, your CME note:** the 1-Ounce Gold future went 24/7 on **2026-07-26** — today.

So the calendar is now **per symbol**, not per book:

| instrument | when it may open |
|---|---|
| **XAU** (spot gold) | **24/7** — trading right now, this Sunday |
| XAG, XPT, XPD, XCU | 24/5 — reopens Sunday 22:00 UTC |
| BRENT, NATGAS, **WTI** | 24/5 — and WTI **auto-flips to 24/7 on 2026-08-30**, pre-registered in code so it happens without me |
| GLD, IAU, SLV, GDX, USO, UNG… | NYSE session only — an ETF is an equity, whatever it tracks |
| equities (IRM…) | NYSE regular session |
| crypto | always |

Your instruction — *"sleeves first, then accounts after it proves to work"* — is exactly what the pyramid already enforces: metal sleeves may now trade gold immediately; the metal **book** stays locked until a metal sleeve earns PROMOTED on ≥3 real closes.

**The Sunday IRM position:** opened 09:18 UTC today, *before* 7.1.4 landed on your tree. Under 7.1.5 that entry is refused at the symbol level. It is still open and will be managed to exit normally — exits are never gated, because a real desk still manages positions through a closed session.

---

## THE OTHER THINGS YOU FLAGGED

**The chart key was confusing** — our fills used the same triangles as the market's peaks and troughs. Now: **our decisions are diamonds ◆**, the **market's structure keeps triangles ▲▼**, and the legend is grouped `OURS:` / `MARKET:` with hover tooltips naming price, time and P&L.

**"Are the graphs defaulting to zero between runs?"** No — and now you never have to wonder. Every vertex is a real print; the line between two prints is straight because we have *no data in between*, so a long gap looks like a snap. The chart footer now prints **its own sampling cadence and worst gap**: *"sampled every ~10m, worst gap 2.9h — every vertex is a real print, straight lines between them mean no data in between (never zero)."*

**Sub-hour regime cells reading "—"** — confirmed, the 12m and 15m bands have no computation behind them; only 30m and up are wired. Logged in the doctrine's open-gaps table rather than silently patched, because it needs the regime engine to sample faster, not a display fix.

---

## THE TWO DOCUMENTS YOU ASKED FOR

### `DOCTRINE.md` — the rulebook, readable in fifteen minutes
Your words: *"we are only as good as our decisions system, so we need to be able to read it like a book."* It covers, in plain language: the four layers and why a pyramid exists at all · how one coin travels from tape → fingerprint → geometry gate → confidence card → sleeve → promotion → book → Master · what all nine confidence components actually mean · **how slots are prioritised** (and the honest admission that each sleeve ranks on one number) · what the graph harvests and how · the 14 standing laws · and **Part 7: what is still open**, including that the graph does not yet drive trading and the confidence weights were designed rather than fitted.

It is written to be *true*, not flattering. Where something does not work, it says so.

### `SILMARIL_DAILY_WORKSHEET_v2.md` + `scripts/daily_block.py`
The v1 sheet had 40 sections and did not work, for three reasons I state in it plainly: **it made you the sensor** (transcribing numbers a machine can read), **it described instead of deciding** (a green board can hide a broken product — your battery read 111 pass / 0 fail while every chart link was dead), and **it had no memory** (no way to see "fourth day metal hasn't traded").

v2 inverts all three:
- **`python scripts/daily_block.py`** prints everything the machine can know about itself — books, arming, feed truth, source divergences, sleeve scoreboard, promotion, refusals, the river, graph verdicts, the gate. One paste, no transcription.
- **Six questions only you can answer**, led by *"Did anything look FAKE today?"* — because every serious bug in this project's history announced itself that way, and several passed a fully green battery.
- **It ends in a decision**: `DECISION / FIX TODAY / WATCH / STREAK` — and "nothing today, keep collecting" is explicitly a valid answer.
- **A streak log**, the memory v1 never had.

---

## TODAY'S AUDIT (run against your 11 AM tree)

```
engine ran 78m ago · last wipe 14.1h ago
BOOKS      all four at $10,000.00 · 0 open · crypto armed=False (OBSERVE — workshop must promote)
FEEDS      647/1074 tradeable · FROZEN 64 · QUANTIZED 49 · COARSE 38 · UNKNOWN 276
SOURCE     1 divergence: TIA-USD card $0.3315 vs tape $0.3455 (−4.05%) · 76 names with no recent print
SLEEVES    crypto E −0.049% (2 closed, 50% win) · A −0.440% · D/F −0.584% · stock E −0.879%
PROMOTION  crypto NO_POSITIVE_SLEEVE (best is G at −1.81%) · stock/metal/energy PROVISIONAL
RIVER      8 outcomes · win rate 12.5% · mean net −0.868%
GRAPH      TOO_EARLY on all six features (n=16) · consumed_by_decisions = False
GATE       8/100 forward closes · 0.6/90 days
```

**STATUS 🟡 — quiet by correct design, and losing honestly.** No book is armed because no workshop has earned it; crypto correctly promotes nobody with its best sleeve at −1.81%. The river's 12.5% win rate is real and bad — and now explained: G's stop→rebuy loop and H's downtrend entries account for it, and both are fixed today.

**That TIA-USD divergence is the new detector earning its keep** — a derived store disagreeing with the tape by 4% is precisely the condition that fabricated the PNUT windfall. Under the fresh-price law it cannot cause a fill.

### DECISION: **NO RESET.**
You are 0.6 days into a 90-day clock and the only corruption found this cycle is one card divergence that cannot fill. Resetting now would cost you the 8 outcomes you have and buy nothing. What would change my answer: fabricated fills appearing *after* this install, or the price-source audit reporting divergences that persist across cycles.

### FIX TODAY: install 7.1.5 and let it run. The rails are the fix.
### WATCH: the river's win rate. If it is still under 30% after 20+ closes *with the rails on*, the problem is the strategies, not the plumbing — and that is a real finding worth having.
### STREAK: day 1 of clean-rails operation.

---

## INSTALL (6 files + report)

```
silmaril/execution/strategy_lab_abcd.py       docs/silmaril_chart.js
scripts/selftest_5_1.py                       scripts/daily_block.py            (NEW)
DOCTRINE.md                          (NEW)    SILMARIL_DAILY_WORKSHEET_v2.md    (NEW)
SILMARIL_7_1_5_RELEASE_REPORT.md     (root)
```

Hard-refresh after the Pages deploy. **Keep active:** `daily.yml` (the only scheduled writer), `selftest.yml`, `weekly_backup.yml`, `verify_install.yml`. **Keep disabled:** hourly, analytics, backfill, venue, compact, cleanup — all manual-only; they cannot race the writer.

## THE HONESTY CAVEAT

Nothing here adds edge. It removes three ways the workshop was losing money to its own plumbing, tells gold it may trade, and gives you two documents so you can check my work instead of trusting it. The river currently says 12.5% win, −0.868% mean over 8 closes — that is the honest starting line, and the rails are what make the next hundred closes worth reading.
