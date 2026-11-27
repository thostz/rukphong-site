// Rukphong PWA service worker
// - Same-origin files (pages, config.js, icons): network first, cache fallback → เปิดแอปได้แม้เน็ตหลุด
// - Cross-origin (Apps Script API, CDN, fonts): ไม่แตะ ปล่อยให้ browser จัดการเอง
const CACHE = 'rukphong-v1';
const SHELL = [
  './', './index.html', './config.js', './manifest.webmanifest',
  './dashboard.html', './expense.html', './tasks.html', './notes.html',
  './investment.html', './smart-import.html', './profile.html', './help.html',
  './icons/icon-192.png', './icons/icon-512.png',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  e.respondWith(
    fetch(req)
      .then(res => {
        if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
        return res;
      })
      .catch(() => caches.match(req, { ignoreSearch: true }))
  );
});
