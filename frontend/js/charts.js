// PANO GÖZ · elle yazılmış Canvas zaman serisi motoru.
//
// Neden kütüphane yok: kurulum hava boşluklu (air-gapped) bir ortamdadır, CDN
// yoktur, npm yoktur. Gereken özellik listesi de kısadır: ortak x ekseni,
// senkron nişangâh, ipucu kutusu, yatay eşik çizgisi, tarihli dikey çizgi ve
// taralı duyarlılık tabanı. Hepsi aşağıda, ~400 satır.
//
// Cihaz piksel oranı (DPR) doğru ele alınır: canvas gerçek piksel sayısında
// ölçeklenir, çizgiler yarım piksel kaydırılır; 4K projeksiyonda da keskindir.

import { num, dateTimeShort, date, time } from './fmt.js';

const PAD = { l: 66, r: 16, t: 22, b: 8 };
const X_AXIS_H = 22;

function niceStep(span, target) {
  const raw = span / Math.max(1, target);
  const mag = Math.pow(10, Math.floor(Math.log10(raw || 1)));
  const norm = raw / mag;
  let step;
  if (norm <= 1) step = 1;
  else if (norm <= 2) step = 2;
  else if (norm <= 2.5) step = 2.5;
  else if (norm <= 5) step = 5;
  else step = 10;
  return step * mag;
}

const TIME_STEPS = [
  60, 300, 900, 1800, 3600, 3 * 3600, 6 * 3600, 12 * 3600,
  86400, 2 * 86400, 7 * 86400, 14 * 86400, 30 * 86400,
];

function timeStep(span, target = 6) {
  const want = span / target;
  for (const s of TIME_STEPS) if (s >= want) return s;
  return TIME_STEPS[TIME_STEPS.length - 1];
}

function timeLabel(ts, step) {
  if (step >= 86400) return date(ts).slice(0, 5);      // gg.AA
  if (step >= 3600) return dateTimeShort(ts).slice(6); // sa:dk (gün kısmı ızgarada)
  return time(ts);
}

export class ChartGroup {
  constructor() {
    this.charts = [];
    this.domain = null;
    this.hoverTs = null;
    this.tip = document.createElement('div');
    this.tip.className = 'chart-tip';
    this.tip.style.display = 'none';
    document.body.appendChild(this.tip);
    this._onResize = () => this.drawAll();
    window.addEventListener('resize', this._onResize);
  }

  add(chart) {
    chart.group = this;
    this.charts.push(chart);
    return chart;
  }

  autoDomain() {
    let lo = Infinity, hi = -Infinity;
    for (const c of this.charts) {
      for (const s of c.series) {
        for (const p of s.points) {
          if (p[0] < lo) lo = p[0];
          if (p[0] > hi) hi = p[0];
        }
      }
    }
    if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) {
      const now = Date.now() / 1000;
      lo = now - 7 * 86400;
      hi = now;
    }
    this.domain = [lo, hi];
    return this.domain;
  }

  setDomain(d) { this.domain = d; }

  drawAll() { for (const c of this.charts) c.draw(); }

  hover(ts, clientX, clientY) {
    this.hoverTs = ts;
    this.drawAll();
    this._showTip(ts, clientX, clientY);
  }

  clearHover() {
    this.hoverTs = null;
    this.tip.style.display = 'none';
    this.drawAll();
  }

  _showTip(ts, cx, cy) {
    const rows = [];
    for (const c of this.charts) {
      for (const s of c.series) {
        if (s.noTip) continue;
        const p = nearest(s.points, ts);
        if (!p) continue;
        rows.push({ color: s.color, label: s.label, value: num(p[1], s.decimals ?? 2), unit: s.unit || c.unit || '' });
      }
    }
    if (!rows.length) { this.tip.style.display = 'none'; return; }
    const t = this.tip;
    while (t.firstChild) t.removeChild(t.firstChild);
    const head = document.createElement('div');
    head.className = 't';
    head.textContent = dateTimeShort(ts);
    t.appendChild(head);
    for (const r of rows) {
      const li = document.createElement('div');
      li.className = 'li';
      const i = document.createElement('i');
      i.style.background = r.color;
      const sp = document.createElement('span');
      sp.textContent = `${r.label}: ${r.value}${r.unit ? ' ' + r.unit : ''}`;
      li.appendChild(i);
      li.appendChild(sp);
      t.appendChild(li);
    }
    t.style.display = 'block';
    const w = t.offsetWidth, hgt = t.offsetHeight;
    let x = cx + 16, y = cy + 14;
    if (x + w > window.innerWidth - 8) x = cx - w - 16;
    if (y + hgt > window.innerHeight - 8) y = window.innerHeight - hgt - 8;
    t.style.left = x + 'px';
    t.style.top = y + 'px';
  }

  destroy() {
    window.removeEventListener('resize', this._onResize);
    if (this.tip.parentNode) this.tip.parentNode.removeChild(this.tip);
    for (const c of this.charts) c.destroy();
    this.charts = [];
  }
}

function nearest(points, ts) {
  if (!points || !points.length) return null;
  let lo = 0, hi = points.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (points[mid][0] < ts) lo = mid + 1; else hi = mid;
  }
  const a = points[Math.max(0, lo - 1)], b = points[lo];
  if (!a) return b;
  if (!b) return a;
  return Math.abs(a[0] - ts) <= Math.abs(b[0] - ts) ? a : b;
}

export class TimeChart {
  /**
   * @param {HTMLCanvasElement} canvas
   * @param {object} opts  {unit, decimals, xAxis, yMin, yMax, yZero, series, hlines, vlines, bands}
   */
  constructor(canvas, opts = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.unit = opts.unit || '';
    this.decimals = opts.decimals ?? 2;
    this.xAxis = !!opts.xAxis;
    this.yMin = opts.yMin;
    this.yMax = opts.yMax;
    this.yZero = opts.yZero !== false;
    this.series = opts.series || [];
    this.hlines = opts.hlines || [];
    this.vlines = opts.vlines || [];
    this.bands = opts.bands || [];
    this.emptyText = opts.emptyText || '';
    this.group = null;
    this._bind();
  }

  _bind() {
    const c = this.canvas;
    this._move = (ev) => {
      const r = c.getBoundingClientRect();
      const x = ev.clientX - r.left;
      const d = this.group && this.group.domain;
      if (!d) return;
      const rect = this._plotRect(r.width, r.height);
      const t = d[0] + ((x - rect.x) / Math.max(1, rect.w)) * (d[1] - d[0]);
      if (this.group) this.group.hover(Math.max(d[0], Math.min(d[1], t)), ev.clientX, ev.clientY);
    };
    this._leave = () => { if (this.group) this.group.clearHover(); };
    c.addEventListener('mousemove', this._move);
    c.addEventListener('mouseleave', this._leave);
  }

  destroy() {
    this.canvas.removeEventListener('mousemove', this._move);
    this.canvas.removeEventListener('mouseleave', this._leave);
  }

  setData(d) {
    if (d.series) this.series = d.series;
    if (d.hlines) this.hlines = d.hlines;
    if (d.vlines) this.vlines = d.vlines;
    if (d.bands) this.bands = d.bands;
    return this;
  }

  _plotRect(w, hgt) {
    const bottom = PAD.b + (this.xAxis ? X_AXIS_H : 0);
    return { x: PAD.l, y: PAD.t, w: Math.max(10, w - PAD.l - PAD.r), h: Math.max(10, hgt - PAD.t - bottom) };
  }

  _yDomain() {
    let lo = Infinity, hi = -Infinity;
    const eat = (v) => {
      if (v === null || v === undefined || Number.isNaN(v)) return;
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    };
    for (const s of this.series) for (const p of s.points) eat(p[1]);
    // Bantlar ölçeği SÜRÜKLEMEZ (scale:false): θ_min düşük yükte 70 K'e çıkar ve
    // ölçeği eline geçirirse asıl büyüklük olan θ ezilir. Bant yine çizilir,
    // sadece eksen sınırını belirlemez.
    for (const b of this.bands) {
      if (b.scale === false) continue;
      for (const p of (b.points || [])) eat(p[1]);
    }
    for (const l of this.hlines) eat(l.value);
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) { lo = 0; hi = 1; }
    if (this.yZero && lo > 0) lo = 0;
    if (hi === lo) { hi = lo + 1; }
    const pad = (hi - lo) * 0.08;
    lo -= pad; hi += pad;
    if (this.yMin !== undefined && this.yMin !== null) lo = this.yMin;
    if (this.yMax !== undefined && this.yMax !== null) hi = this.yMax;
    return [lo, hi];
  }

  draw() {
    const canvas = this.canvas;
    const rect = canvas.getBoundingClientRect();
    const cssW = Math.max(60, rect.width || canvas.clientWidth || 600);
    const cssH = Math.max(50, rect.height || canvas.clientHeight || 150);
    const dpr = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(cssW * dpr) || canvas.height !== Math.round(cssH * dpr)) {
      canvas.width = Math.round(cssW * dpr);
      canvas.height = Math.round(cssH * dpr);
    }
    const ctx = this.ctx;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    const d = (this.group && this.group.domain) || [0, 1];
    const R = this._plotRect(cssW, cssH);
    const [ylo, yhi] = this._yDomain();
    const X = (t) => R.x + ((t - d[0]) / Math.max(1e-9, d[1] - d[0])) * R.w;
    const Y = (v) => R.y + R.h - ((v - ylo) / Math.max(1e-9, yhi - ylo)) * R.h;
    this._X = X; this._Y = Y; this._R = R;

    const css = getComputedStyle(document.documentElement);
    const cLine = css.getPropertyValue('--line-soft').trim() || '#1d2836';
    const cText = css.getPropertyValue('--fg-mute').trim() || '#7f92a8';

    // zemin
    ctx.fillStyle = css.getPropertyValue('--bg-1').trim() || '#0e141c';
    ctx.fillRect(0, 0, cssW, cssH);

    // yatay ızgara + y etiketleri
    const ystep = niceStep(yhi - ylo, 4);
    ctx.font = '12px ui-sans-serif, system-ui, sans-serif';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    ctx.strokeStyle = cLine;
    ctx.lineWidth = 1;
    for (let v = Math.ceil(ylo / ystep) * ystep; v <= yhi + 1e-9; v += ystep) {
      const y = Math.round(Y(v)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(R.x, y);
      ctx.lineTo(R.x + R.w, y);
      ctx.stroke();
      ctx.fillStyle = cText;
      ctx.fillText(num(v, Math.abs(ystep) < 1 ? 2 : (Math.abs(ystep) < 10 ? 1 : 0)), R.x - 8, y);
    }
    // y ekseni birimi
    if (this.unit) {
      ctx.save();
      ctx.translate(14, R.y + R.h / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.textAlign = 'center';
      ctx.fillStyle = cText;
      ctx.fillText(this.unit, 0, 0);
      ctx.restore();
    }

    // dikey ızgara + zaman etiketleri
    const tstep = timeStep(d[1] - d[0], 6);
    ctx.textAlign = 'center';
    for (let t = Math.ceil(d[0] / tstep) * tstep; t <= d[1]; t += tstep) {
      const x = Math.round(X(t)) + 0.5;
      ctx.strokeStyle = cLine;
      ctx.beginPath();
      ctx.moveTo(x, R.y);
      ctx.lineTo(x, R.y + R.h);
      ctx.stroke();
      if (this.xAxis) {
        ctx.fillStyle = cText;
        ctx.fillText(timeLabel(t, tstep), x, R.y + R.h + 12);
      }
    }

    // taralı bantlar (duyarlılık tabanı gibi)
    for (const b of this.bands) {
      const pts = b.points || [];
      if (pts.length < 2) continue;
      ctx.save();
      ctx.beginPath();
      ctx.rect(R.x, R.y, R.w, R.h);
      ctx.clip();
      ctx.beginPath();
      ctx.moveTo(X(pts[0][0]), Y(pts[0][1]));
      for (const p of pts) ctx.lineTo(X(p[0]), Y(p[1]));
      const floorY = b.side === 'above' ? R.y : R.y + R.h;
      ctx.lineTo(X(pts[pts.length - 1][0]), floorY);
      ctx.lineTo(X(pts[0][0]), floorY);
      ctx.closePath();
      ctx.fillStyle = b.color || 'rgba(86,185,255,0.10)';
      ctx.fill();
      if (b.stroke) {
        ctx.beginPath();
        ctx.moveTo(X(pts[0][0]), Y(pts[0][1]));
        for (const p of pts) ctx.lineTo(X(p[0]), Y(p[1]));
        ctx.strokeStyle = b.stroke;
        ctx.setLineDash(b.dash || [4, 4]);
        ctx.lineWidth = 1.4;
        ctx.stroke();
        ctx.setLineDash([]);
      }
      ctx.restore();
    }

    // seriler
    ctx.save();
    ctx.beginPath();
    ctx.rect(R.x, R.y - 2, R.w, R.h + 4);
    ctx.clip();
    for (const sr of this.series) {
      const pts = sr.points || [];
      if (!pts.length) continue;
      ctx.beginPath();
      let started = false;
      let prevY = 0;
      for (const p of pts) {
        if (p[1] === null || p[1] === undefined || Number.isNaN(p[1])) { started = false; continue; }
        const x = X(p[0]), y = Y(p[1]);
        if (!started) { ctx.moveTo(x, y); started = true; }
        else if (sr.step) { ctx.lineTo(x, prevY); ctx.lineTo(x, y); }
        else ctx.lineTo(x, y);
        prevY = y;
      }
      ctx.strokeStyle = sr.color;
      ctx.lineWidth = sr.width || 1.8;
      if (sr.dash) ctx.setLineDash(sr.dash);
      ctx.lineJoin = 'round';
      ctx.stroke();
      ctx.setLineDash([]);
      if (sr.dots && pts.length < 400) {
        ctx.fillStyle = sr.color;
        for (const p of pts) {
          if (p[1] === null || p[1] === undefined) continue;
          ctx.beginPath();
          ctx.arc(X(p[0]), Y(p[1]), 2.2, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }
    ctx.restore();

    // yatay eşik çizgileri
    ctx.textAlign = 'left';
    for (const l of this.hlines) {
      const y = Math.round(Y(l.value)) + 0.5;
      if (y < R.y - 1 || y > R.y + R.h + 1) continue;
      ctx.strokeStyle = l.color || '#f4b13a';
      ctx.setLineDash(l.dash || [7, 5]);
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(R.x, y);
      ctx.lineTo(R.x + R.w, y);
      ctx.stroke();
      ctx.setLineDash([]);
      if (l.label) {
        ctx.fillStyle = l.color || '#f4b13a';
        ctx.font = '11.5px ui-sans-serif, system-ui, sans-serif';
        ctx.fillText(l.label, R.x + 6, y - 7);
      }
    }

    // tarihli dikey çizgiler (değişim noktası)
    for (const v of this.vlines) {
      const x = Math.round(X(v.ts)) + 0.5;
      if (x < R.x || x > R.x + R.w) continue;
      ctx.strokeStyle = v.color || '#ff6b3d';
      ctx.setLineDash(v.dash || [5, 4]);
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      ctx.moveTo(x, R.y);
      ctx.lineTo(x, R.y + R.h);
      ctx.stroke();
      ctx.setLineDash([]);
      if (v.label) {
        ctx.fillStyle = v.color || '#ff6b3d';
        ctx.font = '11.5px ui-sans-serif, system-ui, sans-serif';
        ctx.textAlign = x > R.x + R.w * 0.6 ? 'right' : 'left';
        ctx.fillText(v.label, x + (x > R.x + R.w * 0.6 ? -6 : 6), R.y + 12);
        ctx.textAlign = 'left';
      }
    }

    // nişangâh
    const ht = this.group && this.group.hoverTs;
    if (ht !== null && ht !== undefined && ht >= d[0] && ht <= d[1]) {
      const x = Math.round(X(ht)) + 0.5;
      ctx.strokeStyle = 'rgba(238,244,251,0.45)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, R.y);
      ctx.lineTo(x, R.y + R.h);
      ctx.stroke();
      for (const sr of this.series) {
        if (sr.noTip) continue;
        const p = nearest(sr.points, ht);
        if (!p || p[1] === null || p[1] === undefined) continue;
        ctx.fillStyle = sr.color;
        ctx.beginPath();
        ctx.arc(X(p[0]), Y(p[1]), 3.4, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#05080c';
        ctx.lineWidth = 1.4;
        ctx.stroke();
      }
    }

    // Hiç örnek yoksa bunu yaz: boş bir kutu "veri sıfır" gibi okunur, oysa
    // doğru ifade "bu kanal bu pencerede yazılmamış"tır.
    if (!this.series.some((sr) => sr.points && sr.points.length)) {
      ctx.fillStyle = cText;
      ctx.font = '13px ui-sans-serif, system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(this.emptyText || 'bu kanalda seçilen pencerede kayıt yok',
        R.x + R.w / 2, R.y + R.h / 2);
    }

    // çerçeve
    ctx.strokeStyle = cLine;
    ctx.lineWidth = 1;
    ctx.strokeRect(R.x + 0.5, R.y + 0.5, R.w, R.h);
  }
}

/**
 * PRPD ısı haritası. 64 faz x 32 genlik hücre, cividis rampası, iki şebeke
 * çevrimi boyunca. Ayrı bir sınıfa gerek yok: tek atış çizim.
 */
export function drawHeatmap(canvas, opts) {
  const { cols, rows, get, colorFn, xLabel, yLabel, xTicks, yTicks, cycles = 2 } = opts;
  const rect = canvas.getBoundingClientRect();
  const cssW = Math.max(200, rect.width || 600);
  const cssH = Math.max(160, rect.height || 320);
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const css = getComputedStyle(document.documentElement);
  ctx.fillStyle = css.getPropertyValue('--bg').trim() || '#080b10';
  ctx.fillRect(0, 0, cssW, cssH);

  const R = { x: 62, y: 16, w: cssW - 62 - 16, h: cssH - 16 - 40 };
  const cw = R.w / (cols * cycles);
  const ch = R.h / rows;

  for (let c = 0; c < cols * cycles; c++) {
    for (let r = 0; r < rows; r++) {
      const v = get(c % cols, r);
      if (!v) continue;
      ctx.fillStyle = colorFn(v);
      ctx.fillRect(R.x + c * cw, R.y + R.h - (r + 1) * ch, Math.ceil(cw) + 0.5, Math.ceil(ch) + 0.5);
    }
  }

  // 50 Hz referans sinüsü - faz ekseninin ne olduğunu göstermek için
  ctx.strokeStyle = 'rgba(86,185,255,0.55)';
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  for (let i = 0; i <= 360 * cycles; i += 2) {
    const x = R.x + (i / (360 * cycles)) * R.w;
    const y = R.y + R.h / 2 - Math.sin((i * Math.PI) / 180) * (R.h * 0.42);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  ctx.font = '12px ui-sans-serif, system-ui, sans-serif';
  ctx.fillStyle = css.getPropertyValue('--fg-mute').trim() || '#7f92a8';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (const t of xTicks || []) {
    const x = R.x + (t.at / (360 * cycles)) * R.w;
    ctx.fillText(t.label, x, R.y + R.h + 6);
    ctx.strokeStyle = 'rgba(127,146,168,0.35)';
    ctx.beginPath();
    ctx.moveTo(x + 0.5, R.y);
    ctx.lineTo(x + 0.5, R.y + R.h);
    ctx.stroke();
  }
  // İşaretçiler (akım sıfır geçişi gibi): çizgi + ÜSTTE etiket, x etiket
  // satırıyla çakışmasın.
  for (const m of opts.marks || []) {
    const x = R.x + (m.at / (360 * cycles)) * R.w;
    ctx.strokeStyle = m.color || 'rgba(255,107,61,0.8)';
    ctx.setLineDash([6, 4]);
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(x + 0.5, R.y);
    ctx.lineTo(x + 0.5, R.y + R.h);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = m.color || 'rgba(255,107,61,0.95)';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(m.label, x + 5, R.y + 4);
  }

  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  for (const t of yTicks || []) {
    const y = R.y + R.h - (t.at / rows) * R.h;
    ctx.fillText(t.label, R.x - 8, y);
  }
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  if (xLabel) ctx.fillText(xLabel, R.x + R.w / 2, R.y + R.h + 22);
  if (yLabel) {
    ctx.save();
    ctx.translate(13, R.y + R.h / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(yLabel, 0, 0);
    ctx.restore();
  }
  ctx.strokeStyle = css.getPropertyValue('--line').trim() || '#2a3a4e';
  ctx.strokeRect(R.x + 0.5, R.y + 0.5, R.w, R.h);
  return R;
}
