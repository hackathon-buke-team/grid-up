/* PANO GÖZ · Saha uygulaması
   ---------------------------
   Düz JavaScript, bağımlılık yok. Sunucudan gelen HER metin textContent ile
   basılır; hiçbir yerde innerHTML'e veri verilmez.

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
  const SNOOZE_MS = 5 * 60 * 1000;
  const STEPS = ['yolda', 'sahada', 'tamam'];
  const STEP_LABEL = { yolda: 'Yola çıktım', sahada: 'Sahadayım', tamam: 'İşi tamamladım' };
  const SEV = {
    UYARI: { cls: 'uyari', shape: '▲', name: 'UYARI', rank: 1 },
    KRITIK: { cls: 'kritik', shape: '◆', name: 'KRİTİK', rank: 2 },
    ACIL: { cls: 'acil', shape: '■', name: 'ACİL', rank: 3 },
  };
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
      else if (k === 'aria-pressed') el.setAttribute(k, String(v));
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) {
      if (kid === null || kid === undefined || kid === false) continue;
      el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }

  const num = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v)) ? null
    : Number(v).toLocaleString('tr-TR', { maximumFractionDigits: d, minimumFractionDigits: 0 });
  const clock = (ts) => ts ? new Date(ts * 1000).toLocaleTimeString('tr-TR',
    { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';

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

  // ------------------------------------------------------------------- durum --

  const S = {
    token: store.get(LS.token),
    member: null,
    list: [],
    detail: null,
    detailErr: null,
    filter: 'benim',
    route: parseRoute(),
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
    timer: null,
  };

  function parseRoute() {
    const m = location.hash.match(/^#\/olay\/(\d+)/);
    return m ? { name: 'olay', id: Number(m[1]) } : { name: 'liste' };
  }

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
        if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume();
      } catch (e) { /* ses yok */ }
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
  const unlockAudio = () => Siren.unlock();
  document.addEventListener('pointerdown', unlockAudio, { passive: true });

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
    const sev = SEV[c.severity] || SEV.KRITIK;
    const node = h('div', { id: 'alarm', class: `alarm ${sev.cls} yanip`, role: 'alertdialog', 'aria-label': 'Alarm' },
      h('div', { class: `etiket ${sev.cls}` }, `${sev.shape} ${sev.name}${list.length > 1 ? ` · ${list.length} olay onay bekliyor` : ''}`),
      h('h1', { text: 'Onay bekleyen olay' }),
      h('div', { class: 'konum', text: `${c.panel_key} · ${c.joint_short}` }),
      h('div', { class: 'dim', text: c.mode_label }),
      h('div', { class: 'yapilacak', text: c.action || c.title }),
      Siren.ready() || !S.soundOn ? null
        : h('div', { class: 'notu', text: 'Sesin çalması için ekrana bir kez dokunun.' }),
      h('div', { class: 'dizi' },
        h('button', { class: 'btn birincil', onclick: () => doAck(c.id) }, 'ONAYLA'),
        h('div', { class: 'satir' },
          h('button', { class: 'btn', onclick: () => { location.hash = `#/olay/${c.id}`; S.snooze[c.id] = Date.now() + SNOOZE_MS; syncAlarm(); } }, 'Ayrıntı'),
          h('button', { class: 'btn', onclick: () => { S.snooze[c.id] = Date.now() + SNOOZE_MS; syncAlarm(); } }, '5 dk sessiz'))));
    if (host) host.replaceWith(node); else document.body.append(node);
  }

  // ------------------------------------------------------------------- eylemler --

  async function doAck(id) {
    if (S.busy) return;
    S.busy = true;
    try {
      const r = await api(`/api/saha/olay/${id}/onay`, { method: 'POST', body: {} });
      if (!r.ok) banner(r.reason || 'Onay reddedildi.', true);
      else banner('Onaylandı. Tekrarlar durduruldu.');
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
      banner(r.message_tr || 'Kaydedildi.');
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
    if (!S.token) { root.replaceChildren(loginView(loginMessage)); return; }
    S.sig = signature();
    root.replaceChildren(topBar(), S.route.name === 'olay' ? detailView() : listView());
    paintStatus();
  }

  function paintStatus() {
    const el = document.getElementById('sync');
    if (!el) return;
    el.replaceChildren(h('span', { class: S.offline ? 'dot off' : 'dot' }),
      S.offline ? `Bağlantı yok · son bilinen durum ${clock(S.syncedAt / 1000)}` : `Güncel ${clock(S.syncedAt / 1000)}`);
  }

  function topBar() {
    return h('header', { class: 'bar' },
      h('div', { class: 'marka' }, 'PANO GÖZ', h('small', { text: 'Saha' })),
      h('div', { class: 'fill' }),
      h('div', { class: 'durum', style: 'text-align:right' },
        h('div', { text: S.member ? S.member.name : '' }),
        h('div', { id: 'sync', class: 'mute' })));
  }

  // ---- giriş

  function loginView(message) {
    const nameSel = h('select', { class: 'girdi', id: 'ad', 'aria-label': 'Ad' });
    const pin = h('input', { class: 'girdi pin', id: 'pin', type: 'password', inputmode: 'numeric',
      autocomplete: 'one-time-code', maxlength: '8', 'aria-label': 'PIN', placeholder: '••••' });
    const err = h('div', { class: 'hata', role: 'alert', text: message || '' });
    const btn = h('button', { class: 'btn birincil', type: 'submit' }, 'Giriş');

    api('/api/saha/rota').then((rota) => {
      const last = store.get(LS.name);
      nameSel.replaceChildren(...rota.map((m) => h('option', { value: m.name, selected: m.name === last }, `${m.name} · ${m.role}`)));
    }).catch(() => { err.textContent = 'Sunucuya ulaşılamıyor.'; });

    const form = h('form', { class: 'giris', onsubmit: async (ev) => {
      ev.preventDefault();
      Siren.unlock();
      btn.disabled = true; err.textContent = '';
      try {
        const r = await api('/api/saha/login', { method: 'POST', body: { name: nameSel.value, pin: pin.value } });
        S.token = r.token; store.set(LS.token, r.token); store.set(LS.name, r.member.name);
        S.member = r.member;
        if (S.wantWake) setWake(true);
        registerWorker();
        render();
        pollNow();
      } catch (e) {
        err.textContent = errText(e);
        pin.value = ''; btn.disabled = false; pin.focus();
      }
    } },
      h('div', {}, h('h1', { text: 'PANO GÖZ · Saha' }), h('p', { class: 'dim', text: 'Nöbet listesindeki adınızı seçin ve PIN girin.' })),
      h('label', {}, 'Ad', nameSel),
      h('label', {}, 'PIN', pin),
      err, btn);
    return form;
  }

  // ---- gelen kutusu

  function listView() {
    const mine = S.list.filter((c) => c.notified_at !== null);
    const shown = S.filter === 'benim' ? mine : S.list;
    const offset = S.offset;
    const nowSrv = Date.now() / 1000 + offset;

    const tabs = h('div', { class: 'sekmeler', role: 'group', 'aria-label': 'Filtre' },
      h('button', { class: 'sekme', 'aria-pressed': S.filter === 'benim', onclick: () => { S.filter = 'benim'; renderIfChanged(); } }, `Bana gelenler (${mine.length})`),
      h('button', { class: 'sekme', 'aria-pressed': S.filter === 'tum', onclick: () => { S.filter = 'tum'; renderIfChanged(); } }, `Tümü (${S.list.length})`));

    const cards = shown.length
      ? h('div', { class: 'liste' }, shown.map((c) => incidentCard(c, nowSrv)))
      : h('div', { class: 'bos' }, h('div', { class: 'buyuk', text: '✓' }),
          h('p', { text: S.filter === 'benim' ? 'Size gönderilmiş açık olay yok.' : 'Açık olay yok.' }));

    return h('div', {}, tabs, cards, settingsView());
  }

  function incidentCard(c, nowSrv) {
    const sev = SEV[c.severity] || SEV.UYARI;
    const waiting = c.needs_ack;
    let status;
    if (c.state === 'KAPANDI') status = h('span', { class: 'mute', text: 'Kapandı' });
    else if (c.state === 'ONAYLANDI') {
      const w = c.work ? ` · ${STEP_LABEL[c.work.durum] || c.work.durum}` : '';
      status = h('span', { class: 'tamam', text: `✓ ${c.acked_by || 'Onaylandı'}${w}` });
    } else if (waiting) status = h('span', { class: 'bekle', text: 'ONAY BEKLİYOR' });
    else if (c.severity !== 'UYARI' && !c.dispatched) status = h('span', { class: 'dim', text: 'Henüz kimseye bildirilmedi (bekleme/teyit koşulları)' });
    else status = h('span', { class: 'dim', text: 'Kayıt (telefon çaldırmaz)' });
    return h('button', { class: `kart ${sev.cls}${waiting && c.notified_at ? ' bekliyor' : ''}`,
      onclick: () => { location.hash = `#/olay/${c.id}`; } },
      h('div', { class: 'ust' }, h('span', { class: `etiket ${sev.cls}` }, `${sev.shape} ${sev.name}`),
        h('span', { class: 'mute', text: ago(nowSrv - c.opened_at) })),
      h('div', { class: 'konum', text: `${c.panel_key} · ${c.joint_short}` }),
      h('div', { class: 'mod', text: c.mode_label }),
      h('div', { class: 'alt' }, status));
  }

  function settingsView() {
    const secure = window.isSecureContext;
    const canNotify = secure && 'Notification' in window;
    return h('details', { style: 'margin-top:20px' },
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
    const back = h('button', { class: 'btn kucuk geri', onclick: () => { location.hash = '#/'; } }, '← Olaylar');
    if (S.detailErr) return h('div', {}, back, h('div', { class: 'bos', text: S.detailErr }));
    const d = S.detail;
    if (!d || d.olay.id !== S.route.id) return h('div', {}, back, h('div', { class: 'bos', text: 'Yükleniyor…' }));
    const c = d.olay;
    const sev = SEV[c.severity] || SEV.UYARI;

    return h('div', {}, back,
      h('div', { class: `serit ${sev.cls}` },
        h('div', { class: `etiket ${sev.cls}` }, `${sev.shape} ${sev.name} · olay #${c.id}`),
        h('h1', { text: `${c.panel_key} · ${c.joint_short}` }),
        h('div', { class: 'mod', text: c.mode_label })),
      section('Ne yapmalı', h('div', { class: 'yapilacak', text: c.action || c.title })),
      actionsSection(c),
      locationSection(d.pano),
      measuresSection(d.olcum),
      whySection(d.neden),
      timelineSection(d.zaman_cizgisi));
  }

  function section(title, ...body) {
    return h('section', { class: 'bolum' }, h('h2', { text: title }), ...body);
  }

  function actionsSection(c) {
    if (c.state === 'KAPANDI') return section('Durum', h('p', { class: 'dim', text: 'Olay kapandı.' }));
    if (c.state === 'ACIK') {
      return section('Onay', h('button', { class: c.needs_ack ? 'btn birincil' : 'btn', disabled: S.busy, onclick: () => doAck(c.id) },
        c.needs_ack ? 'ONAYLA · tekrarları durdur' : 'Gördüm · onayla'),
        h('p', { class: 'notu', text: 'Onay, oturumunuzla kaydedilir ve SMS/Telegram tekrarlarını durdurur.' }));
    }
    const done = c.work ? STEPS.indexOf(c.work.durum) : -1;
    const next = STEPS[done + 1];
    const btns = STEPS.map((s, i) => {
      if (i <= done) return h('div', { class: 'btn bitti' }, `✓ ${STEP_LABEL[s]}`);
      return h('button', { class: i === done + 1 ? 'btn birincil' : 'btn', disabled: S.busy || i !== done + 1,
        onclick: () => doStep(c.id, s) }, STEP_LABEL[s]);
    });
    return section('İş emri',
      h('p', { class: 'tamam', text: `✓ Onaylandı · ${c.acked_by || ''}` }),
      h('div', { class: 'adim', style: 'margin-top:10px' }, btns,
        next === 'tamam' ? h('textarea', { class: 'girdi', placeholder: 'Yapılan işlem (örn. tork 40 Nm, pabuç yenilendi)', maxlength: '500',
          'aria-label': 'Not', oninput: (e) => { S.note = e.target.value; } }, S.note) : null),
      h('p', { class: 'notu', text: '"Tamamladım", olayı kapatmaz: sensörler yedi gün temiz okuyunca sistem kendisi kapatır.' }));
  }

  function locationSection(p) {
    const has = p && p.lat !== null && p.lon !== null;
    return section('Konum',
      h('div', { class: 'konum-kutu' },
        h('div', { class: 'ad', text: p && p.name ? p.name : (p ? p.panel_key : '') }),
        h('div', { class: 'dim', text: [p && p.site, p && p.dso].filter(Boolean).join(' · ') }),
        has ? h('div', { class: 'mono mute', text: `${num(p.lat, 5)}, ${num(p.lon, 5)}` }) : h('div', { class: 'mute', text: 'Konum kaydı yok.' }),
        has ? h('div', { class: 'satir', style: 'margin-top:10px' },
          h('a', { class: 'btn kucuk', href: p.maps_url, target: '_blank', rel: 'noopener' }, 'Yol tarifi'),
          h('a', { class: 'btn kucuk', href: p.geo_url }, 'Haritada aç')) : null));
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
    return section('Ölçümler', h('div', { class: 'olcumler' }, cells),
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
      let text = '', cls = '';
      if (e.tip === 'acilis') text = `Olay açıldı`;
      else if (e.tip === 'bildirim') text = `${CHANNEL[e.kanal] || e.kanal} → ${e.hedef} · ${NSTATE[e.durum] || e.durum}`;
      else if (e.tip === 'durum') { text = `${e.by}: ${STEP_LABEL[e.durum] || e.durum}${e.not ? ` — ${e.not}` : ''}`; cls = e.durum === 'tamam' ? 'tamam' : ''; }
      else if (e.tip === 'onay') { text = `Onaylandı · ${e.by}`; cls = 'onay'; }
      return h('li', { class: cls }, h('span', { class: 's', text: clock(e.ts) }), text);
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
  setInterval(() => { if (S.token && !document.hidden) renderIfChanged(); }, 20000);

  render();
  if (S.token) { registerWorker(); if (S.wantWake) setWake(true); pollNow(); }
})();
