// PANO GÖZ · uygulama durumu ve adres yönlendirme.
//
// Seçili pano ve seçili bağlantı adres çubuğunda (hash) durur: bir ekran
// paylaşılabilir, F5 yerini kaybettirmez, judge kendi sekmesinde aynı görüntüyü
// açar. Durum tek yönlüdür: set() -> abonelere haber -> ekran yeniden çizer.

export const VIEWS = ['filo', 'pano', 'kanit', 'prpd', 'alarm', 'scada'];

export const VIEW_TITLE = {
  filo: 'Filo',
  pano: 'Pano detayı · dijital ikiz',
  kanit: 'Kanıt',
  prpd: 'PRPD · RF imzası',
  alarm: 'Alarmlar',
  scada: 'SCADA register bloğu',
};

const state = {
  view: 'filo',
  panelKey: null,
  jointKey: null,
  tab: null,
  fleet: null,       // /api/fleet gövdesi
  panel: null,       // seçili panonun PanelLive.to_dict()
  panelError: null,  // 404 vb.
  health: null,      // /api/health
  conn: 'down',
  connDetail: '',
};

const subs = new Set();

export function get() { return state; }

export function set(patch) {
  let changed = false;
  for (const [k, v] of Object.entries(patch)) {
    if (state[k] !== v) { state[k] = v; changed = true; }
  }
  if (changed) emit();
  return state;
}

export function subscribe(fn) {
  subs.add(fn);
  return () => subs.delete(fn);
}

let raf = 0;
function emit() {
  if (raf) return;
  raf = requestAnimationFrame(() => {
    raf = 0;
    for (const fn of Array.from(subs)) {
      try { fn(state); } catch (e) { console.error('abone hatası', e); }
    }
  });
}

// --------------------------------------------------------------------------
// Hash yönlendirme:  #/filo · #/pano/SOKE-14 · #/kanit/SOKE-14/C06-L1-PABUC
//                    #/prpd/SOKE-14 · #/alarm/bastirilan · #/scada/SOKE-14
// --------------------------------------------------------------------------

export function parseHash(hash) {
  const raw = String(hash || '').replace(/^#\/?/, '');
  const parts = raw.split('/').filter(Boolean).map(decodeURIComponent);
  const view = VIEWS.includes(parts[0]) ? parts[0] : 'filo';
  const out = { view, panelKey: null, jointKey: null, tab: null };
  if (view === 'alarm') {
    out.tab = parts[1] || 'aktif';
  } else if (view === 'kanit') {
    out.panelKey = parts[1] || null;
    out.jointKey = parts[2] || null;
  } else if (view !== 'filo') {
    out.panelKey = parts[1] || null;
  }
  return out;
}

export function buildHash(view, a, b) {
  const p = ['#', view];
  if (a) p.push(encodeURIComponent(a));
  if (b) p.push(encodeURIComponent(b));
  return p.join('/');
}

/** Adres çubuğunu değiştir; hashchange dinleyicisi durumu günceller. */
export function navigate(view, a, b) {
  const target = buildHash(view, a, b);
  if (location.hash === target) applyHash();
  else location.hash = target;
}

export function applyHash() {
  const r = parseHash(location.hash);
  // Adreste pano yoksa son bilinen pano korunur: filo ve alarm ekranları pano
  // taşımaz, ama oradan bir pano ekranına geçildiğinde seçim kaybolmamalıdır.
  set({
    view: r.view,
    tab: r.tab,
    panelKey: r.panelKey || state.panelKey,
    jointKey: r.view === 'kanit' ? (r.jointKey || state.jointKey) : state.jointKey,
  });
}

export function startRouter() {
  window.addEventListener('hashchange', applyHash);
  if (!location.hash) location.hash = buildHash('filo');
  else applyHash();
}

// --------------------------------------------------------------------------
// Küçük yardımcılar
// --------------------------------------------------------------------------

export function panelSummary(key) {
  const f = state.fleet;
  if (!f || !Array.isArray(f.panels)) return null;
  return f.panels.find((p) => p.panel_key === key) || null;
}

export function panelList() {
  const f = state.fleet;
  return f && Array.isArray(f.panels) ? f.panels : [];
}

/** İlk pano: filo geldiğinde bir seçim yoksa en kötü Δ7 günlük panoyu seçeriz. */
export function defaultPanelKey() {
  const list = panelList();
  if (!list.length) return null;
  const sorted = list.slice().sort((a, b) => (b.theta_delta_7d || 0) - (a.theta_delta_7d || 0));
  return sorted[0].panel_key;
}
