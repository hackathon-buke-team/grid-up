/* PANO GÖZ · Saha uygulaması
   ---------------------------
   Düz JavaScript, bağımlılık yok. Sunucudan gelen HER metin textContent ile
   basılır; hiçbir yerde innerHTML'e veri verilmez. Simgeler createElementNS ile
   elle çizilir (dış istek yok, ikon paketi yok).

   Üç ekran: giriş, gelen kutusu, olay ayrıntısı (#/olay/<id> ile doğrudan açılır;
   Telegram mesajındaki bağlantı ve QR bunu kullanır).

   Uyarı davranışı, dürüstçe:
     · Uygulama AÇIKKEN ya da sayfa arka planda YAŞIYORKEN: tam ekran alarm, siren,
       titreşim ve (güvenli bağlamda izin verilmişse) sistem bildirimi çalışır.
     · Uygulama KAPALIYKEN bu uygulama uyandırılamaz. Push servisi yoktur (FCM/APNs
       kamu bulutudur, şirket içi kısıtla çelişir). Kapalı telefonu SMS ve Telegram
       yolları çaldırır; merdivenin üç kanallı olmasının sebebi budur.
     · Sistem bildirimi, ekranı açık tutma ve ana ekrana kurma yalnız GÜVENLİ
       BAĞLAMDA (HTTPS ya da localhost) çalışır. HTTP üzerindeki bir LAN adresi
       güvenli sayılmaz; ses, titreşim ve tam ekran alarm yine çalışır. */
(() => {
  'use strict';

  const POLL_MS = 3000;
  const POLL_HIDDEN_MS = 10000;
  const CLOCK_MS = 10000;             // yaş ve onay süresi çubukları bu aralıkla tazelenir
  const SNOOZE_MS = 5 * 60 * 1000;
  const STEPS = ['yolda', 'sahada', 'tamam'];
  const STEP_LABEL = { yolda: 'Yola çıktım', sahada: 'Sahadayım', tamam: 'İşi tamamladım' };
  const NODE_LABEL = ['Onay', 'Yolda', 'Sahada', 'Tamam'];
  const SEV = {
    UYARI: { cls: 'uyari', shape: '▲', name: 'UYARI', rank: 1 },
    KRITIK: { cls: 'kritik', shape: '◆', name: 'KRİTİK', rank: 2 },
    ACIL: { cls: 'acil', shape: '■', name: 'ACİL', rank: 3 },
  };
  const ZONE = [                         // θ ölçeğinin beş bölgesi (eşikler sunucudan gelir)
    { name: 'Normal', color: 'var(--ok)' },
    { name: 'İzle', color: 'var(--sev-izle)' },
    { name: 'Uyarı', color: 'var(--sev-uyari)' },
    { name: 'Kritik', color: 'var(--sev-kritik)' },
    { name: 'Acil', color: 'var(--sev-acil)' },
  ];
  const CHANNEL = { SMS: 'SMS', TELEGRAM: 'Telegram', MOBIL: 'Uygulama', SESLI: 'Sesli arama',
                    EPOSTA: 'E-posta', MATRIX: 'Sohbet', PANO: 'Pano' };
  const NSTATE = { KUYRUKTA: 'kuyrukta', GONDERILDI: 'gönderildi', ILETILDI: 'iletildi', HATA: 'HATA' };

  // ------------------------------------------------------------ küçük yardımcılar --

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* özel pencere */ } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* yoksay */ } },
  };
  const LS = { token: 'panogoz.saha.oturum', name: 'panogoz.saha.ad', sound: 'panogoz.saha.ses',
               wake: 'panogoz.saha.uyanik' };

  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (k === 'aria-pressed' || k === 'aria-checked') el.setAttribute(k, String(v));
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) {
      if (kid === null || kid === undefined || kid === false) continue;
      el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }

  // ---- simgeler: 24×24 çizgi simgeleri, currentColor ile boyanır
  const NS = 'http://www.w3.org/2000/svg';
  const ICON = {
    check: ['M5 12.5l4.5 4.5L19 7.5'],
    back: ['M15 5l-7 7 7 7'],
    chevron: ['M9 5l7 7-7 7'],
    pin: ['M12 21s-7-6.2-7-11a7 7 0 0114 0c0 4.8-7 11-7 11z', 'M12 7.5a2.5 2.5 0 100 5 2.5 2.5 0 000-5z'],
    backspace: ['M20 6H9l-6 6 6 6h11V6z', 'M13 10l4 4M17 10l-4 4'],
    shield: ['M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z', 'M8.5 12.2l2.6 2.6 4.6-5'],
    bell: ['M6 9a6 6 0 0112 0c0 5 2 6.5 2 6.5H4S6 14 6 9z', 'M10 19a2 2 0 004 0'],
    lock: ['M6 11h12v9H6z', 'M8.5 11V8a3.5 3.5 0 017 0v3'],
  };
  function icon(name, cls) {
    const el = document.createElementNS(NS, 'svg');
    for (const [k, v] of Object.entries({ viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
      'stroke-width': '2', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true' })) el.setAttribute(k, v);
    if (cls) el.setAttribute('class', cls);
    for (const d of ICON[name]) {
      const p = document.createElementNS(NS, 'path');
      p.setAttribute('d', d);
      el.append(p);
    }
    return el;
  }
  // PANO GÖZ işareti: konsolun favicon'uyla aynı (mavi halka + ölçüm sarısı nokta)
  function logo(size) {
    const el = document.createElementNS(NS, 'svg');
    el.setAttribute('viewBox', '0 0 512 512');
    el.setAttribute('width', size); el.setAttribute('height', size);
    el.setAttribute('aria-hidden', 'true'); el.setAttribute('class', 'logo');
    const shapes = [['rect', { width: 512, height: 512, rx: 96, fill: '#0c0f10' }],
      ['circle', { cx: 256, cy: 256, r: 150, fill: 'none', stroke: '#4fa8d8', 'stroke-width': 34 }],
      ['circle', { cx: 256, cy: 256, r: 52, fill: '#ffea46' }]];
    for (const [tag, attrs] of shapes) {
      const s = document.createElementNS(NS, tag);
      for (const [k, v] of Object.entries(attrs)) s.setAttribute(k, v);
      el.append(s);
    }
    return el;
  }

  const num = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v)) ? null
    : Number(v).toLocaleString('tr-TR', { maximumFractionDigits: d, minimumFractionDigits: 0 });
  const clock = (ts) => ts ? new Date(ts * 1000).toLocaleTimeString('tr-TR',
    { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';
  const initials = (name) => String(name || '?').split(/\s+/).filter(Boolean).slice(0, 2)
    .map((w) => w[0]).join('').toLocaleUpperCase('tr-TR');

  // API, SMS ile aynı ASCII seviye adlarını taşır (KRITIK'e, ACIL'e); ekranda Türkçe yazılır.
  const trSeverity = (t) => String(t).replace(/KRITIK/g, 'KRİTİK').replace(/ACIL/g, 'ACİL')
    .replace(/IZLE/g, 'İZLE');

  function ago(seconds) {
    const s = Math.max(0, Math.round(seconds));
    if (s < 60) return `${s} sn önce`;
    if (s < 3600) return `${Math.floor(s / 60)} dk önce`;
    if (s < 86400) return `${Math.floor(s / 3600)} sa ${Math.floor((s % 3600) / 60)} dk önce`;
    return `${Math.floor(s / 86400)} g önce`;
  }
  function span(seconds) {
    const s = Math.max(0, Math.round(seconds));
    if (s < 60) return `${s} sn`;
    if (s < 3600) return `${Math.floor(s / 60)} dk ${String(s % 60).padStart(2, '0')} sn`;
    return `${Math.floor(s / 3600)} sa ${String(Math.floor((s % 3600) / 60)).padStart(2, '0')} dk`;
  }

  // ------------------------------------------------------------------- durum --

  const S = {
    token: store.get(LS.token),
    member: null,
    list: [],
    detail: null,
    detailErr: null,
    filter: 'benim',
    route: parseRoute(),
    screen: '',
    offline: false,
    syncedAt: 0,
    offset: 0,                       // sunucu saati - yerel saat (sn)
    snooze: {},                      // olay -> yeniden çalma zamanı (ms)
    seen: new Set(),                 // sistem bildirimi gönderilen olaylar
    soundOn: store.get(LS.sound) !== '0',
    wantWake: store.get(LS.wake) === '1',
    note: '',
    busy: false,
    sig: '',
    alarmSig: '',
    loginCtl: null,
    timer: null,
  };

  function parseRoute() {
    const m = location.hash.match(/^#\/olay\/(\d+)/);
    return m ? { name: 'olay', id: Number(m[1]) } : { name: 'liste' };
  }
  const nowSrv = () => Date.now() / 1000 + S.offset;

  // --------------------------------------------------------------------- api --

  class ApiError extends Error {
    constructor(status, data) { super(`HTTP ${status}`); this.status = status; this.data = data || {}; }
  }

  async function api(path, opts = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (S.token) headers.Authorization = `Bearer ${S.token}`;
    const res = await fetch(path, { method: opts.method || 'GET', headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined, cache: 'no-store' });
    let data = null;
    try { data = await res.json(); } catch (e) { /* gövdesiz yanıt */ }
    if (!res.ok) {
      const err = new ApiError(res.status, data && (data.detail || data));
      if (res.status === 401 && S.token && !path.endsWith('/login')) logout('Oturum süresi doldu, yeniden giriş yapın.');
      throw err;
    }
    return data;
  }

  // ------------------------------------------------------------- ses / titreşim --

  const Siren = {
    ctx: null, osc: null, timer: null, on: false,
    unlock() {
      try {
        if (!this.ctx) {
          const AC = window.AudioContext || window.webkitAudioContext;
          if (AC) this.ctx = new AC();
        }
        if (this.ctx && this.ctx.state === 'suspended') return this.ctx.resume();
      } catch (e) { /* ses yok */ }
      return Promise.resolve();
    },
    ready() { return !!this.ctx && this.ctx.state === 'running'; },
    start() {
      if (this.on || !this.ready()) return;
      this.on = true;
      const ctx = this.ctx;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'square';
      gain.gain.value = 0.16;
      osc.connect(gain).connect(ctx.destination);
      osc.start();
      let hi = false;
      this.timer = setInterval(() => { hi = !hi; osc.frequency.setValueAtTime(hi ? 880 : 620, ctx.currentTime); }, 450);
      osc.frequency.value = 880;
      this.osc = osc;
    },
    stop() {
      if (!this.on) return;
      this.on = false;
      clearInterval(this.timer);
      try { this.osc.stop(); } catch (e) { /* zaten durdu */ }
      this.osc = null;
    },
  };
  // İlk dokunuş sesi açar. Alarm örtüsü BURADA yeniden kurulmaz: parmağın altındaki
  // düğme pointerdown ile click arasında yok olursa dokunuş kaybolur. Yalnız ipucu
  // satırı kalkar ve siren başlar.
  document.addEventListener('pointerdown', () => {
    Siren.unlock().then(() => {
      const hint = document.getElementById('alarm-ses');
      if (hint && Siren.ready()) hint.remove();
      if (document.getElementById('alarm') && S.soundOn) Siren.start();
    });
  }, { passive: true });

  let vibeTimer = null;
  function vibrate(on) {
    if (!('vibrate' in navigator)) return;
    clearInterval(vibeTimer);
    if (on) {
      navigator.vibrate([500, 250, 500]);
      vibeTimer = setInterval(() => navigator.vibrate([500, 250, 500]), 3000);
    } else navigator.vibrate(0);
  }

  // ----------------------------------------------------------- ekranı açık tut --

  let wakeLock = null;
  async function setWake(on) {
    if (!('wakeLock' in navigator) || !window.isSecureContext) return false;
    try {
      if (on && !wakeLock) {
        wakeLock = await navigator.wakeLock.request('screen');
        wakeLock.addEventListener('release', () => { wakeLock = null; });
      } else if (!on && wakeLock) { await wakeLock.release(); wakeLock = null; }
      return true;
    } catch (e) { return false; }
  }

  // ------------------------------------------------------------- sistem bildirimi --

  async function systemNotify(c) {
    if (!window.isSecureContext || !('Notification' in window) || Notification.permission !== 'granted') return;
    try {
      const reg = await navigator.serviceWorker.ready;
      const sev = SEV[c.severity] || SEV.KRITIK;
      await reg.showNotification(`${sev.shape} ${sev.name} · ${c.panel_key} · ${c.joint_short}`, {
        body: c.action || c.mode_label, tag: `olay-${c.id}`, renotify: true,
        requireInteraction: true, vibrate: [500, 250, 500], data: { id: c.id },
        icon: 'icon-192.png', badge: 'icon-192.png',
      });
    } catch (e) { /* bildirim yoksa alarm örtüsü yine çalışır */ }
  }

  // ------------------------------------------------------------------ alarm örtüsü --

  function ringing() {
    const now = Date.now();
    return S.list.filter((c) => c.sound && !(S.snooze[c.id] > now))
      .sort((a, b) => (SEV[b.severity]?.rank || 0) - (SEV[a.severity]?.rank || 0) || b.opened_at - a.opened_at);
  }

  function syncAlarm() {
    const list = ringing();
    const host = document.getElementById('alarm');
    if (!list.length) {
      Siren.stop(); vibrate(false);
      if (host) host.remove();
      S.alarmSig = '';
      document.title = 'PANO GÖZ · Saha';
      return;
    }
    const c = list[0];
    if (S.soundOn) Siren.start(); else Siren.stop();
    vibrate(S.soundOn);
    document.title = `🔴 (${list.length}) ONAY BEKLİYOR · PANO GÖZ`;
    for (const x of list) {
      if (!S.seen.has(x.id)) { S.seen.add(x.id); systemNotify(x); }
    }
    // Örtü yalnız İÇERİĞİ değişince yeniden kurulur; her yoklamada kurulsa halka
    // animasyonu her üç saniyede baştan başlar ve göz yorar.
    const sig = [list.map((x) => x.id).join(','), S.soundOn].join('|');
    if (host && sig === S.alarmSig) return;
    S.alarmSig = sig;
    const sev = SEV[c.severity] || SEV.KRITIK;
    const snooze = () => { S.snooze[c.id] = Date.now() + SNOOZE_MS; syncAlarm(); };
    const node = h('div', { id: 'alarm', class: `alarm ${sev.cls}`, role: 'alertdialog', 'aria-label': 'Alarm' },
      h('div', { class: 'simge', text: sev.shape }),
      h('div', { class: 'seviye', text: `${sev.name}${list.length > 1 ? ` · ${list.length} olay onay bekliyor` : ''}` }),
      h('h1', { text: 'Onay bekleyen olay' }),
      h('div', { class: 'konum', text: `${c.panel_key} · ${c.joint_short}` }),
      h('div', { class: 'mod', text: c.mode_label }),
      h('div', { class: 'yapilacak', text: c.action || c.title }),
      Siren.ready() || !S.soundOn ? null
        : h('div', { id: 'alarm-ses', class: 'notu', style: 'text-align:center', text: 'Sesin çalması için ekrana bir kez dokunun.' }),
      h('div', { class: 'dizi' },
        h('button', { class: `btn ${sev.cls === 'acil' ? 'acil' : 'birincil'}`, onclick: () => doAck(c.id) }, icon('check'), 'ONAYLA'),
        h('div', { class: 'satir' },
          h('button', { class: 'btn', onclick: () => { location.hash = `#/olay/${c.id}`; snooze(); } }, 'Ayrıntı'),
          h('button', { class: 'btn', onclick: snooze }, '5 dk sessiz'))));
    if (host) host.replaceWith(node); else document.body.append(node);
  }

  // ------------------------------------------------------------------- eylemler --

  async function doAck(id) {
    if (S.busy) return;
    S.busy = true;
    try {
      const r = await api(`/api/saha/olay/${id}/onay`, { method: 'POST', body: {} });
      if (!r.ok) banner(r.reason || 'Onay reddedildi.', true);
      else banner('Onaylandı · tekrarlar durduruldu');
    } catch (e) { banner(errText(e), true); }
    S.busy = false;
    await pollNow();
  }

  async function doStep(id, step) {
    if (S.busy) return;
    S.busy = true;
    try {
      const r = await api(`/api/saha/olay/${id}/durum`, { method: 'POST',
        body: { durum: step, not: step === 'tamam' ? S.note : '' } });
      if (step === 'tamam') S.note = '';
      banner(step === 'tamam' ? 'İş tamamlandı olarak kaydedildi' : (r.message_tr || 'Kaydedildi'));
    } catch (e) { banner(errText(e), true); }
    S.busy = false;
    await pollNow();
  }

  function errText(e) {
    const d = e && e.data;
    if (d && d.message_tr) return d.message_tr;
    if (d && d.detail && d.detail.message_tr) return d.detail.message_tr;
    return e && e.status ? `Sunucu hatası (${e.status}).` : 'Sunucuya ulaşılamıyor.';
  }

  let bannerTimer = null;
  function banner(text, danger) {
    const el = document.getElementById('uyari-bandi');
    el.textContent = text;
    el.className = danger ? 'tehlike' : '';
    el.hidden = false;
    clearTimeout(bannerTimer);
    bannerTimer = setTimeout(() => { el.hidden = true; }, 4000);
  }

  function logout(message) {
    if (S.token) api('/api/saha/logout', { method: 'POST', body: {} }).catch(() => {});
    S.token = null; S.member = null; S.list = []; S.detail = null;
    store.del(LS.token);
    Siren.stop(); vibrate(false);
    const a = document.getElementById('alarm'); if (a) a.remove();
    S.alarmSig = '';
    clearTimeout(S.timer);
    render(message);
  }

  // ------------------------------------------------------------------ yoklama --

  function schedule() {
    clearTimeout(S.timer);
    if (!S.token) return;
    S.timer = setTimeout(poll, document.hidden ? POLL_HIDDEN_MS : POLL_MS);
  }

  async function pollNow() { clearTimeout(S.timer); await poll(); }

  async function poll() {
    if (!S.token) return;
    try {
      const d = await api('/api/saha/olaylar?tum=1');
      S.member = d.member; S.list = d.olaylar;
      S.offset = d.server_ts - Date.now() / 1000;
      S.offline = false; S.syncedAt = Date.now();
      if (S.route.name === 'olay') {
        try { S.detail = await api(`/api/saha/olay/${S.route.id}`); S.detailErr = null; }
        catch (e) { if (e.status === 404) { S.detail = null; S.detailErr = 'Bu olay bulunamadı.'; } else throw e; }
      }
    } catch (e) {
      if (e.status === 401) return;
      S.offline = true;
    }
    syncAlarm();
    renderIfChanged();
    schedule();
  }

  // -------------------------------------------------------------------- çizim --

  const app = () => document.getElementById('app');

  function signature() {
    const strip = (o) => JSON.stringify(o, (k, v) => (k === 'age_s' || k === 'server_ts') ? undefined : v);
    return [S.token ? 1 : 0, S.route.name, S.route.id, S.filter, S.offline, S.busy, S.soundOn, S.wantWake,
            strip(S.list), strip(S.detail), S.detailErr, S.member && S.member.name].join('|');
  }

  function renderIfChanged() {
    const sig = signature();
    const el = document.activeElement;
    const typing = el && (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT');
    if (sig === S.sig || typing) { paintStatus(); return; }
    S.sig = sig;
    render();
  }

  function render(loginMessage) {
    const root = app();
    document.body.classList.toggle('giris-modu', !S.token);
    if (!S.token) {
      S.screen = 'giris';
      document.body.classList.remove('eylemli');
      root.replaceChildren(loginView(loginMessage));
      return;
    }
    S.loginCtl = null;
    S.sig = signature();
    const screen = S.route.name === 'olay' ? `olay:${S.route.id}` : 'liste';
    const changed = screen !== S.screen;
    const y = window.scrollY;
    S.screen = screen;

    const body = S.route.name === 'olay' ? detailView() : listView();
    root.replaceChildren(topBar(), h('div', { class: changed ? 'gecis' : '' }, body.view));
    document.body.classList.toggle('eylemli', !!body.bar);
    if (body.bar) root.append(body.bar);
    window.scrollTo(0, changed ? 0 : y);
    paintStatus();
  }

  function paintStatus() {
    const el = document.getElementById('sync');
    if (!el) return;
    el.replaceChildren(h('span', { class: S.offline ? 'dot off' : 'dot' }),
      S.offline ? `Bağlantı yok · ${clock(S.syncedAt / 1000)}` : `Güncel ${clock(S.syncedAt / 1000)}`);
  }

  function topBar() {
    return h('header', { class: 'bar' },
      h('div', { class: 'marka' }, logo(34), h('div', {}, h('b', { text: 'PANO GÖZ' }), h('small', { text: 'Saha ekibi' }))),
      h('div', { class: 'fill' }),
      h('div', { class: 'kisi' },
        h('div', {}, h('div', { class: 'ad', text: S.member ? S.member.name : '' }), h('div', { id: 'sync', class: 'durum' })),
        h('div', { class: 'avatar', 'aria-hidden': 'true', text: S.member ? initials(S.member.name) : '' })));
  }

  // ---- giriş

  function loginView(message) {
    const ctl = { name: store.get(LS.name), pin: '', busy: false };
    const membersEl = h('div', { class: 'uyeler', role: 'radiogroup', 'aria-label': 'Ad' });
    const dotsEl = h('div', { class: 'noktalar', role: 'img', 'aria-label': 'PIN' });
    const err = h('div', { class: 'hata', role: 'alert', text: message || '' });
    const goBtn = h('button', { class: 'tus gir', type: 'button', disabled: true, onclick: () => submit() }, 'Giriş');

    function paintDots() {
      const n = Math.max(4, ctl.pin.length);
      dotsEl.replaceChildren(...Array.from({ length: n }, (_, i) => h('span', { class: `nokta${i < ctl.pin.length ? ' dolu' : ''}` })));
      goBtn.disabled = ctl.pin.length < 4 || !ctl.name || ctl.busy;
    }
    function paintMembers(rota) {
      if (!rota.some((m) => m.name === ctl.name)) ctl.name = rota.length ? rota[0].name : null;
      membersEl.replaceChildren(...rota.map((m) => h('button', { type: 'button', class: 'uye', role: 'radio',
        'aria-checked': m.name === ctl.name, onclick: () => { ctl.name = m.name; paintMembers(rota); paintDots(); } },
        h('div', { class: 'avatar', text: initials(m.name) }),
        h('div', { class: 'kimlik' }, h('b', { text: m.name }), h('span', { text: `${m.role} · seviye ${m.level}` })),
        h('div', { class: 'secim' }, icon('check')))));
    }
    const press = (d) => { if (!ctl.busy && ctl.pin.length < 8) { ctl.pin += d; err.textContent = ''; paintDots(); } };
    const back = () => { ctl.pin = ctl.pin.slice(0, -1); paintDots(); };
    async function submit() {
      if (ctl.busy || ctl.pin.length < 4 || !ctl.name) return;
      Siren.unlock();
      ctl.busy = true; paintDots(); err.textContent = '';
      try {
        const r = await api('/api/saha/login', { method: 'POST', body: { name: ctl.name, pin: ctl.pin } });
        S.token = r.token; store.set(LS.token, r.token); store.set(LS.name, r.member.name);
        S.member = r.member;
        if (S.wantWake) setWake(true);
        registerWorker();
        render();
        pollNow();
      } catch (e) {
        err.textContent = errText(e);
        ctl.pin = ''; ctl.busy = false; paintDots();
        dotsEl.classList.add('salla');
        setTimeout(() => dotsEl.classList.remove('salla'), 420);
      }
    }
    S.loginCtl = { press, back, submit };

    api('/api/saha/rota').then(paintMembers).then(paintDots)
      .catch(() => { err.textContent = 'Sunucuya ulaşılamıyor. Bağlantıyı kontrol edip sayfayı yenileyin.'; });
    paintDots();

    const keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((d) => h('button', { type: 'button', class: 'tus', onclick: () => press(d), 'aria-label': d }, d));
    // Geniş ekranda iki panel (marka + giriş kartı), telefonda tek sütun; özellik listesi yalnız geniş ekranda görünür.
    const feature = (ic, title, text) => h('li', {}, h('span', { class: 'ic' }, icon(ic)), h('div', {}, h('b', { text: title }), text));
    return h('form', { class: 'giris gecis', onsubmit: (e) => e.preventDefault() },
      h('div', { class: 'marka-panel' },
        h('div', { class: 'hero' }, logo(56),
          h('h1', { text: 'PANO GÖZ · Saha' }),
          h('p', { text: 'Pano içi anomali erken uyarı — ekip uygulaması' })),
        h('ul', { class: 'ozellikler' },
          feature('bell', 'Uyarı gelince telefon çalar', 'Uygulama açıkken tam ekran alarm, siren ve titreşim.'),
          feature('check', 'Onayınız tekrarları durdurur', 'Onaydan sonra SMS ve Telegram tekrarları kesilir.'),
          feature('lock', 'Ayrıntı kurum ağında kalır', 'Ölçümler ve gerekçe bu uygulamanın arkasında durur.'))),
      h('div', { class: 'giris-panel' },
        h('div', {}, h('div', { class: 'etiket-kucuk', text: 'Nöbet listesinden adınızı seçin' }), membersEl),
        h('div', {}, h('div', { class: 'etiket-kucuk', text: 'PIN' }), dotsEl, err),
        h('div', { class: 'tuslar' }, keys,
          h('button', { type: 'button', class: 'tus', onclick: back, 'aria-label': 'Sil' }, icon('backspace')),
          h('button', { type: 'button', class: 'tus', onclick: () => press('0'), 'aria-label': '0' }, '0'),
          goBtn)));
  }

  // ---- gelen kutusu

  function summaryCard(waiting, mine) {
    const open = mine.filter((c) => c.state !== 'KAPANDI').length;
    const closed = mine.length - open;
    const counters = h('div', { class: 'sayaclar', 'aria-hidden': 'true' },
      h('div', { class: `sayac${waiting.length ? ' vurgu' : ''}` }, h('b', { text: String(waiting.length) }), h('small', { text: 'Onay bekliyor' })),
      h('div', { class: 'sayac' }, h('b', { text: String(open) }), h('small', { text: 'Açık' })),
      h('div', { class: 'sayac' }, h('b', { text: String(closed) }), h('small', { text: 'Kapanan' })));
    if (waiting.length) {
      const top = waiting.slice().sort((a, b) => (SEV[b.severity]?.rank || 0) - (SEV[a.severity]?.rank || 0))[0];
      const sev = SEV[top.severity] || SEV.KRITIK;
      return h('div', { class: `ozet bekliyor ${sev.cls}`, role: 'status' },
        h('div', { class: 'simge', text: sev.shape }),
        h('div', { class: 'metin' }, h('b', { text: `${waiting.length} olay onay bekliyor` }),
          h('span', { text: `${top.panel_key} · ${top.joint_short}` })),
        counters);
    }
    return h('div', { class: 'ozet rahat', role: 'status' },
      h('div', { class: 'simge' }, icon('shield')),
      h('div', { class: 'metin' }, h('b', { text: 'Bekleyen onay yok' }),
        h('span', { text: open ? `${open} açık olay takipte` : 'Size gönderilmiş açık olay yok' })),
      counters);
  }

  function listView() {
    const mine = S.list.filter((c) => c.notified_at !== null);
    const waiting = mine.filter((c) => c.needs_ack);
    const shown = S.filter === 'benim' ? mine : S.list;

    const tabs = h('div', { class: 'segment', role: 'group', 'aria-label': 'Filtre' },
      h('button', { 'aria-pressed': S.filter === 'benim', onclick: () => { S.filter = 'benim'; renderIfChanged(); } }, `Bana gelenler · ${mine.length}`),
      h('button', { 'aria-pressed': S.filter === 'tum', onclick: () => { S.filter = 'tum'; renderIfChanged(); } }, `Tümü · ${S.list.length}`));

    const cards = shown.length
      ? h('div', { class: 'liste' }, shown.map((c) => incidentCard(c)))
      : h('div', { class: 'bos' }, icon('shield'),
          h('b', { text: S.filter === 'benim' ? 'Size gönderilmiş açık olay yok' : 'Açık olay yok' }),
          h('span', { text: 'Yeni bir olay olduğunda burada görünür ve telefon çalar.' }));

    return { view: h('div', {}, summaryCard(waiting, mine), tabs, cards, settingsView()), bar: null };
  }

  function slaBlock(c) {
    if (!c.needs_ack || c.notified_at === null || !c.ack_deadline_s) return null;
    const left = c.ack_deadline_s - Math.max(0, nowSrv() - c.notified_at);
    const frac = Math.max(0, Math.min(1, left / c.ack_deadline_s));
    const cls = left <= 0 ? 'doldu az' : frac < 0.25 ? 'az' : frac < 0.55 ? 'orta' : '';
    return h('div', { class: `sla ${cls}` },
      h('div', { class: 'yazi' }, h('span', { text: left > 0 ? 'Onay için kalan süre' : 'Onay süresi doldu' }),
        h('b', { text: left > 0 ? span(left) : 'üst kademeye bildirildi' })),
      h('div', { class: 'cubuk' }, h('span', { style: `width:${(frac * 100).toFixed(1)}%` })));
  }

  function miniSteps(c) {
    const done = c.work ? STEPS.indexOf(c.work.durum) + 1 : 0;
    return h('span', { class: 'mini', 'aria-hidden': 'true' }, STEPS.map((s, i) => h('i', { class: i < done ? 'dolu' : '' })));
  }

  function incidentCard(c) {
    const sev = SEV[c.severity] || SEV.UYARI;
    const waiting = c.needs_ack && c.notified_at !== null;
    let status;
    if (c.state === 'KAPANDI') status = h('span', { class: 'mute', text: 'Kapandı' });
    else if (c.state === 'ONAYLANDI') {
      const w = c.work ? ` · ${STEP_LABEL[c.work.durum] || c.work.durum}` : '';
      status = h('span', { class: 'durum-yazi tamam', text: `✓ ${c.acked_by || 'Onaylandı'}${w}` });
    } else if (c.needs_ack) status = h('span', { class: 'durum-yazi bekle', text: 'ONAY BEKLİYOR' });
    else if (c.severity !== 'UYARI' && !c.dispatched) status = h('span', { class: 'dim', text: 'Henüz kimseye bildirilmedi (bekleme/teyit koşulları)' });
    else status = h('span', { class: 'dim', text: 'Kayıt (telefon çaldırmaz)' });
    return h('button', { class: `kart ${sev.cls}${waiting ? ' bekliyor' : ''}`,
      onclick: () => { location.hash = `#/olay/${c.id}`; } },
      h('div', { class: 'ust' }, h('span', { class: `rozet ${sev.cls}`, text: `${sev.shape} ${sev.name}` }),
        h('span', { class: 'yas', text: `#${c.id} · ${ago(nowSrv() - c.opened_at)}` })),
      h('div', { class: 'konum' }, h('b', { text: c.panel_key }), h('span', { class: 'chip mono', text: c.joint_short })),
      h('div', { class: 'mod', text: c.mode_label }),
      slaBlock(c),
      h('div', { class: 'alt' }, status,
        c.state === 'ONAYLANDI' ? miniSteps(c) : icon('chevron', 'ok-ikon')));
  }

  function settingsView() {
    const secure = window.isSecureContext;
    const canNotify = secure && 'Notification' in window;
    return h('details', { style: 'margin-top:22px' },
      h('summary', { text: 'Ayarlar' }),
      h('div', { class: 'dizi', style: 'padding-bottom:12px' },
        h('button', { class: 'btn', onclick: () => { S.soundOn = !S.soundOn; store.set(LS.sound, S.soundOn ? '1' : '0'); Siren.unlock(); syncAlarm(); renderIfChanged(); } },
          `Sesli alarm: ${S.soundOn ? 'açık' : 'kapalı'}`),
        'wakeLock' in navigator && secure
          ? h('button', { class: 'btn', onclick: async () => { S.wantWake = !S.wantWake; store.set(LS.wake, S.wantWake ? '1' : '0'); await setWake(S.wantWake); renderIfChanged(); } },
              `Ekranı açık tut: ${S.wantWake ? 'açık' : 'kapalı'}`) : null,
        canNotify && Notification.permission !== 'granted'
          ? h('button', { class: 'btn', onclick: async () => { await Notification.requestPermission(); renderIfChanged(); location.reload(); } }, 'Sistem bildirimlerine izin ver') : null,
        !secure ? h('p', { class: 'notu', text: 'Bu bağlantı güvenli değil (HTTP). Sistem bildirimi, ekranı açık tutma ve ana ekrana kurma kullanılamaz; uygulama açıkken ses, titreşim ve tam ekran alarm çalışır. Kalıcı çözüm HTTPS\'tir (docs/12 §4).' }) : null,
        h('p', { class: 'notu', text: 'Uygulama kapalıyken bu telefonu SMS ve Telegram çaldırır; bu uygulama arka planda uyandırılamaz (push servisi kamu bulutudur, şirket içi kısıtla çelişir).' }),
        h('button', { class: 'btn tehlike', onclick: () => logout() }, 'Çıkış yap')));
  }

  // ---- ayrıntı

  function detailView() {
    const back = h('button', { class: 'btn kucuk geri', onclick: () => { location.hash = '#/'; } }, icon('back'), 'Olaylar');
    if (S.detailErr) return { view: h('div', {}, back, h('div', { class: 'bos' }, h('b', { text: S.detailErr }))), bar: null };
    const d = S.detail;
    if (!d || d.olay.id !== S.route.id) {
      return { view: h('div', {}, back, h('div', { class: 'iskelet' }), h('div', { class: 'iskelet', style: 'height:7rem' }),
        h('div', { class: 'iskelet', style: 'height:9rem' })), bar: null };
    }
    const c = d.olay;
    const sev = SEV[c.severity] || SEV.UYARI;

    const hero = h('div', { class: `serit ${sev.cls}` },
      h('div', { class: 'ust' }, h('span', { class: `rozet ${sev.cls}`, text: `${sev.shape} ${sev.name}` }),
        h('span', { class: 'yas', text: `olay #${c.id} · ${ago(nowSrv() - c.opened_at)}` })),
      h('h1', {}, c.panel_key, h('span', { class: 'chip mono', text: c.joint_short })),
      h('div', { class: 'mod', text: c.mode_label }));

    // Telefonda iki kolon alt alta akar (sıra değişmez); geniş ekranda yan yana durur.
    const view = h('div', {}, back, hero,
      h('div', { class: 'kolonlar' },
        h('div', { class: 'kolon' },
          section('Ne yapmalı', h('div', { class: 'yapilacak', text: c.action || c.title })),
          workSection(c),
          locationSection(d.pano)),
        h('div', { class: 'kolon' },
          measuresSection(d.olcum),
          whySection(d.neden),
          timelineSection(d.zaman_cizgisi))),
      h('div', { class: 'alt-bosluk' }));
    return { view, bar: actionBar(c) };
  }

  function section(title, ...body) {
    return h('section', { class: 'bolum' }, h('h2', { text: title }), ...body);
  }

  // Sabit eylem çubuğu: bir sonraki adım her zaman başparmağın altında.
  function actionBar(c) {
    if (c.state === 'KAPANDI') return null;
    const sev = SEV[c.severity] || SEV.UYARI;
    let inner;
    if (c.state === 'ACIK') {
      inner = h('button', { class: `btn ${c.needs_ack && sev.cls === 'acil' ? 'acil' : 'birincil'}`, disabled: S.busy, onclick: () => doAck(c.id) },
        icon('check'), c.needs_ack ? 'ONAYLA · tekrarları durdur' : 'Gördüm · onayla');
    } else {
      const done = c.work ? STEPS.indexOf(c.work.durum) : -1;
      const next = STEPS[done + 1];
      inner = next
        ? h('button', { class: 'btn birincil', disabled: S.busy, onclick: () => doStep(c.id, next) }, STEP_LABEL[next])
        : h('div', { class: 'bitti-yazi' }, '✓ İş tamamlandı',
            h('small', { text: 'Sensörler yedi gün temiz okuyunca olay kendiliğinden kapanır' }));
    }
    return h('div', { class: 'eylem-bar' }, inner);
  }

  function workSection(c) {
    if (c.state === 'KAPANDI') return section('Durum', h('p', { class: 'dim', text: 'Olay kapandı.' }));
    const doneCount = c.state === 'ACIK' ? 0 : 1 + (c.work ? STEPS.indexOf(c.work.durum) + 1 : 0);
    const nodes = NODE_LABEL.map((label, i) => {
      const cls = i < doneCount ? 'bitti' : (i === doneCount ? 'simdi' : '');
      return h('div', { class: `adim ${cls}` }, h('div', { class: 'd' }, i < doneCount ? icon('check') : String(i + 1)), label);
    });
    const progress = Math.max(0, Math.min(doneCount, 4) - 1) / 3 * 75;
    const next = c.state === 'ONAYLANDI' ? STEPS[(c.work ? STEPS.indexOf(c.work.durum) : -1) + 1] : null;
    return section('İş emri',
      h('div', { class: 'adimlar' }, h('div', { class: 'ilerleme', style: `width:${progress}%` }), nodes),
      c.state === 'ACIK'
        ? h('p', { class: 'notu', text: 'Onay, oturumunuzla kaydedilir ve SMS/Telegram tekrarlarını durdurur.' })
        : h('p', { class: 'notu', text: `Onaylayan: ${c.acked_by || ''}` }),
      next === 'tamam' ? h('textarea', { class: 'girdi', placeholder: 'Yapılan işlem (örn. tork 40 Nm, pabuç yenilendi)', maxlength: '500',
        'aria-label': 'Not', oninput: (e) => { S.note = e.target.value; } }, S.note) : null,
      c.state === 'ONAYLANDI' ? h('p', { class: 'notu', text: '"Tamamladım", olayı kapatmaz: sensörler yedi gün temiz okuyunca sistem kendisi kapatır.' }) : null);
  }

  function locationSection(p) {
    const has = p && p.lat !== null && p.lon !== null;
    return section('Konum',
      h('div', { class: 'konum-kutu' },
        h('div', { class: 'ad' }, icon('pin'), p && p.name ? p.name : (p ? p.panel_key : '')),
        h('div', { class: 'dim', text: [p && p.site, p && p.dso].filter(Boolean).join(' · ') }),
        has ? h('div', { class: 'mono mute', text: `${num(p.lat, 5)}, ${num(p.lon, 5)}` }) : h('div', { class: 'mute', text: 'Konum kaydı yok.' }),
        has ? h('div', { class: 'satir', style: 'margin-top:10px' },
          h('a', { class: 'btn kucuk', href: p.maps_url, target: '_blank', rel: 'noopener' }, 'Yol tarifi'),
          h('a', { class: 'btn kucuk', href: p.geo_url }, 'Haritada aç')) : null));
  }

  // θ'yı mutlak basamaklar üzerinde gösterir. Beş bölge eşit genişliktedir (Normal, İzle,
  // Uyarı, Kritik, Acil); işaret bölge içinde doğrusal yerleşir. Ölçek θ'nın basamağıdır:
  // olayın seviyesi birden çok kanıttan çıkar ve bu ölçekten farklı olabilir (ark olayı gibi).
  function thetaScale(theta, ladder) {
    if (theta === null || theta === undefined || !Array.isArray(ladder) || ladder.length !== 4) return null;
    const t = ladder.map((x) => x[1]);
    let z = 0;
    while (z < 4 && theta >= t[z]) z += 1;                      // z = bölge indeksi 0..4
    let within;
    if (z === 0) within = theta / t[0];
    else if (z === 4) within = Math.min(1, (theta - t[3]) / t[3]);
    else within = (theta - t[z - 1]) / (t[z] - t[z - 1]);
    const pos = Math.max(0.01, Math.min(0.99, (z + Math.max(0, within)) / 5));
    return h('div', { class: 'olcek', role: 'img',
      'aria-label': `θ ${num(theta, 1)} K, ${ZONE[z].name} bölgesinde` },
      h('div', { class: 'zemin' }, ZONE.map((zn, i) => h('i', { class: i === z ? 'aktif' : '', style: `--z:${zn.color}` })),
        h('div', { class: 'isaret', style: `left:${(pos * 100).toFixed(1)}%` }, h('b', { text: `${num(theta, 1)} K` }))),
      h('div', { class: 'etiketler' }, ZONE.map((zn) => h('span', { text: zn.name }))),
      h('div', { class: 'esikler' }, t.map((v) => h('span', { text: `${num(v, 0)} K` })), h('span', { text: '' })));
  }

  function measuresSection(o) {
    const cells = [];
    const add = (label, value, unit) => { if (value !== null && value !== undefined) cells.push(h('div', { class: 'olcum' }, h('div', { class: 'e', text: label }), h('div', {}, h('span', { class: 'd', text: value }), unit ? h('span', { class: 'b', text: unit }) : null))); };
    add('θ (kardeşe göre)', num(o.theta_k, 1), 'K');
    add('Bağlantı sıcaklığı', num(o.temp_c, 1), '°C');
    add('Kardeş medyanı', num(o.sibling_median_c, 1), '°C');
    add('Fark ΔT', num(o.delta_t_k, 1), 'K');
    add('Akım', o.current_a > 0 ? num(o.current_a, 0) : null, 'A');   // 0 = bu pabuçta akım kelepçesi yok
    add('Yük faktörü', o.load_factor === null || o.load_factor === undefined ? null : `%${num(o.load_factor * 100, 0)}`, '');
    add('Eğim', num(o.slope_k_per_week, 2), 'K/hafta');
    if (o.excess_resistance) add('Fazla direnç', `${num(o.excess_resistance.lo_uohm, 0)}–${num(o.excess_resistance.hi_uohm, 0)}`, 'µΩ');
    add('Sağlık endeksi', num(o.health_index, 0), '');
    if (o.eta) cells.push(h('div', { class: 'olcum metin' }, h('div', { class: 'e', text: 'Eşiğe kalan' }), h('div', { class: 'd', text: trSeverity(o.eta) })));
    if (!cells.length) return section('Ölçümler', h('p', { class: 'mute', text: 'Bu olay için bağlantı ölçümü yok (pano düzeyinde bulgu).' }));
    const scale = thetaScale(o.theta_k, o.theta_merdiven);
    return section('Ölçümler', scale, h('div', { class: 'olcumler' }, cells),
      scale ? h('p', { class: 'notu', text: 'Ölçek θ\'nın mutlak basamaklarıdır; olayın seviyesi birden çok kanıttan çıkar ve ölçekten farklı olabilir.' }) : null,
      o.excess_resistance
        ? h('p', { class: 'notu', text: 'Fazla direnç tek sayı değil aralıktır: yerel ısıl direnç yalnız 2–4 K/W aralığında bilinir.' })
        : null);
  }

  function whySection(n) {
    const parts = [];
    if (n.aileler && n.aileler.length) parts.push(h('div', { class: 'cips' }, n.aileler.map((a) => h('span', { class: 'cip', text: a }))),
      h('p', { class: 'notu', text: 'Alarm için birbirinden bağımsız iki ölçüm ilkesi hemfikir olmalıdır.' }));
    if (n.terimler && n.terimler.length) parts.push(h('ul', { class: 'madde' }, n.terimler.map((t) => h('li', { text: t }))));
    if (n.elenenler && n.elenenler.length) parts.push(h('details', { style: 'margin-top:10px' },
      h('summary', { text: `Neler elendi (${n.elenenler.length})` }),
      h('ul', { class: 'madde' }, n.elenenler.map((t) => h('li', { text: t })))));
    return section('Neden alarm verildi', ...(parts.length ? parts : [h('p', { class: 'mute', text: 'Gerekçe kaydı yok.' })]));
  }

  function timelineSection(list) {
    const items = (list || []).map((e) => {
      let content, cls = e.tip;
      if (e.tip === 'acilis') content = ['Olay açıldı'];
      else if (e.tip === 'bildirim') content = [h('span', { class: `kanal ${e.kanal}`, text: CHANNEL[e.kanal] || e.kanal }), `${e.hedef} · ${NSTATE[e.durum] || e.durum}`];
      else if (e.tip === 'durum') { content = [`${e.by}: ${STEP_LABEL[e.durum] || e.durum}${e.not ? ` — ${e.not}` : ''}`]; cls = e.durum === 'tamam' ? 'tamam' : 'durum'; }
      else if (e.tip === 'onay') content = [`Onaylandı · ${e.by}`];
      return h('li', { class: cls }, h('span', { class: 's', text: clock(e.ts) }), ...content);
    });
    return section('Zaman çizgisi', h('ol', { class: 'zaman' }, items));
  }

  // -------------------------------------------------------------- başlatma --

  function registerWorker() {
    if (!('serviceWorker' in navigator) || !window.isSecureContext) return;
    navigator.serviceWorker.register('sw.js', { scope: './' }).catch(() => {});
  }

  window.addEventListener('hashchange', () => {
    S.route = parseRoute(); S.detail = null; S.detailErr = null;
    if (S.token) { render(); pollNow(); } else render();
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && S.token) { if (S.wantWake) setWake(true); pollNow(); }
  });
  // Fiziksel klavye (masaüstünde deneyen için): rakam, geri silme, Enter.
  document.addEventListener('keydown', (e) => {
    const c = S.loginCtl;
    if (!c || S.token || e.ctrlKey || e.metaKey || e.altKey) return;
    if (/^\d$/.test(e.key)) c.press(e.key);
    else if (e.key === 'Backspace') c.back();
    else if (e.key === 'Enter') c.submit();
  });
  // Zamana bağlı göstergeler (yaş, onay süresi çubuğu) veri değişmese de akar.
  setInterval(() => {
    if (!S.token || document.hidden || S.route.name !== 'liste') return;
    S.sig = '';
    renderIfChanged();
  }, CLOCK_MS);

  render();
  if (S.token) { registerWorker(); if (S.wantWake) setWake(true); pollNow(); }
})();
