// PANO GÖZ · dijital ikiz.
//
// TEDAŞ-MLZ/2003-06.B, EK-II/14 çiziminin ön görünüşü, elle yazılmış SVG.
// Ölçü birimi milimetredir ve gerçek panonun ölçüleridir: 1600 x 1500 x 450 mm.
// SVG'nin y ekseni aşağı doğrudur, panonun y ekseni yukarı; dönüşüm Y() ile
// yapılır ki yazılar ters dönmesin.
//
// Çizimdeki her parça belgeye dayanır:
//   * dış gövde 1600x1500x450, dahili tip, IP2X, Form 2B
//   * çatıda 4 giriş bara boğazı (Madde 2.2.8.6 Not:1) - AG giriş kesicisi YOKTUR
//   * bara bölmesi: faz başına 2x(100x10) mm² kalaylı elektrolitik bakır + aynı
//     kesitte nötr, terminaller arası 185 mm
//   * 12 DSYA kolonu: 5 x 250 A (1 Boy) + 5 x 400 A (2 Boy) + 2 Yedek (boş, taralı)
//   * 48 pabuçluk çıkış sırası
//   * altta "En az 400mm" serbest kablo bölmesi, taban tamamen açık
//   * sağda ölçü kolonu: analizör, sayaç ve "Modem" bölmesi (Madde 2.2.8.1.iv)
//
// Kaplama (overlay): ölçümü desteklenen bağlantılar θ'ya göre cividis renkli, seviyeye göre
// büyüyen noktalar; 9 cihaz kendi glifiyle; bara ve çatı bağlantıları YALNIZCA
// kontur ve "izlenmiyor — kesinti gerektirir" etiketiyle. Sahip olmadığımız
// kapsamı varmış gibi göstermek, güvenilirliği kaybetmenin en hızlı yoludur.

import { s, h } from './dom.js';
import { thetaColor, sevMeta, sevRank, num, CONDUCTOR_TR } from './fmt.js';

export const PANEL_W = 1600;
export const PANEL_H = 1500;
export const PANEL_D = 450;

const Y = (mm) => PANEL_H - mm;

const FEEDERS = [];
for (let i = 0; i < 12; i++) {
  FEEDERS.push({
    index: i + 1,
    x: 88 + i * 100,
    rated: i < 5 ? 250 : 400,
    boy: i < 5 ? '1 Boy' : '2 Boy',
    spare: i >= 10,
  });
}

const DOT_R = { BILGI: 9, IZLE: 10, UYARI: 12, KRITIK: 14, ACIL: 16 };

/** Cihaz glifleri: her tür farklı bir şekil, renk tek ayırt edici değil. */
function deviceGlyph(kind) {
  if (kind === 'TC') return 'clip';
  if (kind === 'TN-IR') return 'ir';
  if (kind === 'PD') return 'pd';
  return 'gw';
}

function txt(x, y, text, cls, extra) {
  return s('text.' + (cls || 'tw-txt'),
    Object.assign({ x, y, 'text-anchor': 'middle', 'dominant-baseline': 'middle' }, extra || {}),
    text);
}

/**
 * @param {object} o
 *   joints: [{key,label,zone,conductor,feeder_index,x_mm,y_mm,monitored,theta_k,temp_c,severity}]
 *   devices: [{key,kind,label,x_mm,y_mm,online,battery_pct,faults}]
 *   selected: seçili bağlantı anahtarı
 *   onJoint(key), onDevice(key)
 */
export function renderTwin(o = {}) {
  const joints = o.joints || [];
  const devices = o.devices || [];
  const svg = s('svg', {
    viewBox: `-110 -60 ${PANEL_W + 330} ${PANEL_H + 180}`,
    role: 'img',
    'aria-label': 'TEDAŞ 1600 kVA AG dağıtım panosu dijital ikizi',
  });

  // taralı desen (Yedek çıkışlar)
  const defs = s('defs');
  const pat = s('pattern', {
    id: 'hatch', width: 22, height: 22, patternUnits: 'userSpaceOnUse',
    patternTransform: 'rotate(45)',
  });
  pat.appendChild(s('rect', { width: 22, height: 22, fill: 'var(--tw-hatch)' }));
  pat.appendChild(s('line', { x1: 0, y1: 0, x2: 0, y2: 22, stroke: 'var(--tw-hatch-line)', 'stroke-width': 7 }));
  defs.appendChild(pat);
  const fov = s('linearGradient', { id: 'fov', x1: '0', y1: '1', x2: '0', y2: '0' });
  fov.appendChild(s('stop', { offset: '0%', 'stop-color': 'var(--accent)', 'stop-opacity': '0.24' }));
  fov.appendChild(s('stop', { offset: '100%', 'stop-color': 'var(--accent)', 'stop-opacity': '0.02' }));
  defs.appendChild(fov);
  svg.appendChild(defs);

  // ---------------------------------------------------------------- gövde --
  svg.appendChild(s('rect.tw-enclosure', { x: 0, y: 0, width: PANEL_W, height: PANEL_H, rx: 8 }));

  // ---------------------------------------------------------------- çatı ---
  svg.appendChild(s('rect.tw-zone-alt', { x: 8, y: Y(1500) + 4, width: PANEL_W - 16, height: 96 }));
  // Çatı etiketi iki satır ve SOL sütunda: eskiden "izlenmiyor" sözcüğü
  // boğazların tam üstüne, çatı şeridinin dışına düşüyordu ve L1 boğazıyla
  // çakışıyordu. Bölgenin durumu bölgenin adının altında yazar.
  svg.appendChild(txt(26, Y(1462), 'Çatı boğazı', 'tw-txt-sm', { 'text-anchor': 'start', x: 26 }));
  svg.appendChild(txt(26, Y(1432), '4 bara boğazı · izlenmiyor', 'tw-txt-xs',
    { 'text-anchor': 'start', x: 26, fill: 'var(--tw-unmon)' }));
  const stubX = [485, 610, 735, 860];
  ['L1', 'L2', 'L3', 'N'].forEach((c, i) => {
    svg.appendChild(s('rect', {
      x: stubX[i] - 26, y: Y(1500) + 4, width: 52, height: 96, rx: 4,
      fill: i === 3 ? 'var(--tw-stub-n)' : 'var(--tw-stub)', stroke: 'var(--tw-stub-line)', 'stroke-width': 2,
    }));
    svg.appendChild(txt(stubX[i], Y(1425), c, 'tw-txt-sm'));
  });
  svg.appendChild(txt(1180, Y(1452), 'AG giriş kesicisi YOK · direk bara bağlantı (Madde 2.2.10.2.vi)',
    'tw-txt-sm', { 'text-anchor': 'end', x: PANEL_W - 26 }));

  // -------------------------------------------------------- bara bölmesi --
  svg.appendChild(s('rect.tw-zone', { x: 26, y: Y(1392), width: PANEL_W - 52, height: 1392 - 995 }));
  svg.appendChild(txt(26, Y(1360), 'Bara bölmesi · Form 2B', 'tw-txt', { 'text-anchor': 'start', x: 42 }));

  const bars = [
    { y: 1228, cls: 'tw-bar-l1', name: 'L1' },
    { y: 1164, cls: 'tw-bar-l2', name: 'L2' },
    { y: 1100, cls: 'tw-bar-l3', name: 'L3' },
    { y: 1036, cls: 'tw-bar-n', name: 'N' },
  ];
  for (const b of bars) {
    // faz başına İKİ bar - 2x(100x10) mm², kenardan bakışta iki dilim
    // Baralar ölçü kolonunun önünde biter (x = 1230): gerçek panoda da bara
    // bölmesi ile ölçü kolonu ayrı bölmelerdir (Form 2B).
    svg.appendChild(s('rect.' + b.cls, { x: 120, y: Y(b.y) - 14, width: 1110, height: 11, rx: 2 }));
    svg.appendChild(s('rect.' + b.cls, { x: 120, y: Y(b.y) + 3, width: 1110, height: 11, rx: 2 }));
    svg.appendChild(txt(96, Y(b.y), b.name, 'tw-txt-sm'));
  }
  svg.appendChild(txt(1230, Y(1300),
    '2×(100×10) mm² kalaylı Cu · faz başına · N aynı kesit · 2312 A · 38 kA / 80 kA tepe',
    'tw-txt-sm', { 'text-anchor': 'end', x: 1230 }));

  // --------------------------------------------------------- DSYA kolonlar --
  for (const f of FEEDERS) {
    const top = f.rated === 400 ? 995 : 960;
    const bot = 585;
    const cls = f.spare ? 'tw-spare' : (f.rated === 400 ? 'tw-dsya-400' : 'tw-dsya');
    svg.appendChild(s('rect.' + cls, {
      x: f.x - 42, y: Y(top), width: 84, height: top - bot, rx: 4,
    }));
    if (!f.spare) {
      // sigorta bıçakları
      for (let k = 0; k < 3; k++) {
        svg.appendChild(s('rect', {
          x: f.x - 30 + k * 21, y: Y(top - 30), width: 15, height: (top - bot) - 90, rx: 2,
          fill: 'var(--tw-slot)', stroke: 'var(--tw-cell-line)', 'stroke-width': 1.5,
        }));
      }
      // TEK satır. Üç satır yazınca alttaki ikisi pabuç sırası bölmesinin
      // altında kalıyordu (bölme dikdörtgeni sonra çizilir ve üstünü örter)
      // ve y = 500 mm'deki pabuç noktalarıyla çakışıyordu. "1 Boy / 2 Boy"
      // bilgisi aşağıdaki kolon başlığına taşındı.
      svg.appendChild(txt(f.x, Y(bot - 20), `Ç${f.index} · ${f.rated} A`, 'tw-txt-xs'));
    } else {
      svg.appendChild(txt(f.x, Y((top + bot) / 2), 'Yedek', 'tw-txt-sm'));
      svg.appendChild(txt(f.x, Y(bot - 20), 'boş', 'tw-txt-xs', { opacity: 0.75 }));
    }
  }
  // Sağa hizalı: solda "N" bara etiketi duruyor ve sola hizalı bir başlık onun
  // üstüne biniyordu. Üstteki bara künyesiyle aynı sağ kenara hizalanınca ikisi
  // tek bir açıklama sütunu oluşturuyor.
  svg.appendChild(txt(1230, Y(1012), '12 DSYA çıkış · 5×250 A (1 Boy) + 5×400 A (2 Boy) + 2 yedek',
    'tw-txt-xs', { 'text-anchor': 'end', x: 1230 }));

  // ------------------------------------------------------------ pabuç sırası
  svg.appendChild(s('rect.tw-zone', { x: 26, y: Y(545), width: PANEL_W - 52, height: 90 }));
  // Pabuç noktaları x = 58..1018 arasında duruyor; bölmenin sağ ucu (x > 1030)
  // boştur. Etiket oraya yazılır ve gövde kenarını (x = 1600) aşmaz - eskiden
  // x = 1580'den başlayıp çerçeveden taşıyordu.
  svg.appendChild(txt(1548, Y(526), '48 pabuçluk çıkış sırası',
    'tw-txt-xs', { 'text-anchor': 'end', x: 1548 }));
  svg.appendChild(txt(1548, Y(496), `${joints.filter((j) => j.measurement_supported === true).length} TC noktası · IR ayrımı doğrulanmadı`,
    'tw-txt-xs', { 'text-anchor': 'end', x: 1548, opacity: 0.75 }));

  // --------------------------------------------------- alt kablo bölmesi ---
  svg.appendChild(s('rect.tw-zone-alt', {
    x: 26, y: Y(400), width: PANEL_W - 52, height: 400 - 20,
    'stroke-dasharray': '0',
  }));
  // taban tamamen açık - kesik çizgi (Madde 2.2.8.6 Not:2)
  svg.appendChild(s('line', {
    x1: 26, y1: Y(20), x2: PANEL_W - 26, y2: Y(20),
    stroke: 'var(--accent)', 'stroke-width': 3, 'stroke-dasharray': '18 12',
  }));
  // Gövdenin alt kenarı y = 0 mm'dedir; yazı oraya konunca çerçeve çizgisinin
  // tam üstüne biniyordu. Kesik çizginin hemen üstüne alındı.
  svg.appendChild(txt(PANEL_W / 2, Y(42), 'taban tamamen açık · kablo kanalına bakar',
    'tw-txt-xs', { fill: 'var(--accent)' }));

  // "En az 400 mm" ölçü oku
  const dimX = 1450;
  svg.appendChild(s('line.tw-dim', { x1: dimX, y1: Y(400), x2: dimX, y2: Y(20) }));
  svg.appendChild(s('line.tw-dim', { x1: dimX - 16, y1: Y(400), x2: dimX + 16, y2: Y(400) }));
  svg.appendChild(s('line.tw-dim', { x1: dimX - 16, y1: Y(20), x2: dimX + 16, y2: Y(20) }));
  // Ok x = 1450'de; yazı +100 ile 1550'ye kayınca gövde kenarını (1600) aşıyor
  // ve panonun dışına taşıyordu. Ok ile gövde kenarı arasındaki boşluğa sığar.
  svg.appendChild(txt(dimX + 66, Y(210), 'En az 400 mm', 'tw-dim-txt'));

  // PE / topraklama barası
  svg.appendChild(s('rect', {
    x: 60, y: Y(250), width: 1340, height: 16, rx: 3, fill: 'var(--tw-pe)', stroke: 'var(--tw-pe-line)',
    'stroke-width': 2,
  }));
  svg.appendChild(txt(70, Y(285), 'PE barası · M12 paslanmaz saplama (Madde 2.2.6.2.iii)',
    'tw-txt-sm', { 'text-anchor': 'start', x: 70 }));

  // ------------------------------------------------------- ölçü kolonu -----
  svg.appendChild(s('line.tw-inner', { x1: 1252, y1: Y(1392), x2: 1252, y2: Y(300) }));
  const bay = (y0, y1, label, sub) => {
    svg.appendChild(s('rect.tw-zone', { x: 1268, y: Y(y1), width: 300, height: y1 - y0 }));
    svg.appendChild(txt(1418, Y(y0 + 44), label, 'tw-txt-sm'));
    if (sub) svg.appendChild(txt(1418, Y(y0 + 16), sub, 'tw-txt-sm', { opacity: 0.7 }));
  };
  bay(1180, 1330, 'Enerji analizörü', 'MPR-53CS · RS-485');
  bay(1020, 1160, 'Sayaç / ölçü', 'CT 2500/5 · yalnız giriş');
  bay(880, 1000, 'Modem bölmesi', 'Madde 2.2.8.1.iv');
  bay(700, 860, 'İç ihtiyaç', '10 A priz · 6 A gG');
  // anten çıkışı
  svg.appendChild(s('line', { x1: 1568, y1: Y(985), x2: 1620, y2: Y(985), stroke: 'var(--accent)', 'stroke-width': 3 }));
  svg.appendChild(s('path', {
    d: `M1620 ${Y(985)} l0 -60 m-18 22 a26 26 0 0 1 36 0 m-52 -20 a44 44 0 0 1 68 0`,
    fill: 'none', stroke: 'var(--accent)', 'stroke-width': 3,
  }));
  // Anten sembolü x = 1586..1654, y = 455..515 arasını kaplıyor. Etiket sola
  // hizalıyken hem sembolün hem gövde kenarının üstüne biniyordu; sağa hizalı
  // ve sembolün üstünde duruyor.
  svg.appendChild(txt(1800, Y(1070), 'sızdırmaz anten çıkışı', 'tw-txt-xs',
    { 'text-anchor': 'end', x: 1800, fill: 'var(--accent)' }));

  // dış ölçüler
  svg.appendChild(txt(PANEL_W / 2, Y(PANEL_H) - 34, `1600 × 1500 × 450 mm · dahili tip · IP2X`, 'tw-txt-lg'));

  // -------------------------------------------------- izlenmeyen bağlantılar
  const unmonitored = joints.filter((j) => j.zone !== 'bottom');
  const gUn = s('g');
  for (const j of unmonitored) {
    if (!j.x_mm && !j.y_mm) continue;
    const c = s('circle.tw-unmon', { cx: j.x_mm, cy: Y(j.y_mm), r: 9 });
    c.appendChild(s('title', {}, `${j.label || j.key} · izlenmiyor (kesinti gerektirir)`));
    gUn.appendChild(c);
  }
  svg.appendChild(gUn);
  if (unmonitored.length) {
    // Tek etiket yeter: çatı boğazlarının durumu zaten çatı başlığında yazıyor.
    // İkinci kopya L1 boğazının üstüne düşüyordu.
    svg.appendChild(txt(PANEL_W / 2, Y(1330), 'izlenmiyor — kesinti gerektirir',
      'tw-txt-sm', { fill: 'var(--tw-unmon)' }));
  }

  // ------------------------------------------------------ izlenen bağlantılar
  const gJ = s('g');
  for (const j of joints) {
    if (j.zone !== 'bottom') continue;
    const sev = j.severity || 'BILGI';
    const r = DOT_R[sev] || 9;
    const g = s('g.tw-joint-g', { dataset: { joint: j.key } });
    const dot = s('circle.tw-joint' + (o.selected === j.key ? '.sel' : ''), {
      cx: j.x_mm, cy: Y(j.y_mm), r,
      fill: j.measurement_supported === false ? 'none' : thetaColor(j.theta_k),
    });
    dot.appendChild(s('title', {}, [
      `${j.label || j.key}`,
      j.measurement_supported === false ? 'B1: bağımsız IR ölçümü doğrulanmadı' : 'TC ölçüm noktası',
      `θ = ${num(j.theta_k, 2)} K`,
      `T = ${num(j.temp_c, 1)} °C`,
      j.measurement_supported === false ? 'Ölçüm yok' : `${sevMeta(sev).label}`,
    ].join('\n')));
    g.appendChild(dot);
    if (sevRank(sev) >= 2) {
      // renk tek başına anlam taşımasın: uyarı ve üstü için nokta üstünde şekil
      const yy = Y(j.y_mm) - r - 12;
      const mark = sev === 'ACIL'
        ? s('rect', { x: j.x_mm - 8, y: yy - 8, width: 16, height: 16, fill: 'var(--sev-acil)' })
        : s('path', {
            d: `M${j.x_mm} ${yy - 10} L${j.x_mm + 10} ${yy + 8} L${j.x_mm - 10} ${yy + 8} Z`,
            fill: sev === 'KRITIK' ? 'var(--sev-kritik)' : 'none',
            stroke: 'var(--sev-uyari)', 'stroke-width': 3,
          });
      g.appendChild(mark);
    }
    if (o.onJoint) {
      g.style.cursor = 'pointer';
      g.addEventListener('click', () => o.onJoint(j.key));
    }
    gJ.appendChild(g);
  }
  svg.appendChild(gJ);

  // ------------------------------------------------------------- cihazlar --
  const gD = s('g');
  for (const d of devices) {
    const x = d.x_mm || 0, y = Y(d.y_mm || 0);
    const kind = deviceGlyph(d.kind);
    const g = s('g.tw-dev', { dataset: { device: d.key } });
    const offCls = d.online === false ? '.tw-dev-off' : '';

    if (kind === 'clip') {
      g.appendChild(s('path.tw-dev-body' + offCls, {
        d: `M${x - 20} ${y - 16} h40 v32 h-40 z M${x - 20} ${y} h-10 M${x + 20} ${y} h10`,
      }));
    } else if (kind === 'ir') {
      // görüş alanı konisi: pabuç sırasına yukarı bakar
      g.appendChild(s('path', {
        d: `M${x} ${y - 10} L${x - 560} ${Y(470)} L${x + 560} ${Y(470)} Z`,
        fill: 'url(#fov)', stroke: 'none',
      }));
      g.appendChild(s('path.tw-dev-body' + offCls, {
        d: `M${x - 34} ${y + 18} h68 v-26 l-20 -14 h-28 l-20 14 z`,
      }));
    } else if (kind === 'pd') {
      g.appendChild(s('circle.tw-dev-body' + offCls, { cx: x, cy: y, r: 22 }));
      g.appendChild(s('path', {
        d: `M${x} ${y - 22} v-26 m-12 12 a17 17 0 0 1 24 0`,
        fill: 'none', stroke: 'var(--accent)', 'stroke-width': 3,
      }));
    } else {
      g.appendChild(s('rect.tw-dev-body' + offCls, { x: x - 30, y: y - 24, width: 60, height: 48, rx: 5 }));
      g.appendChild(s('path', {
        d: `M${x - 14} ${y + 4} h28 M${x - 14} ${y - 8} h28`,
        stroke: 'var(--accent)', 'stroke-width': 3,
      }));
    }
    g.appendChild(s('title', {}, [
      `${d.key} · ${d.label || ''}`,
      d.online === false ? 'ÇEVRİMDIŞI' : 'çevrimiçi',
      d.battery_pct !== null && d.battery_pct !== undefined ? `pil %${num(d.battery_pct, 0)}` : '',
      d.mount ? 'montaj: ' + d.mount : '',
    ].filter(Boolean).join('\n')));
    if (o.onDevice) {
      g.addEventListener('click', () => o.onDevice(d.key));
    }
    gD.appendChild(g);
  }
  svg.appendChild(gD);

  // cihaz sayısı - jüri noktaları sayarsa 9 bulmalı
  svg.appendChild(txt(120, Y(120), `${devices.length} cihaz`, 'tw-txt-lg',
    { 'text-anchor': 'start', x: 60, fill: 'var(--accent)' }));
  svg.appendChild(txt(60, Y(72), 'gün 1 kiti · yalnızca alt bölme + ölçü kolonu',
    'tw-txt-sm', { 'text-anchor': 'start', x: 60 }));

  return svg;
}

/** SVG'nin altındaki açıklama şeridi. */
export function twinLegend(devices) {
  const glyph = (draw) => {
    const el = s('svg', { viewBox: '0 0 24 24', width: 20, height: 20 });
    draw(el);
    return el;
  };
  const li = (node, text) => h('span.li', node, h('span', { text }));
  const counts = {};
  for (const d of devices || []) counts[d.kind] = (counts[d.kind] || 0) + 1;

  return h('div.twin-legend',
    li(glyph((e) => e.appendChild(s('rect', { x: 4, y: 7, width: 16, height: 10, rx: 2, fill: 'var(--tw-cell)', stroke: 'var(--accent)', 'stroke-width': 2 }))),
      `Isıl kelepçe + ayrılabilir CT (${counts.TC || 0})`),
    li(glyph((e) => e.appendChild(s('path', { d: 'M4 18h16l-5-6h-6z', fill: 'var(--tw-cell)', stroke: 'var(--accent)', 'stroke-width': 2 }))),
      `Termal dizi MLX90640 (${counts['TN-IR'] || 0})`),
    li(glyph((e) => e.appendChild(s('circle', { cx: 12, cy: 13, r: 7, fill: 'var(--tw-cell)', stroke: 'var(--accent)', 'stroke-width': 2 }))),
      `RF + ortam düğümü (${counts.PD || 0})`),
    li(glyph((e) => e.appendChild(s('rect', { x: 4, y: 6, width: 16, height: 12, rx: 2, fill: 'var(--tw-cell)', stroke: 'var(--accent)', 'stroke-width': 2 }))),
      `Ağ geçidi (${counts.GW || 0})`),
    li(glyph((e) => e.appendChild(s('circle', { cx: 12, cy: 12, r: 6, fill: 'none', stroke: 'var(--tw-unmon)', 'stroke-width': 2, 'stroke-dasharray': '3 2' }))),
      'İzlenmiyor · kesinti gerektirir'),
    li(glyph((e) => e.appendChild(s('circle', { cx: 12, cy: 12, r: 6, fill: 'none', stroke: 'var(--accent)', 'stroke-width': 2 }))),
      'Bağımsız IR ölçümü doğrulanmadı'),
    h('span.li',
      h('span.ramp',
        h('span', { text: 'θ 0 K' }),
        h('span.bar', { style: { background: 'linear-gradient(90deg,#00224e,#3b496c,#707173,#a59c74,#e1cc55,#ffea46)' } }),
        h('span', { text: '10 K' }),
        h('span.tiny', { text: '· cividis' }))));
}

export { FEEDERS, CONDUCTOR_TR };
