// PANO GÖZ — bağımlılıksız canvas grafik yardımcıları (framework yok).
// Kullanım: Charts.line(canvas, { x:[...], series:[{y:[...], color, label, width, dash}],
//   lines:[{y, color, label, dash}], yMin, yMax, xFormat(v), yFormat(v), height })
(function () {
  function palette() {
    const cs = getComputedStyle(document.documentElement);
    const get = (n, d) => (cs.getPropertyValue(n).trim() || d);
    return {
      grid: get("--grid", "#22303f"),
      axis: get("--muted", "#8b98a5"),
      bg: get("--chart-bg", "#0c121a"),
      text: get("--text", "#e6edf3"),
    };
  }

  function fit(canvas, height) {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const w = Math.max(160, Math.round(rect.width || canvas.parentElement.clientWidth || 300));
    const h = Math.round(height || Number(canvas.dataset.h) || 180);
    canvas.style.height = h + "px";
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx, w, h };
  }

  function niceRange(lo, hi) {
    if (!isFinite(lo) || !isFinite(hi)) return [0, 1];
    if (lo === hi) { lo -= 1; hi += 1; }
    const pad = (hi - lo) * 0.08;
    return [lo - pad, hi + pad];
  }

  function line(canvas, opts) {
    const P = palette();
    const { ctx, w, h } = fit(canvas, opts.height);
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = P.bg;
    ctx.fillRect(0, 0, w, h);

    const x = opts.x || [];
    const series = (opts.series || []).filter((s) => s.y && s.y.length);
    const lines = opts.lines || [];
    const pad = { l: 46, r: 10, t: 14, b: 22 };
    const pw = w - pad.l - pad.r;
    const ph = h - pad.t - pad.b;
    if (x.length < 2 || !series.length) {
      ctx.fillStyle = P.axis;
      ctx.font = "12px sans-serif";
      ctx.fillText("veri yok", pad.l, h / 2);
      return;
    }

    let lo = opts.yMin, hi = opts.yMax;
    if (lo === undefined || hi === undefined) {
      const vals = [];
      for (const s of series) for (const v of s.y) if (v !== null && v !== undefined && isFinite(v)) vals.push(v);
      for (const l of lines) if (opts.includeLines !== false) vals.push(l.y);
      const [a, b] = niceRange(Math.min(...vals), Math.max(...vals));
      if (lo === undefined) lo = a;
      if (hi === undefined) hi = b;
    }
    const x0 = x[0], x1 = x[x.length - 1];
    const xs = (v) => pad.l + ((v - x0) / (x1 - x0 || 1)) * pw;
    const ys = (v) => pad.t + ph - ((v - lo) / (hi - lo || 1)) * ph;
    const yFmt = opts.yFormat || ((v) => (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1)));
    const xFmt = opts.xFormat || ((v) => v.toFixed(1));

    ctx.font = "10px sans-serif";
    ctx.textBaseline = "middle";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 3; i++) {
      const v = lo + ((hi - lo) * i) / 3;
      const yy = ys(v);
      ctx.strokeStyle = P.grid;
      ctx.beginPath(); ctx.moveTo(pad.l, yy); ctx.lineTo(w - pad.r, yy); ctx.stroke();
      ctx.fillStyle = P.axis;
      ctx.textAlign = "right";
      ctx.fillText(yFmt(v), pad.l - 5, yy);
    }
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (let i = 0; i <= 3; i++) {
      const v = x0 + ((x1 - x0) * i) / 3;
      ctx.fillStyle = P.axis;
      ctx.fillText(xFmt(v), Math.min(w - 24, Math.max(pad.l + 10, xs(v))), h - pad.b + 5);
    }

    for (const l of lines) {
      if (l.y < lo || l.y > hi) continue;
      ctx.strokeStyle = l.color || P.axis;
      ctx.setLineDash(l.dash || [5, 4]);
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(pad.l, ys(l.y)); ctx.lineTo(w - pad.r, ys(l.y)); ctx.stroke();
      ctx.setLineDash([]);
      if (l.label) {
        ctx.fillStyle = l.color || P.axis;
        ctx.textAlign = "right";
        ctx.textBaseline = "bottom";
        ctx.fillText(l.label, w - pad.r - 2, ys(l.y) - 1);
      }
    }

    for (const m of opts.markers || []) {
      if (m.x < x0 || m.x > x1) continue;
      ctx.strokeStyle = m.color || "#f87171";
      ctx.setLineDash([2, 3]);
      ctx.beginPath(); ctx.moveTo(xs(m.x), pad.t); ctx.lineTo(xs(m.x), h - pad.b); ctx.stroke();
      ctx.setLineDash([]);
      if (m.label) {
        ctx.fillStyle = m.color || "#f87171";
        ctx.textAlign = "left";
        ctx.textBaseline = "top";
        ctx.fillText(m.label, xs(m.x) + 3, pad.t + 1);
      }
    }

    for (const s of series) {
      ctx.strokeStyle = s.color;
      ctx.lineWidth = s.width || 1.6;
      ctx.globalAlpha = s.alpha === undefined ? 1 : s.alpha;
      ctx.setLineDash(s.dash || []);
      ctx.beginPath();
      let pen = false;
      for (let i = 0; i < s.y.length; i++) {
        const v = s.y[i];
        if (v === null || v === undefined || !isFinite(v)) { pen = false; continue; }
        const px = xs(x[i]), py = ys(Math.max(lo, Math.min(hi, v)));
        if (!pen) { ctx.moveTo(px, py); pen = true; } else ctx.lineTo(px, py);
      }
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    }

    // efsane (üst sol, satır içi)
    let lx = pad.l + 6;
    ctx.font = "10px sans-serif";
    ctx.textBaseline = "top";
    ctx.textAlign = "left";
    for (const s of series) {
      if (!s.label) continue;
      ctx.fillStyle = s.color;
      ctx.fillRect(lx, pad.t + 3, 9, 9);
      ctx.fillStyle = P.text;
      ctx.fillText(s.label, lx + 13, pad.t + 3);
      lx += ctx.measureText(s.label).width + 26;
    }
  }

  window.Charts = { line };
})();
