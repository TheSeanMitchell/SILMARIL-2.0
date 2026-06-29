# SILMARIL — MAINTENANCE GUIDE (for the forgetful future-you)

Keep this in the repo root. It is the "don't let the machine rot" checklist. None of this is
urgent day-to-day; it's the housekeeping that keeps GitHub happy and the data clean.

## WEEKLY (pick a day, e.g. Sunday night)
- [ ] **Glance at PROJECT HEALTH on the dashboard.** Every feed light should be 🟢. If one is
      🟡/🔴 for more than a day, open the health panel — it names the failing feed. Fallback
      chains usually cover it, but check the cron-pressure row isn't near 100% on any provider.
- [ ] **Check realized P&L per book** (the only metric that matters). Note it somewhere.
- [ ] **Confirm the cron is still running** — "last sim run" on the dashboard should be minutes
      old during market hours, not hours/days.

## EVERY 2–3 WEEKS
- [ ] **Run a GitHub history squash** to keep the repo small. The dashboard shows repo MB; if
      it climbs past ~400–500 MB, squash. (Procedure below.) You are at ~260 MB now — fine.
- [ ] **Delete stale git tags** you no longer need (old version tags pile up). Procedure below.
- [ ] **Run the root-doc cleanup** if new stray READMEs appeared:
      `python scripts/cleanup_root_docs.py` (preview) then `--apply`.

## ONLY WHEN YOU INTEND TO START A CLEAN MEASUREMENT WINDOW
(e.g. beginning the multi-week 2.5.5 data-collection run)
- [ ] **Pristine reset + history rebuild, ONE command:**
      `python scripts/pristine_reset.py --with-backfill`
      This zeroes all four paper books to $10k AND rebuilds price history/fingerprint so the
      next cron run starts clean with data already present. Options:
      `--baseline 10000`, `--backfill-days 30`, `--accounts all`.
      ⚠️ Only do this when you actually want to discard the current track record. Mid-experiment
      resets destroy the very forward data 2.5.5 needs.
- [ ] After a reset, if you use the Alpaca paper dashboard, reset/fund that to match.

## PROCEDURES

### GitHub history squash (shrinks repo)
```
# from a fresh clone or your working copy, on main:
git checkout --orphan _squash
git add -A
git commit -m "Squash history $(date +%Y-%m-%d)"
git branch -D main
git branch -m main
git push -f origin main
```
(Force-push rewrites history — make sure no one else is mid-edit. Keep a ZIP backup first,
which you already do religiously.)

### Delete old tags (local + remote)
```
git tag                      # list them
git tag -d <tagname>         # delete locally
git push origin :refs/tags/<tagname>   # delete on GitHub
# or wipe ALL local tags then re-fetch the ones that still exist remotely:
git tag -l | xargs git tag -d
```

### Verify a workflow run didn't silently fail
- GitHub → Actions tab → look for red X's on the cron workflow. The concurrency group
  `silmaril-state` means runs queue rather than collide, so a backlog of queued runs is the
  signal something stalled.

## THINGS THAT NEED NOTHING FROM YOU (so don't worry about them)
- API keys / secrets — all configured; the system reads them by their exact names. No rotation
  needed unless a provider invalidates one (the health light will go 🟡 if so).
- Data fallbacks — automatic. If a provider dies, the next in the chain carries that run.
- The four paper books — run themselves on the cron; no manual stepping.

## IF SOMETHING LOOKS WRONG
1. Open the dashboard PROJECT HEALTH panel first — it almost always names the problem.
2. Check the GitHub Actions tab for a failed run + its error.
3. The opportunity audit explains "why no trades" (usually: no qualifying setup = correct, not
   broken). Quiet tape ≠ broken system.
