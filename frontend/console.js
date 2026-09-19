// PANO GÖZ — Alarm Konsolu (saf JS, framework yok).
"use strict";

const SEV_TR = { NORMAL: "NORMAL", WARNING: "UYARI", ALARM: "ALARM", CRITICAL: "KRİTİK" };
const STATE_TR = { open: "Onay bekliyor", acked: "Onaylandı", cleared: "Temizlendi · onay bekliyor", closed: "Kapalı" };
const CLOSE_TR = {
  sahada_giderildi: "Sahada giderildi", yanlis_alarm: "Yanlış alarm", planli_bakim: "Planlı bakım",
  bilinen_sorun_izleniyor: "Bilinen sorun, izleniyor", diger: "Diğer",
};
const FAMILY_TR = { thermal: "Isıl", load: "Yük", environment: "Ortam", pd: "PD", arc: "Ark", system: "Sistem" };
const REASON_TR = {
  STALE: "Veri yok (STALE)", DE_ENERGISED: "Enerjisiz", LOW_LOAD: "Düşük yük — θ normalize edilemez", WARMUP: "Isınma / taban çizgisi öğreniliyor",
};
const KIND_TR = {
  sent: "gönderildi", failed: "BAŞARISIZ", rate_limited: "fırtına sınırı", silenced: "sessizde",
};
const MSG_KIND_TR = {
  first: "ilk bildirim", reminder: "hatırlatma", escalation: "eskalasyon", escalated_severity: "şiddet yükseldi",
  handover: "nöbet devri", ack: "onay", closed: "kapanış", digest: "özet",
};
const SEV_COLORS = { WARNING: "#fbbf24", ALARM: "#fb923c", CRITICAL: "#f87171" };
const PHASE_COLORS = { L1: "#5b8dee", L2: "#fbbf24", L3: "#34d399" };

const state = {
  tab: "alarms",
  fleet: null,
  alarms: [],
  selectedAlarm: null,
  selectedPanel: null,
  scenarios: [],
  closeReasons: [],
  timer: null,
  json: {},          // önceki JSON'lar (gereksiz yeniden çizimi önler)
  scadaPrev: {},
  demoOpen: true,
  ready: false,
};

// ------------------------------------------------------------------ yardımcılar
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => Array.from(root.querySelectorAll(s));

function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else if (k === "dataset") Object.assign(node.dataset, v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return node;
}

async function api(path, opts) {
  const resp = await fetch(path, opts);
  let body = null;
  try { body = await resp.json(); } catch (e) { /* JSON olmayan yanıt */ }
  if (!resp.ok) {
    const msg = body && body.error ? body.error : `HTTP ${resp.status}`;
    const err = new Error(msg);
    err.status = resp.status;
    throw err;
  }
  return body;
}
const post = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });

function fmtTime(t) {
  const day = Math.floor(t / 86400);
  const rem = t - day * 86400;
  const hh = String(Math.floor(rem / 3600)).padStart(2, "0");
  const mm = String(Math.floor((rem % 3600) / 60)).padStart(2, "0");
  return `Gün ${day} · ${hh}:${mm}`;
}
function fmtAge(s) {
  if (s < 90) return "az önce";
  const m = Math.round(s / 60);
  if (m < 90) return `${m} dk`;
  const hr = Math.round(m / 60);
  if (hr < 48) return `${hr} sa`;
  return `${Math.round(hr / 24)} gün`;
}
function num(v, d = 1) { return v === null || v === undefined ? "—" : Number(v).toFixed(d); }
function sevBadge(name, label) { return h("span", { class: `badge sev-${name}`, text: label || SEV_TR[name] }); }
function changed(key, value) {
  const s = JSON.stringify(value);
  if (state.json[key] === s) return false;
  state.json[key] = s;
  return true;
}

// ------------------------------------------------------------------ sekmeler
function setTab(name) {
  state.tab = name;
  $$(".tab[data-tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  $$("[role=tabpanel]").forEach((p) => { p.hidden = p.id !== `tab-${name}`; });
  refresh();
}

// ------------------------------------------------------------------ üst şerit / demo kontrol
function renderClock(fleet) {
  const c = fleet.clock;
  $("#clock-day").textContent = fmtTime(c.now_t_s) + ` / ${Math.floor(c.end_day)}`;
  const st = $("#clock-state");
  st.textContent = c.running ? `● Canlı · ${speedLabel(c.speed)}` : "❚❚ Duraklatıldı";
  st.className = "chip " + (c.running ? "live" : "paused");
  $("#play-btn").textContent = c.running ? "❚❚ Duraklat" : "▶ Başlat";
  $("#play-btn").dataset.running = c.running ? "1" : "0";
  const sel = $("#speed-select");
  if (document.activeElement !== sel) sel.value = String(c.speed);
  $("#storm-chip").hidden = !fleet.kpis.storm_active;
}
function speedLabel(s) {
  if (s >= 86400) return `${Math.round(s / 86400)} gün/sn`;
  return `${Math.round(s / 3600)} sa/sn`;
}

function renderDemoOptions(fleet) {
  if (!changed("demoOpts", fleet.panels.map((p) => p.id))) return;
  const opts = fleet.panels.map((p) => h("option", { value: p.id, text: `${p.id} · ${p.name}` }));
  for (const sel of [$("#inject-panel")]) { const v = sel.value; sel.replaceChildren(...opts.map((o) => o.cloneNode(true))); if (v) sel.value = v; }
  const fp = $("#f-panel"); const v = fp.value;
  fp.replaceChildren(h("option", { value: "", text: "Hepsi" }), ...fleet.panels.map((p) => h("option", { value: p.id, text: `${p.id} · ${p.name}` })));
  fp.value = v;
  const sp = $("#scada-panel"); const v2 = sp.value;
  sp.replaceChildren(...fleet.panels.map((p) => h("option", { value: p.id, text: `${p.id} · ${p.name}` })));
  if (v2) sp.value = v2;
}

function demoMsg(text, isErr) {
  const el = $("#demo-msg");
  el.textContent = text || "";
  el.style.color = isErr ? "var(--crit)" : "var(--muted)";
}
async function demoAction(fn, okText) {
  try { await fn(); demoMsg(okText || "Tamam"); } catch (e) { demoMsg(e.message, true); }
  await refresh(true);
}

function wireDemo() {
  $("#demo-toggle").addEventListener("click", () => {
    state.demoOpen = !state.demoOpen;
    $("#demo-bar").hidden = !state.demoOpen;
    $("#demo-toggle").setAttribute("aria-expanded", String(state.demoOpen));
  });
  $("#play-btn").addEventListener("click", () =>
    demoAction(() => post("/api/sim/clock", { running: $("#play-btn").dataset.running !== "1", speed: Number($("#speed-select").value) })));
  $("#speed-select").addEventListener("change", () => demoAction(() => post("/api/sim/clock", { speed: Number($("#speed-select").value) })));
  $("#jump-select").addEventListener("change", () => {
    const v = $("#jump-select").value;
    if (!v) return;
    demoAction(() => post("/api/sim/clock", { jump_to_day: Number(v), running: false }), `Gün ${v}'e atlandı`);
    $("#jump-select").value = "";
  });
  $("#inject-btn").addEventListener("click", () =>
    demoAction(() => post("/api/sim/inject", { panel_id: $("#inject-panel").value, scenario_key: $("#inject-scenario").value, onset_in_min: 15 }),
      "Senaryo enjekte edildi (15 dk sonra başlar)"));
  $("#clear-btn").addEventListener("click", () =>
    demoAction(() => post("/api/sim/clear", { panel_id: $("#inject-panel").value }), "Pano sağlıklı senaryoya döndü"));
  $("#storm-btn").addEventListener("click", () => demoAction(() => post("/api/sim/storm", {}), "8 panoda ortak olay başlatıldı"));
  $("#reset-btn").addEventListener("click", () => demoAction(() => post("/api/sim/reset"), "Sıfırlandı (Gün 30)"));
}

// ------------------------------------------------------------------ KPI + alarmlar
function renderKpis(k) {
  const tiles = [
    { cls: "crit", k: "KRİTİK", v: k.active_by_severity.CRITICAL, s: "aktif alarm" },
    { cls: "alarm", k: "ALARM", v: k.active_by_severity.ALARM, s: "aktif alarm" },
    { cls: "warn", k: "UYARI", v: k.active_by_severity.WARNING, s: "aktif kayıt" },
    { cls: k.awaiting_ack ? "attn" : "", k: "Onay bekleyen", v: k.awaiting_ack, s: `${k.cleared_pending} temizlendi, onay bekliyor` },
    { cls: "", k: "Sistem uyarısı", v: k.system_alerts, s: "cihaz susuyor (sevk yok)" },
    { cls: "", k: "Bildirim (son sa)", v: k.messages_last_hour, s: `${k.rate_limited_last_hour} fırtına sınırı · ${k.failed_last_hour} hata` },
    { cls: "", k: "Pano", v: `${k.panels_alarming}/${k.panels_total}`, s: "ALARM+ durumda" },
  ];
  $("#kpis").replaceChildren(...tiles.map((t) => h("div", { class: `kpi ${t.cls}` },
    h("div", { class: "k", text: t.k }), h("div", { class: "v", text: String(t.v) }), h("div", { class: "s", text: t.s }))));
  const cnt = $("#cnt-alarms");
  const hot = k.active_by_severity.CRITICAL + k.active_by_severity.ALARM;
  cnt.textContent = String(hot + k.active_by_severity.WARNING);
  cnt.className = "count " + (k.active_by_severity.CRITICAL ? "hot" : hot ? "warm" : "");
}

function alarmQuery() {
  const q = new URLSearchParams();
  const f = { state: $("#f-state").value, min_severity: $("#f-sev").value, family: $("#f-family").value, panel: $("#f-panel").value, sort: $("#f-sort").value };
  for (const [k, v] of Object.entries(f)) if (v) q.set(k, v);
  return q.toString();
}

function alarmRow(a) {
  const stateClass = a.state;
  const title = a.label + (a.phase ? ` · faz ${a.phase}` : "");
  const tags = [];
  if (a.advisory) tags.push(h("span", { class: "tag", text: "tavsiye" }));
  if (a.category === "sistem") tags.push(h("span", { class: "tag", text: "sistem" }));
  if (a.latching) tags.push(h("span", { class: "tag", text: "olay" }));
  const row = h("button", {
    class: `alarm-row b-${a.severity} ${stateClass}`, role: "listitem", type: "button",
    "aria-pressed": String(state.selectedAlarm === a.id), dataset: { id: a.id },
    onclick: () => selectAlarm(a.id),
  },
  h("div", {}, sevBadge(a.severity, a.severity_label)),
  h("div", {},
    h("div", { class: "t1", text: title }, ...tags),
    h("div", { class: "t2", text: `${a.panel_name} · ${a.panel_id} · ${a.id}` })),
  h("div", { class: "side" },
    h("div", { class: `state ${stateClass}`, text: STATE_TR[a.state] }),
    h("div", { text: `${fmtTime(a.opened_t_s)} · ${fmtAge(a.age_s)}` }),
    h("div", { text: a.notified_count ? `${a.notified_count} bildirim` : (a.category === "sistem" ? "sevk yok" : a.severity === "WARNING" ? "yalnız konsol" : "—") })));
  return row;
}

function renderAlarms(list) {
  const signature = { q: alarmQuery(), sel: state.selectedAlarm, rows: list.map((a) => [a.id, a.state, a.severity, a.notified_count, Math.floor(a.age_s / 60)]) };
  if (!changed("alarms", signature)) return;
  const box = $("#alarm-list");
  if (!list.length) { box.replaceChildren(h("div", { class: "empty", text: "Bu filtreyle alarm yok." })); return; }
  box.replaceChildren(...list.map(alarmRow));
}

async function refreshAlarms() {
  state.alarms = await api("/api/fleet/alarms?" + alarmQuery());
  renderAlarms(state.alarms);
}

async function selectAlarm(id) {
  state.selectedAlarm = id;
  $$(".alarm-row").forEach((r) => r.setAttribute("aria-pressed", String(r.dataset.id === id)));
  $("#ack-err").textContent = ""; $("#close-err").textContent = ""; $("#mute-err").textContent = "";
  $("#ack-token").value = "";
  state.json.detail = undefined;
  await refreshDetail();
  if (window.matchMedia("(max-width: 1000px)").matches) $("#detail").scrollIntoView({ behavior: "smooth", block: "start" });
}

const WO_STEP_LABEL = "Adımlar";
async function refreshDetail() {
  const id = state.selectedAlarm;
  if (!id) return;
  let d;
  try { d = await api(`/api/fleet/alarms/${encodeURIComponent(id)}`); } catch (e) { $("#detail-body").hidden = true; $("#detail-empty").hidden = false; $("#detail-empty").textContent = e.message; return; }
  $("#detail-empty").hidden = true;
  $("#detail-body").hidden = false;
  if (!changed("detail", [d.alarm.state, d.alarm.severity, d.alarm.acked_by, d.messages.length, d.evidence.t_s.length, d.alarm.closed_t_s])) return;
  const a = d.alarm;
  const badge = $("#d-badge"); badge.textContent = a.severity_label; badge.className = `badge sev-${a.severity}`;
  $("#d-title").textContent = a.label + (a.phase ? ` · faz ${a.phase}` : "");
  $("#d-sub").textContent = `${a.panel_name} · ${d.work_order.location} · ${a.id}`;
  const kv = [
    ["Durum", STATE_TR[a.state]], ["Açılış", fmtTime(a.opened_t_s)], ["Zirve", `${a.peak_label} · ${a.peak_score === null ? "—" : num(a.peak_score, 2)} ${a.unit || ""}`],
    ["Aile", FAMILY_TR[a.family] || a.family], ["Yeniden açılış", String(a.flaps)],
    ["Onaylayan", a.acked_by ? `${a.acked_by} (${fmtTime(a.acked_t_s)})` : "—"],
  ];
  if (a.closed_t_s) kv.push(["Kapanış", `${fmtTime(a.closed_t_s)} · ${CLOSE_TR[a.close_reason] || a.close_reason} · ${a.closed_by || ""}`]);
  $("#d-kv").replaceChildren(...kv.map(([k, v]) => h("div", {}, h("div", { class: "k", text: k }), h("div", { class: "v", text: v }))));

  const ev = d.evidence;
  const days = ev.t_s.map((t) => t / 86400);
  const lines = Object.entries(ev.thresholds).map(([name, y]) => ({ y, color: SEV_COLORS[name], label: SEV_TR[name] }));
  Charts.line($("#d-chart"), {
    x: days, series: [{ y: ev.score, color: "#5b8dee", label: `${a.label} (${ev.unit || "puan"})`, width: 2 }],
    lines, markers: [{ x: a.opened_t_s / 86400, color: "#f87171", label: "açıldı" }],
    yMin: 0, includeLines: false, xFormat: (v) => `Gün ${v.toFixed(1)}`, height: 190,
  });
  const reasons = Object.entries(ev.suppressed_reasons);
  const chipList = reasons.length ? reasons.map(([r, n]) => h("span", { class: "chip mini", text: `${REASON_TR[r] || r}: ${n} örnek` })) : [h("span", { class: "chip mini", text: "Bu pencerede bastırılan örnek yok" })];
  if (ev.advisory_capped_samples) chipList.push(h("span", { class: "chip mini", text: `Füzyon: ${ev.advisory_capped_samples} örnek UYARI'da tavanlandı` }));
  $("#d-reasons").replaceChildren(...chipList);
  $("#d-evidence-note").textContent = `Eşikler: ${lines.map((l) => `${l.label} ${l.y}`).join(" · ")}. Ölü bant %${Math.round(ev.deadband * 100)}, 3/5 debounce${ev.advisory ? ", tavsiye izi (ikinci kanal ailesi olmadan sevk edilmez)" : ""}. Boşluklar bastırılmış örneklerdir.`;

  const wo = d.work_order;
  $("#d-wo").replaceChildren(
    h("h3", { text: "İş emri kartı" }),
    h("div", { class: "wo-head" },
      h("span", { class: "wo-title", text: wo.title }),
      h("span", { class: `badge sev-${wo.priority === "ACİL" ? "CRITICAL" : wo.priority === "Yüksek" ? "ALARM" : "WARNING"}`, text: `${wo.priority} · ${wo.due}` }),
      wo.needs_outage ? h("span", { class: "tag outage", text: "planlı kesinti gerekir" }) : h("span", { class: "tag", text: "kesinti gerekmez" })),
    h("div", { class: "note", text: `Ekip: ${wo.crew} · Tahmini süre: ${wo.est_duration}` }),
    h("div", { class: "note", text: WO_STEP_LABEL }),
    h("ol", {}, ...wo.steps.map((s) => h("li", { text: s }))),
    wo.safety.length ? h("ul", { class: "safety" }, ...wo.safety.map((s) => h("li", { text: s }))) : null);

  const done = a.state === "closed";
  $("#d-ack-info").textContent = done ? `Bu alarm kapalı (${CLOSE_TR[a.close_reason] || a.close_reason}).`
    : a.state === "acked" ? `${a.acked_by} üstlendi. Şiddet yükselirse onay geçersiz olur ve yeniden sevk edilir.`
      : a.family === "sistem" ? "Sistem uyarısı: nöbetçi aranmaz; bakım biletidir." : a.severity === "WARNING" ? "UYARI seviyesi: yalnız konsol, mesaj gönderilmez." : "Onay için bildirim mesajındaki 4 haneli belirteç gerekir (Bildirimler sekmesindeki telefonda).";
  for (const id2 of ["#ack-btn", "#ack-token", "#ack-by"]) $(id2).disabled = done || a.state === "acked";
  $("#close-btn").disabled = done;
  $("#mute-btn").disabled = done;

  $("#d-msgs").replaceChildren(...(d.messages.length ? d.messages.map((m) => h("div", { class: "msg" },
    h("div", { class: "meta" }, h("span", { text: `${fmtTime(m.t_s)} · ${m.to} · ${MSG_KIND_TR[m.kind] || m.kind}` }), h("span", { class: `st-${m.status}`, text: KIND_TR[m.status] || m.status })),
    m.text ? h("pre", { text: m.text }) : null)) : [h("div", { class: "empty", text: "Bu alarm için bildirim gönderilmedi." })]));
}

function wireAlarmForms() {
  for (const id of ["#f-state", "#f-sev", "#f-family", "#f-panel", "#f-sort"]) $(id).addEventListener("change", () => { state.json = {}; refresh(true); });
  $("#ack-btn").addEventListener("click", async () => {
    $("#ack-err").textContent = "";
    try {
      await post(`/api/fleet/alarms/${encodeURIComponent(state.selectedAlarm)}/ack`, { token: $("#ack-token").value, by: $("#ack-by").value });
      $("#ack-token").value = "";
      state.json = {};
      await refresh(true);
    } catch (e) { $("#ack-err").textContent = e.message; }
  });
  $("#close-btn").addEventListener("click", async () => {
    $("#close-err").textContent = "";
    try {
      await post(`/api/fleet/alarms/${encodeURIComponent(state.selectedAlarm)}/close`, { reason: $("#close-reason").value, by: $("#close-by").value });
      state.json = {};
      await refresh(true);
    } catch (e) { $("#close-err").textContent = e.message; }
  });
  $("#mute-btn").addEventListener("click", async () => {
    $("#mute-err").textContent = "";
    const a = state.alarms.find((x) => x.id === state.selectedAlarm);
    if (!a) return;
    try {
      await post("/api/fleet/mute", { panel_id: a.panel_id, scope: a.kind, minutes: Number($("#mute-min").value), by: $("#mute-by").value, reason: $("#mute-reason").value });
      $("#mute-err").textContent = "";
      $("#mute-err").className = "okmsg";
      $("#mute-err").textContent = `${a.panel_id} · ${a.kind} sessize alındı.`;
    } catch (e) { $("#mute-err").className = "err"; $("#mute-err").textContent = e.message; }
  });
}

// ------------------------------------------------------------------ panolar
function flagChips(p) {
  const chips = [];
  if (p.stale) chips.push(h("span", { class: "chip mini", text: "STALE" }));
  if (p.de_energised) chips.push(h("span", { class: "chip mini", text: "ENERJİSİZ" }));
  return chips;
}
function renderPanelGrid(panels) {
  if (!changed("panelGrid", { sel: state.selectedPanel, rows: panels.map((p) => [p.id, p.severity, p.open_alarms, Math.round(p.current_a), Math.round(p.joint_temp_c), p.stale, p.de_energised, p.revision]) })) return;
  $("#panel-grid").replaceChildren(...panels.map((p) => h("button", {
    class: `pcard b-${p.severity}`, type: "button", "aria-pressed": String(state.selectedPanel === p.id), onclick: () => { state.selectedPanel = p.id; refresh(true); },
  },
  h("div", { class: "n" }, h("span", { text: `${p.id} · ${p.name.replace("Örnek ", "")}` }), sevBadge(p.severity, p.severity_label)),
  h("div", { class: "sc", text: `${p.scenario_title}${p.revision ? " (enjekte)" : ""}` }),
  h("div", { class: "m", text: `${num(p.current_a, 0)} A · ${num(p.joint_temp_c, 1)} °C · %${num(p.humidity_rh, 0)} RH` }),
  h("div", { class: "m", text: `${p.active_alarms} aktif alarm${p.open_alarms ? ` · ${p.open_alarms} onay bekliyor` : ""}` }),
  h("div", { class: "fl" }, ...flagChips(p)))));
}

async function refreshPanelDetail() {
  if (!state.selectedPanel) { $("#panel-detail").hidden = true; return; }
  const s = await api(`/api/fleet/panels/${state.selectedPanel}/series?days=14`);
  $("#panel-detail").hidden = false;
  const p = s.panel;
  $("#pd-title").textContent = `${p.id} · ${p.name}`;
  $("#pd-sub").textContent = `${p.location} · senaryo: ${p.scenario_title} · şu an ${p.severity_label}`;
  const x = s.t_s.map((t) => t / 86400);
  const xf = (v) => `Gün ${v.toFixed(1)}`;
  const charts = [
    { id: "ch-cur", title: "Akım (A)", opts: { series: ["L1", "L2", "L3"].map((ph) => ({ y: s.current_a[ph], color: PHASE_COLORS[ph], label: ph })).concat([{ y: s.neutral_current_a, color: "#c084fc", label: "N", dash: [4, 3] }]), lines: [{ y: s.rated_current_a, color: "#8b98a5", label: "anma" }] } },
    { id: "ch-temp", title: "Bağlantı sıcaklığı (°C) ve ortam", opts: { series: ["L1", "L2", "L3"].map((ph) => ({ y: s.joint_temp_c[ph], color: PHASE_COLORS[ph], label: ph })).concat([{ y: s.ambient_c, color: "#8b98a5", label: "ortam", dash: [4, 3] }]) } },
    { id: "ch-theta", title: "θ — kardeş faza göre ek ısınma (K, anma yükünde)", opts: { series: ["L1", "L2", "L3"].map((ph) => ({ y: (s.tracks[`loose_bolt:${ph}`] || {}).score || [], color: PHASE_COLORS[ph], label: ph })), lines: [{ y: 15, color: SEV_COLORS.WARNING, label: "UYARI" }, { y: 30, color: SEV_COLORS.ALARM, label: "ALARM" }, { y: 60, color: SEV_COLORS.CRITICAL, label: "KRİTİK" }], yMin: 0 } },
    { id: "ch-neutral", title: "Nötr: yüklenme (×In) ve K_N oranı", opts: { series: [{ y: (s.tracks.neutral_overload || {}).score || [], color: "#c084fc", label: "yüklenme" }, { y: (s.tracks.neutral_joint || {}).score || [], color: "#f472b6", label: "K_N oranı" }], lines: [{ y: 1.0, color: SEV_COLORS.ALARM, label: "ALARM 1.0" }], yMin: 0 } },
    { id: "ch-rh", title: "Bağıl nem (%RH)", opts: { series: [{ y: s.humidity_rh, color: "#5b8dee", label: "%RH" }], lines: [{ y: 65, color: SEV_COLORS.WARNING, label: "UYARI %65" }] } },
    { id: "ch-dew", title: "Çiy noktası marjı (K) — duvar sıcaklığı − çiy noktası", opts: { series: [{ y: s.dew_margin_c, color: "#34d399", label: "marj" }], lines: [{ y: 3, color: SEV_COLORS.WARNING, label: "UYARI 3 K" }, { y: 1.5, color: SEV_COLORS.ALARM, label: "ALARM 1.5 K" }, { y: 0, color: SEV_COLORS.CRITICAL, label: "yoğuşma" }] } },
    { id: "ch-pd", title: "Kısmi deşarj indeksi", opts: { series: [{ y: s.pd_index, color: "#fb923c", label: "PD" }], lines: [{ y: 15, color: SEV_COLORS.WARNING, label: "UYARI" }, { y: 30, color: SEV_COLORS.ALARM, label: "ALARM" }], yMin: 0 } },
  ];
  const box = $("#pd-charts");
  if (!$("#ch-cur")) {
    box.replaceChildren(...charts.map((c) => h("div", { class: "chart-card" }, h("h3", { text: c.title }), h("canvas", { id: c.id, "data-h": "170" }))));
  }
  for (const c of charts) Charts.line($("#" + c.id), { x, xFormat: xf, height: 170, ...c.opts });

  const tbl = $("#pd-tracks");
  const head = h("tr", {}, ...["İz", "Aile", "Şiddet", "Son puan", "Bastırılan (14 gün)"].map((t, i) => h("th", { class: i === 3 ? "num" : "", text: t })));
  const rows = Object.entries(s.tracks).map(([key, t]) => {
    const last = t.score[t.score.length - 1];
    const sev = ["NORMAL", "WARNING", "ALARM", "CRITICAL"][t.severity[t.severity.length - 1]];
    const counts = {};
    t.reasons.forEach((r) => { if (r && r !== "WARMUP") counts[r] = (counts[r] || 0) + 1; });
    const rs = Object.entries(counts).map(([r, n]) => `${REASON_TR[r] || r}: ${n} sa`).join(" · ");
    return h("tr", {}, h("td", { text: `${t.label}${key.includes(":") ? ` · faz ${key.split(":")[1]}` : ""}${t.advisory ? " (tavsiye)" : ""}` }),
      h("td", { text: FAMILY_TR[t.family] || t.family }), h("td", {}, sevBadge(sev)), h("td", { class: "num", text: last === null || last === undefined ? "—" : `${num(last, 2)} ${t.unit}` }), h("td", { text: rs || "—" }));
  });
  tbl.replaceChildren(head, ...rows);
  $("#pd-tau").textContent = `θ ısıl gecikme telafisi: tau = ${Math.round(s.theta_tau_s)} s (kurulum taban çizgisinden tahmin edildi).`;
}

// ------------------------------------------------------------------ bastırma
async function refreshSuppression() {
  const rows = await api("/api/fleet/suppression");
  if (!changed("sup", rows)) return;
  const head = h("tr", {}, ...["Pano", "Veri yok (STALE)", "Enerjisiz", "Düşük yük", "PD tavanlandı (füzyon)", "Sessize alma", "Aktif sessiz"].map((t, i) => h("th", { class: i >= 1 && i <= 5 ? "num" : "", text: t })));
  const body = rows.map((r) => h("tr", {},
    h("td", { text: `${r.panel_id} · ${r.name}` }),
    h("td", { class: "num", text: String(r.reasons.STALE || 0) }), h("td", { class: "num", text: String(r.reasons.DE_ENERGISED || 0) }),
    h("td", { class: "num", text: String(r.reasons.LOW_LOAD || 0) }), h("td", { class: "num", text: String(r.advisory_capped) }),
    h("td", { class: "num", text: String(r.muted_events) }), h("td", { text: r.mutes.length ? r.mutes.join(", ") : "—" })));
  $("#sup-table").replaceChildren(head, ...body);
}

// ------------------------------------------------------------------ SCADA
async function refreshScada() {
  const pid = $("#scada-panel").value || (state.fleet && state.fleet.panels[0].id);
  if (!pid) return;
  const v = await api(`/api/fleet/scada?panel=${pid}`);
  $("#scada-kv").replaceChildren(...[
    ["Pano", `${v.panel_id} (indeks ${v.panel_index})`], ["Taban adres", `${v.base_address} (0x${v.base_address.toString(16).toUpperCase()})`],
    ["Fonksiyon", "FC04 · salt okunur"], ["ICD sürümü", v.icd_version], ["Şiddet", v.severity_text], ["Bayraklar", v.flags.length ? v.flags.join(", ") : "—"],
  ].map(([k, val]) => h("div", {}, h("div", { class: "k", text: k }), h("div", { class: "v", text: val }))));
  const head = h("tr", {}, ...["Adres", "Ad", "Tip", "Ham", "Değer", "Ekranda (konsol)"].map((t) => h("th", { text: t })));
  const prev = state.scadaPrev[pid] || {};
  const rows = v.registers.map((r) => {
    const flash = prev[r.name] !== undefined && prev[r.name] !== r.raw;
    prev[r.name] = r.raw;
    const shown = r.name === "FLAGS" ? (v.flags.join(", ") || "0") : r.name.startsWith("SEV") || r.name === "SEVERITY_CODE" ? `${r.value} (${["NORMAL", "UYARI", "ALARM", "KRİTİK"][r.value] || "?"})` : `${typeof r.value === "number" && !Number.isInteger(r.value) ? r.value.toFixed(2) : r.value} ${r.unit}`;
    return h("tr", { class: flash ? "flash" : "", title: r.description },
      h("td", { class: "num mono", text: `${r.address} · ${"0x" + r.address.toString(16).toUpperCase().padStart(4, "0")}` }),
      h("td", { class: "mono", text: r.name }), h("td", { text: r.type }), h("td", { class: "num mono", text: r.hex }), h("td", { class: "num", text: shown }), h("td", { text: r.screen }));
  });
  state.scadaPrev[pid] = prev;
  $("#scada-table").replaceChildren(head, ...rows);
  $("#scada-cmd").textContent = `modpoll -m tcp -a 1 -r ${v.base_address + 1} -c ${v.block_size} -t 3 127.0.0.1 -p 5020   # modpoll 1 tabanlı adres kullanır`;
}

// ------------------------------------------------------------------ bildirimler (telefon)
async function refreshPhones() {
  const msgs = await api("/api/fleet/notifications?limit=200");
  if (!changed("phones", msgs.map((m) => [m.t_s, m.to, m.kind, m.status]))) return;
  const byPerson = new Map();
  for (const m of [...msgs].reverse()) {
    if (!byPerson.has(m.to)) byPerson.set(m.to, { role: m.role, msgs: [] });
    byPerson.get(m.to).msgs.push(m);
  }
  if (!byPerson.size) { $("#phones").replaceChildren(h("div", { class: "empty", text: "Henüz bildirim yok. Saati başlatın veya bir senaryo enjekte edin." })); return; }
  $("#phones").replaceChildren(...[...byPerson.entries()].map(([name, info]) => h("div", { class: "phone" },
    h("h3", { text: name }), h("div", { class: "role", text: `${info.role} · ${info.msgs.length} mesaj` }),
    ...info.msgs.slice(-12).map((m) => {
      const ack = /ONAY (\S+) (\d{4})/.exec(m.text || "");
      return h("div", { class: `bubble st-${m.status}` },
        h("div", { class: "meta" }, h("span", { text: `${fmtTime(m.t_s)} · ${MSG_KIND_TR[m.kind] || m.kind}` }), h("span", { text: KIND_TR[m.status] || m.status })),
        h("pre", { text: m.text }),
        ack && m.status === "sent" && ["first", "reminder", "escalation", "escalated_severity", "handover"].includes(m.kind)
          ? h("div", { class: "reply" }, h("button", { class: "btn small", type: "button", onclick: () => replyWithAck(ack[1], ack[2], name) }, "Onay için doldur")) : null);
    }))));
}
function replyWithAck(alarmId, token, person) {
  setTab("alarms");
  $("#f-state").value = "";
  selectAlarm(alarmId).then(() => {
    $("#ack-token").value = token;
    const who = /\((.+)\)/.exec(person);
    $("#ack-by").value = who ? who[1] : person;
    $("#ack-btn").focus();
  });
}

// ------------------------------------------------------------------ ana döngü
async function refresh(force) {
  if (!state.ready) return;
  try {
    const fleet = await api("/api/fleet");
    state.fleet = fleet;
    renderClock(fleet);
    renderKpis(fleet.kpis);
    renderDemoOptions(fleet);
    const sb = $("#storm-banner");
    if (fleet.kpis.storm_active) {
      const st = await api("/api/fleet/storms");
      const ep = st.episodes[st.episodes.length - 1];
      sb.hidden = false;
      sb.replaceChildren(h("b", { text: "Alarm fırtınası: " }), `${ep.count} alarm ${Math.round(st.window_s / 60)} dakika içinde (${ep.panels.length} pano). Bildirimler alıcı başına saatlik sınıra tabidir; fazlası tek özet mesajına döner.`);
    } else sb.hidden = true;

    if (state.tab === "alarms") { await refreshAlarms(); await refreshDetail(); }
    else if (state.tab === "panels") {
      if (!state.selectedPanel) {
        const worst = [...fleet.panels].sort((a, b) => ["NORMAL", "WARNING", "ALARM", "CRITICAL"].indexOf(b.severity) - ["NORMAL", "WARNING", "ALARM", "CRITICAL"].indexOf(a.severity))[0];
        state.selectedPanel = worst ? worst.id : null;
      }
      renderPanelGrid(fleet.panels);
      await refreshPanelDetail();
    } else if (state.tab === "suppression") await refreshSuppression();
    else if (state.tab === "scada") await refreshScada();
    else if (state.tab === "phones") await refreshPhones();
  } catch (e) {
    const f = $("#fatal"); f.hidden = false; f.textContent = "Bağlantı hatası: " + e.message;
    return;
  }
  $("#fatal").hidden = true;
}

function schedule() {
  clearTimeout(state.timer);
  const running = state.fleet && state.fleet.clock.running;
  state.timer = setTimeout(async () => { await refresh(); schedule(); }, running ? 1200 : 3500);
}

async function init() {
  wireDemo();
  wireAlarmForms();
  $$(".tab[data-tab]").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
  $("#scada-panel").addEventListener("change", () => { state.json = {}; refreshScada(); });
  window.addEventListener("resize", () => { state.json = {}; if (state.tab === "panels") refreshPanelDetail(); });

  const status = await api("/api/sim/status");
  if (!status.demo_controls) { $("#demo-bar").hidden = true; $("#demo-toggle").hidden = true; }
  if (!status.ready) $("#loading").hidden = false;
  try {
    const scen = await api("/api/scenarios");
    state.scenarios = scen;
    $("#inject-scenario").replaceChildren(...scen.map((s) => h("option", { value: s.key, text: `${s.title}${s.expect === "detect" ? "" : s.expect === "advisory" ? " (tavsiye)" : " (normal)"}` })));
    $("#inject-scenario").value = "loose_bolt_abrupt";
    state.closeReasons = await api("/api/fleet/close-reasons");
    $("#close-reason").replaceChildren(...state.closeReasons.map((r) => h("option", { value: r, text: CLOSE_TR[r] || r })));
    await api("/api/fleet"); // filo hazır olana kadar bekler
    $("#loading").hidden = true;
    state.ready = true;
    await refresh(true);
    schedule();
  } catch (e) {
    const f = $("#fatal"); f.hidden = false; f.textContent = "Başlatma hatası: " + e.message;
  }
}
init();
