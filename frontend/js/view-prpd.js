// PANO GÖZ · S4 PRPD · RF imzası.
//
// 64 faz x 32 genlik hücrelik histogram, iki şebeke çevrimi boyunca, cividis.
// Ekranda üç şey daima yazar:
//   1. sınıflandırma ve tetikleyen kural,
//   2. 30 günlük dB trendi,
//   3. AG dürüstlük kaydı: 400 V'ta klasik kısmi deşarj OLUŞMAZ (Paschen minimumu
//      327 V). Bu kanal gevşek bağlantı mikro-arkını ölçer, pC EŞDEĞERİ verir,
//      IEC 60270 izlenebilir DEĞİLDİR ve AG tarafında tek başına ekip yönlendirmez.
//
// Fizik notu ekrana da yazılır: seri ark, akım sıfır geçişlerinde söner ve yeniden
// tutuşur, bu yüzden darbeler AKIM SIFIR GEÇİŞLERİNDE kümelenir. Gerilim kaynaklı
// deşarj ise gerilimin yükselen eğimlerinde toplanır. İkisi aynı grafikte ayrışır.

import { h, mount, empty, clear } from './dom.js';
import * as fmt from './fmt.js';
import { api } from './api.js';
import { drawHeatmap, ChartGroup, TimeChart } from './charts.js';

const N_PHASE = 64;
const N_AMP = 32;
const DEG_PER_BIN = 360 / N_PHASE;
const DB_PER_BIN = 2.5;
const PF_ANGLE = 18.19; // cos φ = 0,95 endüktif → akım sıfırı gerilim sıfırından 18,19° sonra

export function create(ctx) {
  const el = h('div.view');
  const head = h('div.view-head');
  const mapCard = h('div.card');
  const side = h('div.col');
  const gridEl = h('div.prpd-grid', h('div.col', mapCard), side);

  function layout() {
    if (!el.contains(head)) mount(el, head, gridEl);
  }

  layout();

  let loadedFor = '';
  let prpd = null;
  let trend = null;
  let group = null;
  let canvas = null;

  async function load(key) {
    const [p, t] = await Promise.all([
      api.prpd(key).catch((e) => ({ error: e })),
      api.trend(key, '', 'pd.qmax_db', 720).catch(() => ({ series: [] })),
    ]);
    prpd = p;
    trend = t;
  }

  function grid(hist) {
    const g = new Array(N_PHASE * N_AMP).fill(0);
    let max = 0;
    for (const row of hist || []) {
      if (!Array.isArray(row) || row.length < 3) continue;
      const [ph, am, c] = row;
      if (ph < 0 || ph >= N_PHASE || am < 0 || am >= N_AMP) continue;
      g[am * N_PHASE + ph] = c;
      if (c > max) max = c;
    }
    return { g, max };
  }

  function drawMap() {
    if (!canvas || !prpd || !prpd.hist) return;
    const { g, max } = grid(prpd.hist);
    const norm = max > 0 ? Math.log1p(max) : 1;
    drawHeatmap(canvas, {
      cols: N_PHASE,
      rows: N_AMP,
      cycles: 2,
      get: (c, r) => g[r * N_PHASE + c],
      colorFn: (v) => fmt.cividis(Math.log1p(v) / norm),
      xLabel: 'faz açısı (°) · iki şebeke çevrimi · 50 Hz referans sinüsü mavi',
      yLabel: 'genlik (dB · pC eşdeğeri)',
      xTicks: [
        { at: 0, label: '0°' },
        { at: 90, label: '90°' },
        { at: 180, label: '180°' },
        { at: 270, label: '270°' },
        { at: 360, label: '360°' },
        { at: 450, label: '450°' },
        { at: 540, label: '540°' },
        { at: 630, label: '630°' },
        { at: 720, label: '720°' },
      ],
      marks: [
        { at: PF_ANGLE, label: 'akım sıfırı', color: 'rgba(255,107,61,0.9)' },
        { at: 180 + PF_ANGLE, label: 'akım sıfırı', color: 'rgba(255,107,61,0.9)' },
        { at: 360 + PF_ANGLE, label: '', color: 'rgba(255,107,61,0.9)' },
        { at: 540 + PF_ANGLE, label: '', color: 'rgba(255,107,61,0.9)' },
      ],
      yTicks: [
        { at: 0, label: '0' },
        { at: 8, label: fmt.num(8 * DB_PER_BIN, 0) },
        { at: 16, label: fmt.num(16 * DB_PER_BIN, 0) },
        { at: 24, label: fmt.num(24 * DB_PER_BIN, 0) },
        { at: 32, label: fmt.num(32 * DB_PER_BIN, 0) },
      ],
    });
  }

  function renderMap(panel) {
    canvas = h('canvas', { style: { width: '100%', height: '420px' } });
    const trendCanvas = h('canvas');
    mount(mapCard,
      h('header',
        h('h2', { text: 'Faz çözünürlüklü desen (PRPD)' }),
        h('span.sp'),
        h('span.tag', { text: `${N_PHASE} × ${N_AMP} hücre` }),
        h('span.tag', { text: prpd && prpd.ts ? fmt.dateTime(prpd.ts) : '—' })),
      h('div.body.flush', h('div.prpd-canvas-wrap', canvas)),
      h('div.twin-legend',
        h('span.li', h('span.ramp',
          h('span', { text: 'az' }),
          h('span.bar', { style: { background: fmt.cividisCss() } }),
          h('span', { text: 'çok' }),
          h('span.tiny', { text: '· logaritmik sayım · cividis' }))),
        h('span.li.tiny', { text: 'Seri ark → akım sıfır geçişlerinde kümelenir' }),
        h('span.li.tiny', { text: 'Gerilim kaynaklı deşarj → gerilimin yükselen eğimlerinde' })),
      h('div.body.flush',
        h('div.chart-box', { style: { height: '150px' } },
          h('div.chart-title', { text: '30 günlük tepe genlik trendi (pd.qmax_db)' }),
          trendCanvas)));

    requestAnimationFrame(() => {
      drawMap();
      if (group) group.destroy();
      group = new ChartGroup();
      group.add(new TimeChart(trendCanvas, {
        unit: 'dB', decimals: 1, xAxis: true,
        series: [{ label: 'tepe genlik', color: '#ffea46',
                   points: ((trend && trend.series) || []).filter((p) => p && p[1] !== null),
                   width: 1.8, unit: 'dB' }],
      }));
      group.autoDomain();
      group.drawAll();
    });
  }

  function classCard(panel) {
    const pd = (panel && panel.pd) || {};
    const klass = (prpd && prpd.klass) || pd.klass || 'GURULTU';
    const label = fmt.PRPD_TR[klass] || (prpd && prpd.label_tr) || pd.klass_label || klass;
    const f = (prpd && prpd.features) || pd.features || {};
    const rule = f.rule || (prpd && prpd.rule) || '';
    const conf = f.confidence !== undefined ? f.confidence : (prpd && prpd.confidence);
    return h('div.card.accent',
      h('header', h('h3', { text: 'Sınıflandırma' }), h('span.sp'),
        h('span.tag', { text: klass })),
      h('div.body.col',
        h('div.stat',
          h('div.stat-k', { text: 'PRPD sınıfı' }),
          h('div.stat-v', { text: label }),
          h('div.stat-n', {
            text: (rule ? `tetikleyen kural: ${rule}` : 'kural motoru çıktısı')
                + (conf !== undefined && conf !== null ? ` · güven ${fmt.pct(100 * conf, 0)}` : ''),
          })),
        h('div.grid-2',
          h('div.stat', h('div.stat-k', { text: 'Darbe hızı' }),
            h('div.stat-v', { text: fmt.num(pd.rate_per_s, 1) }, h('span.stat-u', { text: ' 1/s' }))),
          h('div.stat', h('div.stat-k', { text: 'Tepe genlik' }),
            h('div.stat-v', { text: fmt.num(pd.qmax_db, 1) }, h('span.stat-u', { text: ' dB' }))),
          h('div.stat', h('div.stat-k', { text: '30 günlük trend' }),
            h('div.stat-v', { text: fmt.signed(pd.trend_db_30d, 1) }, h('span.stat-u', { text: ' dB' })),
            h('div.stat-n', { text: '+6 dB tetikleyici eşiği' })),
          h('div.stat', h('div.stat-k', { text: 'TEV / ultrasonik' }),
            h('div.stat-v', { text: `${fmt.num(pd.tev_db, 0)} / ${fmt.num(pd.ultrasonic_db, 0)}` },
              h('span.stat-u', { text: ' dB' })),
            h('div.stat-n', { text: 'ikinci kanal doğrulaması' }))),
        (prpd && prpd.explain_tr)
          ? h('div.note', { text: prpd.explain_tr })
          : null,
        h('div.note.honest', { text: (prpd && prpd.caveat) || pd.caveat || '' })));
  }

  function featureCard() {
    const f = (prpd && prpd.features) || {};
    const rows = Object.entries(f).filter(([, v]) => typeof v === 'number');
    if (!rows.length) {
      return h('div.card', h('header', h('h3', { text: 'Öznitelikler' })),
        h('div.body', empty('Öznitelik yok', 'PRPD kaydı henüz alınmadı')));
    }
    return h('div.card',
      h('header', h('h3', { text: 'Öznitelikler' }), h('span.sp'),
        h('span.tiny.muted', { text: '12 belgelenmiş öznitelik' })),
      h('div.body.flush',
        h('table.tbl',
          h('thead', h('tr', h('th.nosort', { text: 'Öznitelik' }), h('th.nosort', { text: 'Değer' }))),
          h('tbody', ...rows.map(([k, v]) => h('tr',
            h('td', h('div', { text: fmt.FEATURE_TR[k] || k }),
              h('div.tiny.muted.mono', { text: k })),
            h('td.n', { text: fmt.num(v, Math.abs(v) >= 100 ? 0 : 3) })))))));
  }

  function physicsCard() {
    return h('div.card',
      h('header', h('h3', { text: 'Bu grafik nasıl okunur' })),
      h('div.body.col',
        h('ul.reason-list',
          h('li', h('span.b', { text: '›' }), h('span', {
            text: 'Gevşeyen bir bağlantıdaki seri ark, akım sıfıra yaklaşırken söner ve '
                + 'yeniden tutuşur. Bu yüzden darbeler AKIM SIFIR GEÇİŞLERİNDE kümelenir '
                + `(cos φ ≈ 0,95 için gerilim sıfırından ${fmt.num(PF_ANGLE, 2)}° sonra).`,
          })),
          h('li', h('span.b', { text: '›' }), h('span', {
            text: 'Gerilim kaynaklı kısmi deşarj ise gerilimin YÜKSELEN EĞİMLERİNDE toplanır. '
                + 'İki mekanizma aynı grafikte farklı yerlere düşer; ayrım budur.',
          })),
          h('li', h('span.b', { text: '›' }), h('span', {
            text: 'Yüzen elektrot imzası: dar, tekrarlayan genlik ve yaklaşık 11° adımlı '
                + 'yeniden tutuşma tarağı. 5,625°’lik faz kutuları bu tarağı iki blok gibi '
                + 'gösterir; sınıflandırma dişleri ayırt etmeye bağlı değildir.',
          }))),
        h('div.note.warn', {
          text: 'HFCT asla faz iletkenine takılmaz: 50 Hz besleme 6 mV_pp/A üretir. '
              + 'Kelepçe PE saplamasındadır ve 1-3 MHz yüksek geçiren filtre zorunludur.',
        })));
  }

  function update(state) {
    const key = state.panelKey;
    const panel = state.panel;
    if (!key) { mount(el, empty('Pano seçilmedi', 'Filo ekranından bir pano seçin')); return; }
    layout();
    mount(head,
      h('div',
        h('h1', { text: 'PRPD · RF imzası' }),
        h('div.head-sub', { text: `${key} · PD-01 · HFCT + TEV + ultrasonik · PE saplaması` })),
      h('span.sp'),
      h('button.btn', { text: '← Dijital ikiz', onclick: () => ctx.navigate('pano', key) }));

    if (loadedFor !== key) {
      loadedFor = key;
      prpd = null; trend = null;
      mount(mapCard, h('div.body', h('div.skeleton', { style: { height: '420px' } })));
      load(key).then(() => ctx.refresh()).catch(() => ctx.refresh());
      return;
    }
    if (!prpd) { return; }
    if (prpd.error) {
      mount(mapCard, h('header', h('h2', { text: 'PRPD' })),
        h('div.body', empty('PRPD kaydı yok',
          'Bu pano için RF düğümünden henüz histogram gelmedi')));
    } else if (!mapCard.querySelector('canvas')) {
      renderMap(panel);
    }
    mount(side, classCard(panel), featureCard(), physicsCard());
  }

  return { el, update, destroy() { if (group) group.destroy(); clear(el); } };
}
