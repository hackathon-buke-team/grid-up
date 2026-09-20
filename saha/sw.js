/* PANO GÖZ · Saha · service worker
   ---------------------------------
   İki işi vardır ve başka iş yapmaz.

   1. UYGULAMA KABUĞU çevrimdışı açılsın. Trafo binasında çekim zayıftır; uygulama
      açılmazsa ekip "bağlantı yok" ekranını bile göremez. Kabuk AĞ-ÖNCELİKLİ
      alınır (her açılışta yeniden doğrulanır, bayat paket kalmaz), ağ yoksa
      önbellekten gelir.
   2. Sistem bildiriminin tıklanması ilgili olayı açsın.

   /api/ ASLA önbelleğe alınmaz: çevrimdışı bir telefonun bayat bir alarm durumunu
   "güncel" diye göstermesi, hiç göstermemesinden kötüdür. Uygulama, çekmediği
   veriyi açıkça "son bilinen durum" diye etiketler.

   Push servisi YOKTUR: FCM/APNs/Web Push aktarıcısı kamu bulutudur ve şirket içi
   kısıtla çelişir. Kapalı uygulamayı SMS ve Telegram yolları uyandırır. */

const SURUM = 'panogoz-saha-v2';
const KABUK = ['./', 'index.html', 'app.css', 'app.js', 'manifest.webmanifest', 'icon.svg', 'icon-192.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(SURUM).then((c) => c.addAll(KABUK)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((anahtarlar) => Promise.all(anahtarlar.filter((k) => k !== SURUM).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  if (!url.pathname.startsWith('/saha/')) return;          // /api/ dahil: dokunma
  e.respondWith(
    fetch(e.request)
      .then((yanit) => {
        if (yanit.ok) {
          const kopya = yanit.clone();
          caches.open(SURUM).then((c) => c.put(e.request, kopya));
        }
        return yanit;
      })
      .catch(() => caches.match(e.request).then((k) => k || caches.match('./')))
  );
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const id = e.notification.data && e.notification.data.id;
  const hedef = new URL(id ? `./#/olay/${id}` : './', self.registration.scope).href;
  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((pencereler) => {
      for (const p of pencereler) {
        if (p.url.startsWith(self.registration.scope) && 'focus' in p) {
          p.navigate(hedef);
          return p.focus();
        }
      }
      return self.clients.openWindow(hedef);
    })
  );
});
