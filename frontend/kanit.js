// PANO GÖZ izleme konsolu — saf JS, framework yok.

// panogoz/rules/engine.py::THETA_THRESHOLDS ile birebir aynı olmalı.
const THETA_THRESHOLDS = { WARNING: 15.0, ALARM: 30.0, CRITICAL: 60.0 };
const SEVERITY_NAMES = ["NORMAL", "WARNING", "ALARM", "CRITICAL"];
const SEVERITY_LABELS_TR = { NORMAL: "NORMAL", WARNING: "UYARI", ALARM: "ALARM", CRITICAL: "KRİTİK" };
const PHASE_COLORS = { L1: "#5b8dee", L2: "#fbbf24", L3: "#34d399" };

const state = {
  connections: [],
  selectedIndex: null,
  series: null,
  playTimer: null,
  evidence: null,       // /api/connections/<i>/evidence -- gerçek seçili bağlantı
  cusumDemoActive: false,
  cusumDemoEvidence: null, // /api/cusum-demo/evidence -- ayrı, uzatılmış örnek
};

async function loadConnections() {
  const resp = await fetch("/api/connections");
  state.connections = await resp.json();
  renderCards();
  if (state.connections.length > 0) {
    selectConnection(state.connections[0].index);
  }
}

async function selectConnection(index) {
  state.selectedIndex = index;
  state.cusumDemoActive = false;
  stopPlayback();
  const [seriesResp, evidenceResp] = await Promise.all([
    fetch(`/api/connections/${index}/series`),
    fetch(`/api/connections/${index}/evidence`),
  ]);
  state.series = await seriesResp.json();
  state.evidence = await evidenceResp.json();
  const slider = document.getElementById("time-slider");
  slider.max = String(state.series.t_s.length - 1);
  slider.value = String(state.series.t_s.length - 1);
  renderCards();
  renderDetail();
  renderSiblings(state.evidence);
  renderCusum(state.evidence.cusum, { isDemo: false });
}

function renderCards() {
  const container = document.getElementById("connections");
  container.innerHTML = "";
  for (const conn of state.connections) {
    const card = document.createElement("div");
    card.className = "card" + (conn.index === state.selectedIndex ? " selected" : "");
    card.onclick = () => selectConnection(conn.index);
    card.innerHTML = `
      <h3>${conn.connection_id}</h3>
      <span class="card-severity sev-${conn.severity}">${conn.severity_label}</span>
      <div class="card-meta">θ=${conn.theta === null ? "—" : conn.theta.toFixed(1)} · ${conn.current_a.toFixed(0)} A · ${conn.surface_temp_c.toFixed(1)} °C</div>
    `;
    container.appendChild(card);
  }
}

function renderDetail() {
  if (!state.series) return;
  const i = Number(document.getElementById("time-slider").value);
  const severityIdx = state.series.severity[i];
  const severityName = SEVERITY_NAMES[severityIdx];
  const theta = state.series.theta[i];
  const current = state.series.current_a[i];
  const temp = state.series.surface_temp_c[i];
  const hours = state.series.t_s[i] / 3600;

  document.getElementById("detail-title").textContent = state.series.connection_id;
  const badge = document.getElementById("detail-severity");
  badge.textContent = SEVERITY_LABELS_TR[severityName];
  badge.className = "badge sev-" + severityName;

  document.getElementById("readout-theta").textContent = theta === null ? "— (düşük yük)" : theta.toFixed(1);
  document.getElementById("readout-current").textContent = current.toFixed(1) + " A";
  document.getElementById("readout-temp").textContent = temp.toFixed(1) + " °C";
  document.getElementById("readout-time").textContent = hours.toFixed(2) + " sa";

  drawChart(i);
}

function drawChart(playheadIndex) {
  const canvas = document.getElementById("chart");
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const thetas = state.series.theta.map((v) => (v === null ? 0 : v));
  const maxAbs = Math.max(80, ...thetas.map((v) => Math.abs(v)));
  const padding = { left: 40, right: 12, top: 12, bottom: 20 };
  const plotW = w - padding.left - padding.right;
  const plotH = h - padding.top - padding.bottom;
  const zeroY = padding.top + plotH / 2;
  const scaleY = (plotH / 2) / maxAbs;

  const xFor = (idx) => padding.left + (idx / (thetas.length - 1)) * plotW;
  const yFor = (theta) => zeroY - theta * scaleY;

  // eşik çizgileri
  ctx.strokeStyle = "#2a3a4d";
  ctx.setLineDash([4, 4]);
  ctx.font = "10px sans-serif";
  ctx.fillStyle = "#5c6b7a";
  for (const [label, value] of Object.entries(THETA_THRESHOLDS)) {
    for (const sign of [1, -1]) {
      const y = yFor(value * sign);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(w - padding.right, y);
      ctx.stroke();
    }
  }
  ctx.setLineDash([]);

  // sıfır çizgisi
  ctx.strokeStyle = "#3b4a5c";
  ctx.beginPath();
  ctx.moveTo(padding.left, zeroY);
  ctx.lineTo(w - padding.right, zeroY);
  ctx.stroke();

  // theta eğrisi
  ctx.strokeStyle = "#5b8dee";
  ctx.lineWidth = 2;
  ctx.beginPath();
  thetas.forEach((theta, idx) => {
    const x = xFor(idx), y = yFor(theta);
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // oynatma başlığı (playhead)
  const px = xFor(playheadIndex);
  ctx.strokeStyle = "#f87171";
  ctx.beginPath();
  ctx.moveTo(px, padding.top);
  ctx.lineTo(px, h - padding.bottom);
  ctx.stroke();

  const py = yFor(thetas[playheadIndex]);
  ctx.fillStyle = "#f87171";
  ctx.beginPath();
  ctx.arc(px, py, 4, 0, Math.PI * 2);
  ctx.fill();
}

function renderSiblings(evidence) {
  const canvas = document.getElementById("siblings-chart");
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const phases = ["L1", "L2", "L3"];
  const allTemps = phases.flatMap((p) => evidence.siblings[p].surface_temp_c);
  const minT = Math.min(...allTemps), maxT = Math.max(...allTemps);
  const padT = Math.max(2, (maxT - minT) * 0.08);
  const lo = minT - padT, hi = maxT + padT;

  const padding = { left: 44, right: 12, top: 10, bottom: 18 };
  const plotW = w - padding.left - padding.right;
  const plotH = h - padding.top - padding.bottom;
  const n = evidence.siblings.L1.surface_temp_c.length;
  const xFor = (idx) => padding.left + (idx / (n - 1)) * plotW;
  const yFor = (t) => padding.top + plotH - ((t - lo) / (hi - lo)) * plotH;

  // y ekseni etiketleri (min/max)
  ctx.fillStyle = "#5c6b7a";
  ctx.font = "10px sans-serif";
  ctx.fillText(hi.toFixed(0) + "°C", 2, padding.top + 8);
  ctx.fillText(lo.toFixed(0) + "°C", 2, padding.top + plotH);

  for (const phase of phases) {
    const temps = evidence.siblings[phase].surface_temp_c;
    const isWatched = phase === evidence.watched_phase;
    ctx.strokeStyle = PHASE_COLORS[phase];
    ctx.globalAlpha = isWatched ? 1.0 : 0.55;
    ctx.lineWidth = isWatched ? 2.2 : 1.3;
    ctx.beginPath();
    temps.forEach((t, idx) => {
      const x = xFor(idx), y = yFor(t);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }
  ctx.globalAlpha = 1.0;

  const legend = document.getElementById("siblings-legend");
  legend.innerHTML = phases
    .map((phase) => {
      const tag = phase === evidence.watched_phase ? ' <span class="watched-tag">(izlenen)</span>' : "";
      return `<span class="legend-item"><span class="swatch" style="background:${PHASE_COLORS[phase]}"></span>${phase}${tag}</span>`;
    })
    .join("");
}

function renderCusum(cusum, { isDemo }) {
  const statusEl = document.getElementById("cusum-status");
  const canvas = document.getElementById("cusum-chart");

  if (!cusum.available) {
    statusEl.textContent = (isDemo ? "[uzatılmış demo] " : "") + "CUSUM için yeterli veri yok — " + cusum.note + ".";
    statusEl.className = "note" + (isDemo ? " demo-active" : "");
    canvas.hidden = true;
    return;
  }

  const cpText = cusum.changepoint_day_index !== null
    ? `değişim noktası: gün ${cusum.changepoint_day_index}`
    : "değişim noktası tespit edilmedi (seri eşik altında kaldı)";
  statusEl.textContent = (isDemo ? "[uzatılmış demo — gerçek ölçümün tekrarı] " : "") +
    `${cusum.day_index.length} günlük taban çizgisi üzerinden CUSUM: ${cpText} (h=±${cusum.h.toFixed(2)}).`;
  statusEl.className = "note" + (isDemo ? " demo-active" : "");
  canvas.hidden = false;

  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const allVals = [...cusum.s_pos, ...cusum.s_neg, cusum.h, -cusum.h];
  const maxAbs = Math.max(1, ...allVals.map(Math.abs));
  const padding = { left: 44, right: 12, top: 10, bottom: 18 };
  const plotW = w - padding.left - padding.right;
  const plotH = h - padding.top - padding.bottom;
  const zeroY = padding.top + plotH / 2;
  const scaleY = (plotH / 2) / maxAbs;
  const n = cusum.day_index.length;
  const xFor = (idx) => padding.left + (n <= 1 ? 0 : (idx / (n - 1)) * plotW);
  const yFor = (v) => zeroY - v * scaleY;

  // karar esigi (h)
  ctx.strokeStyle = "#f87171";
  ctx.setLineDash([4, 4]);
  for (const sign of [1, -1]) {
    ctx.beginPath();
    ctx.moveTo(padding.left, yFor(cusum.h * sign));
    ctx.lineTo(w - padding.right, yFor(cusum.h * sign));
    ctx.stroke();
  }
  ctx.setLineDash([]);

  // sifir cizgisi
  ctx.strokeStyle = "#3b4a5c";
  ctx.beginPath();
  ctx.moveTo(padding.left, zeroY);
  ctx.lineTo(w - padding.right, zeroY);
  ctx.stroke();

  // S+ ve S-
  for (const [series, color] of [[cusum.s_pos, "#5b8dee"], [cusum.s_neg, "#fb923c"]]) {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    series.forEach((v, idx) => {
      const x = xFor(idx), y = yFor(v);
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  // degisim noktasi isareti
  if (cusum.changepoint_day_index !== null) {
    const cpIdx = cusum.day_index.indexOf(cusum.changepoint_day_index);
    if (cpIdx >= 0) {
      const px = xFor(cpIdx);
      ctx.strokeStyle = "#f87171";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(px, padding.top);
      ctx.lineTo(px, h - padding.bottom);
      ctx.stroke();
      ctx.fillStyle = "#f87171";
      ctx.font = "10px sans-serif";
      ctx.fillText("gün " + cusum.changepoint_day_index, px + 4, padding.top + 10);
    }
  }
}

async function toggleCusumDemo() {
  const btn = document.getElementById("cusum-demo-btn");
  state.cusumDemoActive = !state.cusumDemoActive;
  btn.classList.toggle("active", state.cusumDemoActive);

  if (!state.cusumDemoActive) {
    // gerçek seçili bağlantının CUSUM'una geri dön
    if (state.evidence) renderCusum(state.evidence.cusum, { isDemo: false });
    return;
  }
  btn.textContent = "Yükleniyor…";
  if (!state.cusumDemoEvidence) {
    const resp = await fetch("/api/cusum-demo/evidence");
    state.cusumDemoEvidence = await resp.json();
  }
  btn.textContent = "Uzatılmış demo örneği göster";
  renderCusum(state.cusumDemoEvidence.cusum, { isDemo: true });
}

function stopPlayback() {
  if (state.playTimer) {
    clearInterval(state.playTimer);
    state.playTimer = null;
    document.getElementById("play-btn").textContent = "▶ Oynat";
  }
}

function togglePlayback() {
  if (state.playTimer) {
    stopPlayback();
    return;
  }
  document.getElementById("play-btn").textContent = "⏸ Durdur";
  const slider = document.getElementById("time-slider");
  state.playTimer = setInterval(() => {
    let next = Number(slider.value) + 1;
    if (next > Number(slider.max)) {
      stopPlayback();
      return;
    }
    slider.value = String(next);
    renderDetail();
  }, 80);
}

document.getElementById("time-slider").addEventListener("input", renderDetail);
document.getElementById("play-btn").addEventListener("click", togglePlayback);
document.getElementById("cusum-demo-btn").addEventListener("click", toggleCusumDemo);

loadConnections();
