// PANO GÖZ — Saha (mobil) görünümü: tek pano, konum, aktif alarm + iş emri + onay.
"use strict";

const SEV_TR = { NORMAL: "NORMAL", WARNING: "UYARI", ALARM: "ALARM", CRITICAL: "KRİTİK" };
const STATE_TR = { open: "Onay bekliyor", acked: "Onaylandı", cleared: "Temizlendi · onay bekliyor", closed: "Kapalı" };
const CLOSE_TR = { sahada_giderildi: "Sahada giderildi", yanlis_alarm: "Yanlış alarm", planli_bakim: "Planlı bakım", bilinen_sorun_izleniyor: "Bilinen sorun, izleniyor", diger: "Diğer" };

const $ = (s, r = document) => r.querySelector(s);
function h(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) { if (c === null || c === undefined || c === false) continue; n.append(c.nodeType ? c : document.createTextNode(String(c))); }
  return n;
}
async function api(path, opts) {
  const r = await fetch(path, opts);
  let b = null; try { b = await r.json(); } catch (e) { /* */ }
  if (!r.ok) throw new Error(b && b.error ? b.error : `HTTP ${r.status}`);
  return b;
}
const post = (p, body) => api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
function fmtTime(t) {
  const d = Math.floor(t / 86400), rem = t - d * 86400;
  return `Gün ${d} · ${String(Math.floor(rem / 3600)).padStart(2, "0")}:${String(Math.floor((rem % 3600) / 60)).padStart(2, "0")}`;
}
const num = (v, d = 1) => (v === null || v === undefined ? "—" : Number(v).toFixed(d));

let panelId = new URLSearchParams(location.search).get("panel");
const open = new Set(); // açık iş emri kartları (yeniden çizimde korunur)
let lastSig = "";
let timer = null;

async function renderPanel() {
  const fleet = await api("/api/fleet");
  const sel = $("#s-panel");
  if (!sel.options.length) {
    sel.replaceChildren(...fleet.panels.map((p) => h("option", { value: p.id, text: `${p.id} · ${p.name}` })));
    sel.addEventListener("change", () => { panelId = sel.value; history.replaceState(null, "", `?panel=${panelId}`); lastSig = ""; refresh(); });
  }
  if (!panelId || !fleet.panels.some((p) => p.id === panelId)) panelId = fleet.panels[0].id;
  sel.value = panelId;
  const p = fleet.panels.find((x) => x.id === panelId);
  $("#s-name").textContent = `${p.id} · ${p.name}`;
  $("#s-loc").textContent = p.location;
  const b = $("#s-badge"); b.textContent = p.severity_label; b.className = `badge sev-${p.severity}`;
  $("#s-clock").textContent = `${fmtTime(fleet.clock.now_t_s)} · simülasyon saati${fleet.clock.running ? " (canlı)" : " (duraklatıldı)"}`;
  $("#s-read").replaceChildren(...[
    ["Akım", `${num(p.current_a, 0)} A`], ["Bağlantı", `${num(p.joint_temp_c, 1)} °C`],
    ["Ortam", `${num(p.ambient_c, 1)} °C`], ["Nem", `%${num(p.humidity_rh, 0)}`],
  ].map(([k, v]) => h("div", {}, h("div", { class: "k", text: k }), h("div", { class: "v", text: v }))));
  const flags = [];
  if (p.stale) flags.push(h("span", { class: "chip mini", text: "Veri yok (STALE)" }));
  if (p.de_energised) flags.push(h("span", { class: "chip mini", text: "Enerjisiz" }));
  if (p.revision) flags.push(h("span", { class: "chip mini", text: "Demo: enjekte edilmiş senaryo" }));
  $("#s-flags").replaceChildren(...flags);

  const qr = $("#s-qr");
  const url = `/api/fleet/panels/${panelId}/qr.svg`;
  if (qr.getAttribute("src") !== url) {
    qr.setAttribute("src", url);
    const link = await api(`/api/fleet/panels/${panelId}/link`);
    $("#s-url").textContent = link.url;
  }
}

async function renderAlarms() {
  const list = await api(`/api/fleet/alarms?panel=${panelId}&state=active&sort=priority`);
  const details = await Promise.all(list.map((a) => api(`/api/fleet/alarms/${encodeURIComponent(a.id)}`)));
  const sig = JSON.stringify(details.map((d) => [d.alarm.id, d.alarm.state, d.alarm.severity, d.messages.length]));
  if (sig === lastSig) return;
  lastSig = sig;
  const box = $("#s-alarms");
  if (!details.length) { box.replaceChildren(h("div", { class: "s-ok", text: "Bu panoda aktif alarm yok." })); return; }
  box.replaceChildren(...details.map((d) => alarmCard(d)));
}

function alarmCard(d) {
  const a = d.alarm, wo = d.work_order;
  const woBox = h("div", { class: "wo", hidden: !open.has(a.id) },
    h("div", { class: "note", text: `Ekip: ${wo.crew} · ${wo.est_duration}` }),
    h("ol", {}, ...wo.steps.map((s) => h("li", { text: s }))),
    wo.safety.length ? h("ul", { class: "safety" }, ...wo.safety.map((s) => h("li", { text: s }))) : null);
  const err = h("div", { class: "err", role: "alert" });
  const token = h("input", { inputmode: "numeric", maxlength: "4", placeholder: "0000", autocomplete: "off", "aria-label": "Onay belirteci" });
  const by = h("input", { placeholder: "Ad Soyad", autocomplete: "off", "aria-label": "Adınız" });
  const ackBtn = h("button", { class: "btn primary", type: "button", onclick: async () => {
    err.textContent = "";
    try { await post(`/api/fleet/alarms/${encodeURIComponent(a.id)}/ack`, { token: token.value, by: by.value }); lastSig = ""; await refresh(); }
    catch (e) { err.textContent = e.message; }
  } }, "Onayla");
  const canAck = a.state === "open" && a.family !== "system" && a.peak !== "WARNING" && a.peak !== "NORMAL";
  const toggle = h("button", { class: "btn", type: "button", onclick: () => {
    woBox.hidden = !woBox.hidden;
    if (woBox.hidden) open.delete(a.id); else open.add(a.id);
    toggle.textContent = woBox.hidden ? "İş emrini göster" : "İş emrini gizle";
  } }, open.has(a.id) ? "İş emrini gizle" : "İş emrini göster");
  return h("article", { class: `s-alarm b-${a.severity}` },
    h("div", { class: "s-row" }, h("span", { class: `badge sev-${a.severity}`, text: a.severity_label }),
      h("span", { class: "meta", text: STATE_TR[a.state] })),
    h("h3", { text: a.label + (a.phase ? ` · faz ${a.phase}` : "") }),
    h("div", { class: "meta", text: `${wo.title} · ${wo.priority} (${wo.due})` }),
    h("div", { class: "meta", text: `Açılış ${fmtTime(a.opened_t_s)}${a.acked_by ? ` · ${a.acked_by} üstlendi` : ""}` }),
    wo.needs_outage ? h("span", { class: "tag outage", text: "planlı kesinti gerekir" }) : null,
    h("div", { class: "actions" }, toggle),
    woBox,
    canAck ? h("div", { class: "form", style: "margin-top:10px" },
      h("label", { text: "Onay belirteci (SMS'teki 4 hane)" }, token), h("label", { text: "Adınız" }, by), ackBtn) : null,
    canAck ? err : null);
}

async function refresh() {
  try {
    await renderPanel();
    await renderAlarms();
    $("#s-fatal").hidden = true;
  } catch (e) {
    const f = $("#s-fatal"); f.hidden = false; f.textContent = "Bağlantı hatası: " + e.message;
  }
}
async function loop() { await refresh(); clearTimeout(timer); timer = setTimeout(loop, 3000); }
loop();
