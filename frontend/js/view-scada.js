// PANO GÖZ · S6 SCADA register bloğu.
//
// Bir jüri üyesinin kendi modpoll çıktısını ekranda aynı anda görmesi, entegrasyon
// hikâyesinin oturduğu andır. Bu ekran canlı Modbus görüntüsünü gösterir:
// PDU adresi, register adı, ham değer, mühendislik değeri ve birim; ayrıca
// STATUS_WORD ve ARC_STATE bitleri Türkçe adlarıyla çözülür.
//
// Bit tabloları panogoz/contracts/icd.py ile birebir aynıdır (tek kaynak orada;
// burada yalnızca gösterim kopyası vardır).

import { h, mount, empty, clear, copyToClipboard } from './dom.js';
import * as fmt from './fmt.js';
import { api } from './api.js';

const STATUS_BITS = [
  [0, 'DATA_VALID', 'Veri geçerli'],
  [1, 'STALE', 'Veri bayat'],
  [2, 'SENSITIVITY_LOW', 'Görünürlük düşük'],
  [3, 'DE_ENERGISED', 'Pano enerjisiz'],
  [4, 'LEARN_MODE', 'Öğrenme modu'],
  [5, 'SUPPRESSED', 'Bastırılmış alarm var'],
  [6, 'MAINTENANCE', 'Bakım modu'],
  [7, 'ANALYSER_COMMS_LOST', 'Analizör haberleşmesi yok'],
  [8, 'ARC_RELAY_COMMS_LOST', 'Ark rölesi haberleşmesi yok'],
  [9, 'GATEWAY_COMMS_LOST', 'Ağ geçidi çevrimdışı'],
  [10, 'MOUNT_LOST', 'Sensör düştü/kaydı'],
  [11, 'AIM_SHIFTED', 'Termal dizi nişanı kaydı'],
  [12, 'CELL_LOW', 'Pil zayıf'],
  [13, 'CLOCK_UNSYNCED', 'Saat senkron değil'],
  [14, 'CONFIG_MISMATCH', 'Yapılandırma uyuşmazlığı'],
  [15, 'SELFTEST_DUE', 'Ark otokontrolü gecikti'],
];

const ARC_BITS = [
  [0, 'ACTIVE_TRIP', 'Aktif açma'],
  [1, 'ACTIVE_ERROR', 'Aktif hata'],
  [2, 'START_SEQUENCE', 'Başlatma dizisi'],
  [3, 'DIAGNOSTICS_RUNNING', 'Otokontrol çalışıyor'],
  [4, 'DETECTOR_FAULT', 'Dedektör arızası'],
  [5, 'AMBIENT_WARNING', 'Ortam ışığı uyarısı'],
  [6, 'COMMS_LOST', 'Haberleşme yok'],
  [7, 'SELFTEST_DISABLED', 'Otokontrol devre dışı'],
  [8, 'NOT_FITTED', 'Ark rölesi takılı değil'],
];

const DEVICE_BITS = ['TC01', 'TC02', 'TC03', 'TC04', 'TC05', 'TC06', 'TNIR', 'PD01', 'GW01']
  .map((k, i) => [i, 'DEV_' + k, k + ' arızalı']);

const ENGINE_BITS = [
  [0, 'INGEST_OK', 'Toplama servisi çalışıyor'],
  [1, 'DETECTOR_OK', 'Dedektör çalışıyor'],
  [2, 'STORE_OK', 'Veri tabanı erişilebilir'],
  [3, 'NOTIFY_OK', 'Bildirim servisi çalışıyor'],
  [4, 'SMS_PATH_OK', 'SMS yolu doğrulandı'],
  [5, 'STORM_ACTIVE', 'Alarm fırtınası bastırma etkin'],
  [6, 'DEGRADED', 'Sistem düşük kapasitede'],
];

const WARN_BITS = new Set([
  'STALE', 'SENSITIVITY_LOW', 'DE_ENERGISED', 'ANALYSER_COMMS_LOST', 'ARC_RELAY_COMMS_LOST',
  'GATEWAY_COMMS_LOST', 'MOUNT_LOST', 'AIM_SHIFTED', 'CELL_LOW', 'CONFIG_MISMATCH',
  'SELFTEST_DUE', 'ACTIVE_TRIP', 'ACTIVE_ERROR', 'DETECTOR_FAULT', 'AMBIENT_WARNING',
  'COMMS_LOST', 'NOT_FITTED', 'DEGRADED', 'STORM_ACTIVE',
]);

export function create(ctx) {
  const el = h('div.view');
  const head = h('div.view-head');
  const left = h('div.col');
  const right = h('div.col');
  mount(el, head, h('div.scada-grid', left, right));

  let data = null;
  let audit = null;
  let loadedFor = '';
  let timer = null;
  let prevRaw = new Map();

  async function load(key) {
    try {
      data = await api.scada(key);
    } catch (e) {
      data = { error: e };
    }
    if (audit === null) {
      audit = await api.audit().catch((e) => ({ ok: null, error: String(e.message || e) }));
    }
    ctx.refresh();
  }

  function bitChips(word, table) {
    const w = Number(word) || 0;
    return h('div.bitgrid', ...table.map(([bit, name, label]) => {
      const on = (w >> bit) & 1;
      const cls = 'span.bit' + (on ? '.on' : '') + (on && WARN_BITS.has(name) ? '.warn' : '');
      return h(cls, { title: name },
        h('span.ix', { text: bit }), h('span', { text: label }));
    }));
  }

  function regTable(block, title, base) {
    const decoded = (block && block.decoded) || [];
    const words = (block && block.words) || [];
    if (!decoded.length && !words.length) {
      return h('div.card', h('header', h('h3', { text: title })),
        h('div.body', empty('Blok boş', 'Bu pano için register bloğu doldurulmamış')));
    }
    const rows = decoded.map((r) => {
      const key = title + ':' + r.pdu;
      const changed = prevRaw.has(key) && prevRaw.get(key) !== r.raw;
      prevRaw.set(key, r.raw);
      return h('tr' + (changed ? '.changed' : ''),
        h('td.addr', { text: String(r.pdu) }),
        h('td.addr.tiny', { text: '0x' + Number(r.pdu).toString(16).toUpperCase().padStart(4, '0') }),
        h('td.addr.tiny', { text: String(40001 + Number(r.pdu)) }),
        h('td.nm', { text: r.name }),
        h('td.raw', { text: Array.isArray(r.raw) ? r.raw.join(' ') : String(r.raw) }),
        h('td.eng', { text: typeof r.eng === 'number' ? fmt.num(r.eng, 2) : String(r.eng ?? '—') }),
        h('td', { text: r.unit || '' }));
    });
    return h('div.card',
      h('header', h('h3', { text: title }), h('span.sp'),
        base !== undefined ? h('span.tag', { text: 'taban PDU ' + base }) : null,
        h('span.tag', { text: `${words.length || decoded.length} word` })),
      h('div.body.flush',
        h('table.tbl.reg-tbl',
          h('thead', h('tr',
            h('th.nosort', { text: 'PDU' }),
            h('th.nosort', { text: 'hex' }),
            h('th.nosort', { text: '4x' }),
            h('th.nosort', { text: 'Register' }),
            h('th.nosort', { text: 'Ham' }),
            h('th.nosort', { text: 'Mühendislik' }),
            h('th.nosort', { text: 'Birim' }))),
          h('tbody', ...rows))));
  }

  function valueOf(block, name) {
    const d = (block && block.decoded) || [];
    const r = d.find((x) => x.name === name);
    return r ? r.raw : 0;
  }

  function bitsCard() {
    const p = data && data.panel;
    const g = data && data.global;
    if (!p && !g) return null;
    return h('div.card.accent',
      h('header', h('h3', { text: 'Çözülmüş bit alanları' })),
      h('div.body.col',
        h('div', h('div.small.muted', { text: 'STATUS_WORD (+4)' }),
          bitChips(valueOf(p, 'STATUS_WORD'), STATUS_BITS)),
        h('div', h('div.small.muted', { text: 'ARC_STATE (+36)' }),
          bitChips(valueOf(p, 'ARC_STATE'), ARC_BITS)),
        h('div', h('div.small.muted', { text: 'DEVICE_FAULT_MAP (+44)' }),
          bitChips(valueOf(p, 'DEVICE_FAULT_MAP'), DEVICE_BITS)),
        h('div', h('div.small.muted', { text: 'ENGINE_STATE (global +10)' }),
          bitChips(valueOf(g, 'ENGINE_STATE'), ENGINE_BITS))));
  }

  function pollCard() {
    const st = (data && data.poll_stats) || {};
    const host = st.host || location.hostname || '127.0.0.1';
    const port = st.port || 5020;
    const unit = st.unit_id !== undefined ? st.unit_id : 1;
    const base = (data && data.panel && data.panel.base) !== undefined ? data.panel.base : 1000;
    // Sunucu kendi komut satırlarını veriyorsa onları göster: ekrandaki komut,
    // slave'in gerçekten dinlediği port ve unit id ile birebir aynı olmalıdır.
    const cmds = Array.isArray(data && data.modpoll) && data.modpoll.length
      ? data.modpoll
      : [
          `modpoll -m tcp -a ${unit} -r 0 -c 32 -0 -p ${port} ${host}`,
          `modpoll -m tcp -a ${unit} -r ${base} -c 48 -0 -p ${port} ${host}`,
          `modpoll -m tcp -a ${unit} -t 3 -r ${base} -c 48 -0 -p ${port} ${host}   # FC 04, aynı veri`,
        ];
    return h('div.card',
      h('header', h('h3', { text: 'Kendi pollunuzu görün' })),
      h('div.body.col',
        h('div.small.muted', {
          text: 'Aşağıdaki komutu kendi makinenizde çalıştırın; okuduğunuz word’ler '
              + 'sağdaki tabloyla birebir aynıdır. Harita salt okunurdur: FC 03 ve 04 '
              + 'servis edilir, FC 05/06/15/16 exception 0x01 döndürür.',
        }),
        ...cmds.map((c) => h('div.copy-row',
          h('pre.code', { text: c }),
          h('button.btn.sm', {
            text: 'kopyala',
            onclick: () => copyToClipboard(c).then(() => ctx.toast('Kopyalandı', c, 'ok')),
          }))),
        h('div.kv',
          h('span.kv-k', { text: 'Son poll' }),
          h('span.kv-v', { text: st.last_poll_ts ? fmt.dateTime(st.last_poll_ts) : '—' }),
          h('span.kv-k', { text: 'Poll’dan beri' }),
          h('span.kv-v', { text: fmt.dur(st.seconds_since_last_poll) }),
          h('span.kv-k', { text: 'İstek / register' }),
          h('span.kv-v', { text: `${fmt.int(st.request_count)} / ${fmt.int(st.register_count)}` }),
          h('span.kv-k', { text: 'Reddedilen yazma' }),
          h('span.kv-v', { text: fmt.int(st.rejected_writes) }),
          h('span.kv-k', { text: 'Heartbeat' }),
          h('span.kv-v', { text: fmt.int(st.heartbeat) }),
          h('span.kv-k', { text: 'İstemciler' }),
          h('span.kv-v', { text: (st.clients || []).join(', ') || '—' })),
        h('div.row.wrap',
          h('a.btn.sm', { href: '/api/icd', target: '_blank', text: 'ICD (markdown)' }),
          h('a.btn.sm', { href: '/api/icd.csv', target: '_blank', text: 'Nokta listesi (CSV)' })),
        h('div.note.honest', {
          text: '100 panoluk bir filo 4800 register eder; FC 03 tek istekte en fazla 125 '
              + 'register taşır, yani tam tarama 39 pakettir. Bir SCADA ön yüzü 1 Hz’de '
              + 'zaten iki blok okur: global blok + ilgili pano bloğu.',
        })));
  }

  function auditCard() {
    if (!audit) return null;
    const ok = audit.ok;
    return h('div.card',
      h('header', h('h3', { text: 'Denetim zinciri' }), h('span.sp'),
        h('span.tag' + (ok ? '.ok' : (ok === false ? '.bad' : '')),
          { text: ok ? 'bütün' : (ok === false ? 'KIRIK' : 'bilinmiyor') })),
      h('div.body.col',
        h('div.kv',
          h('span.kv-k', { text: 'Kayıt' }), h('span.kv-v', { text: fmt.int(audit.rows) }),
          h('span.kv-k', { text: 'Kırılma' }),
          h('span.kv-v', { text: audit.broken_at === null || audit.broken_at === undefined
            ? 'yok' : String(audit.broken_at) })),
        h('div.tiny.muted', {
          text: 'Olay kayıtları zincirleme özetlenir: bir satır sonradan değiştirilirse '
              + 'zincir kırılır ve burada görünür.',
        })));
  }

  function update(state) {
    const key = state.panelKey;
    mount(head,
      h('div',
        h('h1', { text: 'SCADA · Modbus TCP register bloğu' }),
        h('div.head-sub', {
          text: `${key || 'pano seçilmedi'} · salt okunur · 0 tabanlı PDU adresleme · `
              + 'ICD v2.0.0',
        })),
      h('span.sp'),
      h('button.btn', { text: 'Yenile', onclick: () => key && load(key) }),
      h('button.btn', { text: '← Dijital ikiz', onclick: () => key && ctx.navigate('pano', key) }));

    if (!key) { mount(left, empty('Pano seçilmedi')); mount(right, ''); return; }
    if (loadedFor !== key) {
      loadedFor = key;
      data = null;
      prevRaw = new Map();
      mount(right, h('div.card', h('div.body', h('div.skeleton', { style: { height: '400px' } }))));
      load(key);
      if (timer) clearInterval(timer);
      timer = setInterval(() => { if (loadedFor) load(loadedFor); }, 3000);
      return;
    }
    if (!data) return;
    if (data.error) {
      mount(left, pollCard());
      mount(right, h('div.card', h('div.body',
        empty('Register bloğu alınamadı', String(data.error.message || data.error)))));
      return;
    }
    mount(left, pollCard(), bitsCard(), auditCard());
    mount(right,
      regTable(data.panel, `Pano bloğu · ${key}`, data.panel && data.panel.base),
      regTable(data.global, 'Global blok', 0));
  }

  return {
    el,
    update,
    destroy() { if (timer) clearInterval(timer); clear(el); },
  };
}
