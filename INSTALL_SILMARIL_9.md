# SILMARIL 9 — THE LADDER — install (about 15 minutes, drag and drop)

## UPDATE 1 (8 Nov 2026, evening) — the headline test, watch-only

Already installed SILMARIL 9? Upload only these six files, replacing what is there:

| from this package | into the repo |
|---|---|
| `ladder/headlines.py` (new), `ladder/cli.py`, `ladder/report.py` | `ladder/` |
| `scripts/test_ladder.py` | `scripts/` |
| `REGISTRATION_HEADLINES.md` (new) | repo root |
| `.github/workflows/ladder.yml` | `.github/workflows/` |

**Do not upload anything from `docs/`** — the repo's copies are newer (the nightly run
writes them). Then Actions → SILMARIL 9 - The Ladder (daily) → Run workflow. The page gains
a "Headline test — watch-only" section. It never trades; its first weekly call comes after
a full week of headlines. The trading fingerprint stays `d6ebfac647c082b8`.

---

Nothing in here deletes anything. The old engine, Steward and every data file stay in the
repo as the archive.

---

## PART 0 — already done

GitHub shows **Daily Run (single efficient cadence)** as *disabled* since 8 Nov 2026. Good:
that is the old engine. Leave it disabled forever.

## PART 1 — stop the outside alarm clock (5 minutes)

The old engine was being started every 10 minutes by an outside cron service (cron-job.org
or similar) using a GitHub token with no expiry. It is still firing at a disabled workflow.

1. Log in to that cron service and **delete or pause every job** that posts to
   `.../SILMARIL-2.0/actions/workflows/<something>.yml/dispatches`.
2. GitHub → your avatar → Settings → Developer settings → Fine-grained personal access
   tokens → **revoke `silmaril-cron`**. Nothing in SILMARIL 9 needs it.

## PART 2 — upload (5 minutes)

From this folder into the repo at github.com/TheSeanMitchell/SILMARIL-2.0
(Add file → Upload files → drag → Commit changes). Folders keep their place:

| from this package | into the repo |
|---|---|
| `ladder/` (whole folder, 9 files) | repo root |
| `scripts/test_ladder.py` | `scripts/` |
| `REGISTRATION_9.md` and `INSTALL_SILMARIL_9.md` | repo root |
| `docs/index.html` | `docs/` — **replaces the old main page** |
| `docs/silmaril7_archive.html` | `docs/` — the old main page, kept under a new name |
| `docs/data/ladder_prices.json`, `ladder_results.json`, `ladder_record.json`, `ladder_ledger.jsonl` | `docs/data/` |
| `.github/workflows/ladder.yml` | `.github/workflows/` (open that folder on GitHub first, then upload) |

## PART 3 — first run (2 minutes)

Actions → **SILMARIL 9 - The Ladder (daily)** → Run workflow. A green check means:
the 14 tests passed, prices were fetched, the page was rebuilt and saved.

If it is red, the run says why at the top of its page. A red run is the system working:
the old engine hid about 3,400 failed saves behind green checks; this one cannot.

From then on it runs by itself every night at 02:17 UTC. The main page,
<https://theseanmitchell.github.io/SILMARIL-2.0/>, now shows the ladder.

## PART 4 — switch off what is left of the old system (2 minutes)

Actions → click each one → the **⋯** menu → **Disable workflow**:

- **STEWARD (the one lane)** — only after the ladder's first green run. Its page stays at
  `/steward.html` as a frozen record. SILMARIL 9 carries its idea forward as the MOMENTUM
  sleeve, with its bugs fixed.
- **Weekly Learning Backup** — it backs up the old engine's learning files, which no longer change.

Keep **pages-build-deployment** (that publishes the website).

## PART 5 — never do this

**Never edit `docs/data/history.json`.** It is 99.3 MB, a hair under GitHub's 100 MB
file limit. That file going over the limit is what silently stopped the old engine's
saves on 8 October. If you ever want the repo small and clean, the safe way is a new
repository with only the SILMARIL 9 files. Ask before doing it.

---

## How to read the page

- **Top banner.** Green: fresh data, record intact. Yellow/red: stale prices, or DRIFT
  (a recorded number changed after the fact). Both fix themselves or tell you exactly what is wrong.
- **Master account.** What it is worth, and the difference against simply holding all 8
  assets and against holding SPY. Those differences are the only numbers that say whether
  the rules are worth anything.
- **Category accounts.** Each against its own hold twin, with what each sleeve is doing.
- **Sixteen sleeves.** The replay record of every rule against its HOLD twin.
- **History replay.** Labelled "context, not proof". It is what the same rules did on past
  prices; the forward record from 9 Nov 2026 on is the experiment.

## What to expect

From the replay: about market-like growth with smaller worst drops, not more money than
holding. Over a few months the forward numbers will mostly reflect what the markets did.
A real verdict needs 104 weeks; the page counts toward it and will not call it early.
