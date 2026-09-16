// PANO GÖZ · tema.
//
// İki yüzey vardır: KOYU, kontrol odası ve karartılmış sunum salonu için;
// AÇIK, gün ışığı alan bir şantiye ofisi veya yazıcı çıktısı için. İkisi de
// aynı belirteç (custom property) kümesini doldurur, bu yüzden hiçbir bileşen
// hangi temada olduğunu bilmek zorunda değildir.
//
// Seçim tarayıcıda kalır (localStorage). Varsayılan koyudur: bu ekran öncelikle
// bir trafo merkezi kontrol odasında ve projeksiyonla izlenir.
//
// Canvas çizen her şey (zaman serileri, PRPD ısı haritası) renklerini
// getComputedStyle ile belirteçlerden okur. Tema değişince yeniden çizmeleri
// için document üzerinde 'panogoz:tema' olayı yayınlanır.

const KEY = 'panogoz.tema';
const KOYU = 'koyu';
const ACIK = 'acik';

export const TEMA = { KOYU, ACIK };

function stored() {
  try {
    const v = localStorage.getItem(KEY);
    return v === KOYU || v === ACIK ? v : null;
  } catch (e) {
    // Gizli sekmede veya depolama kapalıyken okuma patlar; tema yine çalışır.
    return null;
  }
}

/** Şu anki tema. Kullanıcı seçmemişse koyu. */
export function current() {
  const attr = document.documentElement.getAttribute('data-tema');
  return attr === ACIK ? ACIK : (attr === KOYU ? KOYU : (stored() || KOYU));
}

export function apply(tema) {
  const t = tema === ACIK ? ACIK : KOYU;
  document.documentElement.setAttribute('data-tema', t);
  try { localStorage.setItem(KEY, t); } catch (e) { /* yoksay */ }
  document.dispatchEvent(new CustomEvent('panogoz:tema', { detail: { tema: t } }));
  return t;
}

export function toggle() {
  return apply(current() === KOYU ? ACIK : KOYU);
}

/** Tema değişimini dinle. Geri dönen işlevi çağırmak aboneliği bitirir. */
export function onChange(fn) {
  const h = (ev) => fn(ev.detail && ev.detail.tema);
  document.addEventListener('panogoz:tema', h);
  return () => document.removeEventListener('panogoz:tema', h);
}

/** Bir belirtecin hesaplanmış değeri; canvas çizerken kullanılır. */
export function token(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback || '';
}

/** İlk boyamadan önce çalışsın diye index.html başında da bir kopyası var. */
export function boot() {
  document.documentElement.setAttribute('data-tema', stored() || KOYU);
}
