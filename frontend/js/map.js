// PANO GÖZ · filo haritası.
//
// Gerçek Türkiye coğrafyası, yerel bir dosyadan (data/turkiye.js). Karo (tile)
// sunucusu yoktur ve olmayacaktır: kurulum hava boşluklu. Ama "harita altlığı
// yok" demek "kıyı şeridi yok" demek zorunda değil - il sınırları 110 KB'lık
// tek bir dosyada, ağ isteği sıfır.
//
// İzdüşüm: 39° K standart paralelli eşuzaklıklı silindirik (plate carrée).
// Türkiye 36-42° arasında olduğu için bu izdüşümde biçim bozulması gözle
// görülmez ve 1 birim = 111,32 m olur; ölçek çubuğu bu yüzden dürüsttür.
//
// Kalem kalınlıkları vector-effect ile ekran pikselinde sabittir: yakınlaştırma
// çizgileri şişirmez. Etiketler ve pano işaretleri de her yakınlaştırmada
// yeniden ölçeklenir, böylece 30 kat yaklaşınca ekranı dev noktalar kaplamaz.

import { s, h } from './dom.js';
import * as fmt from './fmt.js';
import { zoomPan } from './zoompan.js';
import { OLCEK, YAYLAR, ILLER } from '../data/turkiye.js';

// ---------------------------------------------------------------- izdüşüm --

const REF_LAT = 39.0;
const KX = Math.cos((REF_LAT * Math.PI) / 180);
const LON0 = 25.0;
const LAT0 = 43.0;
const U = 1000;                 // birim / derece
const KM_PER_UNIT = 111.32 / U; // 39° K'de her iki eksende de geçerli

export const X = (lon) => (lon - LON0) * KX * U;
export const Y = (lat) => (LAT0 - lat) * U;

// ------------------------------------------------------- veriyi bir kez aç --

let geo = null;

function decodeArc(str) {
  const out = [];
  let i = 0, x = 0, y = 0;
  while (i < str.length) {
    let dx = 0, dy = 0;
    for (let k = 0; k < 2; k++) {
      let shift = 0, result = 0, b;
      do {
        b = str.charCodeAt(i++) - 63;
        result |= (b & 0x1f) << shift;
        shift += 5;
      } while (b >= 0x20);
      const v = (result & 1) ? ~(result >> 1) : (result >> 1);
      if (k === 0) dx = v; else dy = v;
    }
    x += dx; y += dy;
    out.push(x, y);
  }
  return out;
}

/** Yayları çöz, her ili tek bir yol metnine çevir, iç/dış sınırı ayır. */
function build() {
  if (geo) return geo;

  const arcs = YAYLAR.map(decodeArc);
  const use = new Uint8Array(arcs.length);   // kaç il bu yayı kullanıyor

  const pathOfArc = arcs.map((a) => {
    // Yay noktalarını izdüşüme çevir ve bir kez metne bas; hem il dolgusunda
    // hem sınır çiziminde aynı dize kullanılır.
    const pts = new Array(a.length / 2);
    for (let i = 0, k = 0; i < a.length; i += 2, k++) {
      pts[k] = X(a[i] / OLCEK).toFixed(1) + ' ' + Y(a[i + 1] / OLCEK).toFixed(1);
    }
    return pts;
  });

  const iller = ILLER.map((p) => {
    let d = '';
    for (const poly of p.p) {
      for (const ring of poly) {
        let pts = [];
        for (const idx of ring) {
          use[idx < 0 ? ~idx : idx] = Math.min(255, use[idx < 0 ? ~idx : idx] + 1);
          const a = pathOfArc[idx < 0 ? ~idx : idx];
          const seq = idx < 0 ? a.slice().reverse() : a;
          if (pts.length && pts[pts.length - 1] === seq[0]) pts = pts.concat(seq.slice(1));
          else pts = pts.concat(seq);
        }
        d += 'M' + pts.join('L') + 'Z';
      }
    }
    return { ad: p.n, d, lon: p.c[0] / OLCEK, lat: p.c[1] / OLCEK, poly: p.p };
  });

  // Bir yayı yalnız tek bir il kullanıyorsa o yay ülkenin dış hattıdır:
  // kıyı şeridi veya kara sınırı. İkisi de kullanıyorsa il sınırıdır.
  let dIc = '', dDis = '';
  for (let i = 0; i < arcs.length; i++) {
    const seg = 'M' + pathOfArc[i].join('L');
    if (use[i] >= 2) dIc += seg; else dDis += seg;
  }

  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const a of arcs) {
    for (let i = 0; i < a.length; i += 2) {
      const px = X(a[i] / OLCEK), py = Y(a[i + 1] / OLCEK);
      if (px < x0) x0 = px; if (px > x1) x1 = px;
      if (py < y0) y0 = py; if (py > y1) y1 = py;
    }
  }

  geo = { iller, dIc, dDis, bbox: { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } };
  return geo;
}

/** Nokta hangi ilin içinde? Işın atma, önce kutu eleyerek. */
function provinceAt(lon, lat) {
  const g = build();
  const qx = lon * OLCEK, qy = lat * OLCEK;
  for (const il of g.iller) {
    for (const poly of il.poly) {
      if (ringContains(poly[0], qx, qy)) {
        let inHole = false;
        for (let i = 1; i < poly.length; i++) {
          if (ringContains(poly[i], qx, qy)) { inHole = true; break; }
        }
        if (!inHole) return il.ad;
      }
    }
  }
  return null;
}

const ringCache = new Map();

function ringPoints(ring) {
  const key = ring.join(',');
  let pts = ringCache.get(key);
  if (pts) return pts;
  const arcs = ringArcs();
  pts = [];
  for (const idx of ring) {
    const a = arcs[idx < 0 ? ~idx : idx];
    const seq = idx < 0 ? reversePairs(a) : a;
    const from = (pts.length >= 2 && pts[pts.length - 2] === seq[0] && pts[pts.length - 1] === seq[1]) ? 2 : 0;
    for (let i = from; i < seq.length; i++) pts.push(seq[i]);
  }
  ringCache.set(key, pts);
  return pts;
}

let _arcs = null;
function ringArcs() {
  if (!_arcs) _arcs = YAYLAR.map(decodeArc);
  return _arcs;
}

function reversePairs(a) {
  const out = new Array(a.length);
  for (let i = 0, k = a.length - 2; i < a.length; i += 2, k -= 2) {
    out[i] = a[k]; out[i + 1] = a[k + 1];
  }
  return out;
}

function ringContains(ring, qx, qy) {
  const p = ringPoints(ring);
  let inside = false;
  for (let i = 0, j = p.length - 2; i < p.length; j = i, i += 2) {
    const xi = p[i], yi = p[i + 1], xj = p[j], yj = p[j + 1];
    if ((yi > qy) !== (yj > qy) && qx < ((xj - xi) * (qy - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

// ------------------------------------------------------------- etiketleme --
//
// Aynı ilçedeki panolar haritada birbirinin üstüne düşer. Eski çözüm etiketi
// sırayla bir yukarı bir aşağı kaydırmaktı; 112 panoda bu hiçbir şey çözmez.
// Buradaki kural: etiketler ÖNCELİK SIRASINA göre yerleştirilir ve yer yoksa
// yazılmaz. Seçili pano ile kritik/acil seviyeler her zaman yazılır, gerekirse
// daha az önemli bir etiketi iterek.

const ADAYLAR = [
  [ 1, 0, 'start',  0.32], [-1, 0, 'end',   0.32],
  [ 1,-1, 'start', -0.55], [ 1, 1, 'start', 1.15],
  [-1,-1, 'end',   -0.55], [-1, 1, 'end',   1.15],
  [ 0,-1, 'middle',-0.85], [ 0, 1, 'middle', 1.5],
];

function layoutLabels(items, view, px, always, obstacles) {
  const placed = [];
  const hit = (r) => placed.some((q) =>
    r.x < q.x + q.w && r.x + r.w > q.x && r.y < q.y + q.h && r.y + r.h > q.y);

  // İşaretlerin kendisi de birer engeldir: etiket başka bir panonun noktasının
  // üstüne yazılmasın. İl adları da engeldir - "DENIZLI-MERKEZ-05" yazısının
  // "Denizli" yazısının üstüne binmesi ikisini de okunmaz yapar.
  for (const it of items) {
    placed.push({ x: it.x - px * 7, y: it.y - px * 7, w: px * 14, h: px * 14 });
  }
  for (const o of obstacles || []) placed.push(o);

  const out = [];
  for (const it of items) {
    const fs = px * 11.5;
    const w = it.text.length * fs * 0.55;
    const hgt = fs * 1.18;
    const zorunlu = always.has(it.key);
    let put = null;
    for (const [dx, dy, anchor, dyf] of ADAYLAR) {
      const ax = it.x + dx * px * 11;
      const ay = it.y + dy * px * 11 + fs * dyf;
      const box = {
        x: anchor === 'end' ? ax - w : (anchor === 'middle' ? ax - w / 2 : ax),
        y: ay - hgt * 0.78, w, h: hgt,
      };
      // Görünümün dışına taşan etiket yazılmaz.
      if (box.x < view.x || box.x + box.w > view.x + view.w
          || box.y < view.y || box.y + box.h > view.y + view.h) continue;
      if (!hit(box)) { put = { x: ax, y: ay, anchor, box }; break; }
    }
    if (!put && zorunlu) {
      const ax = it.x + px * 11, ay = it.y + fs * 0.32;
      put = { x: ax, y: ay, anchor: 'start', box: { x: ax, y: ay - hgt * 0.78, w, h: hgt } };
    }
    if (put) { placed.push(put.box); out.push({ it, put, fs }); }
  }
  return out;
}

// -------------------------------------------------------------------- api --

/**
 * @param {object} o  { onSelect(panelKey) }
 */
export function createMap(o = {}) {
  const g = build();

  // Açılış görünümü filonun bulunduğu bölge; veri gelince daraltılır.
  const base = { x: X(25.4), y: Y(42.3), w: X(45.2) - X(25.4), h: Y(35.6) - Y(42.3) };

  const svg = s('svg.map-svg', {
    viewBox: `${base.x} ${base.y} ${base.w} ${base.h}`,
    role: 'img',
    'aria-label': 'Filo haritası · Türkiye il sınırları',
  });

  svg.appendChild(s('rect.map-sea', { x: base.x - base.w, y: base.y - base.h,
    width: base.w * 3, height: base.h * 3 }));

  const gGrid = s('g.map-grid-g');
  const gLand = s('g.map-land-g');
  const gHi = s('g.map-hi-g');
  const gBorder = s('g.map-border-g');
  const gProvLbl = s('g.map-prov-lbl');
  const gDots = s('g.map-dots');
  const gLbl = s('g.map-lbl');
  const gScale = s('g.map-scale');
  svg.append(gGrid, gLand, gHi, gBorder, gProvLbl, gDots, gLbl, gScale);

  // enlem/boylam ızgarası · tam derecelerde, çok sessiz
  for (let lon = 26; lon <= 45; lon++) {
    gGrid.appendChild(s('line', { x1: X(lon), y1: Y(35.5), x2: X(lon), y2: Y(42.5) }));
  }
  for (let lat = 36; lat <= 42; lat++) {
    gGrid.appendChild(s('line', { x1: X(25.5), y1: Y(lat), x2: X(45.2), y2: Y(lat) }));
  }

  for (const il of g.iller) {
    const p = s('path.map-prov', { d: il.d, dataset: { il: il.ad } });
    p.appendChild(s('title', {}, il.ad));
    gLand.appendChild(p);
  }
  gBorder.appendChild(s('path.map-inner', { d: g.dIc }));
  gBorder.appendChild(s('path.map-coast', { d: g.dDis }));

  const wrap = h('div.map-wrap', svg);

  let panels = [];
  // Seçim bir KÜMEdir: Ctrl ile birden çok pano işaretlenebilir. `birincil`
  // künyesi açık olandır ve haritada beyaz konturla ayrılır.
  let secililer = new Set();
  let birincil = null;
  let fleetBox = null;
  let fleetIller = new Set();
  let upp = 1;    // kullanıcı birimi / ekran pikseli
  // Canlı akış saniyede bir çerçeve gönderir. İşaret katmanı ancak GÖRÜNEN bir
  // şey değişince yeniden kurulur: pano listesi, bir seviye ya da seçim. Aksi
  // hâlde her çerçevede 112 SVG grubu yeniden yaratılır, imlecin altındaki
  // ipucu kapanır ve harita hafifçe titrer.
  let dotSig = null;
  let ilSig = null;
  let fitted = false;   // ilk veri gelince filo bölgesine bir kez yakınlaşılır
  let gorunurPanolar = null;   // filtre sonrası çizilen alt küme

  /** Verilen panoların kapsayan kutusu; hiçbiri konumlu değilse null. */
  function kutu(list) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const p of list || []) {
      if (!p.lat || !p.lon) continue;
      const px = X(p.lon), py = Y(p.lat);
      if (px < x0) x0 = px; if (px > x1) x1 = px;
      if (py < y0) y0 = py; if (py > y1) y1 = py;
    }
    if (!Number.isFinite(x0)) return null;
    // Tek pano kaldıysa kutu sıfır boyutlu olur; ilçe ölçeğine aç.
    const w = Math.max(x1 - x0, 300), hgt = Math.max(y1 - y0, 300);
    return { x: (x0 + x1) / 2 - w / 2, y: (y0 + y1) / 2 - hgt / 2, w, h: hgt };
  }

  const zp = zoomPan(svg, {
    base,
    minKat: 0.82,
    maxKat: 260,
    limit: { x: g.bbox.x - 400, y: g.bbox.y - 400, w: g.bbox.w + 800, h: g.bbox.h + 800 },
    onChange: () => redrawScaled(),
  });

  // ----------------------------------------------------------- ölçeklenen --

  function redrawScaled() {
    // Kutu ölçümü yerleşimi zorlar; kare başına bir kez okunur.
    const r = svg.getBoundingClientRect();
    const v = zp.view();
    upp = (!r.width || !r.height) ? v.w / 900 : Math.max(v.w / r.width, v.h / r.height);

    // pano işaretleri: ekran pikselinde sabit boy
    for (const node of gDots.children) {
      const x = Number(node.dataset.x), y = Number(node.dataset.y);
      node.setAttribute('transform', `translate(${x} ${y}) scale(${upp})`);
    }

    // il adları yalnız yeterince yaklaşıldığında; ülke görünümünde 81 ad gürültü
    const showProv = v.w < base.w * 0.75;
    gProvLbl.style.display = showProv ? '' : 'none';
    if (showProv) {
      for (const t of gProvLbl.children) t.setAttribute('font-size', String(upp * 13));
    }

    drawLabels(v);
    drawScaleBar(v, r.width > 0);
  }

  function drawLabels(v) {
    while (gLbl.firstChild) gLbl.removeChild(gLbl.firstChild);

    // 112 panonun hepsini aynı anda etiketlemek haritayı okunmaz yapar; çakışma
    // testinden geçseler bile göz bir yazı duvarı görür.
    //
    // Ölçüt yakınlaştırma KATI değil, ekrandaki YOĞUNLUKtur: görünen alanda kaç
    // pano var? Az sayıda ise hepsi yazılır. Kalabalıksa yalnız seçili pano ile
    // uyarı ve üstü yazılır - operatörün aradığı zaten onlardır, gerisi için
    // nokta ve yanındaki tablo var. Böylece kural filo 12 panoya da inse
    // 1200 panoya da çıksa aynı şekilde çalışır.
    const tum = (gorunurPanolar || panels).filter((p) => p.lat && p.lon).map((p) => ({
      key: p.panel_key, text: p.panel_key,
      x: X(p.lon), y: Y(p.lat),
      rank: fmt.sevRank(p.severity),
      delta: Math.abs(Number(p.theta_delta_7d) || 0),
    }));
    const gorunen = tum.filter((i) =>
      i.x >= v.x && i.x <= v.x + v.w && i.y >= v.y && i.y <= v.y + v.h).length;
    const kalabalik = gorunen > 22;

    const items = tum
      .filter((i) => !kalabalik || i.rank >= 2 || secililer.has(i.key))
      .sort((a, b) => (secililer.has(b.key) - secililer.has(a.key))
        || b.rank - a.rank || b.delta - a.delta);

    // İl adları yerlerini önce kapar.
    const obst = [];
    if (gProvLbl.style.display !== 'none') {
      for (const tnode of gProvLbl.children) {
        const tx = Number(tnode.getAttribute('x')), ty = Number(tnode.getAttribute('y'));
        const w = (tnode.textContent || '').length * upp * 13 * 0.55;
        obst.push({ x: tx - w / 2, y: ty - upp * 11, w, h: upp * 16 });
      }
    }

    const always = new Set(items.filter((i) => i.rank >= 3 || secililer.has(i.key)).map((i) => i.key));
    for (const { it, put, fs } of layoutLabels(items, v, upp, always, obst)) {
      const t = s('text.map-lbl-t' + (secililer.has(it.key) ? '.sel' : ''), {
        x: put.x, y: put.y, 'text-anchor': put.anchor, 'font-size': fs,
      }, it.text);
      gLbl.appendChild(t);
    }
  }

  function drawScaleBar(v, ready) {
    while (gScale.firstChild) gScale.removeChild(gScale.firstChild);
    if (!ready) return;
    const wantKm = (v.w * KM_PER_UNIT) * 0.22;
    const nice = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];
    const km = nice.find((n) => n >= wantKm) || 1000;
    const len = km / KM_PER_UNIT;
    const pad = upp * 14;
    const x1 = v.x + v.w - pad;
    const x0 = x1 - len;
    const yb = v.y + v.h - pad;
    gScale.appendChild(s('path.map-scale-bar', {
      d: `M${x0} ${yb - upp * 5}V${yb}H${x1}V${yb - upp * 5}`,
    }));
    gScale.appendChild(s('text.map-scale-t', {
      x: (x0 + x1) / 2, y: yb - upp * 9, 'text-anchor': 'middle', 'font-size': upp * 11,
    }, `${km} km`));
  }

  // -------------------------------------------------------------- panolar --

  function markerFor(p) {
    // Renk tek ayırt edici değil: her seviye ayrı bir şekil.
    const meta = fmt.sevMeta(p.severity);
    const rank = fmt.sevRank(p.severity);
    const isim = 'g.map-dot'
      + (secililer.has(p.panel_key) ? '.sel' : '')
      + (p.panel_key === birincil ? '.bir' : '');
    const g2 = s(isim, { dataset: { panel: p.panel_key, x: X(p.lon), y: Y(p.lat) } });
    g2.appendChild(s('circle.halo', { cx: 0, cy: 0, r: 7 + rank * 2.4, fill: meta.color }));
    let shape;
    if (rank === 0) {
      shape = s('circle', { cx: 0, cy: 0, r: 4.2, fill: meta.color });
    } else if (rank === 1) {
      shape = s('circle', { cx: 0, cy: 0, r: 4.6, fill: 'none', stroke: meta.color, 'stroke-width': 2.4 });
    } else if (rank === 4) {
      shape = s('rect', { x: -4.6, y: -4.6, width: 9.2, height: 9.2, fill: meta.color });
    } else {
      shape = s('path', {
        d: 'M0 -5.6L5.4 3.8L-5.4 3.8Z',
        fill: rank === 3 ? meta.color : 'none', stroke: meta.color, 'stroke-width': 2.2,
      });
    }
    shape.setAttribute('class', 'pin');
    g2.appendChild(shape);
    g2.appendChild(s('title', {}, [
      `${p.panel_key} · ${p.name || ''}`,
      `${p.dso || ''} ${p.site || ''}`,
      `${meta.label} · sağlık ${fmt.num(p.health_index, 0)}`,
      `θ maks ${fmt.num(p.theta_max, 2)} K · Δ7g ${fmt.signed(p.theta_delta_7d, 2)} K`,
    ].join('\n')));
    // Olayı da geçiriyoruz: Ctrl/Cmd basılıysa çoklu seçim.
    if (o.onSelect) g2.addEventListener('click', (ev) => o.onSelect(p.panel_key, ev));
    return g2;
  }

  /**
   * @param {Array}  list     filonun TAMAMI (il vurgusu ve çerçeve bundan)
   * @param {string} sel      seçili pano
   * @param {Set}    gorunur  çizilecek pano anahtarları; yoksa hepsi
   */
  function setPanels(list, sel, gorunur) {
    panels = list || [];
    secililer = sel instanceof Set ? sel : new Set(sel ? [sel] : []);
    birincil = [...secililer][secililer.size - 1] || null;
    // İl vurgusu ve açılış çerçevesi filoya bakar, filtreye değil: kullanıcı
    // süzdükçe haritanın zıplaması istenmez.
    const gorunurler = gorunur ? panels.filter((p) => gorunur.has(p.panel_key)) : panels;
    gorunurPanolar = gorunurler;

    const keys = panels.map((p) => p.panel_key).join(',');
    const changed = keys !== ilSig;
    ilSig = keys;

    if (changed) {
      // Filonun kapsadığı iller · zeminde bir ton açık çizilir
      fleetIller = new Set();
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (const p of panels) {
        if (!p.lat || !p.lon) continue;
        const il = provinceAt(p.lon, p.lat);
        if (il) fleetIller.add(il);
        const px = X(p.lon), py = Y(p.lat);
        if (px < x0) x0 = px; if (px > x1) x1 = px;
        if (py < y0) y0 = py; if (py > y1) y1 = py;
      }
      fleetBox = Number.isFinite(x0) ? { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } : null;

      while (gHi.firstChild) gHi.removeChild(gHi.firstChild);
      while (gProvLbl.firstChild) gProvLbl.removeChild(gProvLbl.firstChild);
      for (const il of g.iller) {
        if (fleetIller.has(il.ad)) gHi.appendChild(s('path.map-prov-hi', { d: il.d }));
        gProvLbl.appendChild(s('text.map-prov-t' + (fleetIller.has(il.ad) ? '.on' : ''), {
          x: X(il.lon), y: Y(il.lat), 'text-anchor': 'middle', 'font-size': 13,
        }, il.ad));
      }
      if (fleetBox && !fitted) {
        fitted = true;
        zp.goto(fleetBox, 0.16);
      }
    }

    const sig = gorunurler.map((p) => p.panel_key + p.severity).join(',')
      + '#' + [...secililer].sort().join(',') + '#' + (birincil || '');
    if (sig === dotSig) return;
    dotSig = sig;

    while (gDots.firstChild) gDots.removeChild(gDots.firstChild);
    // En ağır seviye en üste çizilsin: bir acil, bir bilgi noktasının altında
    // kalmamalı.
    const order = gorunurler.slice().sort((a, b) => fmt.sevRank(a.severity) - fmt.sevRank(b.severity));
    for (const p of order) {
      if (!p.lat || !p.lon) continue;
      gDots.appendChild(markerFor(p));
    }
    redrawScaled();
  }

  const onResize = () => redrawScaled();
  window.addEventListener('resize', onResize);

  return {
    el: wrap,
    svg,
    setPanels,
    /** Süzgeç etkinse SÜZÜLEN panolara sığdırır: "şunları göster" dedikten
     *  sonra haritanın hâlâ tüm filoyu çerçevelemesi cevapsız bir hareket. */
    fitFleet() {
      const hedef = (gorunurPanolar && gorunurPanolar.length < panels.length
        ? kutu(gorunurPanolar) : null) || fleetBox;
      if (hedef) zp.goto(hedef, 0.16); else zp.fit();
    },
    fitCountry() { zp.goto(g.bbox, 0.03); },
    zoomIn() { zp.zoomBy(1.45); },
    zoomOut() { zp.zoomBy(1 / 1.45); },
    /**
     * Panoyu ortala. `yakinlas` ise ilçe ölçeğine iner - sokak ölçeğine değil:
     * operatör tıkladığı panonun komşularını da görmek ister, tek bir noktayla
     * baş başa kalmak istemez. Zaten daha yakındaysa ölçeğe dokunmayız.
     */
    gotoPanel(key, yakinlas = true) {
      const p = panels.find((q) => q.panel_key === key);
      if (!p || !p.lat && !p.lon) return;
      const px = X(p.lon), py = Y(p.lat);
      const v = zp.view();
      const ILCE = 430;            // ~48 km, bir ilçe ve çevresi
      const w = yakinlas ? Math.min(v.w, ILCE) : v.w;
      const hgt = w * (v.h / v.w);
      zp.goto({ x: px - w / 2, y: py - hgt / 2, w, h: hgt }, 0);
    },
    redraw: redrawScaled,
    /** Tam ekrana girip çıkarken: öğe büyüdü, çerçeve oranı ona uysun. */
    refit() { zp.refit(); redrawScaled(); },
    destroy() { window.removeEventListener('resize', onResize); zp.destroy(); },
  };
}
