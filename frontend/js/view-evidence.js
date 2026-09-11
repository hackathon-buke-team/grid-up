// PANO GÖZ · S3 Kanıt.
//
// Dört grafik, TEK ve ORTAK x ekseni, senkron nişangâh:
//   1. ham sıcaklık ve iki kardeş fazı
//   2. akım ve yük faktörü
//   3. θ · taban çizgisi, tarihli değişim noktası, taralı duyarlılık tabanı
//   4. CUSUM istatistiği ve h = 8 eşiği
//
// Formül ekranda yazar. Bir jüri üyesi "bu sayı nereden geliyor" diye sorduğunda
// cevap ekranın kendisinde olmalıdır:
//     θ = [T − kardeş medyanı] / (I / I_ref)²
// Fazla temas direnci ARALIK olarak verilir, tek sayı olarak asla: R_th,local
// bir pabuç için ancak 2-4 K/W doğrulukla bilinir.

import { h, mount, empty, clear } from './dom.js';
import * as fmt from './fmt.js';
import { api } from './api.js';
import { ChartGroup, TimeChart } from './charts.js';

const CH = {
  tempTc: 'tc.temp_c',
  tempIr: 'ir.lug_temp_c',
  current: 'tc.current_a',
  theta: 'det.theta_k',
  thetaMin: 'det.theta_min_k',
  cusum: 'det.cusum',
};

const COLORS = {
  self: '#56b9ff',
  sib1: '#8a8678',
  sib2: '#c3b369',
  current: '#4aa3ff',
  load: '#a59c74',
  theta: '#ffea46',
  base: '#7f92a8',
  cusum: '#ff6b3d',
};

const RANGES = [
  { label: '24 saat', hours: 24 },
  { label: '7 gün', hours: 168 },
  { label: '30 gün', hours: 720 },
];

export function create(ctx) {
  const el = h('div.view');
  const head = h('div.view-head');
  const chartCard = h('div.card');
  const side = h('div.col');
  const grid = h('div.evidence-grid', h('div.col', chartCard), side);

  // Boş/yükleniyor durumları kökü değiştirir; layout() iskeleti geri kurar.
  // Aksi hâlde head/chartCard/side DOM'dan kopar ve ekran tek bir iskelet
  // kartında donar - bu hatayı bir kez yaşadık, bir daha yaşamayalım diye
  // yerleşim tek bir yerden kuruluyor.
  function layout() {
    if (!el.contains(head)) mount(el, head, grid);
  }

  layout();

  let group = null;
  let charts = [];
  let hours = 168;
  let loadedFor = '';
  let data = null;
  let loading = false;

  function destroyCharts() {
    if (group) { group.destroy(); group = null; }
    charts = [];
  }

  function siblingsOf(panel, joint) {
    if (!panel || !joint) return [];
    return (panel.joints || []).filter((j) =>
      j.zone === joint.zone
      && j.feeder_index === joint.feeder_index
      && j.conductor !== 'N'
      && j.key !== joint.key);
  }

  async function series(panelKey, jointKey, channel) {
    try {
      const r = await api.trend(panelKey, jointKey, channel, hours);
      const pts = (r && r.series) || [];
      return { points: pts.filter((p) => Array.isArray(p) && p[1] !== null), meta: r || {} };
    } catch (e) {
      return { points: [], meta: {}, error: e };
    }
  }

  async function tempSeries(panelKey, jointKey) {
    const [a, b] = await Promise.all([
      series(panelKey, jointKey, CH.tempTc),
      series(panelKey, jointKey, CH.tempIr),
    ]);
    return a.points.length ? a : b;
  }

  async function load(panel, joint) {
    loading = true;
    const key = panel.panel_key;
    const sibs = siblingsOf(panel, joint).slice(0, 2);
    const panelChan = joint.conductor === 'N' ? 'mpr.i_n_a' : `mpr.i_${String(joint.conductor).toLowerCase()}_a`;
    const [self, s1, s2, cur, pcur, th, thMin, cus, daily] = await Promise.all([
      tempSeries(key, joint.key),
      sibs[0] ? tempSeries(key, sibs[0].key) : Promise.resolve({ points: [] }),
      sibs[1] ? tempSeries(key, sibs[1].key) : Promise.resolve({ points: [] }),
      series(key, joint.key, CH.current),
      series(key, '', panelChan),
      series(key, joint.key, CH.theta),
      series(key, joint.key, CH.thetaMin),
      series(key, joint.key, CH.cusum),
      api.daily(key, joint.key, 120).catch(() => []),
    ]);
    data = { self, s1, s2, cur, pcur, th, thMin, cus, daily, sibs };
    loading = false;
  }

  // Raw theta samples are pruned after the raw-retention window, and older days
  // in a backfill are deliberately sparse.  The daily table is not a fallback
  // for that: it is the series the detector actually judges, and the CUSUM and
  // the changepoint are computed from it.  So we plot it in its own right,
  // which also means the dated changepoint line always has data around it.
  function dailyPoints(field) {
    const rows = (data && data.daily) || [];
    const out = [];
    for (const r of rows) {
      const v = r && r[field];
      if (typeof r.ts === 'number' && typeof v === 'number' && isFinite(v)) out.push([r.ts, v]);
    }
    out.sort((a, b) => a[0] - b[0]);
    return out;
  }

  function withinWindow(points) {
    if (!points.length) return points;
    const from = (Date.now() / 1000) - hours * 3600;
    // Keep one point before the window so the line enters from the left edge
    // instead of starting in mid-air.
    const idx = points.findIndex((p) => p[0] >= from);
    if (idx <= 0) return points;
    return points.slice(idx - 1);
  }

  function chartBox(title, legend, height) {
    const canvas = h('canvas');
    const box = h('div.chart-box', { style: { height: height + 'px' } },
      h('div.chart-title', { text: title }),
      h('div.chart-legend', ...legend.map((l) => h('span.li',
        h('i', { style: { background: l.color } }), h('span', { text: l.label })))),
      canvas);
    return { box, canvas };
  }

  function renderCharts(panel, joint) {
    destroyCharts();
    const d = data;
    if (!d) return;
    const anyData = d.self.points.length || d.th.points.length;
    if (!anyData) {
      mount(chartCard,
        h('header', h('h2', { text: 'Zaman serisi' }), rangeSeg()),
        h('div.body', empty('Bu bağlantı için seri yok',
          'Gateway henüz veri yayınlamamış olabilir; ekran hata vermez, boş kalır')));
      return;
    }

    const c1 = chartBox('1 · Ham sıcaklık ve kardeş fazlar', [
      { color: COLORS.self, label: fmt.shortJoint(joint.key) },
      ...(d.sibs[0] ? [{ color: COLORS.sib1, label: fmt.shortJoint(d.sibs[0].key) }] : []),
      ...(d.sibs[1] ? [{ color: COLORS.sib2, label: fmt.shortJoint(d.sibs[1].key) }] : []),
    ], 170);
    const c2 = chartBox('2 · Akım ve yük faktörü (f = pano akımı / 2312 A)', [
      ...(d.cur.points.length ? [{ color: COLORS.current, label: 'damar akımı · kendi CT’si' }] : []),
      { color: COLORS.load, label: 'pano faz akımı' },
    ], 150);
    const c3 = chartBox('3 · θ · taban, değişim noktası, duyarlılık tabanı', [
      { color: COLORS.theta, label: 'θ anlık' },
      { color: '#ffd166', label: 'θ günlük medyan · alarm buna bakar' },
      { color: COLORS.base, label: 'taban' },
      { color: 'rgba(86,185,255,0.5)', label: 'θ_min altı = kör bölge' },
    ], 200);
    const c4 = chartBox('4 · CUSUM (k = 0,5 · h = 8)', [
      { color: COLORS.cusum, label: 'CUSUM+' },
      { color: '#f4b13a', label: 'eşik h = 8' },
    ], 160);

    mount(chartCard,
      h('header', h('h2', { text: 'Zaman serisi · ortak eksen' }), h('span.sp'), rangeSeg()),
      h('div.body.flush', h('div.chart-stack', c1.box, c2.box, c3.box, c4.box)),
      h('div.body.col',
        h('div.tiny.muted', {
          text: 'Dört grafik aynı x eksenini paylaşır ve nişangâh senkrondur: yükün ne '
              + 'yaptığını görmeden bir sıcaklık artışı yorumlanamaz.',
        }),
        joint.theta_min_k
          ? h('div.tiny.muted', {
              text: `Şu anki duyarlılık tabanı θ_min = ${fmt.num(joint.theta_min_k, 2)} K `
                  + `(3σ/f², f = ${fmt.num(100 * (joint.load_factor || 0), 0)} %). `
                  + (joint.theta_min_k > 8
                      ? 'Bu yükte taban grafiğin üstünde kalır: gölgeli alan tüm ekranı kaplar, '
                      + 'çünkü bu yükte bu büyüklüğün altındaki bir kusuru göremeyiz. '
                      + 'Bunu gizlemek yerine söylüyoruz.'
                      : 'Gölgeli alan, bu yükte göremediğimiz bölgedir.'),
            })
          : null));

    group = new ChartGroup();
    const rated = joint.rated_a || 400;

    charts = [
      group.add(new TimeChart(c1.canvas, {
        unit: '°C', decimals: 2, yZero: false,
        series: [
          { label: fmt.shortJoint(joint.key), color: COLORS.self, points: d.self.points, width: 2.1, unit: '°C' },
          ...(d.s1.points.length ? [{ label: fmt.shortJoint(d.sibs[0].key), color: COLORS.sib1, points: d.s1.points, width: 1.4, unit: '°C' }] : []),
          ...(d.s2.points.length ? [{ label: fmt.shortJoint(d.sibs[1].key), color: COLORS.sib2, points: d.s2.points, width: 1.4, unit: '°C' }] : []),
        ],
      })),
      group.add(new TimeChart(c2.canvas, {
        unit: 'A', decimals: 0,
        series: [
          ...(d.cur.points.length
            ? [{ label: 'damar akımı', color: COLORS.current, points: d.cur.points, width: 1.8, unit: 'A', decimals: 0 }]
            : []),
          ...(d.pcur && d.pcur.points.length
            ? [{ label: 'pano faz akımı', color: COLORS.load, points: d.pcur.points, width: 1.5, unit: 'A', decimals: 0 }]
            : []),
        ],
        hlines: [
          { value: rated, color: '#f4b13a', label: `bağlantı anması ${fmt.num(rated, 0)} A` },
          { value: rated * 0.35, color: '#4aa3ff', label: 'f = 0,35 · bunun altında duyarlılık düşük' },
        ],
      })),
      group.add(new TimeChart(c3.canvas, {
        unit: 'K', decimals: 2,
        series: [
          { label: 'θ', color: COLORS.theta, points: d.th.points, width: 2.2, unit: 'K' },
          { label: 'θ günlük medyan', color: '#ffd166',
            points: withinWindow(dailyPoints('theta_med')), width: 2.6, unit: 'K' },
        ],
        yMax: (() => {
          const vals = d.th.points.map((p) => p[1])
            .concat(withinWindow(dailyPoints('theta_med')).map((p) => p[1]))
            .filter((v) => typeof v === 'number');
          const top = Math.max(6, joint.baseline_k || 0, ...(vals.length ? vals : [0]));
          return top * 1.25 + 1;
        })(),
        bands: d.thMin.points.length
          ? [{ points: d.thMin.points, side: 'below', color: 'rgba(86,185,255,0.13)',
               stroke: 'rgba(86,185,255,0.6)', scale: false }]
          : [],
        hlines: [
          ...(joint.baseline_k !== null && joint.baseline_k !== undefined
            ? [{ value: joint.baseline_k, color: COLORS.base, label: 'taban ' + fmt.num(joint.baseline_k, 2) + ' K' }]
            : []),
          { value: 5.0, color: '#ff6b3d', label: 'alarm eşiği 5 K' },
        ],
        vlines: joint.changepoint_ts
          ? [{ ts: joint.changepoint_ts, color: '#ff2f79',
               label: 'değişim noktası · ' + fmt.date(joint.changepoint_ts) }]
          : [],
      })),
      group.add(new TimeChart(c4.canvas, {
        unit: '-', decimals: 2, xAxis: true,
        emptyText: 'CUSUM günlük medyandan hesaplanır · bu bağlantıda henüz yeterli gün yok',
        series: [{
          label: 'CUSUM',
          color: COLORS.cusum,
          // The CUSUM lives on the daily table by construction: it is a
          // statistic over daily medians, so there is no per-sample value to
          // plot and pretending otherwise would draw a line nobody computed.
          points: withinWindow(dailyPoints('cusum')),
          width: 2.2,
          unit: '',
        }],
        hlines: [{ value: 8, color: '#f4b13a', label: 'h = 8' }],
      })),
    ];
    group.autoDomain();
    // Değişim noktası aralığın dışında kalıyorsa ekseni genişlet: tarihli çizgi
    // görünmüyorsa hiçbir işe yaramaz.
    if (joint.changepoint_ts && group.domain && joint.changepoint_ts < group.domain[0]) {
      group.setDomain([joint.changepoint_ts - 3600, group.domain[1]]);
    }
    requestAnimationFrame(() => group && group.drawAll());
  }

  function rangeSeg() {
    return h('span.seg', ...RANGES.map((r) => h('button', {
      text: r.label,
      'aria-pressed': String(r.hours === hours),
      onclick: () => { hours = r.hours; loadedFor = ''; ctx.refresh(); },
    })));
  }

  // ------------------------------------------------------------- yan kartlar

  function formulaCard(joint) {
    return h('div.card.accent',
      h('header', h('h3', { text: 'Ölçülen büyüklük' })),
      h('div.body.col',
        h('div.formula',
          'θ = [ T − kardeş medyanı ] / ( I / I',
          h('sub', { text: 'ref' }), ' )²',
          h('span.why', {
            text: 'Yükten bağımsız (I² sadeleşir), ortam ve mevsimden bağımsız (aynı yerdeki '
                + 'sensörlerin farkı), yayıcılıktan bağımsız (özdeş yüzeyler). Geçmiş gerekmez: '
                + 'bir baradaki üç özdeş faz, montaj gününde geçerli bir referanstır.',
          })),
        h('div.kv',
          h('span.kv-k', { text: 'I_ref' }),
          h('span.kv-v', { text: fmt.num(joint.rated_a, 0) + ' A · DSYA anma akımı' }),
          h('span.kv-k', { text: 'Kardeş kümesi' }),
          h('span.kv-v', {
            text: joint.conductor === 'N'
              ? 'nötrün geçerli faz kardeşi yoktur → kural H3'
              : `aynı fiderin diğer iki fazı (${(data && data.sibs || []).map((s) => s.conductor).join(', ') || '—'})`,
          }),
          h('span.kv-k', { text: 'Medyan' }),
          h('span.kv-v', { text: 'kardeşlerin medyanı · kendisi hariç' }))));
  }

  function resistanceCard(joint) {
    const lo = joint.excess_r_lo_uohm, hi = joint.excess_r_hi_uohm, mid = joint.excess_r_uohm;
    const i = joint.rated_a || 400;
    const pw = (r) => (r === null || r === undefined) ? null : (r * 1e-6) * i * i;
    return h('div.card',
      h('header', h('h3', { text: 'Fazla temas direnci' }), h('span.sp'),
        h('span.tag', { text: 'aralık · nokta değer değil' })),
      h('div.body.col',
        (lo === null || lo === undefined) && (mid === null || mid === undefined)
          ? empty('Henüz kestirim yok', 'θ ölçülebilir seviyeye çıkmadı')
          : h('div',
              h('div.interval',
                h('span', { text: fmt.num(lo ?? mid, 1) }),
                h('span.u', { text: '…' }),
                h('span', { text: fmt.num(hi ?? mid, 1) }),
                h('span.u', { text: 'µΩ' })),
              h('div.small.muted', {
                text: `anma akımında kayıp ≈ ${fmt.num(pw(lo ?? mid), 1)} … `
                    + `${fmt.num(pw(hi ?? mid), 1)} W`,
              })),
        h('div.note.honest', {
          text: 'ΔR = θ / (R_th · I_ref²). Bir 240 mm² kablo pabucu için R_th,local ancak '
              + '2-4 K/W doğrulukla bilinir, bu yüzden sonuç daima aralıktır. Sağlıklı kalaylı '
              + 'civatalı bir bağlantı 2-5 µΩ’dur; 50 µΩ’a bozulmuş bir 400 A pabucu 8 W harcar.',
        })));
  }

  function reasonCard(panel, joint) {
    const alarm = (panel.alarms || []).find((a) => a.joint_key === joint.key)
      || (panel.alarms || [])[0] || null;
    const ev = (alarm && alarm.evidence) || {};
    const reasons = [];
    if (joint.theta_k !== null && joint.theta_k !== undefined) {
      reasons.push(`θ = ${fmt.num(joint.theta_k, 2)} K · kardeşlerine göre yük düzeltilmiş fazla sıcaklık`);
    }
    if (joint.theta_min_k) {
      reasons.push(`Şu anki görülebilir en küçük θ = ${fmt.num(joint.theta_min_k, 2)} K `
        + `(3σ/f², f = ${fmt.num(100 * (joint.load_factor || 0), 0)} %)`);
    }
    if (joint.slope_k_per_week) {
      reasons.push(`Eğim ${fmt.signed(joint.slope_k_per_week, 2)} K/hafta (Theil-Sen)`);
    }
    if (joint.cusum) reasons.push(`CUSUM ${fmt.num(joint.cusum, 2)} · eşik 8`);
    if (joint.alarm_days) reasons.push(`Son 5 günün ${joint.alarm_days} tanesinde eşik aşıldı`);
    if (joint.changepoint_ts) reasons.push(`Değişim noktası ${fmt.dateTime(joint.changepoint_ts)}`);
    // Olayın kanıt sözlüğünden yalnız ölçüm alanları; pano/mod gibi meta alanlar
    // zaten başlıkta yazıyor, listede tekrar etmezler.
    const SKIP = new Set(['panel', 'panel_key', 'mode', 'mode_label_tr', 'joint', 'joint_key',
      'theta_k', 'slope_k_per_week', 'cusum', 'sensitivity_pct']);
    const EV_TR = {
      health_index: ['Sağlık endeksi', ''],
      risk: ['Füzyon riski', ''],
      load_factor: ['Yük faktörü', ''],
      temp_c: ['Sıcaklık', '°C'],
      theta_min_k: ['Görülebilir en küçük θ', 'K'],
      detectors_ok: ['Sağlam dedektör', ''],
      detectors_total: ['Kurulu dedektör', ''],
      excess_r_uohm: ['Fazla direnç', 'µΩ'],
    };
    for (const [k, v] of Object.entries(ev)) {
      if (SKIP.has(k) || v === null || v === undefined || typeof v === 'object') continue;
      const meta = EV_TR[k];
      if (typeof v === 'number') {
        reasons.push(meta ? `${meta[0]}: ${fmt.num(v, 2)}${meta[1] ? ' ' + meta[1] : ''}`
                          : `${k}: ${fmt.num(v, 2)}`);
      } else {
        reasons.push(meta ? `${meta[0]}: ${v}` : `${k}: ${v}`);
      }
    }
    const ruled = (alarm && alarm.ruled_out) || [];

    return h('div.card',
      h('header', h('h3', { text: 'NEDEN' }), h('span.sp'),
        alarm ? fmt.sevBadge(alarm.severity) : h('span.tag', { text: 'alarm yok' })),
      h('div.body.col',
        alarm ? h('div', h('div', { text: alarm.title }),
          h('div.small.muted', { text: alarm.action || '' })) : null,
        reasons.length
          ? h('ul.reason-list', ...reasons.map((r) => h('li', h('span.b', { text: '›' }), h('span', { text: r }))))
          : h('div.muted.small', { text: 'Bu bağlantıda kayda değer bulgu yok.' }),
        h('h3', { text: 'ELENEN NEDENLER', style: { marginTop: '6px' } }),
        ruled.length
          ? h('ul.reason-list.ruled', ...ruled.map((r) => h('li', h('span.b', { text: '✕' }), h('span', { text: r }))))
          : h('div.muted.small', {
              text: 'Henüz eleme kaydı yok. Alarm açıldığında hangi alternatif nedenlerin '
                  + '(şebeke olayı, yük adımı, sıcak hava dalgası, sensör kayması) elendiği '
                  + 'burada listelenir.',
            })));
  }

  function factsCard(panel, joint) {
    const daily = (data && data.daily) || [];
    const last = daily.length ? daily[daily.length - 1] : null;
    return h('div.card',
      h('header', h('h3', { text: 'Bağlantı künyesi' })),
      h('div.body.col',
        h('div.kv',
          h('span.kv-k', { text: 'Anahtar' }), h('span.kv-v.mono', { text: joint.key }),
          h('span.kv-k', { text: 'Etiket' }), h('span.kv-v', { text: joint.label || '—' }),
          h('span.kv-k', { text: 'Bölge' }), h('span.kv-v', { text: fmt.jointZoneTR(joint.zone) }),
          h('span.kv-k', { text: 'İletken' }), h('span.kv-v', { text: fmt.CONDUCTOR_TR[joint.conductor] || joint.conductor }),
          h('span.kv-k', { text: 'Anma' }), h('span.kv-v', { text: fmt.num(joint.rated_a, 0) + ' A' }),
          h('span.kv-k', { text: 'Sıcaklık' }), h('span.kv-v', { text: fmt.num(joint.temp_c, 2) + ' °C' }),
          h('span.kv-k', { text: 'Kardeş medyanı' }), h('span.kv-v', { text: fmt.num(joint.sibling_median_c, 2) + ' °C' }),
          h('span.kv-k', { text: 'Akım' }), h('span.kv-v', {
            text: joint.current_a === null || joint.current_a === undefined
              ? 'ölçülmüyor · pano yük faktöründen türetildi'
              : fmt.num(joint.current_a, 0) + ' A',
          }),
          h('span.kv-k', { text: 'Görünürlük' }), h('span.kv-v', { text: fmt.pct(joint.sensitivity_pct, 0) }),
          last ? h('span.kv-k', { text: 'Son gün medyanı' }) : null,
          last ? h('span.kv-v', { text: fmt.num(last.theta_med, 2) + ' K · ' + fmt.dayLabel(last.date || last.day) }) : null),
        joint.note ? h('div.tiny.muted', { text: joint.note }) : null,
        joint.current_a === null || joint.current_a === undefined
          ? h('div.note.honest', {
              text: '40 izlenen bağlantının yalnızca 6’sında kendi ayrılabilir CT’si vardır: '
                  + 'hiçbir çıkış fiderinde dağıtım şirketi CT’si yoktur (2500/5 yalnız girişi ölçer). '
                  + 'Diğerleri pano yük faktörüyle normalize edilir ve bu ekranda böyle etiketlenir.',
            })
          : null));
  }

  function dailyCard() {
    const daily = (data && data.daily) || [];
    if (!daily.length) return null;
    const rows = daily.slice(-14).reverse();
    return h('div.card',
      h('header', h('h3', { text: 'Günlük θ medyanı · son 14 gün' }), h('span.sp'),
        h('span.tiny.muted', { text: 'CUSUM bu diziden beslenir' })),
      h('div.body.flush',
        h('table.tbl',
          h('thead', h('tr',
            h('th.nosort', { text: 'Gün' }),
            h('th.nosort', { text: 'θ med' }),
            h('th.nosort', { text: 'θ p90' }),
            h('th.nosort', { text: 'n' }),
            h('th.nosort', { text: 'Yük' }),
            h('th.nosort', { text: 'Görünürlük' }))),
          h('tbody', ...rows.map((r) => h('tr',
            h('td', { text: fmt.dayLabel(r.date || r.day) }),
            h('td.n', { text: fmt.num(r.theta_med, 2) }),
            h('td.n', { text: fmt.num(r.theta_p90, 2) }),
            h('td.n', { text: fmt.int(r.n) }),
            h('td.n', { text: fmt.pct(100 * (r.load_mean || 0), 0) }),
            h('td.n', { text: fmt.pct(r.sens_pct, 0) })))))));
  }

  // ------------------------------------------------------------------ update

  function update(state) {
    const panel = state.panel;
    const key = state.panelKey;
    if (!key) { mount(el, empty('Pano seçilmedi', 'Filo ekranından bir pano seçin')); return; }
    layout();
    if (!panel || panel.panel_key !== key) {
      mount(head, h('h1', { text: 'Kanıt' }), h('span.head-sub', { text: key + ' · yükleniyor…' }));
      mount(chartCard, h('div.body', h('div.skeleton', { style: { height: '520px' } })));
      mount(side, h('div.card', h('div.body', h('div.skeleton', { style: { height: '200px' } }))));
      return;
    }
    const joints = (panel.joints || []).filter((j) => j.zone === 'bottom');
    const jointKey = state.jointKey || panel.theta_max_joint || (joints[0] && joints[0].key);
    const joint = joints.find((j) => j.key === jointKey) || joints[0];
    if (!joint) {
      mount(chartCard, h('div.body', empty('İzlenen bağlantı yok',
        'Bu panoda alt kablo bölmesi bağlantısı raporlanmıyor')));
      mount(side, '');
      return;
    }

    mount(head,
      h('div',
        h('h1', { text: `Kanıt · ${fmt.shortJoint(joint.key)}` }),
        h('div.head-sub', { text: `${panel.panel_key} · ${joint.label || joint.key}` })),
      h('span.sp'),
      fmt.sevBadge(joint.severity),
      h('span.chip', h('span', { text: 'θ' }),
        h('b', { text: fmt.num(joint.theta_k, 2) + ' K' })),
      h('span.chip', h('span', { text: 'Δ eğim' }),
        h('b', { text: fmt.signed(joint.slope_k_per_week, 2) + ' K/hf' })),
      jointSelect(panel, joint),
      h('button.btn', { text: '← Dijital ikiz', onclick: () => ctx.navigate('pano', panel.panel_key) }));

    const want = `${panel.panel_key}|${joint.key}|${hours}`;
    if (want !== loadedFor && !loading) {
      loadedFor = want;
      mount(chartCard, h('div.body', h('div.skeleton', { style: { height: '640px' } })));
      load(panel, joint).then(() => { renderCharts(panel, joint); }).catch((e) => {
        mount(chartCard, h('div.body', empty('Seri alınamadı', String(e && e.message || e))));
      });
    } else if (data && !loading) {
      renderCharts(panel, joint);
    }

    mount(side,
      formulaCard(joint),
      reasonCard(panel, joint),
      resistanceCard(joint),
      factsCard(panel, joint),
      dailyCard());
  }

  function jointSelect(panel, joint) {
    const joints = (panel.joints || []).filter((j) => j.zone === 'bottom')
      .slice().sort((a, b) => (b.theta_k || -99) - (a.theta_k || -99));
    const sel = h('select.panel-select', {
      onchange: (ev) => ctx.navigate('kanit', panel.panel_key, ev.target.value),
    }, ...joints.map((j) => h('option', {
      value: j.key,
      selected: j.key === joint.key,
      text: `${fmt.shortJoint(j.key)} · θ ${fmt.num(j.theta_k, 2)} K`,
    })));
    return sel;
  }

  return { el, update, destroy() { destroyCharts(); clear(el); } };
}
