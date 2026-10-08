/* Ortak SVG yardımcıları, renk ölçekleri ve simgeler. */
const H = {
  line(pts) { return 'M' + pts.map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join('L'); },
  smooth(pts) {
    if (pts.length < 2) return '';
    let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
      const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
      d += `C${c1[0].toFixed(1)},${c1[1].toFixed(1)} ${c2[0].toFixed(1)},${c2[1].toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
    }
    return d;
  },
  sc(d0, d1, r0, r1) { const k = (r1 - r0) / (d1 - d0); return v => r0 + (v - d0) * k; },
  rng(seed) { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; },
  clamp(v, a, b) { return Math.max(a, Math.min(b, v)); },
  ease(p) { p = H.clamp(p, 0, 1); return p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2; },
  /* termal renk ölçeği (inferno yaklaşık) — yalnız ısı görselleri için */
  heat(t) {
    const S = [[0, [0, 0, 4]], [.15, [31, 12, 72]], [.3, [85, 15, 109]], [.45, [136, 34, 106]], [.6, [186, 54, 85]],
               [.72, [227, 89, 51]], [.85, [249, 142, 9]], [.95, [244, 209, 58]], [1, [252, 255, 164]]];
    t = H.clamp(t, 0, 1);
    for (let i = 1; i < S.length; i++) if (t <= S[i][0]) {
      const [a, ca] = S[i - 1], [b, cb] = S[i], k = (t - a) / (b - a);
      return `rgb(${ca.map((c, j) => Math.round(c + (cb[j] - c) * k)).join(',')})`;
    }
    return 'rgb(252,255,164)';
  },
  sev(theta) {
    if (theta >= 25) return ['Acil', 'acil'];
    if (theta >= 12) return ['Kritik', 'kritik'];
    if (theta >= 5) return ['Uyarı', 'uyari'];
    if (theta >= 2) return ['İzle', 'izle'];
    return ['Bilgi', ''];
  },
};
/* 24×24 çizgi simgeler */
const I = (d, extra = '') => `<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" ${extra}>${d}</svg>`;
const IC = {
  therm: I('<path d="M14 14.8V5a2 2 0 10-4 0v9.8a4 4 0 104 0z"/><path d="M12 9v7"/>'),
  drop: I('<path d="M12 3s6 6.4 6 11a6 6 0 01-12 0c0-4.6 6-11 6-11z"/>'),
  bolt: I('<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>'),
  wave: I('<path d="M2 12c2-6 4 6 6 0s4 6 6 0 4 6 6 0"/>'),
  flash: I('<path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/><circle cx="12" cy="12" r="3.2"/>'),
  server: I('<rect x="3" y="4" width="18" height="7" rx="1.5"/><rect x="3" y="13" width="18" height="7" rx="1.5"/><path d="M7 7.5h.01M7 16.5h.01"/>'),
  phone: I('<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>'),
  check: I('<path d="M5 12.5l4.2 4.2L19 7"/>'),
  x: I('<path d="M6 6l12 12M18 6L6 18"/>'),
  clock: I('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
  bell: I('<path d="M6 9a6 6 0 1112 0c0 5 2 6 2 6H4s2-1 2-6zM10 21h4"/>'),
  grid: I('<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>'),
  eye: I('<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'),
  cloudx: I('<path d="M7 18h10a4 4 0 00.5-8A6 6 0 006 9.5 4.3 4.3 0 007 18z"/><path d="M3 3l18 18"/>'),
  lock: I('<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/>'),
  nfc: I('<path d="M6 8.3a8 8 0 010 7.4M9.5 6.5a12 12 0 010 11M13 4.7a16 16 0 010 14.6"/>'),
  user: I('<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>'),
  wrench: I('<path d="M14.7 6.3a4 4 0 00-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 005.4-5.4l-2.6 2.6-2.4-.6-.6-2.4z"/>'),
  sun: I('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
  chip: I('<rect x="6" y="6" width="12" height="12" rx="1.5"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>'),
  battery: I('<rect x="2" y="7" width="17" height="10" rx="2"/><path d="M22 11v2M5 10v4M8 10v4"/>'),
  antenna: I('<path d="M12 12v10M8.5 8.5a5 5 0 017 0M5.6 5.6a9 9 0 0112.8 0"/><circle cx="12" cy="11" r="1.2"/>'),
  plug: I('<path d="M9 2v6M15 2v6M6 8h12v4a6 6 0 01-12 0zM12 18v4"/>'),
  camera: I('<rect x="3" y="7" width="18" height="13" rx="2"/><circle cx="12" cy="13.5" r="3.5"/><path d="M8 7l1.5-3h5L16 7"/>'),
  scan: I('<path d="M4 8V5a1 1 0 011-1h3M16 4h3a1 1 0 011 1v3M20 16v3a1 1 0 01-1 1h-3M8 20H5a1 1 0 01-1-1v-3M7 12h10"/>'),
  pin: I('<path d="M12 21s7-6.2 7-12a7 7 0 00-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/>'),
  flag: I('<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>'),
  book: I('<path d="M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2zM4 5v16"/>'),
};
