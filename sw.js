const CACHE_NAME = 'shadowapp-v2'; // שינינו את שם הגרסה כדי להרוס את הקודמת!

self.addEventListener('install', e => {
  self.skipWaiting(); // כופה על ה-SW החדש להשתלט מיד
});

self.addEventListener('activate', e => {
  e.waitUntil(clients.claim()); // מוחק גרסאות ישנות מהזיכרון
});

self.addEventListener('fetch', e => {
  // קודם כל מנסה להביא מהשרת את הקובץ המעודכן ביותר, ורק אם אין אינטרנט - לוקח מהזיכרון
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
