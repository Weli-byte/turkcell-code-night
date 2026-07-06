/**
 * Service Worker — Sprint 22.
 *
 * Strateji:
 * - /api/* isteklerine ASLA dokunmaz (network only) — canlı veri, SSE,
 *   puan/rozet akışları her zaman gerçek sunucudan gelir.
 * - HTML: network-first (her zaman güncel sayfa; ağ yoksa cache fallback).
 * - CSS/JS/SVG/manifest: stale-while-revalidate (hızlı açılış, arka planda
 *   tazeleme).
 */

const CACHE_NAME = 'ge-static-v1';

const PRECACHE = [
  '/css/main.css',
  '/js/api.js',
  '/js/global.js',
  '/js/notifications.js',
  '/icon.svg',
  '/manifest.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Sadece kendi origin'imizin GET'leri; API'ye ve SSE'ye dokunma
  if (req.method !== 'GET') return;
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  const isHTML   = req.mode === 'navigate' || url.pathname.endsWith('.html') || url.pathname === '/';
  const isStatic = /\.(css|js|svg|json|woff2?)$/.test(url.pathname);

  if (isHTML) {
    // Network-first: bayat sayfa riski yok, offline'da cache
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE_NAME).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req))
    );
  } else if (isStatic) {
    // Stale-while-revalidate
    event.respondWith(
      caches.match(req).then((cached) => {
        const fresh = fetch(req)
          .then((res) => {
            if (res.ok) {
              const copy = res.clone();
              caches.open(CACHE_NAME).then((c) => c.put(req, copy));
            }
            return res;
          })
          .catch(() => cached);
        return cached || fresh;
      })
    );
  }
});
