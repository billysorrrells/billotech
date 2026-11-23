const CACHE = 'billo-os-v3';
const SHELL = ['/app.html', '/os.html', '/info.html', '/manifest.json', '/icons/icon-192.png'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
// pages: network first (so updates show right away), cache when offline; other files: cache first
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET' || new URL(e.request.url).origin !== location.origin) return;
  const page = e.request.mode === 'navigate' || e.request.destination === 'document';
  const save = res => { const copy = res.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)).catch(()=>{}); return res; };
  e.respondWith(page
    ? fetch(e.request).then(save).catch(() => caches.match(e.request).then(h => h || caches.match('/app.html')))
    : caches.match(e.request).then(hit => hit || fetch(e.request).then(save)));
});
