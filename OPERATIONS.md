# SILMARIL — OPERATIONS MANUAL
### Every workflow, what it does, how often it should run, and exactly how to reset. Read once; keep it open on reset day.

---

## PART 0 — THE THIRTY-SECOND VERSION

**You should have exactly four workflows on a schedule and nothing else.** Everything else is a button you press when you want it.

| workflow | schedule | writes? | what it is |
|---|---|---|---|
| **Daily Run** | every 10 min | **YES** | the engine. The only scheduled thing that touches money. |
| **Selftest** | 03:45 UTC daily | no | 127 tripwires. Read-only. |
| **Verify Install** | Mon 04:15 UTC | no | confirms the deploy matches the release. Read-only. |
| **Weekly Backup** | Sun 00:00 UTC | archive only | compressed history snapshot. |

If you ever see a **fifth** thing running on a timer, that is a bug — tell me.

---

## PART 1 — HOW TO RESET (the whole thing, step by step)

**Do this only when you want to restart the paper money.** It does *not* delete your price history — that is the part that takes weeks to accumulate, and it survives every standard reset.

### Step 1 — Install the current release
Drag-and-drop the ZIP contents at their exact paths, as always. Commit.

### Step 2 — Let one Daily Run finish
**Actions → Daily Run → Run workflow.** Wait for the green tick. This proves the install is healthy *before* you wipe anything. If it fails, stop and tell me — do not reset on top of a broken install.

### Step 3 — Run Selftest
**Actions → Selftest → Run workflow.** You want **127 pass · 0 fail**. If anything is red, stop.

### Step 4 — Reset
**Actions → Reset Internal Clean → Run workflow.**
- `confirm`: type **`WIPE`**
- `wipe_mode`: **`standard`**

**Never type `GENESIS-BURN-THE-LIBRARY` unless you truly intend to destroy your price history.** Standard is what you want, always.

The log will now tell you in plain English exactly what happened:

```
WHAT THIS RESET DID
  RESTARTED AT $10,000: the four books, all 20 sleeves each, the Master,
                        every open position and closed-trade record
  KEPT:                 price_samples.json (20.8 MB), ccxt_samples.json (8.4 MB),
                        fingerprints, chart history, every knob, and the permanent
                        ledgers (harvests, repairs, key migrations)
  REBUILDS ITSELF:      GRAPH_READ, PRICE_TRUTH, WARM_START, SLEEVE_VETOES,
                        INSPECTOR, HARVEST — on the next Daily Run, nothing to do
```

### Step 5 — Run one Daily Run
**Actions → Daily Run → Run workflow.** Then look at the log. You should see, in this order:

```
price truth: 6xx/1075 feeds tradeable
warm start: stock→A, crypto→A, energy→A, metal→A     <- each book gets an opening sleeve
fingerprints: 4xx name(s) excluded — feed not trustworthy
```

### Step 6 — Confirm it woke up
Open the dashboard. Within one cycle you should see **sleeves holding positions** (I measured 45 crypto positions in the first cycle after reset). The **four funded books will be quiet** — that is the pyramid law: a book cannot trade until one of its sleeves earns 3 real closed trades. **Quiet books after a reset are correct, not broken.**

### That is the whole reset. Six steps, about fifteen minutes, mostly waiting.

---

## PART 2 — WHAT EACH WORKFLOW IS FOR

### The four that run themselves

**Daily Run** — `*/10 * * * *`
The engine. One scheduled writer, by law. Internally it does different work depending on the clock, so you do not need separate lanes:

| when | what it does |
|---|---|
| every 10 min | FAST pulse — fetch prices, mark positions, trade |
| top of each hour | FULL pass — brains, fingerprints, outside-venue overlay |
| 07 / 11 / 23 UTC | deep analytics suite + data diet |
| 08 UTC | nightly universe backfill |
| 09 UTC | venue listings refresh |

**Selftest** — `45 3 * * *` · **Verify Install** — `15 4 * * 1` · **Weekly Backup** — `0 0 * * 0`
Read-only or archive-only. They cannot interfere with the engine.

### The buttons (manual only — press when you want them)

| workflow | when you would press it |
|---|---|
| **Reset Internal Clean** | restarting the paper money (Part 1) |
| **Maintenance Toolbox** | one-time repairs and reports (Part 3) |
| Deep Analytics | you want the heavy suite now instead of waiting for 07/11/23 UTC |
| Backfill Universe | you want history depth refreshed now |
| Venue Universe | you want exchange listings refreshed now |
| Compact History | the repo is getting large |
| Hourly Brain | **retired** — folded into Daily Run. Pressing it just prints a notice. |

---

## PART 3 — THE MAINTENANCE TOOLBOX

**Actions → Maintenance Toolbox → Run workflow.** Pick a tool from the dropdown. **Everything is dry-run by default** — nothing is written or committed unless you set `apply` to `true`.

| tool | what it does | needs apply? |
|---|---|---|
| `inspector` | run the pattern-recognition audit now | no (read-only) |
| `daily_block` | print the auto-block for your daily worksheet | no |
| `click_path_check` | prove every chart link on the site opens | no |
| `repair_capital_leak` | restore paper capital deducted for positions never created | yes |
| `quarantine_bad_fills` | exclude fabricated limit fills from the learning river | yes |
| `harvest_now` | bank realized profit into the non-spendable vault | yes |
| `manual_sweep` | force the SWEEP switch on a strong market day | yes |
| `backfill_history` | jumpstart fingerprints & charts from stored history | yes |
| `train_from_backtest` | ingest backtest outcomes into agent training | yes |

**The habit worth forming:** run `inspector` (dry, read-only) whenever something looks wrong. Its verdict line is either `CLEAN` or `ATTENTION — N critical/high findings`, and each finding names the evidence and the action.

---

## PART 4 — THE SCHEDULE YOU SHOULD SEE

Open **Actions** on any normal day. This is what healthy looks like:

```
Daily Run                 ~6 runs per hour, every hour, green
Daily Run                 one longer run at the top of each hour (the FULL pass)
Selftest                  once, ~03:45 UTC, green, "127 pass · 0 fail"
Verify Install            once a week, Monday ~04:15 UTC, green
Weekly Backup             once a week, Sunday ~00:00 UTC, green
pages-build-deployment    after each push — that is GitHub publishing the dashboard
```

**Red flags, in order of seriousness:**
1. **Two Daily Runs overlapping** — should be impossible; the serial lane lock prevents it. If you see it, tell me.
2. **A workflow you did not press running on a timer** — a cron has crept back in.
3. **Daily Run failing repeatedly** — read the log; the first error line is usually the whole story.
4. **Daily Run green but the dashboard clock is stale** — the push step failed; check the last run's final step.

---

## PART 5 — YOUR DAILY LOOP (five minutes)

1. Dashboard → does the **engine updated** clock read minutes, not hours?
2. **Actions → Maintenance Toolbox → `inspector`** (dry). `CLEAN` or read the findings.
3. Look at **realized**, never the headline. `INSPECTOR.json` and the sleeve rows both publish `realized_pct` beside `return_pct`.
4. Anything that looks fake — tell me, with the symbol. Your eye has caught every serious bug in this project; the instruments exist to serve it, not replace it.

---

## PART 6 — HOW THIS GETS SIMPLER FROM HERE

You asked how to make it truly automated. Honestly: **it already is, and the complexity you feel is not in the running — it is in the watching.** The engine needs nothing from you. What has needed you is verifying that it is not lying, and that is the part now carried by instruments instead of by your attention:

- **the one-writer law** — one scheduled workflow, so state can never be corrupted by a race
- **the inspector** — reads the record every cycle and tells you what to look at
- **the capital invariant** — money cannot leave a book without arriving somewhere
- **the realized/unrealized split** — published on every row, so no headline can flatter
- **T131** — every script you might need is reachable from the Actions tab

**What I would delete when you are ready:** `cleanup_5_11`, `integrity_backfill`, `remap_keys` and `compact_history` are one-time migrations from older releases and will never be pressed again. They are harmless but they clutter the Actions list. Say the word and I will remove them so the menu shows only things you would actually use.

---

*Operations manual · current as of release 7.2.5 · four scheduled workflows, one toolbox, six-step reset.*
