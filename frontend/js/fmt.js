// PANO GÖZ · biçimlendirme ve renk.
//
// tr-TR kuralları: ondalık virgül, binlik nokta, gg.AA.yyyy, Europe/Istanbul.
// Türkçe metinde büyük harfe çevirme YOK (CSS text-transform:uppercase "i"yi
// "I" yapar, "İ" yapmaz). Etiketler kaynakta zaten doğru yazılmıştır.
//
// Ölçüm renk rampası cividis'tir: algısal olarak düzgün ve renk körlüğüne
// dayanıklı. Gökkuşağı rampası hiçbir yerde kullanılmaz. Saf kırmızı/yeşil
// yalnızca topolojiye (faz rengi, enerjili/enerjisiz) ayrılmıştır.

import { h, s } from './dom.js';

export const TZ = 'Europe/Istanbul';

const nf = new Map();
function numFmt(min, max) {
  const key = min + ':' + max;
  let f = nf.get(key);
  if (!f) {
    f = new Intl.NumberFormat('tr-TR', { minimumFractionDigits: min, maximumFractionDigits: max });
    nf.set(key, f);
  }
  return f;
}

/** Sayı. null/undefined/NaN -> "—" (tire değil, uzun tire: veri yok demek). */
export function num(v, dec = 1, dash = '—') {
  if (v === null || v === undefined || v === '' || Number.isNaN(Number(v))) return dash;
  return numFmt(dec, dec).format(Number(v));
}

export function int(v, dash = '—') { return num(v, 0, dash); }

/** İşaretli sayı: pozitifin başına + koyar (trend sütunları için). */
export function signed(v, dec = 2, dash = '—') {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return dash;
  const x = Number(v);
  return (x > 0 ? '+' : '') + num(x, dec);
}

export function pct(v, dec = 0, dash = '—') {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return dash;
  return num(v, dec) + ' %';
}

export function unit(v, u, dec = 1, dash = '—') {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return dash;
  return num(v, dec) + ' ' + u;
}

const dtFull = new Intl.DateTimeFormat('tr-TR', {
  timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric',
  hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
});
const dtShort = new Intl.DateTimeFormat('tr-TR', {
  timeZone: TZ, day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
});
const dOnly = new Intl.DateTimeFormat('tr-TR', {
  timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric',
});
const tOnly = new Intl.DateTimeFormat('tr-TR', {
  timeZone: TZ, hour: '2-digit', minute: '2-digit', hour12: false,
});

const toDate = (ts) => new Date((Number(ts) || 0) * 1000);

export function dateTime(ts) { return ts ? dtFull.format(toDate(ts)) : '—'; }
export function dateTimeShort(ts) { return ts ? dtShort.format(toDate(ts)) : '—'; }
export function date(ts) { return ts ? dOnly.format(toDate(ts)) : '—'; }
export function time(ts) { return ts ? tOnly.format(toDate(ts)) : '—'; }

/** "gg.AA.yyyy" biçimli gün anahtarını (joint_daily.day) olduğu gibi gösterir. */
export function dayLabel(day) {
  if (!day) return '—';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(day));
  return m ? `${m[3]}.${m[2]}.${m[1]}` : String(day);
}

/** Süre: 45 sn / 12 dk / 3 sa 20 dk / 4 gün */
export function dur(sec) {
  if (sec === null || sec === undefined || Number.isNaN(Number(sec))) return '—';
  const x = Math.max(0, Math.round(Number(sec)));
  if (x < 90) return x + ' sn';
  const m = Math.round(x / 60);
  if (m < 90) return m + ' dk';
  const hh = Math.floor(x / 3600), mm = Math.round((x % 3600) / 60);
  if (hh < 48) return mm ? `${hh} sa ${mm} dk` : `${hh} sa`;
  return Math.floor(x / 86400) + ' gün';
}

/** "3 dk önce". now saniye cinsinden epoch. */
export function ago(ts, now) {
  if (!ts) return '—';
  const n = now === undefined ? Date.now() / 1000 : now;
  return dur(n - ts) + ' önce';
}

// --------------------------------------------------------------------------
// Seviye ölçeği - renk + ŞEKİL + Türkçe etiket, üçü birden
// --------------------------------------------------------------------------

export const SEVERITY = {
  BILGI:  { label: 'Bilgi',  shape: 'dot',      color: 'var(--sev-bilgi)',  rank: 0,
            action: 'Kayda alınır, aksiyon yok' },
  IZLE:   { label: 'İzle',   shape: 'ring',     color: 'var(--sev-izle)',   rank: 1,
            action: 'Haftalık özet listesine girer, ekip çıkmaz' },
  UYARI:  { label: 'Uyarı',  shape: 'tri',      color: 'var(--sev-uyari)',  rank: 2,
            action: 'İş emri açılır, bir sonraki planlı ziyarette doğrulanır' },
  KRITIK: { label: 'Kritik', shape: 'tri-fill', color: 'var(--sev-kritik)', rank: 3,
            action: '7 gün içinde saha ziyareti, yük aktarımı planlanır' },
  ACIL:   { label: 'Acil',   shape: 'square',   color: 'var(--sev-acil)',   rank: 4,
            action: 'Derhal ekip yönlendirilir, SMS ve sesli arama tetiklenir' },
};

export const SEVERITY_ORDER = ['BILGI', 'IZLE', 'UYARI', 'KRITIK', 'ACIL'];

export function sevMeta(key) { return SEVERITY[key] || SEVERITY.BILGI; }
export function sevRank(key) { return sevMeta(key).rank; }
export function sevColor(key) { return sevMeta(key).color; }

/** Seviye şekli - SVG. Renk körü bir izleyici için şekil tek başına yeterlidir. */
export function sevShape(key, size = 12) {
  const m = sevMeta(key);
  const svg = s('svg', { viewBox: '0 0 12 12', width: size, height: size, 'aria-hidden': 'true' });
  const col = 'currentColor';
  if (m.shape === 'dot') svg.appendChild(s('circle', { cx: 6, cy: 6, r: 4, fill: col }));
  else if (m.shape === 'ring') svg.appendChild(s('circle', { cx: 6, cy: 6, r: 4, fill: 'none', stroke: col, 'stroke-width': 2 }));
  else if (m.shape === 'tri') svg.appendChild(s('path', { d: 'M6 1.2 11 10.6H1z', fill: 'none', stroke: col, 'stroke-width': 1.8, 'stroke-linejoin': 'round' }));
  else if (m.shape === 'tri-fill') svg.appendChild(s('path', { d: 'M6 1.2 11 10.6H1z', fill: col }));
  else svg.appendChild(s('rect', { x: 1.6, y: 1.6, width: 8.8, height: 8.8, rx: 1, fill: col }));
  return svg;
}

/** Tam rozet: şekil + Türkçe etiket. */
export function sevBadge(key, extra) {
  const m = sevMeta(key);
  return h('span.sev.sev-' + (SEVERITY[key] ? key : 'BILGI'),
    { title: m.label + ' · ' + m.action },
    sevShape(key), h('span', { text: extra ? `${m.label} · ${extra}` : m.label }));
}

// --------------------------------------------------------------------------
// cividis - ölçüm ısı rampası
// --------------------------------------------------------------------------

const CIVIDIS = [
  [0, 34, 78], [18, 53, 112], [59, 73, 108], [87, 93, 109], [112, 113, 115],
  [138, 134, 120], [165, 156, 116], [195, 179, 105], [225, 204, 85], [254, 232, 56],
  [255, 234, 70],
];

/** t 0..1 -> "rgb(...)" cividis. Aralık dışı değerler kırpılır. */
export function cividis(t) {
  const x = Math.max(0, Math.min(1, Number(t) || 0)) * (CIVIDIS.length - 1);
  const i = Math.min(CIVIDIS.length - 2, Math.floor(x));
  const f = x - i;
  const a = CIVIDIS[i], b = CIVIDIS[i + 1];
  const c = [0, 1, 2].map((k) => Math.round(a[k] + (b[k] - a[k]) * f));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}

export function cividisCss(stops = 9) {
  const parts = [];
  for (let i = 0; i < stops; i++) parts.push(cividis(i / (stops - 1)));
  return `linear-gradient(90deg, ${parts.join(',')})`;
}

/** θ -> renk. 0 K soğuk uç, THETA_HI sıcak uç. */
export const THETA_HI = 10;
export function thetaColor(theta) {
  if (theta === null || theta === undefined || Number.isNaN(Number(theta))) return 'var(--tw-unmon)';
  return cividis(Number(theta) / THETA_HI);
}

// --------------------------------------------------------------------------
// Durum bayrakları - "körüz" demenin insana okunur hâli
// --------------------------------------------------------------------------

export const FLAG_TR = {
  DATA_VALID: 'Veri geçerli',
  STALE: 'Veri bayat',
  SENSITIVITY_LOW: 'Görünürlük düşük',
  DE_ENERGISED: 'Pano enerjisiz',
  LEARN_MODE: 'Öğrenme modu',
  SUPPRESSED: 'Bastırılmış alarm var',
  MAINTENANCE: 'Bakım modu',
  ANALYSER_COMMS_LOST: 'Analizör haberleşmesi yok',
  ARC_RELAY_COMMS_LOST: 'Ark rölesi haberleşmesi yok',
  GATEWAY_COMMS_LOST: 'Ağ geçidi çevrimdışı',
  MOUNT_LOST: 'Sensör düştü / kaydı',
  AIM_SHIFTED: 'Termal dizi nişanı kaydı',
  CELL_LOW: 'Pil zayıf',
  CLOCK_UNSYNCED: 'Saat senkron değil',
  CONFIG_MISMATCH: 'Yapılandırma uyuşmazlığı',
  SELFTEST_DUE: 'Ark otokontrolü gecikti',
};

/** Bu bayraklar bir pano arızası DEĞİL, bizim görme kaybımızdır. Ayrı gösterilir. */
export const BLIND_FLAGS = new Set([
  'DE_ENERGISED', 'SENSITIVITY_LOW', 'MOUNT_LOST', 'AIM_SHIFTED',
  'CELL_LOW', 'STALE', 'GATEWAY_COMMS_LOST', 'ANALYSER_COMMS_LOST',
  'ARC_RELAY_COMMS_LOST', 'CLOCK_UNSYNCED', 'LEARN_MODE',
]);

export function flagTag(name) {
  const blind = BLIND_FLAGS.has(name);
  return h('span.tag' + (blind ? '.blind' : ''), {
    text: FLAG_TR[name] || name,
    title: blind ? 'Görüş kısıtı: pano arızası değil, PANO GÖZ’ün göremediği durum' : name,
  });
}

export const MODE_TR = {
  loose_connection: 'Gevşek bağlantı',
  overload: 'Aşırı yük',
  arc_integrity: 'Ark koruma bütünlüğü',
  thermal_runaway: 'Isıl kaçış / soğutma kaybı',
  harmonic_neutral: 'Harmonik nötr yüklenmesi',
  moisture: 'Nem / yoğuşma',
  insulation: 'Yalıtım zayıflaması',
};

export const PRPD_TR = {
  GURULTU: 'Gürültü',
  BOSLUK: 'İç boşluk deşarjı',
  YUZEY: 'Yüzey kaçağı',
  KORONA: 'Korona',
  YUZEN: 'Yüzen elektrot / gevşek bağlantı',
};

export const FEATURE_TR = {
  rate: 'Darbe hızı (1/s)',
  ndom: 'Çevrim başına baskın darbe',
  asymmetry_n: 'Yarım dalga sayı asimetrisi',
  asymmetry_q: 'Yarım dalga genlik asimetrisi',
  sigma_phi: 'Faz yayılımı (°)',
  cv: 'Genlik değişkenlik katsayısı',
  cross_corr: 'İki yarım dalga benzerliği',
  phase_entropy: 'Faz entropisi (0-1)',
  r_pq: 'Genlik-faz bağlaşımı',
  regularity: 'Genlik tekrarlılığı (0-1)',
  qmax: 'Tepe genlik (pC eşdeğeri)',
  nqn: 'Normalize gürültü sayısı',
};

export const CONDUCTOR_COLOR = { L1: '#9aa6b3', L2: '#39424f', L3: '#8a6440', N: '#5fa8dc' };
export const CONDUCTOR_TR = { L1: 'L1 · gri', L2: 'L2 · siyah', L3: 'L3 · kahverengi', N: 'N · açık mavi' };

/** "C06-L1-PABUC" -> "Ç6 · L1". Alarm listesinde ve grafik başlığında kullanılır. */
export function shortJoint(key) {
  if (!key) return '—';
  const m = /^C(\d+)-(L\d|N)-(\w+)$/.exec(key);
  if (m) return `Ç${Number(m[1])} · ${m[2]}`;
  const g = /^GIRIS-(L\d|N)$/.exec(key);
  if (g) return `Giriş · ${g[1]}`;
  return key;
}

export function jointZoneTR(zone) {
  return { bottom: 'Alt kablo bölmesi', busbar: 'Bara bölmesi', roof: 'Çatı girişi' }[zone] || zone;
}

/** Sağlık endeksi çubuğu için sınıf. */
export function hiClass(hi) {
  if (hi >= 85) return '';
  if (hi >= 65) return 'warn';
  if (hi >= 40) return 'bad';
  return 'acil';
}
