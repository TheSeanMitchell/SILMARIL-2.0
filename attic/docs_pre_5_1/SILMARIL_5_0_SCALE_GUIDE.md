# SILMARIL 5.0 — SCALE & HOSTING GUIDE
### "How do we run this faster, harder, and more accurately than GitHub Actions allows?"
### A staged migration you can do in the order written, stopping at any rung. Nothing here is required for 5.0 to work — the installer runs today on Actions. This is the runway to the next height.

---

## THE HONEST FRAME FIRST

GitHub Actions gave you something rare for $0: a deterministic, publicly-auditable engine with a
free dashboard. It also imposed the exact ceiling you have hit:

- **Cadence is coarse and jittery.** Cron is best-effort (often minutes late) and the practical
  floor is ~5 min even before a job's own runtime. The 5.0 lane split gets you a clean ~10-minute
  pulse; it cannot get you a true 1-minute loop.
- **Every cycle is cold.** Fresh checkout, fresh `pip install`, 30 MB of JSON parsed from disk,
  commit, push. Most wall-clock time is overhead, not thinking.
- **State lives in git.** `price_samples.json` is already ~30 MB; the repo is ~205 MB. Git was
  never meant to be a time-series database, and every write is a full-file commit.

The single highest-leverage change is **decoupling the three concerns git currently fuses**:
compute, state, and presentation. Below, each rung separates one more of them.

---

## RUNG 1 — LIFT COMPUTE ONTO ONE SMALL VPS (biggest single win, ~$5–10/mo)

A single always-on box removes the cold-start tax and unlocks real cadence.

- **Box:** Hetzner CX22 (~€4/mo) or DigitalOcean/Vultr $6 droplet. 2 vCPU / 4 GB is plenty; the
  engine is I/O- and logic-bound, not CPU-bound.
- **Cadence:** replace the Actions cron with **systemd timers** (preferred — journald logging,
  `OnUnitActiveSec=60`, no overlap with `RemainAfterExit`) or plain cron. You choose the loop:
  every 60 s for the pulse, `:07`-style offsets for the hourly and deep passes. The `run_lock`
  and `silmaril-state` discipline already in the code map 1:1 onto a local flock.
- **Environment stays warm:** one venv, dependencies installed once. A cycle becomes "read state,
  think, write state" — seconds, not the current minutes of setup.
- **What does NOT change:** the code. `python -m silmaril --live` is the same entry point; only the
  scheduler and the working directory move. Keep committing a snapshot to GitHub on a slower timer
  (see Rung 4) so your audit trail and backups survive.

> Migration test: run the VPS loop in parallel with Actions for a few days, both writing to
> separate output dirs, and diff the derived stores. They should agree. Then cut Actions down to
> backup-only.

---

## RUNG 2 — MOVE STATE OFF GIT INTO A REAL STORE

Once compute is warm, git-as-database becomes the bottleneck and the survivorship risk (every wipe
is a history edit). Separate **state** from **code**.

- **Time-series / samples → SQLite first, Postgres when it hurts.** `price_samples.json` becomes a
  `prices(symbol, ts, px, source)` table with an index on `(symbol, ts)`. This alone turns "parse
  30 MB every cycle" into indexed point-in-time queries — which is also exactly what the backbone's
  **point-in-time snapshots** and **census** want. SQLite runs in-process with zero ops; Postgres
  (managed, ~$15/mo, or on the same box) buys concurrency and real backups when you outgrow it.
- **Derived stores (champion, validation, bench, contracts, census, research-os) can stay JSON**
  for now — they are small and the dashboard reads them directly. Move them into the DB only if you
  want history/versioning per store (worth it eventually for Decision Replay).
- **Keep the atomic-write contract.** `atomic_io` becomes "write row / upsert in a transaction";
  the invariant (never a half-written store) is preserved, now by the database.
- **Backups become real:** `pg_dump` / litestream to object storage on a timer. A wipe is a
  `DELETE` you can roll back, not a lost git history.

---

## RUNG 3 — OBJECT STORAGE FOR BLOBS & THE PUBLIC FEED

- **Cloudflare R2** (no egress fees — ideal here) or Backblaze B2 / S3. Push the JSON the dashboard
  needs (or a nightly DB export) to a bucket; the dashboard fetches from the bucket instead of the
  repo. Now presentation is decoupled from both code and the live DB, and the UI never waits on a
  git push.
- Large raw archives (full sample history, backtest corpora) live here cheaply instead of bloating
  the repo.

---

## RUNG 4 — KEEP GITHUB FOR WHAT IT IS GOOD AT

Do not abandon it — **demote** it:

- **Code + version control:** unchanged; still the source of truth for the engine.
- **Backup remote:** the VPS pushes a state snapshot on a slow timer (hourly/daily) so you keep the
  auditable, restorable history you value — without it being the hot path.
- **Pages can stay your dashboard host** (it is just static files reading JSON) — point it at the R2
  bucket, or move the front-end to **Cloudflare Pages** for tighter integration with R2. Either way
  the UI is unchanged HTML/JS.

---

## RUNG 5 — CADENCE & ACCURACY ONCE YOU ARE WARM

With a warm box and a real store, accuracy improvements the current setup cannot support:

- **True per-quadrant lanes** (the brief's "own schedule/universe/system"): separate systemd
  services per book, each on its own interval and universe, each with its own store namespace. This
  is the point at which parallel engines are safe — the DB handles concurrency that `silmaril-state`
  currently serializes on purpose. (Until then, the 5.0 lane split + session clocks are the right
  shape.)
- **Sub-minute crypto pulse** where the venue data supports it — crypto is 24/7 and the June-30
  density lesson says cadence *is* edge for the fast books. Stocks stay session-gated.
- **A real FX bid/ask practice feed** unlocks the pre-registered FX probe (Movement W2, F0) — the
  fee-to-target theory the aggressive books are waiting to push. No leverage, ever.
- **Websocket price ingestion** instead of polling: lower latency, fewer rate-limit collisions
  (`cron pressure` on the dashboard goes to zero).

---

## RECOMMENDED ORDER & COST

| Step | Change | Effort | ~Cost/mo | Payoff |
|---|---|---|---|---|
| 1 | VPS + systemd timers (compute warm) | half a day | $5–10 | Real cadence; cold-start tax gone |
| 2 | Samples → SQLite (state off git) | 1–2 days | $0 | Indexed point-in-time; wipe-safe |
| 3 | R2 bucket for the public feed | hours | ~$0 | UI decoupled from git push |
| 4 | GitHub demoted to code + backup | hours | $0 | Keep the audit trail, lose the bottleneck |
| 5 | Per-quadrant lanes / sub-min / FX feed | ongoing | +DB tier | The next accuracy tier |

**Total to escape every current ceiling: roughly $5–25/month and a weekend.**

---

## WHAT NOT TO CHANGE (the discipline that makes SILMARIL trustworthy)

- **Determinism.** Same inputs → same decisions. Every rung above preserves it; do not introduce
  wall-clock nondeterminism into the decision path.
- **No synthetic trading data.** The DB makes it tempting to backfill gaps — do not. The
  `"T00:00:00"` / real-tick discipline must survive the migration intact.
- **Append-only / wipe-proof long-memory.** EVOLUTION_LEDGER, RESEARCH_OS, CONDUCTOR_LEDGER,
  CENSUS_ROSTER stay cumulative. In a DB that means "never `DROP`, always version."
- **The live-money gate.** 100 out-of-sample trades over 90 unbroken days — hosting speed changes
  how fast evidence *accrues*, never what unlocks the door. Faster infrastructure means you reach
  an honest verdict sooner; it does not lower the bar.
- **The Null Layer stays the referee.** However fast it runs, "up" still has to mean "up versus
  BENCH_HODL and BENCH_CASH," or it is not edge.
