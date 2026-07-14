# SW CACHE FIX — why the old UI kept showing, and the one-time recovery

## What was wrong (root cause, confirmed)
The service worker shipped with 5.1B (`sw.js`, cache name `silmaril-shell-v51b`) cached
the **HTML shell cache-first**. Result:
- **Soft reload (Ctrl+R):** the worker served the *cached OLD* `index.html` → you saw the old
  site, and it "worked" because old HTML + old JS are a matched pair.
- **Hard reload (Ctrl+Shift+R):** the browser fetched the *new* `index.html` from the network but
  the worker still served stale copies of other assets → a torn, half-updated page that looked broken.

**Nothing else was broken.** Your engine, data, new stores (confidence engine, strategy lab, MTF
ladder), knobs, and the whole 5.1 Final UI all landed correctly and pass 18/18 selftests. You just
couldn't *see* the new UI because the old worker kept feeding you the old page.

## What this drop fixes
1. **`sw.js` rewritten NETWORK-FIRST** (cache name bumped to `silmaril-v3-20260712`). The newest
   version always wins; cache is only an offline fallback. On activate it purges every old cache.
2. **`index.html` self-heals**: it calls `reg.update()` on every load and reloads ONCE when a new
   worker takes control — so the stale worker is replaced automatically on your next visit.
3. **`reset-app.html`** — a one-time recovery page (also linked in Settings as "↻ reset app cache")
   that force-unregisters any worker and clears caches, then bounces you to the live dashboard.

## INSTALL (drag-drop, 3 files)
Replace `docs/index.html` and `docs/sw.js`; add `docs/reset-app.html`. Commit.

## TO RECOVER YOUR BROWSER RIGHT NOW (one time)
After the files are live, do ONE of these — you only need it once, ever:
- **Easiest:** visit **`<your-pages-url>/reset-app.html`** — it clears the old worker and redirects.
- **Or:** DevTools (F12) → Application → Service Workers → **Unregister** → then reload.
- **Or:** just hard-reload twice — the self-heal will replace the worker and reload into the new UI.

After that, normal soft reloads (Ctrl+R) will always show the current UI. The bug cannot recur —
network-first means the shell is never trapped again.
