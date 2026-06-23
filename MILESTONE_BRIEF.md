# SILMARIL 2.0 — MILESTONE BRIEF: answers + plan + what I changed

You asked a lot of deep questions. Here are straight answers, then the
plan for the four big priorities, then what I actually changed this round.

═══════════════════════════════════════════════════════════════════
## YOUR QUESTIONS — ANSWERED
═══════════════════════════════════════════════════════════════════

### "Is crypto broken? No orders since 4:04 PM."
NOT broken. There's a buy at 04:03 AM UTC, and Account #3 is **90% deployed**
($8,797 in 6 positions, only $931 cash). Equity **$10,448, up 4.5%**. Orders
slowed because it's nearly out of cash — it's FULL, not stuck. That's correct
behavior for "full aggression, no reserve."

### "It hit +5% ($500) then fell back to +3.7% — why didn't it harvest?"
You found the real gap. The crypto account has **0 sells** — it only buys and
holds on conviction. There is NO daily profit-taking. The sell-side barely
exists. You are 100% right that the sell-side matters as much as the buy-side,
and right now it's missing. This is THE thing to fix for stocks+valuables.

### "Will low performers learn from good ones via breeding / teaching?"
Honest answer in two parts:
  - BREEDING: yes, it's built — fitness = realized profit, strong agents
    breed, weak ones get benched. But it needs WEEKS of clean records to
    visibly move the population. It will NOT fix a structural problem fast.
  - TEACHING (agents copying good agents' live behavior): NOT really built.
    Propagation is by evolution (breeding + senate), not direct instruction.
    Adding real "teaching" is a substantial new system — possible, but it's
    a future build, not a switch.

### "Is the stock side suffering because of learning, or lack of it?"
LACK of it — but more precisely, it's not a learning problem at all right now.
Stocks underperform because (a) the leaned-in news strategy genuinely favors
crypto's momentum, and (b) your own theory may be right that heavily-covered
stocks underperform. Learning won't fix that quickly; a STRATEGY change for
the stock accounts will. The migration's old "never learn its way out" fear
does NOT apply here — that was about corrupted data poisoning the loop, which
the clean v2 restart fixed. The current stock weakness is strategy, not rot.

### "Why is crypto so good and stocks so bad?"
The hotlist + momentum-squared weighting is PERFECT for crypto (24/7, trends
hard, momentum persists). Stocks are choppier, news-driven, and mean-revert
more — the same aggressive momentum model whipsaws them. Different asset,
different optimal strategy. Which is exactly why your two-account idea is right.

═══════════════════════════════════════════════════════════════════
## THE HARVEST QUESTION — your $100/$300/$500 daily-goal idea
═══════════════════════════════════════════════════════════════════
This is a genuinely good instinct and the infrastructure is HALF-built:
the accounts already have per-position profit-take tiers (Acct#1 3%, Acct#2
4%, Acct#3 6%) AND a clock-aware harvest gate that waits for a name's typical
daily-HIGH window before selling (so it doesn't dump at the floor).

What's MISSING is the ACCOUNT-LEVEL daily goal you described: "the whole
account made $500 today — lock it in." I've built that as an experiment in
**Account #2 (HARVEST_3)** exactly as you asked (see below), leaving Account
#1 pure-stock and Account #3 (crypto) UNTOUCHED per your instruction.

The "get ahead of the predictable selloff, not react to it" idea: the
clock-aware gate already does a version of this (harvest in the high window).
Tying it to the daily macro fingerprint is a strong future enhancement.

═══════════════════════════════════════════════════════════════════
## THE FOUR BIG PRIORITIES — plan
═══════════════════════════════════════════════════════════════════

### 1) FUTUREPROOFING
- All deliverables are whole-file, version-tagged, drag-and-drop. Good.
- RECOMMEND: a VERSION file + a one-page "how to run / restore" runbook in
  the repo so a future you (or a new laptop) can rebuild in minutes.
- The backfill + clean-restart pattern means data loss is recoverable.

### 2) SECURITY / PRIVATIZATION (no interference or counterfeiting)
- Make the repo PRIVATE (Settings → change visibility). The engine code,
  the agent logic, the secrets-config — none of it should be public.
- Keep secrets ONLY in GitHub Actions secrets (never in code/commits). Done.
- The dashboard can stay public WITHOUT exposing the engine (see #4).

### 3) HARDENING (decay, storage, security)
- STORAGE: the compaction workflow is your storage cure — see the dedicated
  safety note below. Run weekly, delete old tags after.
- DECAY: the "never delete, quarantine stale" design already resists data rot.
- RECOMMEND a weekly backup tag (you're already backing up manually).

### 4) PUBLIC DISPLAY without exposing the engine  ← the big one
The clean architecture: **split the dashboard from the engine.**
  - The engine repo (private) computes everything and writes JSON.
  - A SEPARATE public repo holds ONLY the dashboard HTML + a COPY of the
    display JSON (no code, no secrets, no agent logic, no Alpaca keys).
  - A workflow in the private repo pushes ONLY docs/ (the safe display
    files + data) to the public repo each run.
  - Result: you can stream/share the public dashboard URL; nobody can see
    or steal the engine, the strategy code, or the keys.
This is a real build (a sync workflow + a second repo). It's the right way
to "wrap for public display without leading back to the engine." I can build
the sync workflow when you're ready — it's ~1 workflow file + a deploy token.

### THE BACKPACKER SETUP (run it from a laptop/phone abroad)
- Everything already runs in GitHub's cloud on a cron — your laptop/phone
  doesn't compute anything; it just VIEWS the dashboard. That's already
  mobile-proof: close the laptop, it keeps trading.
- To operate from a phone: the GitHub mobile app can trigger workflows and
  read backups; the dashboard is a normal mobile web page.
- The ONLY recurring chore is weekly compaction + tag cleanup (2 min on
  phone via GitHub web). Everything else is autonomous.

═══════════════════════════════════════════════════════════════════
## COMPACT GIT HISTORY — is it safe? (you asked before using it)
═══════════════════════════════════════════════════════════════════
SAFE to use. It does NOT corrupt or lose data/learning/agents — those live
in the current JSON files, which it snapshots intact. It only collapses the
git COMMIT history (the rewind log nothing reads at runtime). It tags the old
history as a backup BEFORE rewriting, so nothing is destroyed.
  - You do NOT need to rebuild anything first. It's ready.
  - CADENCE: weekly (the file says monthly, but at your churn weekly is right).
  - AFTER each run: delete the OLDER backup tags at /tags (keep newest 1-2),
    or the space creeps back (the tags hold the old bloat).
  - Don't run it twice the same day (tag-name collision — harmless error).

═══════════════════════════════════════════════════════════════════
## WHICH WORKFLOWS TO ENABLE NOW
═══════════════════════════════════════════════════════════════════
Since it's working, KEEP IT SIMPLE. You only need:
  - daily.yml — the main engine run (your cron triggers this). KEEP ON.
  - compact_history.yml — manual, weekly. Leave it manual.
  - backfill_history.yml — manual, run once to seed charts. Then ignore.
DO NOT enable the reset/wipe workflows (full_reset, reset_10k, wipe_*) —
those are dangerous one-shots; leave them disabled so they can't fire by
accident. The senate/evolution/learning runs (senate.yml, reflection.yml,
train_from_backtest.yml) can stay OFF for now — they're for when you want to
actively evolve the population; the core trading doesn't need them. Turn
senate.yml on later once you have weeks of clean agent records and WANT
elections/breeding to start shaping the roster.

═══════════════════════════════════════════════════════════════════
## WHAT I CHANGED THIS ROUND
═══════════════════════════════════════════════════════════════════
1. docs/index.html:
   - Header now reads SILMARIL 2.0 (title + brand).
   - "Going into [day]" is now a full daily-coffee briefing: every position
     with its current value, open P&L, and move-since-last-read (▲▼), plus
     account-level equity and P&L totals. The day auto-rolls to the next
     session (computed in ET) — tomorrow it will say the next weekday.
2. Account #2 (HARVEST_3) daily-goal harvest — see the separate file
   harvest_daily_goal.py and how it plugs in. Account #1 stays pure stock;
   Account #3 (crypto) UNTOUCHED per your instruction.

Everything else (crypto engine, agents, scoring) UNCHANGED.
