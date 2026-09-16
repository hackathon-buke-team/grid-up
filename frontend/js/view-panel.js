// PANO GÖZ · S2 Pano detayı - dijital ikiz. Amiral gemisi ekran.
//
// Solda EK-II/14 ön görünüşü (twin.js), üstünde 40 izlenen bağlantı ve 9 cihaz.
// Sağda panonun özeti, "Koruma Bütünlüğü" kartı ve cihaz sağlığı.
//
// Bu ekranın dürüstlük yükü şudur: bara bölmesindeki 36 ve çatıdaki 4 bağlantı
// da çizilir, ama içi boş konturla ve "izlenmiyor — kesinti gerektirir" etiketiyle.
// PANO GÖZ'ün gün 1 kiti yalnızca alt kablo bölmesine, ölçü kolonundaki DIN raya
// ve mevcut 10 A prize dokunur. Enerjili bara bölmesine montaj İDDİA EDİLMEZ.

import { h, mount, empty, clear } from './dom.js';
import * as fmt from './fmt.js';
import { api } from './api.js';
import { renderTwin, twinLegend } from './twin.js';
import { zoomPan, fullscreen, exitFullscreen, isFullscreen } from './zoompan.js';

const twinCache = new Map();

// Küçük simgeler; harici bir simge seti yok, dört yol yeter.
// Küçük simgeler; harici bir simge seti yok. "Sığdır" bir çerçeve içindeki
// çizim, "tam ekran" dışa açılan dört köşedir - ikisi bir bakışta ayrılmalı.
// Tam ekrandayken ok yönü tersine döner: düğme artık çıkışı gösterir.
const IC = {
  fit: 'M3 5h18v14H3zM8.5 9.5h7v5h-7z',
  full: 'M9 4H4v5M15 4h5v5M15 20h5v-5M9 20H4v-5',
  fullOut: 'M4 9h5V4M20 9h-5V4M20 15h-5v5M4 15h5v5',
};

export function create(ctx) {
  const el = h('div.view');
  const head = h('div.view-head');
  const stage = h('div.surface.twin-card');
  const side = h('div.col');
  const grid = h('div.twin-grid', h('div.col', stage), side);

  // Çizim canlı veriyle yeniden kurulur, ama kullanıcının yakınlaştırması
  // kurulumu aşar: bir pabucun üstüne yaklaşmış operatör, bir sonraki ölçüm
  // geldiğinde kendini yine tüm panoya bakarken bulmamalı.
  let zp = null;
  let twinView = null;
  let pctLbl = null;
  // Çizim yeniden kurulunca eski düğmenin dinleyicisi çöpe gider; ekran
  // kapanırken hepsini sökebilmek için listede tutuyoruz.
  const fsListeners = [];

  function dropFsListeners() {
    while (fsListeners.length) {
      document.removeEventListener('fullscreenchange', fsListeners.pop());
    }
  }

  function layout() {
    if (!el.contains(head)) mount(el, head, grid);
  }

  layout();

  let lastSig = '';
  let lastKey = null;

  function ensureTwin(key) {
    if (!key || twinCache.has(key)) return;
    twinCache.set(key, null); // tekrar tekrar istememek için
    api.twin(key)
      .then((t) => { twinCache.set(key, t); lastSig = ''; ctx.refresh(); })
      .catch(() => { twinCache.set(key, { joints: [], devices: [], error: true }); });
  }

  function statBox(k, v, u, note) {
    return h('div.stat',
      h('div.stat-k', { text: k }),
      h('div.stat-v', v instanceof Node ? v : { text: v }, u ? h('span.stat-u', { text: ' ' + u }) : null),
      note ? h('div.stat-n', { text: note }) : null);
  }

  function renderHead(p) {
    mount(head,
      h('div',
        h('h1', { text: p.name && p.name !== p.panel_key ? `${p.panel_key} · ${p.name}` : p.panel_key }),
        h('div.head-sub', {
          text: `${p.dso || ''} · ${p.site || ''} · TEDAŞ MLZ.DSYA 1600 kVA dahili tip · `
              + `güncelleme ${fmt.dateTime(p.ts)} (veri yaşı ${fmt.dur(p.data_age_s)})`,
        })),
      h('span.sp'),
      fmt.sevBadge(p.severity),
      h('span.chip', h('span', { text: 'Sağlık' }), h('b', { text: fmt.num(p.health_index, 0) })),
      h('button.btn', {
        text: 'PRPD ekranı',
        onclick: () => ctx.navigate('prpd', p.panel_key),
      }),
      h('button.btn', {
        text: 'SCADA bloğu',
        onclick: () => ctx.navigate('scada', p.panel_key),
      }));
  }

  function mergeJoints(p, twin) {
    const live = new Map((p.joints || []).map((j) => [j.key, j]));
    const base = (twin && Array.isArray(twin.joints) && twin.joints.length) ? twin.joints : (p.joints || []);
    return base.map((j) => Object.assign({}, j, live.get(j.key) || {}));
  }

  function renderStage(p, twin, selected) {
    const joints = mergeJoints(p, twin);
    const devices = (p.devices && p.devices.length) ? p.devices
      : ((twin && twin.devices) || []);
    const svg = renderTwin({
      joints,
      devices,
      selected,
      onJoint: (key) => ctx.navigate('kanit', p.panel_key, key),
      onDevice: (key) => ctx.toast('Cihaz', key + ' · ' + ((devices.find((d) => d.key === key) || {}).label || '')),
    });
    // ---- araç şeridi ----------------------------------------------------
    dropFsListeners();
    pctLbl = h('span.tool.pct', { text: '%100' });
    const icon = (d) => {
      const e = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      e.setAttribute('viewBox', '0 0 24 24');
      e.setAttribute('fill', 'none');
      e.setAttribute('stroke', 'currentColor');
      e.setAttribute('stroke-width', '1.8');
      e.setAttribute('stroke-linecap', 'round');
      const pa = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      pa.setAttribute('d', d);
      e.appendChild(pa);
      return e;
    };
    const fsBtn = h('button.tool.ic', {
      title: 'Tam ekran (Esc ile çık)',
      onclick: () => { if (isFullscreen(stage)) exitFullscreen(); else fullscreen(stage); },
    }, icon(IC.full));
    // Düğme hangi işe yaradığını göstermeli: tam ekrandayken "çık" demeli.
    // Kullanıcı Esc ile de çıkabilir, o yüzden olayı dinliyoruz.
    const fsSync = () => {
      const acik = isFullscreen(stage);
      mount(fsBtn, icon(acik ? IC.fullOut : IC.full));
      fsBtn.title = acik ? 'Tam ekrandan çık (Esc)' : 'Tam ekran';
    };
    document.addEventListener('fullscreenchange', fsSync);
    fsListeners.push(fsSync);
    const bar = h('div.tool-row',
      h('button.tool.ic', { text: '−', title: 'Uzaklaş', onclick: () => zp && zp.zoomBy(1 / 1.4) }),
      pctLbl,
      h('button.tool.ic', { text: '+', title: 'Yaklaş', onclick: () => zp && zp.zoomBy(1.4) }),
      h('button.tool.ic', { title: 'Panonun tamamını sığdır', onclick: () => zp && zp.fit() }, icon(IC.fit)),
      fsBtn);

    mount(stage,
      h('header',
        h('h2', { text: 'Dijital ikiz · EK-II/14 ön görünüş' }),
        h('span.sp'),
        h('span.tag', { text: `${joints.filter((j) => j.zone === 'bottom').length} izlenen bağlantı` }),
        h('span.tag', { text: `${joints.length} civatalı bağlantı` }),
        h('span.tag', { text: `${devices.length} cihaz` }),
        h('span.sp.grow'),
        bar),
      h('div.twin-stage', svg),
      twinLegend(devices),
      h('div.pad',
        h('div.note.honest', {
          text: `Bara bölmesindeki ${joints.filter((j) => j.zone === 'busbar').length} ve `
              + `çatıdaki ${joints.filter((j) => j.zone === 'roof').length} bağlantı içi boş `
              + 'konturla çizilir: bunlara ulaşmak 2312 A taşıyan canlı baranın kapağını açmak '
              + 'demektir ve PANO GÖZ bunu yapmaz. Gün 1 kiti alt kablo bölmesi, ölçü kolonu '
              + 'DIN rayı ve mevcut 10 A prizden ibarettir.',
        })));

    // ---- yakınlaştırma ---------------------------------------------------
    if (zp) zp.destroy();
    zp = zoomPan(svg, {
      view: twinView,
      minKat: 1,
      maxKat: 22,
      onChange: (kat) => {
        twinView = zp.view();
        if (pctLbl) pctLbl.textContent = '%' + Math.round(kat * 100);
      },
    });
    // Bir bağlantıya çift tıklamak o pabucun üstüne yaklaşır; tek tık zaten
    // kanıt ekranına gider.
    for (const g of svg.querySelectorAll('.tw-joint-g')) {
      g.addEventListener('dblclick', (ev) => {
        ev.stopPropagation();
        const b = g.getBBox();
        zp.goto({ x: b.x - 90, y: b.y - 90, w: b.width + 180, h: b.height + 180 }, 0.1);
      });
    }
  }

  function renderJointTable(p, selected) {
    const joints = (p.joints || []).filter((j) => j.zone === 'bottom');
    const rows = joints.slice().sort((a, b) => (b.theta_k || -99) - (a.theta_k || -99)).slice(0, 12);
    if (!rows.length) return h('div.card', h('header', h('h3', { text: 'Bağlantılar' })),
      h('div.body', empty('Bağlantı verisi yok')));
    return h('div.card',
      h('header', h('h3', { text: 'En yüksek θ · ilk 12 bağlantı' }),
        h('span.sp'),
        h('span.tiny.muted', { text: 'satıra tıkla → kanıt ekranı' })),
      h('div.body.flush', h('div.joint-list',
        h('table.tbl',
          h('thead', h('tr',
            h('th.nosort', { text: 'Bağlantı' }),
            h('th.nosort', { text: 'θ (K)' }),
            h('th.nosort', { text: 'T (°C)' }),
            h('th.nosort', { text: 'Eğim' }),
            h('th.nosort', { text: 'Seviye' }))),
          h('tbody', ...rows.map((j) => {
            const tr = h('tr.click' + (j.key === selected ? '.sel' : ''),
              h('td',
                h('div', { text: fmt.shortJoint(j.key) }),
                h('div.tiny.muted', { text: fmt.jointZoneTR(j.zone) + ' · ' + fmt.num(j.rated_a, 0) + ' A' })),
              h('td.n', {
                text: fmt.num(j.theta_k, 2),
                style: { color: fmt.thetaColor(j.theta_k), fontWeight: 650 },
              }),
              h('td.n', { text: fmt.num(j.temp_c, 1) }),
              h('td.n', { text: fmt.signed(j.slope_k_per_week, 2) + ' K/hf' }),
              h('td', fmt.sevBadge(j.severity)));
            tr.addEventListener('click', () => ctx.navigate('kanit', p.panel_key, j.key));
            return tr;
          }))))));
  }

  function renderArcCard(p) {
    const a = p.arc || {};
    if (!a.fitted) {
      return h('div.card',
        h('header', h('h3', { text: 'Koruma bütünlüğü' })),
        h('div.body',
          h('div.note.warn', {
            text: 'Bu panoda ABB TVOC-2 ark koruma rölesi TAKILI DEĞİL. '
                + '"Veri yok" ile "cihaz yok" aynı şey değildir; bu kart ikisini asla '
                + 'karıştırmaz.',
          })));
    }
    const ok = Number(a.detectors_ok || 0), tot = Number(a.detectors_total || 0);
    const degraded = tot > 0 && ok < tot;
    return h('div.card' + (degraded ? '' : ''),
      h('header',
        h('h3', { text: 'Koruma bütünlüğü' }),
        h('span.sp'),
        h('span.tag' + (a.online ? '.ok' : '.bad'), { text: a.online ? 'haberleşme var' : 'haberleşme yok' })),
      h('div.body.col',
        h('div.grid-2',
          statBox('Sağlam dedektör', `${fmt.int(ok)} / ${fmt.int(tot)}`, '',
            degraded ? 'en az bir dedektör hatalı' : 'reg 222/223 · yalnız X2/X3'),
          statBox('Ortam ışığı uyarısı', fmt.int(a.ambient_warn), '',
            a.ambient_warn ? 'dedektör körleşebilir (3000 lx)' : 'uyarı yok'),
          statBox('Son otokontrol', a.last_selftest_days >= 9999 ? '—' : fmt.int(a.last_selftest_days), 'gün',
            a.selftest_enabled ? 'otokontrol etkin' : 'otokontrol varsayılan olarak kapalı'),
          statBox('Aktif açma / hata',
            `${a.active_trip ? 'AÇMA' : 'yok'} / ${a.active_error ? 'HATA' : 'yok'}`, '',
            'reg 1300 bit0 / bit1')),
        a.fault_list && a.fault_list.length
          ? h('div.flags', ...a.fault_list.map((f) => h('span.tag.bad', { text: f })))
          : null,
        a.ambient_warn_list && a.ambient_warn_list.length
          ? h('div.flags', ...a.ambient_warn_list.map((d) => h('span.tag.warn', { text: d + ' · ışık' })))
          : null,
        h('div.note.honest', { text: a.caveat || '' }),
        h('div.tiny.muted', {
          text: 'Sayım TVOC-2 reg 222/223’ten okunur. Bu iki register X2 ve X3 modüllerini '
              + 'kapsar ve yalnızca FW ≥ 03.00.00’de vardır; X1 modülüne bağlı dedektörler '
              + 'bu registerlarda görünmez. Kapsam, takılı modüle göre değişir.',
        }),
        a.firmware ? h('div.tiny.muted', { text: 'TVOC-2 yazılımı: ' + a.firmware }) : null));
  }

  function renderDevices(p) {
    const devs = p.devices || [];
    return h('div.card',
      h('header', h('h3', { text: 'Cihazlar' }), h('span.sp'),
        h('span.tag' + (devs.filter((d) => d.online).length === devs.length ? '.ok' : '.warn'),
          { text: `${devs.filter((d) => d.online).length}/${devs.length} çevrimiçi` })),
      h('div.body.flush',
        devs.length
          ? h('table.tbl',
              h('thead', h('tr',
                h('th.nosort', { text: 'Cihaz' }),
                h('th.nosort', { text: 'Durum' }),
                h('th.nosort', { text: 'Pil' }),
                h('th.nosort', { text: 'Sinyal' }))),
              h('tbody', ...devs.map((d) => h('tr',
                h('td',
                  h('div', { text: d.key }),
                  h('div.tiny.muted', { text: d.label || d.kind })),
                h('td', d.online
                  ? h('span.tag.ok', { text: 'çevrimiçi' })
                  : h('span.tag.bad', { text: 'çevrimdışı' })),
                h('td.n', { text: d.battery_pct === null || d.battery_pct === undefined
                  ? 'şebeke' : fmt.pct(d.battery_pct, 0) }),
                h('td.n', { text: d.rssi_dbm === null || d.rssi_dbm === undefined
                  ? '—' : fmt.num(d.rssi_dbm, 0) + ' dBm' })))))
          : empty('Cihaz verisi yok')),
      h('div.body',
        h('div.tiny.muted', {
          text: 'Enerji hasadı iddia edilmez: birincil Li-SOCl₂ hücre, 9-16 yıl tasarım ömrü.',
        })));
  }

  function renderRisk(p) {
    const wf = (p.hi_waterfall || []).slice().sort((a, b) => (b.delta_hi || 0) - (a.delta_hi || 0));
    const risks = p.risks || {};
    const items = wf.length ? wf : Object.entries(risks).map(([mode, risk]) => ({ mode, risk }));
    if (!items.length) {
      return h('div.card', h('header', h('h3', { text: 'Risk dağılımı' })),
        h('div.body', empty('Füzyon katmanı henüz çalışmadı')));
    }
    const maxDelta = Math.max(1e-6, ...items.map((i) => Math.abs(i.delta_hi || 0)));
    return h('div.card',
      h('header', h('h3', { text: 'Sağlık endeksi şelalesi' }), h('span.sp'),
        h('span.tiny.muted', { text: 'HI = 100·∏(1−r)^w · katkılar toplanır' })),
      h('div.body.col',
        ...items.map((i) => h('div',
          h('div.row',
            h('span', { text: i.label_tr || fmt.MODE_TR[i.mode] || i.mode }),
            h('span.sp', { style: { flex: '1 1 auto' } }),
            h('span.small.muted', { text: fmt.pct(100 * (i.risk || 0), 0) }),
            i.delta_hi !== undefined
              ? h('span.small', { text: fmt.signed(-Math.abs(i.delta_hi), 1) + ' puan' })
              : null),
          h('div.hi-bar', { style: { width: '100%', marginTop: '4px' } },
            h('i', {
              class: fmt.hiClass(100 - 100 * (i.risk || 0)),
              style: { width: Math.min(100, (Math.abs(i.delta_hi || 0) / maxDelta) * 100) + '%' },
            }))))));
  }

  function renderSummary(p) {
    const an = p.analyser || {};
    const env = p.env || {};
    const worst = (p.joints || []).find((j) => j.key === p.theta_max_joint);
    const flags = p.status_flags || [];
    const blind = flags.filter((f) => fmt.BLIND_FLAGS.has(f));
    const other = flags.filter((f) => !fmt.BLIND_FLAGS.has(f));
    return h('div.card',
      h('header', h('h3', { text: 'Özet' })),
      h('div.body.col',
        h('div.grid-2',
          statBox('θ maks', fmt.num(p.theta_max, 2), 'K',
            worst ? fmt.shortJoint(worst.key) : (p.theta_max_joint || '—')),
          statBox('Δ7 gün', fmt.signed(p.theta_delta_7d, 2), 'K', 'θ değişimi'),
          statBox('Görünürlük', fmt.num(p.sensitivity_pct, 0), '%',
            p.sensitivity_pct < 50 ? 'düşük yük · θ güvenilir değil' : '3σ/f² ölçütü'),
          statBox('Yük faktörü', fmt.num(100 * (p.load_factor || 0), 0), '%', 'anma 2312 A')),
        h('div.kv',
          h('span.kv-k', { text: 'Akımlar' }),
          h('span.kv-v', {
            text: ['i_l1', 'i_l2', 'i_l3'].map((k) => fmt.num(an['mpr.' + k + '_a'], 0)).join(' / ')
                + ' A · N ' + fmt.num(an['mpr.i_n_a'], 0) + ' A',
          }),
          h('span.kv-k', { text: 'Gerilim / frekans' }),
          h('span.kv-v', {
            text: ['v_l1', 'v_l2', 'v_l3'].map((k) => fmt.num(an['mpr.' + k + '_v'], 0)).join(' / ')
                + ' V · ' + fmt.num(an['mpr.freq_hz'], 2) + ' Hz',
          }),
          h('span.kv-k', { text: 'THD (V / I)' }),
          h('span.kv-v', {
            text: fmt.num(Math.max(an['mpr.thd_v_l1_pct'] || 0, an['mpr.thd_v_l2_pct'] || 0,
              an['mpr.thd_v_l3_pct'] || 0), 1) + ' % / '
                + fmt.num(Math.max(an['mpr.thd_i_l1_pct'] || 0, an['mpr.thd_i_l2_pct'] || 0,
                  an['mpr.thd_i_l3_pct'] || 0), 1) + ' %',
          }),
          h('span.kv-k', { text: 'Ortam' }),
          h('span.kv-v', {
            text: fmt.num(env['env.air_c'], 1) + ' °C · % ' + fmt.num(env['env.rh_pct'], 0)
                + ' nem · yoğuşma payı ' + fmt.num(env['env.condensation_margin_k'], 1) + ' K',
          }),
          h('span.kv-k', { text: 'Analizör' }),
          h('span.kv-v', {
            text: p.analyser_fitted === false ? 'takılı değil'
              : (p.analyser_online ? 'çevrimiçi' : 'haberleşme yok'),
          })),
        blind.length
          ? h('div',
              h('div.tiny.muted', { text: 'Görüş kısıtları (pano arızası değil):' }),
              h('div.flags', ...blind.map((f) => fmt.flagTag(f))))
          : null,
        other.length
          ? h('div',
              h('div.tiny.muted', { text: 'Diğer durum bayrakları:' }),
              h('div.flags', ...other.map((f) => fmt.flagTag(f))))
          : null,
        p.learn_mode
          ? h('div.note', { text: 'Öğrenme modu etkin: devreye alma sonrası ilk 7 gün. '
              + 'Mutlak sıcaklık limitleri yine de aktiftir.' })
          : null));
  }

  function renderPd(p) {
    const pd = p.pd || {};
    return h('div.card',
      h('header', h('h3', { text: 'RF kanalı' }), h('span.sp'),
        h('button.btn.sm', { text: 'PRPD →', onclick: () => ctx.navigate('prpd', p.panel_key) })),
      h('div.body.col',
        h('div.grid-2',
          statBox('Sınıf', fmt.PRPD_TR[pd.klass] || pd.klass_label || '—', '', 'PRPD kural motoru'),
          statBox('Tepe genlik', fmt.num(pd.qmax_db, 1), 'dB', 'pC eşdeğeri'),
          statBox('Darbe hızı', fmt.num(pd.rate_per_s, 1), '1/s', ''),
          statBox('30 günlük trend', fmt.signed(pd.trend_db_30d, 1), 'dB', '')),
        h('div.tiny.muted', { text: pd.caveat || '' })));
  }

  function update(state) {
    const key = state.panelKey;
    if (!key) {
      mount(el, empty('Pano seçilmedi', 'Filo ekranından bir pano seçin'));
      return;
    }
    if (key !== lastKey) { lastKey = key; lastSig = ''; }
    layout();
    if (state.panelError) {
      mount(head, h('h1', { text: key }), h('span.sp'),
        h('button.btn', { text: 'Filoya dön', onclick: () => ctx.navigate('filo') }));
      mount(stage, h('div.body',
        empty(`Pano bulunamadı: ${key}`, String(state.panelError))));
      mount(side, '');
      return;
    }
    const p = state.panel;
    if (!p || p.panel_key !== key) {
      mount(stage, h('div.body', h('div.skeleton', { style: { height: '420px' } })));
      mount(head, h('h1', { text: key }), h('span.head-sub', { text: 'yükleniyor…' }));
      mount(side, h('div.card', h('div.body', h('div.skeleton', { style: { height: '180px' } }))));
      return;
    }
    ensureTwin(key);
    renderHead(p);

    // Çizim yalnızca GÖRÜNEN bir şey değişince yeniden kurulur. θ 0,1 K
    // çözünürlükle imzaya girer: ekranda bir nokta rengi ancak o kadar
    // değişince fark eder, daha incesi boşuna yeniden çizimdir. Panonun zaman
    // damgası imzadan ÇIKARILDI - her saniye değişiyor ve tek başına hiçbir
    // görsel farka karşılık gelmiyordu.
    const sig = JSON.stringify([
      state.jointKey,
      (p.joints || []).map((j) => [j.key, Math.round((j.theta_k || 0) * 10), j.severity]),
      (p.devices || []).map((d) => [d.key, d.online]),
      twinCache.get(key) ? 1 : 0,
    ]);
    if (sig !== lastSig) {
      lastSig = sig;
      renderStage(p, twinCache.get(key), state.jointKey);
    }
    mount(side,
      renderSummary(p),
      renderArcCard(p),
      renderJointTable(p, state.jointKey),
      renderDevices(p),
      renderRisk(p),
      renderPd(p));
  }

  return {
    el,
    update,
    destroy() {
      if (zp) { zp.destroy(); zp = null; }
      dropFsListeners();
      if (isFullscreen(stage)) exitFullscreen();
      clear(el);
    },
  };
}
