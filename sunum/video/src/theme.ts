import { Easing } from "remotion";
import { loadFont as loadArchivo } from "@remotion/google-fonts/Archivo";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";
import { loadFont as loadStix } from "@remotion/google-fonts/STIXTwoText";

/* ----------------------------------------------------------------------
   Renkler — sunum/src/deck.css ile aynı jeton seti.
   Seviye renkleri ürünün kendi merdivenidir: Bilgi · İzle · Uyarı · Kritik · Acil
   ---------------------------------------------------------------------- */
export const C = {
  bg: "#06080c",
  bg2: "#0a0e14",
  panel: "#0e131b",
  panel2: "#121a25",
  line: "#1c2632",
  line2: "#2a3746",
  ink: "#e9eef4",
  muted: "#93a0b2",
  dim: "#5f6c7e",
  brand: "#f78320",
  brand2: "#ffb066",
  brandSoft: "rgba(247,131,32,.14)",
  olcum: "#ffea46",
  bilgi: "#9dabbd",
  izle: "#4aa3ff",
  uyari: "#f4b13a",
  kritik: "#ff6b3d",
  acil: "#ff2f79",
  ok: "#35c07a",
  /* TEDAŞ kablo renkleri; L2 "siyah" koyu zeminde okunsun diye bir ton açık */
  l1: "#a3abb5",
  l2: "#6b7480",
  l3: "#b8774a",
} as const;

/* ----------------------------------------------------------------------
   Yazı tipleri
   Archivo: başlık + gövde (Türkçe karakterler latin-ext'te)
   STIX Two Text: θ ve formüller (Archivo'da Yunanca yok; yığında otomatik düşer)
   JetBrains Mono: sayılar, register'lar, kod
   ---------------------------------------------------------------------- */
const archivo = loadArchivo("normal", {
  weights: ["400", "500", "600", "700", "800", "900"],
  subsets: ["latin", "latin-ext"],
});
const stix = loadStix("normal", {
  weights: ["400", "600"],
  subsets: ["latin", "greek"],
});
loadStix("italic", { weights: ["400", "600"], subsets: ["latin", "greek"] });
const mono = loadMono("normal", {
  weights: ["400", "500", "700"],
  subsets: ["latin", "latin-ext", "greek"],
});

export const F = {
  sans: `${archivo.fontFamily}, ${stix.fontFamily}, sans-serif`,
  mono: `${mono.fontFamily}, ${stix.fontFamily}, monospace`,
  math: `${stix.fontFamily}, serif`,
};

/* ----------------------------------------------------------------------
   Hareket
   ---------------------------------------------------------------------- */
export const EASE_OUT = Easing.bezier(0.16, 1, 0.3, 1);
export const EASE_IN_OUT = Easing.bezier(0.65, 0, 0.35, 1);
export const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/* Sahne geçişi (kare). Sahne içi girişler bu süreden sonra başlamalı. */
export const TRANSITION = 20;

/* ----------------------------------------------------------------------
   Yardımcılar — sunum/src/helpers.js'in TypeScript karşılığı
   ---------------------------------------------------------------------- */
export const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));

/** Doğrusal ölçek: [d0,d1] → [r0,r1] */
export const sc = (d0: number, d1: number, r0: number, r1: number) => {
  const k = (r1 - r0) / (d1 - d0);
  return (v: number) => r0 + (v - d0) * k;
};

/** Tekrarlanabilir rastgele sayı üreteci (render'lar arasında aynı) */
export const rng = (seed: number) => {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 4294967296;
  };
};

export type Pt = [number, number];

export const linePath = (pts: Pt[]) =>
  "M" + pts.map((p) => p[0].toFixed(1) + "," + p[1].toFixed(1)).join("L");

/** Catmull-Rom → kübik Bézier, yumuşak eğri */
export const smoothPath = (pts: Pt[]) => {
  if (pts.length < 2) return "";
  let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] || p2;
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += `C${c1[0].toFixed(1)},${c1[1].toFixed(1)} ${c2[0].toFixed(1)},${c2[1].toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
  }
  return d;
};

/** Termal renk ölçeği (inferno yaklaşık) — yalnız ısı görselleri için */
export const heat = (t: number, alpha = 1) => {
  const S: [number, [number, number, number]][] = [
    [0, [0, 0, 4]],
    [0.15, [31, 12, 72]],
    [0.3, [85, 15, 109]],
    [0.45, [136, 34, 106]],
    [0.6, [186, 54, 85]],
    [0.72, [227, 89, 51]],
    [0.85, [249, 142, 9]],
    [0.95, [244, 209, 58]],
    [1, [252, 255, 164]],
  ];
  const x = clamp(t, 0, 1);
  for (let i = 1; i < S.length; i++) {
    if (x <= S[i][0]) {
      const [a, ca] = S[i - 1];
      const [b, cb] = S[i];
      const k = (x - a) / (b - a);
      return `rgba(${ca.map((c, j) => Math.round(c + (cb[j] - c) * k)).join(",")},${alpha})`;
    }
  }
  return `rgba(252,255,164,${alpha})`;
};

/** θ → seviye (ürünün merdiveni: 2 / 5 / 12 / 25 K) */
export const severity = (theta: number) => {
  if (theta >= 25) return { name: "Acil", color: C.acil };
  if (theta >= 12) return { name: "Kritik", color: C.kritik };
  if (theta >= 5) return { name: "Uyarı", color: C.uyari };
  if (theta >= 2) return { name: "İzle", color: C.izle };
  return { name: "Bilgi", color: C.bilgi };
};

/** Türkçe sayı biçimi: 17.6 → "17,6" */
export const tr = (v: number, digits = 1) =>
  v.toLocaleString("tr-TR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
