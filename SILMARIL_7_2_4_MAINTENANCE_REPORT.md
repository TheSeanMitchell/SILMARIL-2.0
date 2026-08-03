# SILMARIL 7.2.4 — "THE SCRIPTS YOU COULD NOT RUN"
### You were right. I shipped four scripts and told you to run commands you have no way to run.

**Battery: 127/127** on the full tree, a reset tree, and a simulated install. New tripwire T131 makes this class of failure impossible to repeat.

---

## THE MISTAKE

You deploy by drag-and-drop through the GitHub web UI. No terminal, no local checkout. I know that — it is in every release report I write. And yet across several releases I shipped a script and wrote *"run this once"*:

| script | what it does | workflow |
|---|---|---|
| `repair_capital_leak.py` | restores $26,130 of leaked paper capital | **none** |
| `quarantine_bad_fills.py` | excludes the fabricated PNUT/BRENT fills | **none** |
| `daily_block.py` | the auto-block the daily worksheet is built around | **none** |
| `click_path_check.js` | proves every chart link actually opens | **none** |

Four scripts, zero workflows. The instructions weren't inconvenient — they were **impossible to follow**, which is why $26,130 sat unrepaired for two days while I kept telling you to run a command.

**And when I wrote the test to catch it, it found fourteen more.** Including `backfill_history.py` and `manual_sweep.py`, both of which you have asked me about directly.

## THE FIX — `.github/workflows/maintenance.yml`

One workflow, a dropdown, nine tools. **Actions → Maintenance Toolbox → Run workflow.**

```
repair_capital_leak     restore paper capital deducted for positions never created
quarantine_bad_fills    exclude fabricated limit fills from the learning river
harvest_now             bank realized profit into the non-spendable vault
daily_block             print the auto-block for the daily worksheet     (read-only)
click_path_check        prove every chart link opens                     (read-only)
inspector               run the pattern-recognition audit now            (read-only)
manual_sweep            force the SWEEP switch on a strong market day
backfill_history        jumpstart fingerprints & charts from stored history
train_from_backtest     ingest backtest outcomes into agent training
```

**Safe by default.** Every mutating tool runs **DRY RUN** unless you set `apply` to `true`, and nothing is committed on a dry run. Read-only tools ignore the flag. It carries the same serial lane lock as your other workflows, so it can never overlap a Daily Run, and it has no cron — it only ever runs when you press the button.

## HOW TO REPAIR YOUR $26,130

1. Install this ZIP (drag-and-drop as usual — `maintenance.yml` goes in `.github/workflows/`)
2. **Actions → Maintenance Toolbox → Run workflow**
3. tool: `repair_capital_leak`, apply: **`false`** → read the log, confirm the three books it names
4. Run it again with apply: **`true`**

Dry run against your current tree, so you know what to expect:

```
crypto:R    missing $6,712.38    cash 62.68 -> 6,775.06
crypto:S    missing $9,567.64    cash 11.46 -> 9,579.10
crypto:T    missing $9,850.36    cash 141.65 -> 9,992.01
books needing repair: 3   total restored: $26,130.38
```

Trade history is not touched — only the phantom deductions are undone, a `.pre_repair` backup is written first, and every repair is journaled to `CAPITAL_REPAIR.jsonl`.

## THE TRIPWIRE — T131

> **If a script exists for you to run, it must be reachable from the Actions tab.**

T131 walks `scripts/` and fails the battery if any operator-facing script has no workflow. The eleven genuinely dead ones (one-time migrations from superseded releases, already applied) are listed explicitly **with the reason each is excluded** — because a silent exclusion list is exactly how the original gap hid. It also asserts the toolbox is manual-only, dry-run by default, and commits only when applied.

**A new script with no home now fails the battery instead of failing silently in a report footnote.**

---

## INSTALL (3 files + report)

```
.github/workflows/maintenance.yml   (NEW)
scripts/selftest_5_1.py                    (adds T131)
SILMARIL_7_2_4_MAINTENANCE_REPORT.md
```

*(If you have not yet installed 7.2.3, install that ZIP first — it contains `harvest.py`, the arm fix and `repair_capital_leak.py` itself. This one makes them runnable.)*

## THE HONESTY CAVEAT

This release adds no capability. It makes capability you already paid for actually reachable, which it should have been on the day each script shipped.

The pattern is worth naming because it is the same one as the code bugs: **the parts were all correct and the wiring between them was missing.** The graph never reached decisions; the readers never reached candidates; cash never reached a position; and scripts never reached the operator. Four instances of one failure mode. T131 closes the fourth.
