# STEWARD — SILMARIL 8.0 — the one install

This is the final installation. Not because nothing will ever change, but because
**change itself now has a cost you can see**: every parameter is frozen behind a
registration hash (`cd5feead39c46f3b`), and any edit breaks the build loudly and
restarts the clock. The system is designed to be left alone for a quarter at a
time. That is a feature you asked for, and it is enforced by code, not promises.

**15 files replace 374 modules.** Same repo, same GitHub Pages site, same free plan.

---

## PART 1 — Upload (about ten minutes, drag and drop as always)

From this package folder into your repo at github.com:

1. **`steward/`** — upload the whole folder to the repo root (Add file → Upload
   files → drag the `steward` folder in). 10 files.
2. **`scripts/test_steward.py`** — into the existing `scripts/` folder.
3. **`REGISTRATION.md`** — into the repo root.
4. **`.github/workflows/steward.yml`** — into `.github/workflows/`.
5. Commit.

## PART 2 — Turn off the old engine (two minutes, no deletions yet)

Repo → **Actions** tab → click each workflow in the left sidebar → the **⋯** menu,
top right → **Disable workflow**. Disable these twelve:

- Daily Run (single efficient cadence)  ← the important one
- deep-analytics
- Backfill Universe (full coin + 1y fing…)
- Venue Universe (venue truth, daily)
- selftest (regression battery)
- Maintenance Toolbox (one-time rep…)
- Remap Keys (fix crypto graphs)
- integrity backfill (one-shot, 2026-07…)
- cleanup 5.11 (attic superseded docs…)
- **Reset Internal Clean (post-fix wipe)** ← disable and never look back
- Hourly Brain (RETIRED lane — folde…)
- verify-install

**Keep enabled:** Weekly Learning Backup, Compact Git History, pages-build-deployment.

Disabling is one click and fully reversible — nothing is lost, the old dashboards
simply stop updating and stand as the archive.

## PART 3 — First run (one minute)

Actions → **STEWARD (the one lane)** → Run workflow. The first run:

- pulls 2 years of daily history for 28 symbols,
- runs the regression battery (17 checks — the fee law, the no-lookahead law, the
  registration hash — the run refuses to trade if any fail),
- sets the **epoch** (the clock that never resets),
- queues the first positions (they fill at the next day's close — t+1, always),
- runs the design-check backtest over the warmup tape (on the 2024–2026 tape it
  showed: crypto +$2,663 vs hold in a bear, metal's kill locking in +$11,050,
  energy −$5,750 and killed — the rules all fire; treat the total as context),
- publishes the new page.

Your new homepage: **`https://theseanmitchell.github.io/SILMARIL-2.0/steward.html`**
Bookmark it. It updates once a day after the US close.

After that: **you do not need to do anything for 91 days.** Day 91 is the first
checkpoint (an execution audit the page runs itself). The verdict on the whole
experiment is at week 104, and the page counts down to it.

## PART 4 — Delete-later list (whenever you feel ready — nothing depends on it)

After steward has run cleanly for a couple of weeks:

- The 12 disabled workflow files in `.github/workflows/` can be deleted.
- `silmaril/` (348 modules) can be moved to `attic/silmaril7_RETIRED/`.
- Keep forever: `docs/data/` (the frozen archive), `scripts/recompute_fees.py`,
  `scripts/test_fee_law.py`, `REGISTRATION.md`, and the audit documents.

## Optional (nice, not needed)

- Repo → Settings → Secrets → Actions → add `SEC_USER_AGENT_EMAIL` with your real
  email — the SEC asks politely that EDGAR requests carry contact info. Without it
  the FORM4 shadow still runs with a placeholder.

---

## How to read the new page (this part matters)

- **The big number per book is NOT equity.** It is delta-vs-hold: dollars gained
  or lost against simply buying and holding that book's benchmark. Positive means
  the rotation is earning its keep. Negative means doing nothing was better —
  which the page will say to your face, because the last dashboard never did.
- **Expect deltas near zero for months.** A monthly strategy makes ~12 decisions
  a year. There is nothing to see weekly, and that is by design.
- **A KILLED light is the system working**, not breaking: a pre-registered limit
  was hit, the book liquidated itself, and the result stands recorded.
- The **shadows table** is your old ideas on trial — the news system (as the
  NEWSFADE hypothesis it honestly earned) and Form 4 insider flow — graded with
  real pass/kill bars, never funded. The congress-trades idea is registered and
  waiting for a feed, so the hypothesis officially predates the data.

## What this will and will not do (from REGISTRATION.md, so it is in writing)

Central expectation **6–10%/yr** ($50–85/month on $10k), range −5% to +15%.
**P(beat buy-and-hold over 2 years): 40–55%** — in a straight bull market the hold
twins will likely win, and the page will show it. **P($1,000/month): ~0.** The
honest reasons are in REGISTRATION.md §6. Worst case is a drawdown kill — per class:
crypto −40%, everything else −30% — which on $10k paper is $3,000–4,000 locked in as a
recorded negative result. On the 18-month design tape, three of five books ended
KILLED — expect kills; they are results, not malfunctions. This experiment answers
a question; it does not pay rent.

— built and verified 19 August 2026 · registration cd5feead39c46f3b
