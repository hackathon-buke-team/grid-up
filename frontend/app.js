// PANO GÖZ izleme konsolu — saf JS, framework yok.

// panogoz/rules/engine.py::THETA_THRESHOLDS ile birebir aynı olmalı.
const THETA_THRESHOLDS = { WARNING: 15.0, ALARM: 30.0, CRITICAL: 60.0 };
const SEVERITY_NAMES = ["NORMAL", "WARNING", "ALARM", "CRITICAL"];
const SEVERITY_LABELS_TR = { NORMAL: "NORMAL", WARNING: "UYARI", ALARM: "ALARM", CRITICAL: "KRİTİK" };

const state = {
  connections: [],
  selectedIndex: null,
  series: null,
  playTimer: null,
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
  stopPlayback();
  const resp = await fetch(`/api/connections/${index}/series`);
  state.series = await resp.json();
  const slider = document.getElementById("time-slider");
  slider.max = String(state.series.t_s.length - 1);
  slider.value = String(state.series.t_s.length - 1);
  renderCards();
  renderDetail();
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

loadConnections();
