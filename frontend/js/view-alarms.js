// PANO GÖZ · S5 Alarmlar.
//
// İki sekme, EŞİT ağırlıkta:
//   "Aktif"      · açık olaylar, yaş, kanıt, onaylama (4 haneli jeton).
//   "Bastırılan" · kasıtlı olarak AÇMADIĞIMIZ her alarm ve Türkçe gerekçesi.
//
// İkincisi dipnot değildir, ürünün yarısıdır. Bir izleme sistemi sahada üçüncü
// ayda kapatılıyorsa sebebi hemen her zaman yanlış alarmdır. "Şu alarmı şu
// nedenle açmadım" diyebilen bir sistem, açtığı alarmlara da güven kazandırır.
//
// Üçüncü sekme "Bildirimler" gönderilen SMS/sesli kayıtları gösterir; hangi
// mesajın gerçekten gittiğini görmek, gecikme iddiasının denetlenebilir hâlidir.

import { h, mount, empty, clear } from './dom.js';
import * as fmt from './fmt.js';
import { api } from './api.js';

const SUPP_TITLE_TR = {
  GRID_THD_3PH: 'Şebeke olayı · üç faz birlikte',
  INRUSH: 'Trafo devreye alma (inrush)',
  GRID_FREQUENCY: 'Şebeke frekansı pencere dışında',
  LOAD_STEP: 'Yük adımı · ısıl geçici rejim',
  SENSITIVITY_LOW: 'Görünürlük düşük',
  DE_ENERGISED: 'Pano enerjisiz',
  STALE: 'Veri bayat',
  LEARN_WEEK: 'Öğrenme haftası',
  MAINTENANCE: 'Bakım modu',
  THD_I_UNGATED: 'Akım THD’si kapılandı',
  DEVICE_MOUNT_LOST: 'Sensör teması kayboldu',
  DEVICE_AIM_SHIFTED: 'Termal dizi nişanı kaydı',
  HEAT_WAVE: 'Sıcak hava dalgası',
  STORM_CAP: 'Alarm fırtınası sınırı',
  DEDUP: 'Yinelenen olay',
};

const TABS = [
  { key: 'aktif', label: 'Aktif' },
  { key: 'bastirilan', label: 'Bastırılan' },
  { key: 'bildirim', label: 'Bildirimler' },
];

export function create(ctx) {
  const el = h('div.view');
  const head = h('div.view-head');
  const tabBar = h('div.tabs');
  const body = h('div.card');
  mount(el, head, tabBar, body);

  let tab = 'aktif';
  let alarms = null;
  let supps = null;
  let notes = null;
  let loading = false;
  let lastLoad = 0;

  async function load(force) {
    const now = Date.now();
    if (loading || (!force && now - lastLoad < 4000)) return;
    loading = true;
    lastLoad = now;
    try {
      const [a, s, n] = await Promise.all([
        api.alarms('ACIK', 200).catch(() => []),
        api.suppressions(24).catch(() => []),
        api.notifications(50).catch(() => []),
      ]);
      alarms = Array.isArray(a) ? a : [];
      supps = Array.isArray(s) ? s : [];
      notes = Array.isArray(n) ? n : [];
    } finally {
      loading = false;
      ctx.refresh();
    }
  }

  function ackDialog(alarm) {
    const who = h('input.txt', { value: 'Nöbetçi operatör', placeholder: 'Adınız' });
    const token = h('input.txt.token', { maxlength: '4', inputmode: 'numeric', placeholder: '••••' });
    const msg = h('div.small.muted', {
      text: 'Onay jetonu, olay kaydıyla birlikte SMS olarak gönderilen 4 haneli koddur. '
          + 'Jeton doğrulanmadan onay kabul edilmez.',
    });
    ctx.modal({
      title: `Alarmı onayla · #${alarm.id}`,
      body: h('div.col',
        h('div', { text: alarm.title }),
        h('div.small.muted', { text: `${alarm.panel_key} · ${fmt.shortJoint(alarm.joint_key)}` }),
        h('div.row', h('span.kv-k', { text: 'Onaylayan' }), who),
        h('div.row', h('span.kv-k', { text: 'Jeton' }), token),
        msg),
      okLabel: 'Onayla',
      onOk: async () => {
        try {
          const r = await api.ack(alarm.id, who.value || 'operatör', (token.value || '').trim());
          if (r && r.ok) {
            ctx.toast('Onaylandı', `#${alarm.id} · ${who.value}`, 'ok');
            load(true);
            return true;
          }
          ctx.toast('Onay reddedildi', (r && r.reason) || 'jeton hatalı', 'bad');
          return false;
        } catch (e) {
          ctx.toast('Onay başarısız', String(e.message || e), 'bad');
          return false;
        }
      },
    });
  }

  // Kanıt rozetlerinde meta alanları tekrarlanmaz (pano ve mod zaten üst satırda),
  // bilinen büyüklükler Türkçe adıyla ve doğru birimle yazılır.
  const EV_SKIP = new Set(['panel', 'panel_key', 'mode', 'mode_label_tr', 'joint', 'joint_key']);
  const EV_TR = {
    theta_k: ['θ', 'K', 2],
    theta_min_k: ['θ_min', 'K', 2],
    slope_k_per_week: ['eğim', 'K/hafta', 2],
    cusum: ['CUSUM', '', 2],
    sensitivity_pct: ['görünürlük', '%', 0],
    load_factor: ['yük faktörü', '', 2],
    health_index: ['sağlık', '', 0],
    risk: ['risk', '', 2],
    temp_c: ['sıcaklık', '°C', 1],
    detectors_ok: ['sağlam dedektör', '', 0],
    detectors_total: ['kurulu dedektör', '', 0],
    alarm_days: ['eşik aşan gün', '', 0],
    excess_r_uohm: ['ΔR', 'µΩ', 1],
  };

  function evChip(k, v) {
    const meta = EV_TR[k];
    if (meta && typeof v === 'number') {
      return h('span.tag', { text: `${meta[0]}: ${fmt.num(v, meta[2])}${meta[1] ? ' ' + meta[1] : ''}` });
    }
    return h('span.tag', {
      text: `${k}: ${typeof v === 'number' ? fmt.num(v, 2) : String(v).slice(0, 40)}`,
    });
  }

  function alarmRow(a) {
    const now = Date.now() / 1000;
    const ev = a.evidence || {};
    const evChips = Object.entries(ev)
      .filter(([k, v]) => !EV_SKIP.has(k) && v !== null && v !== undefined && typeof v !== 'object')
      .slice(0, 7)
      .map(([k, v]) => evChip(k, v));
    return h('div.alarm-item',
      h('div.col', { style: { gap: '6px' } },
        fmt.sevBadge(a.severity),
        h('span.tiny.muted', { text: fmt.dateTimeShort(a.opened_at) }),
        h('span.tiny.muted', { text: fmt.ago(a.opened_at, now) })),
      h('div',
        h('div.ttl', { text: a.title || a.mode_label || a.mode }),
        h('div.meta', {
          text: `${a.panel_key} · ${fmt.shortJoint(a.joint_key)} · `
              + `${fmt.MODE_TR[a.mode] || a.mode_label || a.mode} · durum ${a.state}`
              + (a.dispatched ? ' · ekip yönlendirildi' : ''),
        }),
        a.action ? h('div.act', { text: a.action }) : null,
        evChips.length ? h('div.ev', ...evChips) : null,
        (a.ruled_out && a.ruled_out.length)
          ? h('details', h('summary.tiny.muted', { text: `elenen nedenler (${a.ruled_out.length})` }),
              h('ul.reason-list.ruled', ...a.ruled_out.map((r) =>
                h('li', h('span.b', { text: '✕' }), h('span', { text: r })))))
          : null),
      h('div.side',
        a.acked_at
          ? h('span.tag.ok', { text: 'onaylandı · ' + (a.acked_by || '') })
          : h('button.btn.primary', { text: 'Onayla', onclick: () => ackDialog(a) }),
        h('button.btn.sm', {
          text: 'Kanıt →',
          onclick: () => a.joint_key
            ? ctx.navigate('kanit', a.panel_key, a.joint_key)
            : ctx.navigate('pano', a.panel_key),
        })));
  }

  /** Bastırmalar tek tek değil, (pano · gerekçe) olarak kümelenir.
   *  Aynı gerekçe 60 bağlantı için 60 satır üretir; operatörün göreceği şey
   *  "TURGUTLU-02'de görünürlük düşük, 63 kez" olmalıdır - gerekçe metni birebir
   *  aynı kalır, yalnızca tekrarlar toplanır. */
  function groupSupps(list) {
    const m = new Map();
    for (const s0 of list || []) {
      const raw = String(s0.reason || '').trim();
      const code = (s0.detail && s0.detail.code)
        || (/^[A-Z0-9_]+$/.test(raw) ? raw : 'DIGER');
      const k = (s0.panel_key || '') + '|' + code;
      let g = m.get(k);
      if (!g) {
        g = { code, panel_key: s0.panel_key, count: 0, last: 0, modes: new Set(),
              joints: new Set(), sample: s0 };
        m.set(k, g);
      }
      g.count += 1;
      if ((s0.ts || 0) >= g.last) { g.last = s0.ts || 0; g.sample = s0; }
      if (s0.mode) g.modes.add(s0.mode);
      if (s0.joint_key) g.joints.add(s0.joint_key);
    }
    return Array.from(m.values()).sort((a, b) => (b.last - a.last) || (b.count - a.count));
  }

  function suppRow(g) {
    const s0 = g.sample;
    const raw = String(s0.reason || '').trim();
    const isCode = /^[A-Z0-9_]+$/.test(raw);
    const title = SUPP_TITLE_TR[g.code] || (isCode ? raw : 'Bastırıldı');
    const text = isCode ? ((s0.detail && s0.detail.text) || '') : raw;
    const det = s0.detail || {};
    const detKeys = Object.entries(det)
      .filter(([k, v]) => k !== 'text' && k !== 'code' && (typeof v === 'number' || typeof v === 'string'))
      .slice(0, 6)
      .map(([k, v]) => `${k}=${typeof v === 'number' ? fmt.num(v, 2) : v}`)
      .join('  ');
    return h('div.supp-item',
      h('div.col', { style: { gap: '4px' } },
        h('span.tag.blind', { text: 'alarm açılmadı' }),
        h('span.tiny.muted', { text: fmt.dateTimeShort(g.last) }),
        h('span.tiny.muted', { text: g.panel_key || '' }),
        g.count > 1 ? h('span.tag', { text: '× ' + fmt.int(g.count) }) : null),
      h('div',
        h('div.rsn', { text: title }),
        text ? h('div.small.dim', { text }) : null,
        h('div.meta.tiny.muted', {
          text: [
            g.joints.size ? `${fmt.int(g.joints.size)} bağlantı` : null,
            g.modes.size ? Array.from(g.modes).map((m) => fmt.MODE_TR[m] || m).join(' · ') : null,
          ].filter(Boolean).join(' · '),
        }),
        detKeys ? h('div.det', { text: detKeys }) : null));
  }

  function noteRow(n) {
    return h('tr',
      h('td', { text: fmt.dateTimeShort(n.ts) }),
      h('td', h('span.tag', { text: n.channel || '—' })),
      h('td', { text: n.target || '—' }),
      h('td.wide', h('div', { text: (n.body || '').slice(0, 220) }),
        n.transcript ? h('details', h('summary.tiny.muted', { text: 'oturum kaydı' }),
          h('pre.code', { text: String(n.transcript).slice(0, 2000) })) : null),
      h('td', h('span.tag' + (n.state === 'GONDERILDI' || n.state === 'SENT' ? '.ok' : ''),
        { text: n.state || '—' })),
      h('td.n', { text: n.incident_id ? '#' + n.incident_id : '—' }));
  }

  function renderTabs() {
    mount(tabBar, ...TABS.map((t) => {
      const count = t.key === 'aktif' ? (alarms || []).length
        : t.key === 'bastirilan' ? (supps || []).length : (notes || []).length;
      return h('button', {
        'aria-selected': String(tab === t.key),
        onclick: () => { tab = t.key; ctx.setTab(t.key); ctx.refresh(); },
      }, h('span', { text: t.label }),
        h('span.count', { text: fmt.int(count) }));
    }));
  }

  function renderBody() {
    if (alarms === null) {
      mount(body, h('div.body', h('div.skeleton', { style: { height: '220px' } })));
      return;
    }
    if (tab === 'aktif') {
      mount(body,
        h('header', h('h2', { text: 'Aktif olaylar' }), h('span.sp'),
          h('span.tiny.muted', {
            text: 'Yalnızca KRITIK ve ACIL bir telefona gider; diğerleri kuyruk kaydıdır.',
          })),
        alarms.length
          ? h('div.body.flush', ...alarms.map(alarmRow))
          : h('div.body', empty('Açık alarm yok',
              'Bu iyi haber. Bastırılan sekmesi, açılmayan alarmların gerekçesini gösterir.')));
    } else if (tab === 'bastirilan') {
      mount(body,
        h('header', h('h2', { text: 'Bastırılan alarmlar · son 24 saat' }), h('span.sp'),
          h('span.tiny.muted', {
            text: `${fmt.int((supps || []).length)} kayıt · `
                + `${fmt.int(groupSupps(supps).length)} ayrı gerekçe · denetlenebilir`,
          })),
        h('div.body',
          h('div.note.honest', {
            text: 'Bu liste bir hata günlüğü değildir, ürünün yarısıdır. Şebeke olayı, yük '
                + 'adımı, sıcak hava dalgası, düşük yük görünürlüğü, bayat veri ve sensör '
                + 'kaymaları burada ayrı ayrı görünür; hiçbiri pano arızası olarak sayılmaz.',
          })),
        (supps && supps.length)
          ? h('div.body.flush', ...groupSupps(supps).map(suppRow))
          : h('div.body', empty('Son 24 saatte bastırılan alarm yok',
              'Bastırma kuralları çalışıyor, tetiklenecek olay olmadı')));
    } else {
      mount(body,
        h('header', h('h2', { text: 'Gönderilen bildirimler' }), h('span.sp'),
          h('span.tiny.muted', {
            text: 'Bildirim gecikmesi bir ARALIKTIR: 4-13 saniye (TVOC Modbus görüntü '
                + 'yayılımı 0,2-2 s + 1 s yoklama + sunucu + SMS yolu).',
          })),
        (notes && notes.length)
          ? h('div.body.flush', h('table.tbl',
              h('thead', h('tr',
                h('th.nosort', { text: 'Zaman' }),
                h('th.nosort', { text: 'Kanal' }),
                h('th.nosort', { text: 'Hedef' }),
                h('th.nosort', { text: 'Metin' }),
                h('th.nosort', { text: 'Durum' }),
                h('th.nosort', { text: 'Olay' }))),
              h('tbody', ...notes.map(noteRow))))
          : h('div.body', empty('Bildirim kaydı yok')));
    }
  }

  function update(state) {
    if (state.tab && state.tab !== tab && TABS.some((t) => t.key === state.tab)) tab = state.tab;
    mount(head,
      h('div',
        h('h1', { text: 'Alarmlar' }),
        h('div.head-sub', {
          text: 'Aktif olaylar ve kasıtlı olarak açılmayan alarmlar - ikisi eşit ağırlıkta',
        })),
      h('span.sp'),
      h('button.btn', { text: 'Yenile', onclick: () => load(true) }));
    load(false);
    renderTabs();
    renderBody();
  }

  return { el, update, destroy() { clear(el); } };
}
