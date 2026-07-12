# CRON SETUP — eternal token + external scheduling for every lane (5.1B)

## 1 · The token that never expires (one-time, ~2 minutes)
GitHub → Settings (your avatar) → Developer settings → **Fine-grained personal access tokens** → Generate new token:
- Token name: `silmaril-cron` · **Expiration: No expiration**
- Resource owner: your account · Repository access: **Only select repositories → SILMARIL-2.0**
- Permissions → Repository permissions → **Actions: Read and write** (nothing else needed)
Generate, copy once, store in your cron site's secret field. Revoke/rotate any time from the same page.

## 2 · The dispatch endpoints (one per lane)
All are `POST https://api.github.com/repos/<YOUR_USER>/SILMARIL-2.0/actions/workflows/<FILE>/dispatches`
Headers: `Authorization: Bearer <TOKEN>` · `Accept: application/vnd.github+json`
Body: `{"ref":"main"}`

| Lane | FILE | Recommended external schedule (UTC) |
|---|---|---|
| PULSE | `daily.yml` | every 10 min (`*/10`) — this is the heartbeat |
| HOURLY | `hourly.yml` | `7 * * * *` |
| DEEP | `analytics.yml` | `20 7 * * *` · `20 11 * * *` · `20 23 * * *` |
| BACKFILL | `backfill_universe.yml` | `10 8 * * *` |
| WEEKLY | `weekly_backup.yml` | `0 0 * * 0` |
| SELFTEST | `selftest.yml` | `45 3 * * 1` |

(cron-job.org, GitHub-external runners, or any scheduler that can POST with headers works. Mirror the stagger — it exists to dodge GitHub's :00 congestion and the NYSE open.)

## 3 · Flip the switch
Repo → Settings → Secrets and variables → **Variables** → New repository variable:
`EXTERNAL_CRON_ONLY = true`
Internal timers now no-op (each shows a skipped run — that's correct). Reversible instantly.

## 4 · Sanity check
After the first external day: Actions tab shows runs arriving from `workflow_dispatch` on the schedule above; `STORE_CONTRACTS` stays ALL GREEN; the ENGINE PULSE cadence line stays ≤ ~12 min median. If any lane goes quiet, the wiring audit names it.
