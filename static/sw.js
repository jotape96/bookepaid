// Minimal Service Worker required for PWA installation
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Let Streamlit handle all live requests normally
  event.respondWith(fetch(event.request));
});