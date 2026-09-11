// PANO GÖZ · S1 Filo.
//
// Sol: filonun coğrafi görünümü. Harita altlığı YOKTUR ve olmayacaktır - kurulum
// hava boşluklu, karo (tile) sunucusu yok. Bunun yerine gerçek enlem/boylamdan
// eşdikdörtgen izdüşümle çizilmiş bir ızgara, ölçek çubuğu ve panolar. Bir
// operatörün haritadan istediği tek şey "hangi ilçede, birbirine yakın mı" ve
// bunu ızgara da verir.
//
// Sağ: sıralanabilir tablo. VARSAYILAN SIRALAMA "Δ7 gün"dür, risk değil.
// Kontrol odası operatörü şu an en kötü olanı ister; varlık mühendisi en hızlı
// bozulanı ister. İkincisi ürünün kendisidir: bir pano bugün 78 sağlık endeksiyle
// duruyorsa ve haftada 1,2 K kötüleşiyorsa, bugün 62'de duran ama sabit olan
// panodan daha acildir. Sütun başlığındaki ipucu bunu ekranda da söyler.

import { h, s, mount, empty, hint } from './dom.js';
import * as fmt from './fmt.js';
import * as store from './store.js';

const COLS = [
  { key: 'panel_key', label: 'Pano', type: 'text', sortable: true },
  { key: 'severity', label: 'Seviye', type: 'sev', sortable: true },
  { key: 'health_index', label: 'Sağlık', type: 'hi', sortable: true },
  { key: 'theta_max', label: 'θ maks', type: 'num', dec: 2, unit: 'K', sortable: true },
  {
    key: 'theta_delta_7d', label: 'Δ7 gün', type: 'delta', dec: 2, unit: 'K', sortable: true,
    tip: 'θ değerinin son 7 gündeki değişimi. Bu tablo VARSAYILAN olarak buna göre sıralanır, '
       + 'riske göre değil: kontrol odası "şu an en kötü"yü ister, varlık mühendisi "en hızlı '
       + 'bozulanı" ister. Ürün olan sütun budur - bugün iyi görünen ama haftada 1 K tırmanan '
       + 'bir bağlantı, sabit duran kötü bir bağlantıdan daha acildir.',
  },
  { key: 'sensitivity_pct', label: 'Görünürlük', type: 'sens', sortable: true,
    tip: 'θ ancak yük varsa görülür: θ_min = 3σ / f². Yük faktörü 0,35’in altına düşerse '
       + 'sistem "görünürlük düşük" der ve bunu saklamaz.' },
  { key: 'load_factor', label: 'Yük', type: 'pct100', sortable: true },
  { key: 'alarm_count', label: 'Alarm', type: 'int', sortable: true },
  { key: 'devices_online', label: 'Cihaz', type: 'dev', sortable: true },
  { key: 'data_age_s', label: 'Veri yaşı', type: 'age', sortable: true },
];

export function create(ctx) {
  const el = h('div.view');
  let sortKey = 'theta_delta_7d';
  let sortDir = -1;
  let lastPanels = [];

  const statRow = h('div.row.wrap');
  const mapCard = h('div.card');
  const tblCard = h('div.card');
  const head = h('div.view-head',
    h('h1', { text: 'Filo' }), statRow);

  mount(el, head, h('div.fleet-grid', mapCard, tblCard));

  function statChip(label, value, note) {
    return h('div.stat',
      h('div.stat-k', { text: label }),
      h('div.stat-v', { text: value }),
      note ? h('div.stat-n', { text: note }) : null);
  }

  function renderStats(fleet) {
    const panels = (fleet && fleet.panels) || [];
    const worst = panels.reduce((a, p) => Math.max(a, fmt.sevRank(p.severity)), 0);
    const alarms = panels.reduce((a, p) => a + (p.alarm_count || 0), 0);
    const blind = panels.filter((p) => (p.status_flags || []).some((f) => fmt.BLIND_FLAGS.has(f))).length;
    mount(statRow,
      h('div.grid-4', { style: { minWidth: '760px' } },
        statChip('Pano', fmt.int(panels.length), 'izlenen dağıtım panosu'),
        statChip('Aktif alarm', fmt.int(alarms),
          'ekip kuyruğu: ' + fmt.int(fleet && fleet.dispatch_queue)),
        statChip('Bastırılan (24 sa)', fmt.int(fleet && fleet.suppressed_24h),
          'gerekçeleriyle kayıtlı'),
        statChip('Görüş kısıtlı pano', fmt.int(blind),
          'arıza değil · göremediğimiz durum')),
      h('div.row.wrap', { style: { marginLeft: 'auto' } },
        h('span.chip', h('span', { text: 'En yüksek seviye' }), fmt.sevBadge(fmt.SEVERITY_ORDER[worst])),
        h('span.chip', h('span', { text: 'Dedektör gecikmesi' }),
          h('b', { text: fmt.dur(fleet && fleet.detector_lag_s) }))));
  }

  // ---------------------------------------------------------------- harita --

  function renderMap(panels, selected) {
    if (!panels.length) {
      mount(mapCard,
        h('header', h('h2', { text: 'Coğrafi görünüm' })),
        h('div.body', empty('Filo verisi yok', 'API bağlantısı kurulunca panolar burada belirir')));
      return;
    }
    const lats = panels.map((p) => p.lat || 0).filter(Boolean);
    const lons = panels.map((p) => p.lon || 0).filter(Boolean);
    let lat0 = Math.min(...lats), lat1 = Math.max(...lats);
    let lon0 = Math.min(...lons), lon1 = Math.max(...lons);
    if (!Number.isFinite(lat0) || lat1 - lat0 < 0.2) { lat0 = 36.4; lat1 = 39.4; }
    if (!Number.isFinite(lon0) || lon1 - lon0 < 0.2) { lon0 = 26.5; lon1 = 29.6; }
    const padLat = (lat1 - lat0) * 0.12, padLon = (lon1 - lon0) * 0.12;
    lat0 -= padLat; lat1 += padLat; lon0 -= padLon; lon1 += padLon;

    // eşdikdörtgen izdüşüm, ortalama enlemde kosinüs düzeltmesiyle
    const midLat = (lat0 + lat1) / 2;
    const kx = Math.cos((midLat * Math.PI) / 180);
    const W = 1000;
    const H = Math.max(360, Math.round((W * (lat1 - lat0)) / ((lon1 - lon0) * kx)));
    const X = (lon) => ((lon - lon0) / (lon1 - lon0)) * W;
    const Y = (lat) => H - ((lat - lat0) / (lat1 - lat0)) * H;

    const svg = s('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Filo haritası' });
    svg.appendChild(s('rect', { x: 0, y: 0, width: W, height: H, fill: '#070a0f' }));

    // ızgara
    const gstep = (lon1 - lon0) > 3 ? 1 : 0.5;
    for (let lon = Math.ceil(lon0 / gstep) * gstep; lon <= lon1; lon += gstep) {
      svg.appendChild(s('line', { x1: X(lon), y1: 0, x2: X(lon), y2: H, stroke: '#1a2430', 'stroke-width': 1 }));
      svg.appendChild(s('text', { x: X(lon) + 4, y: H - 8, fill: '#54657a', 'font-size': 15 },
        fmt.num(lon, 1) + '° D'));
    }
    for (let lat = Math.ceil(lat0 / gstep) * gstep; lat <= lat1; lat += gstep) {
      svg.appendChild(s('line', { x1: 0, y1: Y(lat), x2: W, y2: Y(lat), stroke: '#1a2430', 'stroke-width': 1 }));
      svg.appendChild(s('text', { x: 6, y: Y(lat) - 6, fill: '#54657a', 'font-size': 15 },
        fmt.num(lat, 1) + '° K'));
    }

    // ölçek çubuğu: 1° boylam = 111,32 km * cos(enlem)
    const kmPerDegLon = 111.32 * kx;
    const barKm = (lon1 - lon0) * kmPerDegLon > 220 ? 50 : 20;
    const barPx = (barKm / kmPerDegLon / (lon1 - lon0)) * W;
    svg.appendChild(s('line', { x1: W - barPx - 30, y1: 30, x2: W - 30, y2: 30, stroke: '#8ea0b4', 'stroke-width': 3 }));
    svg.appendChild(s('text', { x: W - barPx - 30, y: 22, fill: '#8ea0b4', 'font-size': 15 }, `${barKm} km`));

    for (const p of panels) {
      if (!p.lat || !p.lon) continue;
      const cx = X(p.lon), cy = Y(p.lat);
      const meta = fmt.sevMeta(p.severity);
      const rank = fmt.sevRank(p.severity);
      const g = s('g.map-dot' + (p.panel_key === selected ? '.sel' : ''), {
        dataset: { panel: p.panel_key },
      });
      g.appendChild(s('circle.halo', {
        cx, cy, r: 18 + rank * 2, fill: meta.color, opacity: p.panel_key === selected ? 0.28 : 0.10,
      }));
      // renk + şekil birlikte
      if (rank <= 1) {
        g.appendChild(s('circle', {
          cx, cy, r: 8, fill: rank === 0 ? meta.color : 'none', stroke: meta.color, 'stroke-width': 3,
        }));
      } else if (rank === 4) {
        g.appendChild(s('rect', { x: cx - 8, y: cy - 8, width: 16, height: 16, fill: meta.color }));
      } else {
        g.appendChild(s('path', {
          d: `M${cx} ${cy - 10} L${cx + 10} ${cy + 7} L${cx - 10} ${cy + 7} Z`,
          fill: rank === 3 ? meta.color : 'none', stroke: meta.color, 'stroke-width': 3,
        }));
      }
      // Etiketler üst üste binmesin: sıraya göre bir yukarı bir aşağı kaydır ve
      // arkasına koyu bir kontur koy (paint-order) ki ızgara üstünde okunsun.
      const dy = (panels.indexOf(p) % 2 === 0) ? -14 : 20;
      g.appendChild(s('text', {
        x: cx + 13, y: cy + dy, fill: '#c6d3e2', 'font-size': 15,
        stroke: '#070a0f', 'stroke-width': 4, 'paint-order': 'stroke',
      }, p.panel_key));
      g.appendChild(s('title', {}, [
        `${p.panel_key} · ${p.name || ''}`,
        `${p.dso || ''} ${p.site || ''}`,
        `Sağlık ${fmt.num(p.health_index, 0)} · ${meta.label}`,
        `θ maks ${fmt.num(p.theta_max, 2)} K · Δ7g ${fmt.signed(p.theta_delta_7d, 2)} K`,
      ].join('\n')));
      g.addEventListener('click', () => ctx.navigate('pano', p.panel_key));
      svg.appendChild(g);
    }

    mount(mapCard,
      h('header',
        h('h2', { text: 'Coğrafi görünüm' }),
        h('span.sp'),
        h('span.tiny.muted', { text: 'eşdikdörtgen izdüşüm · harita altlığı yok (çevrimdışı)' })),
      h('div.body.flush',
        h('div.map-wrap', svg,
          h('div.map-legend',
            ...fmt.SEVERITY_ORDER.map((k) => h('span.li',
              h('span', { style: { color: fmt.sevColor(k), display: 'inline-flex' } }, fmt.sevShape(k, 13)),
              h('span', { text: fmt.sevMeta(k).label }))),
            h('span.li.tiny.muted', { text: 'nokta = pano · tıkla, dijital ikize git' })))));
  }

  // ----------------------------------------------------------------- tablo --

  function cellFor(col, p) {
    switch (col.type) {
      case 'sev': return h('td', fmt.sevBadge(p.severity));
      case 'hi': {
        const hi = Number(p.health_index || 0);
        return h('td.n',
          h('span.hi-bar', h('i', { class: fmt.hiClass(hi), style: { width: Math.max(2, hi) + '%' } })),
          h('span', { text: fmt.num(hi, 0) }));
      }
      case 'delta': {
        const v = Number(p.theta_delta_7d || 0);
        const cls = v > 0.5 ? 'delta-up' : (v < -0.5 ? 'delta-down' : 'delta-flat');
        return h('td.n', h('span.' + cls, { text: fmt.signed(v, 2) + ' K' }));
      }
      case 'num': return h('td.n', { text: fmt.num(p[col.key], col.dec) + ' ' + (col.unit || '') });
      case 'int': return h('td.n', { text: fmt.int(p[col.key]) });
      case 'pct100': return h('td.n', { text: fmt.pct(100 * Number(p.load_factor || 0), 0) });
      case 'sens': {
        const v = Number(p.sensitivity_pct || 0);
        const low = (p.status_flags || []).includes('SENSITIVITY_LOW') || v < 50;
        return h('td.n', h('span', { text: fmt.pct(v, 0), style: { color: low ? 'var(--sev-uyari)' : '' } }));
      }
      case 'dev': {
        const on = Number(p.devices_online || 0);
        return h('td.n', h('span', {
          text: `${fmt.int(on)}/9`,
          style: { color: on < 9 ? 'var(--sev-uyari)' : '' },
        }));
      }
      case 'age': {
        const a = Number(p.data_age_s || 0);
        return h('td.n', h('span', { text: fmt.dur(a), style: { color: a > 90 ? 'var(--sev-kritik)' : '' } }));
      }
      default:
        return h('td',
          h('div', { text: p.panel_key }),
          h('div.tiny.muted', { text: `${p.dso || ''} · ${p.site || ''}` }));
    }
  }

  function renderTable(panels, selected) {
    const rows = panels.slice().sort((a, b) => {
      const va = a[sortKey], vb = b[sortKey];
      if (sortKey === 'severity') return (fmt.sevRank(a.severity) - fmt.sevRank(b.severity)) * sortDir;
      if (typeof va === 'string' || typeof vb === 'string') {
        return String(va || '').localeCompare(String(vb || ''), 'tr') * sortDir;
      }
      return ((Number(va) || 0) - (Number(vb) || 0)) * sortDir;
    });

    const thead = h('thead', h('tr', ...COLS.map((c) => {
      const arrow = sortKey === c.key ? h('span.arrow', { text: sortDir < 0 ? '▼' : '▲' }) : null;
      const label = c.tip ? hint(c.label, c.tip) : h('span', { text: c.label });
      const th = h('th' + (sortKey === c.key ? '.sorted' : ''), label, arrow);
      th.addEventListener('click', () => {
        if (sortKey === c.key) sortDir = -sortDir;
        else { sortKey = c.key; sortDir = c.key === 'panel_key' ? 1 : -1; }
        renderTable(lastPanels, store.get().panelKey);
      });
      return th;
    })));

    const tbody = h('tbody', ...rows.map((p) => {
      const tr = h('tr.click' + (p.panel_key === selected ? '.sel' : ''),
        ...COLS.map((c) => cellFor(c, p)));
      tr.addEventListener('click', () => ctx.navigate('pano', p.panel_key));
      return tr;
    }));

    mount(tblCard,
      h('header',
        h('h2', { text: 'Panolar' }),
        h('span.sp'),
        h('span.tiny.muted', { text: `${fmt.int(rows.length)} kayıt · sıralama: ` }),
        h('span.tiny', { text: COLS.find((c) => c.key === sortKey).label })),
      rows.length
        ? h('div.body.flush', h('div.fleet-table-wrap', h('table.tbl', thead, tbody)))
        : h('div.body', empty('Pano yok', 'Simülatör başlatılınca liste dolar')));
  }

  function update(state) {
    const panels = (state.fleet && state.fleet.panels) || [];
    lastPanels = panels;
    renderStats(state.fleet);
    renderMap(panels, state.panelKey);
    renderTable(panels, state.panelKey);
  }

  return { el, update, destroy() {} };
}
