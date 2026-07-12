/* SILMARIL service worker — 5.1 FINAL (v3).
   FIX (2026-07-12): the old v51b cached the HTML shell CACHE-FIRST, so a soft
   reload kept serving the OLD index.html forever while a hard reload showed a
   torn half-updated page. This version is NETWORK-FIRST for the document and
   all code assets — the newest UI ALWAYS wins — and only falls back to cache
   when the network is unreachable. The cache name is bumped so activate() purges
   every stale entry. */
const CACHE = 'silmaril-v3-20260712';

self.addEventListener('install', e => {
  // take over immediately; do not pre-cache the shell (network-first below)
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;

  // NETWORK-FIRST for everything same-origin (HTML, JS, JSON): the live version
  // is always preferred; cache is only a last-resort offline fallback.
  e.respondWith(
    fetch(e.request)
      .then(r => {
        const cp = r.clone();
        caches.open(CACHE).then(c => c.put(e.request, cp));
        return r;
      })
      .catch(() => caches.match(e.request))
  );
});
