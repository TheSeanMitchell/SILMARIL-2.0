# SILMARIL-2.0 — independent sandbox setup guide

## What this is
A CLEAN copy of the SILMARIL working tree (~101 MB, 222 files, NO .git
history bloat). Use it to populate the empty repo at
github.com/TheSeanMitchell/SILMARIL-2.0 as a fully independent project you
can edit freely without any risk to the live v1.

## Why it starts clean
This contains only the current files — none of v1's ~900 MB of committed
git history. So v2 begins at ~101 MB and you get a full storage budget.

## TWO WAYS TO GET IT INTO SILMARIL-2.0

### Path A — Git command line (RECOMMENDED for 222 files)
One-time: install Git (git-scm.com), then in a terminal, in the unzipped
folder:
    git init
    git add -A
    git commit -m "SILMARIL v2 — clean import from v1 working tree"
    git branch -M main
    git remote add origin https://github.com/TheSeanMitchell/SILMARIL-2.0.git
    git push -u origin main
(GitHub will prompt for login / a personal access token the first time.)
This preserves every folder exactly and uploads in one shot.

### Path B — GitHub web upload (no tools, but tedious)
On the empty SILMARIL-2.0 repo page: "uploading an existing file" ->
drag files in. WARNING: do it folder-by-folder (docs/, silmaril/,
.github/) so nested structure is preserved; the web uploader can flatten
deep folders if you dump everything at once. Verify docs/data/ and
silmaril/agents/ arrived intact afterward.

## CRITICAL — what does NOT copy, and what to do
1. SECRETS (API keys) do NOT travel with files. In SILMARIL-2.0 ->
   Settings -> Secrets and variables -> Actions, re-add: ALPACA keys and
   every data-provider key from v1.
2. USE SEPARATE ALPACA PAPER ACCOUNTS for v2 so its trades never collide
   with v1's. (New paper account numbers in the Alpaca dashboard.)
3. LEAVE ACTIONS DISABLED at first (Actions tab -> enable only when you
   want it running). You WANT v2's cron off while you experiment, so it
   never trades on half-finished code.
4. NO cron-job.org trigger for v2 unless you deliberately add one. Run
   workflows MANUALLY (Actions -> select workflow -> Run) while testing.
5. Pages will publish to ...github.io/SILMARIL-2.0/ automatically once
   enabled — separate URL from your live dashboard.

## THE THREE BUGS THIS SANDBOX EXISTS TO FIX (evidence-confirmed)
1. HARVEST_5 buy/sell routing is INVERTED — it evaluates BUY candidates
   against a SELL gate ("signal HOLD is not SELL/STRONG_SELL"), blocking
   every crypto buy. This is why XLM's 30% run was never traded. The
   crypto/valuables account currently cannot buy anything.
2. CRYPTO MISLABELED as asset_class=equity (NEAR-USD, JTO-USD, XLM-USD) —
   so crypto gets offered to the stock accounts (which correctly reject
   it) instead of the crypto account. Routing dead-end.
3. DEPLOYMENT — LEGACY had $3,451 idle, HARVEST_5 $8,833 idle while the
   top-8 BUY list went unbought. Once 1&2 are fixed, verify cash actually
   deploys into the BUY list and rotates out names demoted to HOLD.

Fix order: #1 first (it's why crypto can't trade at all), then #2, then
verify #3. None of these are learning/evolution issues — they are
execution-routing bugs. The agents getting smarter will NOT fix them.
