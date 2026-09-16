// PANO GÖZ · uygulama kabuğu.
//
// Sol raylık, üst şerit, ekran değiştirme, canlı bağlantı göstergesi, senaryo
// çekmecesi, kip pencereleri ve bildirim balonları. Hepsi düz ES modülü;
// paket yöneticisi, derleyici veya çalışma zamanı çerçevesi yoktur.

import { h, mount, clear, qs, empty } from './dom.js';
import * as fmt from './fmt.js';
import * as store from './store.js';
import { api, Live, LIVE_STATE } from './api.js';
import * as theme from './theme.js';
import { combo } from './combo.js';

import * as viewFleet from './view-fleet.js';
import * as viewPanel from './view-panel.js';
import * as viewEvidence from './view-evidence.js';
import * as viewPrpd from './view-prpd.js';
import * as viewAlarms from './view-alarms.js';
import * as viewScada from './view-scada.js';

const VIEW_MODULES = {
  filo: viewFleet,
  pano: viewPanel,
  kanit: viewEvidence,
  prpd: viewPrpd,
  alarm: viewAlarms,
  scada: viewScada,
};

const RAIL = [
  { key: 'filo', label: 'Filo', sub: 'S1', icon: 'map' },
  { key: 'pano', label: 'Pano', sub: 'S2 · ikiz', icon: 'panel' },
  { key: 'kanit', label: 'Kanıt', sub: 'S3', icon: 'chart' },
  { key: 'prpd', label: 'PRPD', sub: 'S4', icon: 'wave' },
  { key: 'alarm', label: 'Alarmlar', sub: 'S5', icon: 'bell' },
  { key: 'scada', label: 'SCADA', sub: 'S6', icon: 'grid' },
];

const ICONS = {
  map: 'M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3zM9 3v15M15 6v15',
  panel: 'M4 3h16v18H4zM4 9h16M8 12v6M12 12v6M16 12v6',
  chart: 'M3 20h18M5 16l4-6 4 4 6-9',
  wave: 'M3 12c2-7 4 7 6 0s4 7 6 0 4 7 6 0',
  bell: 'M6 9a6 6 0 1112 0c0 5 2 6 2 6H4s2-1 2-6zM10 21h4',
  grid: 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',
};

const TEMA_ICONS = {
  // güneş: daire + ışınlar · ay: hilal. İkisi de tek yollu, harici set yok.
  acik: 'M12 5.6a6.4 6.4 0 100 12.8 6.4 6.4 0 000-12.8M12 1.6v2M12 21v2M3.9 3.9l1.4 1.4'
      + 'M18.7 18.7l1.4 1.4M1.6 12h2M20.4 12h2M3.9 20.1l1.4-1.4M18.7 5.3l1.4-1.4',
  koyu: 'M20.5 14.6A8.6 8.6 0 019.4 3.5a8.6 8.6 0 1011.1 11.1z',
};

function temaSwitch() {
  const cur = theme.current();
  const btn = (t, label) => h('button', {
    'aria-pressed': String(cur === t),
    'aria-label': label,
    title: label,
    onclick: () => { if (theme.current() !== t) theme.apply(t); },
  }, (() => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '1.7');
    svg.setAttribute('stroke-linecap', 'round');
    const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', TEMA_ICONS[t]);
    svg.appendChild(p);
    return svg;
  })());
  return h('div.tema-sw', { role: 'group', 'aria-label': 'Tema' },
    btn('koyu', 'Koyu tema'), btn('acik', 'Açık tema'));
}

function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.6');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  p.setAttribute('d', ICONS[name] || ICONS.grid);
  svg.appendChild(p);
  return svg;
}

// --------------------------------------------------------------------------
// Kabuk parçaları
// --------------------------------------------------------------------------

const main = qs('#main');
const rail = qs('#rail');
const head = qs('#head');
const drawer = qs('#drawer');
const toasts = qs('#toasts');

let current = null;      // {mod, inst}
let panelFetchKey = null;
let scenarios = null;

function toast(title, detail, kind) {
  const t = h('div.toast' + (kind ? '.' + kind : ''),
    h('div.t', { text: title }),
    detail ? h('div.d', { text: detail }) : null);
  toasts.appendChild(t);
  setTimeout(() => { if (t.parentNode) t.parentNode.removeChild(t); }, 6500);
}

function modal(opts) {
  const bg = h('div#modal-bg');
  const close = () => { if (bg.parentNode) bg.parentNode.removeChild(bg); };
  const okBtn = h('button.btn.primary', {
    text: opts.okLabel || 'Tamam',
    onclick: async () => {
      if (!opts.onOk) { close(); return; }
      okBtn.disabled = true;
      let r;
      try { r = await opts.onOk(); } finally { okBtn.disabled = false; }
      if (r !== false) close();
    },
  });
  const box = h('div.modal',
    h('header', h('h2', { text: opts.title || '' }), h('span.sp'),
      h('button.btn.sm', { text: 'kapat', onclick: close })),
    h('div.body', opts.body || ''),
    h('footer',
      opts.note ? h('span.tiny.muted', { text: opts.note }) : null,
      h('span.sp', { style: { flex: '1 1 auto' } }),
      h('button.btn', { text: 'Vazgeç', onclick: close }),
      okBtn));
  bg.addEventListener('click', (ev) => { if (ev.target === bg) close(); });
  document.addEventListener('keydown', function esc(ev) {
    if (ev.key === 'Escape') { close(); document.removeEventListener('keydown', esc); }
  });
  bg.appendChild(box);
  document.body.appendChild(bg);
  return close;
}

const ctx = {
  navigate: (view, a, b) => store.navigate(view, a, b),
  toast,
  modal,
  refresh: () => render(store.get()),
  setTab: (tab) => { location.hash = store.buildHash('alarm', tab); },
};

// --------------------------------------------------------------------------
// Raylık ve üst şerit
// --------------------------------------------------------------------------

let railSig = '';

function renderRail(state) {
  if (state.view === railSig) return;
  railSig = state.view;
  mount(rail, ...RAIL.map((r) => {
    const btn = h('button.rail-btn', {
      'aria-current': String(state.view === r.key),
      title: store.VIEW_TITLE[r.key],
      onclick: () => {
        const key = state.panelKey || store.defaultPanelKey();
        if (r.key === 'kanit') store.navigate('kanit', key, state.jointKey || '');
        else if (r.key === 'filo' || r.key === 'alarm') store.navigate(r.key);
        else store.navigate(r.key, key);
      },
    }, icon(r.icon), h('span.lbl', { text: r.label }), h('span.sub', { text: r.sub }));
    return btn;
  }),
  h('div.rail-spacer'),
  h('button.rail-btn', {
    title: 'Senaryo çekmecesi',
    onclick: () => toggleDrawer(),
  }, icon('wave'), h('span.lbl', { text: 'Demo' }), h('span.sub', { text: 'senaryo' })));
}

function connPill(state) {
  const cls = state.conn === LIVE_STATE.WS ? 'conn-ws'
    : state.conn === LIVE_STATE.POLL ? 'conn-poll' : 'conn-down';
  const label = state.conn === LIVE_STATE.WS ? 'canlı · WebSocket'
    : state.conn === LIVE_STATE.POLL ? 'yoklama · 3 sn' : 'bağlantı yok';
  return h('span.chip.' + cls, { title: state.connDetail || '' },
    h('span.conn-dot'), h('span', { text: label }));
}

// Üst şerit canlı akışın her çerçevesinde yeniden kurulmaz: içindeki 112
// seçenekli açılır liste her seferinde yeniden yaratılırsa kullanıcı onu açık
// tutamaz, liste elinin altında kapanır. Görünen bir şey değişmedikçe
// dokunmuyoruz.
let headSig = '';
let uptimeEl = null;

// Pano seçici tek bir örnektir ve üst şerit yeniden kurulsa da yaşar: içinde
// açık bir arama kutusu olabilir, onu her çerçevede yok etmek olmaz.
let panoSecici = null;

function panoSeciciEl(state, panels) {
  if (!panoSecici) {
    panoSecici = combo({
      placeholder: 'Pano seç…',
      ara: 'Pano, ilçe veya dağıtım şirketi ara…',
      bos: 'pano yok',
      genislik: '270px',
      onPick: (key) => {
        const st = store.get();
        // Filo ekranındayken seçim ekran değiştirmez, sağdaki künyeyi açar.
        if (st.view === 'filo') { store.set({ panelKey: key }); return; }
        const v = st.view === 'alarm' ? 'pano' : st.view;
        store.navigate(v, key, v === 'kanit' ? '' : undefined);
      },
    });
  }
  panoSecici.setItems(panels.map((p) => ({
    value: p.panel_key,
    label: p.panel_key,
    sub: `${p.dso || ''} · ${p.site || ''} · Δ7g ${fmt.signed(p.theta_delta_7d, 1)} K`,
    badge: fmt.sevBadge(p.severity),
  })));
  panoSecici.setValue(state.panelKey);
  return panoSecici.el;
}

function renderHead(state) {
  const panels = store.panelList();
  const hlth0 = state.health || {};
  // Calisma suresi her saniye degisir ve TEK BASINA seridi yeniden kurmaya
  // degmez; yerinde tazelenir. Imzada olsaydi acilir liste saniyede bir
  // kapanirdi.
  const sig = [state.view, state.panelKey, state.conn, panels.length,
    hlth0.version, hlth0.sim_running, theme.current(),
    panels.map((p) => p.panel_key + p.severity + fmt.signed(p.theta_delta_7d, 1)).join()].join('|');
  if (sig === headSig) {
    if (uptimeEl) uptimeEl.textContent = fmt.dur(hlth0.uptime_s);
    return;
  }
  headSig = sig;
  const sel = panoSeciciEl(state, panels);

  const hlth = state.health || {};
  mount(head,
    h('div.head-title', { text: store.VIEW_TITLE[state.view] || 'PANO GÖZ' }),
    sel,
    h('span.head-spacer'),
    hlth.sim_running !== undefined
      ? h('span.chip', { title: 'Simülatör durumu' },
          h('span', { text: 'Simülatör' }),
          h('b', { text: hlth.sim_running ? 'çalışıyor' : 'durdu' }))
      : null,
    h('span.chip.link', {
      title: 'Sağlanan "Akım Sensörü" verisinin RANDBETWEEN olduğunun kanıtı',
      onclick: showSuppliedProof,
    }, h('span', { text: 'Veri kanıtı' })),
    connPill(state),
    h('span.chip', { title: 'Sunucu sürümü ve çalışma süresi' },
      h('span', { text: 'v' + (hlth.version || '—') }),
      (uptimeEl = h('b', { text: fmt.dur(hlth.uptime_s) }))),
    temaSwitch());
}

// --------------------------------------------------------------------------
// Senaryo çekmecesi
// --------------------------------------------------------------------------

function toggleDrawer(force) {
  const open = force !== undefined ? force : !drawer.classList.contains('open');
  drawer.classList.toggle('open', open);
  if (open) loadScenarios();
}

async function loadScenarios() {
  const body = qs('.body', drawer);
  if (scenarios === null) {
    mount(body, h('div.skeleton', { style: { height: '120px' } }));
    scenarios = await api.scenarios().catch(() => []);
  }
  const list = Array.isArray(scenarios) ? scenarios : [];
  const state = store.get();
  const key = state.panelKey || store.defaultPanelKey();
  mount(body,
    h('div.note', {
      text: key ? `Hedef pano: ${key}` : 'Önce bir pano seçin; senaryo o panoya enjekte edilir.',
    }),
    h('div.note.honest', {
      text: 'Negatif kontroller ayrıca işaretlidir. İzleyicinin dikkat etmesi gereken şey, '
          + 'bunların alarm ÜRETMEMESİDİR: sistemin değeri, açtığı alarmlar kadar '
          + 'açmadıklarındadır.',
    }),
    ...list.map((sc) => {
      const negative = sc.expect_alarm === false;
      return h('div.scenario' + (negative ? '.negative' : ''),
        h('div.top',
          h('span.ttl', { text: sc.label_tr || sc.key }),
          negative ? h('span.neg-badge', { text: 'alarm ÜRETMEMELİ' }) : null,
          h('button.btn.sm', {
            text: 'Enjekte et',
            disabled: !key,
            onclick: async (ev) => {
              const btn = ev.currentTarget;
              btn.disabled = true;
              try {
                const r = await api.inject(sc.key, { panel_key: key });
                toast('Senaryo enjekte edildi', `${sc.label_tr || sc.key} → ${key}`,
                  negative ? '' : 'warn');
                if (r && r.injected) console.info('injected', r.injected);
              } catch (e) {
                toast('Enjeksiyon başarısız', String(e.message || e), 'bad');
              } finally {
                btn.disabled = false;
              }
            },
          })),
        h('div.desc', { text: sc.description_tr || '' }),
        h('div.tiny.muted.mono', { text: sc.key }));
    }),
    h('button.btn', {
      text: 'Demoyu sıfırla',
      style: { marginTop: '10px' },
      onclick: async () => {
        try { await api.demoReset(); toast('Demo sıfırlandı', '', 'ok'); }
        catch (e) { toast('Sıfırlama başarısız', String(e.message || e), 'bad'); }
      },
    }));
}

// --------------------------------------------------------------------------
// "Veri kanıtı" - sağlanan sayfanın RANDBETWEEN olduğunun gösterimi
// --------------------------------------------------------------------------

function jsonTree(value) {
  if (value === null || value === undefined) return h('span.muted', { text: 'null' });
  if (Array.isArray(value)) {
    if (value.every((v) => typeof v !== 'object')) {
      return h('span.n', { text: value.map((v) => typeof v === 'number' ? fmt.num(v, 4) : String(v)).join(', ') });
    }
    return h('ul', ...value.map((v) => h('li', jsonTree(v))));
  }
  if (typeof value === 'object') {
    return h('ul', ...Object.entries(value).map(([k, v]) =>
      h('li', h('span.k', { text: k + ': ' }), jsonTree(v))));
  }
  if (typeof value === 'number') return h('span.n', { text: fmt.num(value, 4) });
  if (typeof value === 'boolean') return h('span.b', { text: value ? 'doğru' : 'yanlış' });
  return h('span.s', { text: String(value) });
}

async function showSuppliedProof() {
  const body = h('div', h('div.skeleton', { style: { height: '160px' } }));
  modal({
    title: 'Sağlanan verinin analizi',
    body,
    okLabel: 'Kapat',
    note: 'Kaynak: /api/analysis/supplied-data',
  });
  try {
    const d = await api.supplied();
    mount(body,
      h('div.note.honest', {
        text: 'Yarışmayla verilen "Akım Sensörü" sayfası, 15 dakikalık aralıklarla 152 satırdır '
            + 've =RANDBETWEEN(15;90) ile üretilmiş düzgün dağılımlı gürültüdür. Bunu saklamak '
            + 'yerine kanıtlıyoruz: gecikme-1 otokorelasyon ≈ 0, fark varyansı oranı 2,00, '
            + 'aşırı basıklık −1,21, KS ve ki-kare testleri düzgün dağılımı reddetmiyor. '
            + 'Gerçek bir fider 15 dakikalık ölçümde 0,97’nin üzerinde otokorelasyon verir.',
      }),
      h('div.jtree', jsonTree(d)));
  } catch (e) {
    mount(body, empty('Analiz alınamadı', String(e.message || e)));
  }
}

// --------------------------------------------------------------------------
// Ekran değiştirme
// --------------------------------------------------------------------------

function render(state) {
  renderRail(state);
  renderHead(state);
  const mod = VIEW_MODULES[state.view] || VIEW_MODULES.filo;
  if (!current || current.mod !== mod) {
    if (current && current.inst.destroy) current.inst.destroy();
    const inst = mod.create(ctx);
    current = { mod, inst };
    mount(main, inst.el);
  }
  try {
    current.inst.update(state);
  } catch (e) {
    console.error('ekran çizim hatası', e);
    mount(main, empty('Ekran çizilemedi', String(e && e.message || e)));
  }
}

// --------------------------------------------------------------------------
// Veri akışı
// --------------------------------------------------------------------------

const NEEDS_PANEL = new Set(['pano', 'kanit', 'prpd', 'scada']);

// 404 veren bir pano anahtarı bir daha istenmez: aksi hâlde her canlı çerçevede
// yeniden denenir ve konsol 404 çöplüğüne döner. Anahtar değişince veya filo
// listesinde o anahtar görününce yeniden denenir.
let failedPanelKey = null;

async function fetchPanel(key) {
  if (!key || key === failedPanelKey) return;
  panelFetchKey = key;
  try {
    const p = await api.panel(key);
    if (panelFetchKey !== key) return;
    failedPanelKey = null;
    store.set({ panel: p, panelError: null });
  } catch (e) {
    if (panelFetchKey !== key) return;
    if (e.status === 404) failedPanelKey = key;
    store.set({ panel: null, panelError: e.status === 404 ? 'Bu anahtarla bir pano yok' : String(e.message || e) });
  }
}

const live = new Live({
  panelKey: () => {
    const st = store.get();
    return st.panelKey === failedPanelKey ? null : st.panelKey;
  },
  onFleet: (data) => {
    if (!data) return;
    store.set({ fleet: data });
    const st = store.get();
    if (!st.panelKey) {
      const k = store.defaultPanelKey();
      if (k) store.set({ panelKey: k });
    }
    // Filo listesinde görünen bir anahtar artık "yok" değildir; yeniden dene.
    if (failedPanelKey && (data.panels || []).some((p) => p.panel_key === failedPanelKey)) {
      failedPanelKey = null;
    }
    if (NEEDS_PANEL.has(st.view) && st.panelKey && st.panelKey !== failedPanelKey
        && (!st.panel || st.panel.panel_key !== st.panelKey)) {
      fetchPanel(st.panelKey);
    }
  },
  onPanel: (data) => {
    if (!data) return;
    const st = store.get();
    if (data.panel_key === st.panelKey) store.set({ panel: data, panelError: null });
  },
  onAlarm: (data) => {
    if (!data) return;
    const sev = data.severity || 'UYARI';
    toast(`Alarm · ${fmt.sevMeta(sev).label}`,
      `${data.panel_key || ''} ${fmt.shortJoint(data.joint_key)} · ${data.title || ''}`,
      fmt.sevRank(sev) >= 3 ? 'bad' : 'warn');
    if (store.get().view === 'alarm') ctx.refresh();
  },
  onState: (st, detail) => store.set({ conn: st, connDetail: detail }),
});

async function pollHealth() {
  try {
    const hlth = await api.health();
    store.set({ health: hlth });
  } catch (e) {
    store.set({ health: null });
  }
}

// --------------------------------------------------------------------------
// Başlangıç
// --------------------------------------------------------------------------

let lastPanelKey = null;
store.subscribe((state) => {
  if (state.panelKey !== lastPanelKey) {
    lastPanelKey = state.panelKey;
    if (failedPanelKey && failedPanelKey !== state.panelKey) failedPanelKey = null;
    if (state.panelKey) { fetchPanel(state.panelKey); live.watch(state.panelKey); }
  }
  render(state);
});

// Tema değişince canvas çizen ekranlar (PRPD ısı haritası, SCADA) renklerini
// belirteçlerden yeniden okumalı; CSS tek başına bir canvas'ı boyamaz.
theme.onChange(() => { headSig = ''; ctx.refresh(); });

store.startRouter();
render(store.get());
live.start();
pollHealth();
setInterval(pollHealth, 15000);

// İlk filo isteği: WebSocket kurulmadan da ekran dolsun.
api.fleet().then((f) => {
  store.set({ fleet: f });
  const st = store.get();
  if (!st.panelKey) {
    const k = store.defaultPanelKey();
    if (k) store.set({ panelKey: k });
  }
}).catch((e) => {
  store.set({ conn: 'down', connDetail: String(e.message || e) });
});

qs('#drawer-close').addEventListener('click', () => toggleDrawer(false));

window.PANOGOZ = { store, api, live, ctx };
