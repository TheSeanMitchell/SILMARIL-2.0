# SILMARIL — DAILY WORKSHEET v2
### Replaces the 40-section audit sheet. Six questions, ten minutes, and it ends with a decision — not a description.

---

## WHY v2 EXISTS (read once, then never again)

The v1 sheet had 40 sections across 7 tabs. It was thorough and it did not work, for three reasons:

1. **It asked you to be the sensor.** Forty `>>>` lines meant transcribing numbers a machine could read. You are the only one who can judge *"does this feel wrong?"* — everything else should fill itself in.
2. **It described, it did not decide.** A wall of 🟢/🟡 tells you the state of the world. It does not tell you what to *do*, and it lets a healthy-looking board hide a broken product — which happened: the battery read 111 pass / 0 fail while every chart link on the site was dead.
3. **It had no memory.** Each day started from zero, so nothing accumulated. There was no way to see "this is the fourth day metal has not traded."

v2 inverts all three. **The machine reports; you judge; the sheet ends in a decision.** Most of it is a single paste.

---

## THE DAILY LOOP (10 minutes)

```
  ┌─ 1. PASTE the auto-block (30 seconds)
  ├─ 2. Answer SIX questions (5 minutes)
  ├─ 3. Add anything that FELT wrong (2 minutes — this is the part only you can do)
  └─ 4. Get back: ONE decision, ONE fix, ONE thing to watch tomorrow
```

---

# ═══════ STEP 1 — THE AUTO-BLOCK (paste, don't transcribe) ═══════

Run this in Actions → **Daily Audit Block**, or locally:
```
python scripts/daily_block.py docs/data
```

It prints a compact block covering: books & equity · arming state per book · feed truth counts · price-source divergences · sleeve scoreboard with Δ-vs-null · vetoes by rail · promotion status · the river · graph→decision verdicts · tripwire count · the 90-day gate. **Paste it whole. Do not retype anything.**

```
>>> PASTE THE AUTO-BLOCK HERE
```

---

# ═══════ STEP 2 — THE SIX QUESTIONS ═══════

*These are the only things the machine cannot answer about itself.*

### Q1 — Did anything look FAKE today?
A price that can't be real, a chart that snaps, a win that felt too good, a number that contradicts another number.
```
>>> 
```
*(Why this is first: every serious problem in this project's history announced itself this way, and every one of them was real.)*

### Q2 — Did anything that used to work stop working?
A link, a panel, a book that traded yesterday and not today.
```
>>> 
```

### Q3 — What did the system REFUSE today, and do you agree with the refusals?
From `SLEEVE_VETOES.json` in the block: cooldowns, trajectory vetoes, closed markets, feed quarantines.
```
>>> 
```
*(A quiet day with good reasons is a healthy day. A quiet day with no reasons is a broken one.)*

### Q4 — Pick ONE trade and read its chart. Does the graph explain the outcome?
Open its ticker. Look at where we bought relative to floors, ceilings, range position and peak trajectory.
```
Trade picked:     >>> 
Graph said:       >>> 
Outcome:          >>> 
Does it explain?  >>> yes / no / partly
```
*(This is the heart of v2. Over weeks it is how you learn whether the graph deserves to trade.)*

### Q5 — What is the single most annoying thing about the system right now?
Not the most broken — the most *annoying*. Friction is where the next real bug is hiding.
```
>>> 
```

### Q6 — Is there anything you are avoiding looking at?
```
>>> 
```

---

# ═══════ STEP 3 — THE STANDING FRAME (the AI reads this; do not delete) ═══════

```
You are auditing SILMARIL from the operator's daily worksheet. Rules:

- The auto-block is the data. Do not ask the operator to transcribe more of it.
- Answer the six questions FIRST, in order, briefly. Their answers outrank the block:
  if the operator says something looked fake, investigate it before anything else, with
  receipts from the repo — the operator's eye has caught every serious bug in this project's
  history, several of which passed a fully green tripwire battery.
- Distinguish, always and explicitly:
    QUIET BY CORRECT DESIGN  (arming gate, cooldown, closed market, no qualifying dip,
                              feed quarantined, maturity gate)
    ACTUALLY BROKEN          (stale stores, panels reading dead sources, zero output where
                              output is due, a rail that did not fire when it should have)
- Realized fee-paid P&L is the only score. Open marks are unrealized — say so.
- Δ-vs-null or it did not happen.
- Never claim edge the numbers do not show. One honesty caveat maximum.
- End with EXACTLY this, and nothing more:

    DECISION:  reset / no reset  (default: NO RESET — say what would have to be true to change it)
    FIX TODAY: one thing, specific enough to act on, with the file it lives in
    WATCH:     one number, and what value tomorrow would mean trouble
    STREAK:    what is now on its Nth consecutive day (trading, quiet, red, unpromoted)

- If nothing warrants a fix, say so. "Nothing today; keep collecting" is a valid, good answer
  and is often the correct one. Manufacturing work is how a system gets churned instead of run.
```

---

# ═══════ STEP 4 — THE STREAK LOG (the memory v1 never had) ═══════

*One line per day. Append; never rewrite. This is the only part you keep between days, and after two weeks it will tell you more than any single day's audit.*

| date | closes today | Δ-vs-null | armed books | vetoes | verdict in one word |
|---|---|---|---|---|---|
| 2026-07-26 | | | | | |
| | | | | | |

**Rules for the log:** if a cell would be a guess, leave it blank. A blank is data; an invented number is not.

---

# ═══════ THE WEEKLY QUESTION (Sundays only) ═══════

Once a week, instead of Q1–Q6, ask this one:

```
Looking at the STREAK LOG for the past seven days: what has this system PROVEN, what has it
DISPROVEN, and what is it still merely HOPING? Answer in three sentences. Then: has the
100-trade / 90-day gate moved closer, stood still, or reset — and why?
```

*Seven days of streak log will answer that better than any single day's panel sweep.*

---

*Worksheet v2 · replaces the 40-section v1 · the block does the reporting, you do the judging, and the day ends in a decision. If a section here ever becomes something the machine could fill in, move it into the auto-block and delete it from here — this sheet should get shorter over time, never longer.*
