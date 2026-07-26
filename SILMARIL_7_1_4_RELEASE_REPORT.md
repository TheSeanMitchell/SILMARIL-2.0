# SILMARIL 7.1.4 — "THE FILL IS THE TRUTH"
### The $242.19 traced to the print, a second fabrication you already suspected, the Sunday trade, the prioritisation answer, and the graph→decision audit you asked for.

**Battery: 116/116 green** on the full tree, a genuinely reset tree, and a simulated install over your 6:45 AM backup. Live cycle, sleeve engine, both new audits and the quarantine all run clean on your real data.

**You do NOT need a genesis wipe. You do not need a reset at all.** See "THE RESET QUESTION" below — the two poisoned rows are neutralised surgically and your clock keeps running.

---

## 1 · THE $242.19 — traced to the print, then closed three ways

`2026-07-26 06:52:19 · SELL · PNUT-USD · STRIKE · $242.19 · 11.533% · TARGET`

That position's target was **+4%**. Here is what actually happened:

- The **exit** was priced from the live tape: **0.0443**.
- The **entry** was priced at **~0.0397** — arithmetic: `wager 2100 × 1.11533`.
- PNUT's tape only carried 0.0397 the **previous morning** (2026-07-25 08:03). At 06:09:59, the freshest print was **0.0448**.

One position, two prices, from two different moments. Not a trade — arithmetic on mismatched inputs. Then it was appended to `LAB_OUTCOMES.jsonl` as **1 of only 5 rows** the maturity gate and sleeve promotion had to read. A single unreal fill was **20% of the system's knowledge**. That is the corruption you kept sensing and could not name.

**Three independent rails now, because any one alone can be defeated** (tripwire T117 replays your actual PNUT numbers):

1. **Only the tape may price a fill.** Confidence cards, decision traces and rosters may *rank and suggest*; they may never set a price. The `cards.last_px` fallback that was the vector is deleted — a name with no tape mark is no longer a candidate at all.
2. **No fill on a stale print**, and unknown age counts as stale. With money on the line, "we don't know how old this is" must mean no. Window 45 min, matching the books. An unfilled position simply stays armed, exactly as a live venue leaves a resting order.
3. **A take-profit cannot fill above its limit.** A stop takes the **worse** of trigger and mark, because slippage is real and must be worn. This asymmetry *is* real execution, and it is the backstop: even if a stale price ever slips through again, a windfall is arithmetically impossible.

The identical defect was in the funded books at `paper_sim.py:1165` (`why, fill = "TAKE", cur`) — capped there too. Every capped fill now stamps what was given up (`forgone_pct`), every gap-crossing fill stamps the hole it crossed, and every fill stamps `px_age_min`.

## 2 · THE SCAN FOUND A SECOND ONE — the trade that made energy look like a winner

`scripts/quarantine_bad_fills.py` scans the learning river for outcomes that could only come from a pre-7.1.4 fabricated fill. On your tree it found **two**:

| when | name | booked | reality |
|---|---|---|---|
| 2026-07-26 06:52 | PNUT-USD (sleeve E) | **+11.533% · $242.19** | limit was +4% |
| 2026-07-23 16:22 | **BRENT (energy)** | **+15.280% · $198.64** | limit far below that |

That BRENT fill is the one behind your July 24 note — *"The ENERGY accounts and sleeves made so much money."* Part of that was fabricated. I'd rather tell you now than let it keep electing champions.

The test is deliberately narrow: a **limit-class** exit more than 1% above the most generous take-profit any sleeve can set (6%). Nothing else qualifies — a big STOP loss stays (losses were never inflated), a big trailing-exit win stays (market orders may legitimately run), a modest TARGET win stays. **Nothing is ever deleted** (learning-permanence law): rows are annotated `excluded: true` with the reason, a `.pre_7_1_4` backup is written, and the run is idempotent. I also made the consumers **actually skip** excluded rows — annotating without skipping changes nothing.

## 3 · THE RESET QUESTION — no, and here is why

You asked twice, and you said you feel sad about the months you threw away. You are right to.

The corruption was **two rows**, and they are now neutralised in place. A standard reset would clear them *and* the real evidence beside them; a genesis wipe would additionally destroy fingerprint maturity and restart the 90-day clock from zero. Neither is warranted for two annotated rows.

**Run this instead — it is the surgical alternative you have been asking for:**
```
python scripts/quarantine_bad_fills.py docs/data --apply
```
(or Actions → Daily Run, then read `PRICE_SOURCE_AUDIT.json`). Your clock keeps running. **My recommendation: no reset, no genesis.**

## 4 · WHY THE SHIB TRADE WENT BAD — not corruption, a real design gap

`SELL · SHIB-USD · $-190.27 · -6.342% · STOP`. I reconstructed the graph from the tape **as of the entry** (05:27:58), using only prints that existed then:

| the graph said, at entry | value |
|---|---|
| range position | **97.4%** — the very top of its 48h band |
| nearest ceiling | **price was 25% ABOVE a level tested 3×** |
| cadence phase | **MID_CYCLE** — not at a rhythm low |
| peak trajectory / trend | RISING / UP +22.5% |

Then: 5.66e-6 → 5.15e-6 over eight hours into its −6% stop.

**Why it did that:** STRIKE fires on `mom_h1 ≥ 3%` with a hardcoded 4%/5% target/stop and looks at **nothing else**. It is a momentum entry, and it bought the peak of a spike. An honest loss with a terrible entry — and the clearest possible argument for §7.

## 5 · THE SUNDAY TRADE — the sleeves had no calendar at all

`E ADAPTIVE STRIKER · IRM · $128.3100 → $128.3100` on a Sunday. The books have carried a market-closed gate for releases; the **sleeves had zero references to any calendar**, so the whole workshop could trade equities, metals and energy all weekend against Friday's close — fills a live broker would simply have queued to Monday and filled elsewhere.

Gated now (T118): **entries only**. Exits and marks keep working through a closed session, because a real desk still manages a position while the market is shut. Crypto is 24/7 and untouched. Verified on your tree right now: `crypto True · stock False · metal False · energy False`.

## 6 · ARE THE SLEEVES PRIORITISING? — you were half right, and the half matters

You asked whether limited slots get the *best* candidates or just the *first*. From the code:

| sleeve class | how slots are filled | prioritised? |
|---|---|---|
| conf-gate snipers | top decile of this cycle's confidence, sorted best-first | **yes** — by confidence |
| STRIKE slots | ranked by 1h momentum, strongest first | **yes** — by momentum only |
| plain MR sleeves | sorted by deepest dip | **yes** — by dip depth only |

So it is **not** "first to arrive." But every sleeve ranks on **one thin number**, and **none of them consult the graph.** That is the real answer to your question, and it leads directly to the next section.

## 7 · IS THE GRAPH ACTUALLY HELPING? — the honest answer, and the instrument to fix it

**`CHART_INTEL.json` — the graph brain computing peaks, troughs, floors, ceilings and trajectory — is read by the dashboard and by NOTHING in the selection path.** A grep of the engine finds zero references in the sleeves. The graph is a **display, not an input**.

Your words were: *"we feel like we have given so much attention to so many tools to watch a system simply not use them."* That is architecture, not mood. You were right.

**I did not quietly wire it in.** Bolting an unmeasured signal onto live selection is exactly how the last several regressions happened. Instead, new module `graph_decision_audit.py` (read-only, runs every cycle, panel on the dashboard) measures the coupling:

- For every closed trade it reconstructs the graph **as of the entry** — using only prints that existed then, so **no hindsight can leak in** (T120 proves this: a violent post-entry spike must not change the entry-time read).
- It buckets outcomes by **peak trajectory · trend · cadence phase · range position · floor support · ceiling overhead** and grades each: PREDICTIVE / NEUTRAL / TOO_EARLY.
- It states the coupling gap out loud, per feature: *read at entry?* → mostly **"NO — drawn, ignored."**

**An honesty note about my own first draft, because it is the exact failure mode that has cost you weeks.** My first version used n≥8 and duly reported four features as **PREDICTIVE** off nine trades with buckets of three. That is noise wearing a verdict. I raised the bar to **25 graded entries with ≥5 in each bucket compared**. It now honestly reads **TOO_EARLY across all six features** on your 9 closed trades, and says so.

When a feature earns PREDICTIVE over a real sample, **that** is the moment to gate entries on it — with a knob, a pre-registered kill and an A/B, never silently. The panel will tell you when, and name the feature.

## 8 · WHAT YOU COULD NOT SEE, NOW VISIBLE

- **Trade age** — your explicit ask. Open positions carry **held** and **price age**; a position on a stale print shows **⚠ stale** in amber (that is precisely the condition that made the PNUT fill). Closed trades carry **held**.
- **Real sub-penny prices** — SHIB rendered `$0.0000 → $0.0000` because the table was fixed at 4 decimals. Now `$0.00000566`. A price you cannot read is a price you cannot check.
- **Fill stamps** — `◉ capped −7.5%` when a limit was enforced, `⚠ gap 2.9h` when a fill crossed a hole in the tape, `px 22m` when the print used was aging.
- **PRICE_SOURCE_AUDIT.json** — every cycle, names any derived store whose "current price" disagrees with the tape. Your tree right now: **CLEAN, 798 store prices agree, 0 divergences, 74 names with no recent print** (those 74 are exactly where a stale fill used to be possible — now blocked).

## 9 · WORKFLOWS — verified correct

| lane | cron | runs `--live` | verdict |
|---|---|---|---|
| daily.yml | ✅ | ✅ | the **only** scheduled writer |
| selftest / verify_install | ✅ | ✗ | read-only, safe |
| weekly_backup | ✅ | ✗ | disjoint archive paths |
| hourly / analytics / backfill / venue / compact / cleanup | ✗ | ✗ | manual only — cannot race |

The one-writer law holds. Your Actions screenshot matches: `Daily Run #5148: Scheduled`, everything else manual or disabled.

## 10 · THE HONESTY AUDIT — does this behave like a live engine?

You asked whether the system works "exactly like it will when live trading platforms are plugged in."

**Closer than it has ever been, and specifically:** take-profits now behave like limit orders (cannot overfill), stops like market orders (wear slippage), entries cannot fill on stale prices, closed markets refuse entries, and gap-crossing fills are labelled. Those are the four places paper simulators habitually flatter themselves, and all four are now honest.

**Still not live-equivalent, stated plainly:** no order book depth or partial fills, no queue position, no venue rejections, no funding/borrow costs, and fees are modelled from venue tables rather than confirmed by real fills. `VENUE_SHADOW` (roadmap 10.0) is the item that closes the remaining gap.

## INSTALL (9 files, drag-and-drop, exact paths)

```
silmaril/execution/graph_decision_audit.py   (NEW)   silmaril/execution/strategy_lab_abcd.py
silmaril/execution/paper_sim.py                      silmaril/execution/price_truth.py
silmaril/cli.py                                      docs/index.html
scripts/quarantine_bad_fills.py              (NEW)   scripts/selftest_5_1.py
SILMARIL_7_1_4_RELEASE_REPORT.md             (root)
```

After install: hard-refresh the dashboard, then run `python scripts/quarantine_bad_fills.py docs/data --apply` (or let the next Daily Run land and read the two new panels). **No reset.**

On the first cycles expect: equity sleeves quiet until Monday 13:30 UTC · `px_age_min` and `held` appearing on new trades · `PRICE_SOURCE_AUDIT.json` reading CLEAN · the graph audit reading TOO_EARLY and counting upward.

## THE HONESTY CAVEAT

Two fabricated fills are now excluded, which means your realized P&L just got **worse and truer** — the energy book's headline win was partly one of them. With the windfalls removed, the remaining edge is small, fee-sensitive and unproven, and the 100-trade / 90-unbroken-day bar has not moved.

What changed is not the edge. It is that every corruption class you have hit — scale-blend, survivorship, session gaps, stale-price fills, weekend fills, fabricated limits — is now a rail with a test that reproduces the original failure. That is what makes a clean week possible for the first time, rather than hoped for.
