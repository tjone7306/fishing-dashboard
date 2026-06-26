const CACHE = 'b4u-fish-v2';
self.addEventListener('install', function(e){ self.skipWaiting(); });
self.addEventListener('activate', function(e){
  e.waitUntil(
    caches.keys().then(function(keys){
      return Promise.all(keys.filter(function(k){ return k !== CACHE; }).map(function(k){ return caches.delete(k); }));
    }).then(function(){ return self.clients.claim(); })
  );
});
self.addEventListener('fetch', function(e){
  var req = e.request;
  if (req.method !== 'GET') return;
  var accept = req.headers.get('accept') || '';
  if (req.mode === 'navigate' || accept.indexOf('text/html') !== -1) {
    e.respondWith(
      fetch(req).then(function(r){ var c = r.clone(); caches.open(CACHE).then(function(ca){ ca.put(req, c); }); return r; })
                .catch(function(){ return caches.match(req).then(function(m){ return m || caches.match('./'); }); })
    );
    return;
  }
  if (new URL(req.url).origin === self.location.origin) {
    // stale-while-revalidate for static assets so updated icons refresh on next load
    e.respondWith(
      caches.match(req).then(function(m){
        var fetchP = fetch(req).then(function(r){ var c = r.clone(); caches.open(CACHE).then(function(ca){ ca.put(req, c); }); return r; }).catch(function(){ return m; });
        return m || fetchP;
      })
    );
  }
});
