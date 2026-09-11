// PANO GÖZ · REST + WebSocket istemcisi.
//
// Tek bir fetch sarmalayıcı, tek bir hata tipi ve WebSocket düşerse 3 saniyede
// bir yoklamaya (polling) düşen bir canlı bağlantı. Bağlantı durumu her zaman
// ekranda görünür: "canlı", "yoklama", "bağlantı yok". Sessizce eski veriyi
// canlıymış gibi göstermek, bir izleme sisteminin yapabileceği en kötü şeydir.

export class ApiError extends Error {
  constructor(status, path, detail) {
    super(`HTTP ${status} · ${path}`);
    this.status = status;
    this.path = path;
    this.detail = detail || '';
  }
}

async function req(path, opts) {
  let r;
  try {
    r = await fetch(path, opts);
  } catch (e) {
    throw new ApiError(0, path, 'ağ hatası: ' + e.message);
  }
  if (!r.ok) {
    let detail = '';
    try { detail = (await r.text()).slice(0, 400); } catch (e) { /* yoksay */ }
    throw new ApiError(r.status, path, detail);
  }
  const ct = r.headers.get('content-type') || '';
  if (ct.includes('application/json')) return r.json();
  return r.text();
}

const q = (o) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o || {})) {
    if (v === undefined || v === null || v === '') continue;
    p.set(k, String(v));
  }
  const str = p.toString();
  return str ? '?' + str : '';
};

const enc = encodeURIComponent;

async function post(path, body) {
  return req(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
}

export const api = {
  health:        ()                       => req('/api/health'),
  fleet:         ()                       => req('/api/fleet'),
  panel:         (k)                      => req('/api/panel/' + enc(k)),
  twin:          (k)                      => req('/api/panel/' + enc(k) + '/twin'),
  trend:         (k, joint, channel, hours = 168) =>
                    req('/api/panel/' + enc(k) + '/trend' + q({ joint, channel, hours })),
  daily:         (k, joint, days = 120)   => req('/api/panel/' + enc(k) + '/daily' + q({ joint, days })),
  prpd:          (k)                      => req('/api/panel/' + enc(k) + '/prpd'),
  alarms:        (state = 'ACIK', limit = 200) => req('/api/alarms' + q({ state, limit })),
  ack:           (id, by, token)          => post('/api/alarms/' + enc(id) + '/ack', { by, token }),
  suppressions:  (hours = 24)             => req('/api/suppressions' + q({ hours })),
  devices:       (panel)                  => req('/api/devices' + q({ panel })),
  scada:         (panel)                  => req('/api/scada/registers' + q({ panel })),
  icd:           ()                       => req('/api/icd'),
  icdCsvUrl:     ()                       => '/api/icd.csv',
  notifications: (limit = 50)             => req('/api/notifications' + q({ limit })),
  scenarios:     ()                       => req('/api/scenarios'),
  inject:        (key, body)              => post('/api/scenario/' + enc(key), body),
  demoReset:     ()                       => post('/api/demo/reset', {}),
  audit:         ()                       => req('/api/audit/verify'),
  supplied:      ()                       => req('/api/analysis/supplied-data'),
};

// --------------------------------------------------------------------------
// Canlı bağlantı
// --------------------------------------------------------------------------

export const LIVE_STATE = { WS: 'ws', POLL: 'poll', DOWN: 'down' };

export class Live {
  /**
   * @param {object} opts
   *   onFleet(data), onPanel(data), onAlarm(data), onState(state, detail),
   *   panelKey() -> seçili pano anahtarı (yoklama modunda çekilir)
   */
  constructor(opts = {}) {
    this.opts = opts;
    this.state = LIVE_STATE.DOWN;
    this.ws = null;
    this.pollTimer = null;
    this.retryTimer = null;
    this.pollMs = opts.pollMs || 3000;
    this.lastMessageTs = 0;
    this.messages = 0;
    this.reconnects = 0;
    this.stopped = false;
  }

  start() {
    this.stopped = false;
    this._openWs();
    // WebSocket 4 saniyede kurulmazsa yoklamaya düş; demo asla boş ekranla başlamaz.
    setTimeout(() => { if (this.state !== LIVE_STATE.WS) this._startPolling(); }, 4000);
  }

  stop() {
    this.stopped = true;
    if (this.ws) { try { this.ws.close(); } catch (e) { /* yoksay */ } this.ws = null; }
    this._stopPolling();
    clearTimeout(this.retryTimer);
  }

  _setState(st, detail) {
    if (this.state === st) return;
    this.state = st;
    if (this.opts.onState) this.opts.onState(st, detail || '');
  }

  _openWs() {
    if (this.stopped) return;
    let url;
    try {
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      url = `${proto}//${location.host}/ws`;
    } catch (e) { return; }
    let ws;
    try { ws = new WebSocket(url); } catch (e) { this._startPolling(); return; }
    this.ws = ws;

    ws.onopen = () => {
      this.reconnects += 1;
      this._stopPolling();
      this._setState(LIVE_STATE.WS, url);
      // Sunucu {"panel": "<anahtar>"} mesajıyla hangi panonun itileceğini seçtirir.
      const key = this.opts.panelKey && this.opts.panelKey();
      if (key) this.watch(key);
    };
    ws.onmessage = (ev) => {
      this.messages += 1;
      this.lastMessageTs = Date.now() / 1000;
      let msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      this._dispatch(msg && msg.type, msg && msg.data);
    };
    ws.onerror = () => { /* onclose zaten tetiklenecek */ };
    ws.onclose = () => {
      this.ws = null;
      if (this.stopped) return;
      this._startPolling();
      clearTimeout(this.retryTimer);
      this.retryTimer = setTimeout(() => this._openWs(), 10000);
    };
  }

  _dispatch(type, data) {
    if (type === 'fleet' && this.opts.onFleet) this.opts.onFleet(data);
    else if (type === 'panel' && this.opts.onPanel) this.opts.onPanel(data);
    else if (type === 'alarm' && this.opts.onAlarm) this.opts.onAlarm(data);
  }

  _startPolling() {
    if (this.pollTimer || this.stopped) return;
    this._setState(LIVE_STATE.POLL, `${this.pollMs / 1000} sn yoklama`);
    const tick = async () => {
      try {
        const fleet = await api.fleet();
        this.lastMessageTs = Date.now() / 1000;
        this._setState(LIVE_STATE.POLL, `${this.pollMs / 1000} sn yoklama`);
        this._dispatch('fleet', fleet);
        const key = this.opts.panelKey && this.opts.panelKey();
        if (key) {
          try { this._dispatch('panel', await api.panel(key)); } catch (e) { /* 404 normaldir */ }
        }
      } catch (e) {
        this._setState(LIVE_STATE.DOWN, e.message);
      }
    };
    tick();
    this.pollTimer = setInterval(tick, this.pollMs);
  }

  _stopPolling() {
    if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
  }

  /** Sunucuya hangi panoyu itmesini istediğimizi bildir. */
  watch(key) {
    this.watched = key;
    if (this.ws && this.ws.readyState === 1) {
      try { this.ws.send(JSON.stringify({ panel: key })); } catch (e) { /* yoksay */ }
    }
  }

  /** Ekranlar kendi verisini tazelemek istediğinde çağırır. */
  async refreshNow() {
    const fleet = await api.fleet();
    this._dispatch('fleet', fleet);
    return fleet;
  }

  describe() {
    if (this.state === LIVE_STATE.WS) return 'WebSocket · canlı';
    if (this.state === LIVE_STATE.POLL) return `Yoklama · ${this.pollMs / 1000} sn`;
    return 'Bağlantı yok';
  }
}
