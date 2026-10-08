import React from "react";
import { evolvePath } from "@remotion/paths";
import { C, F } from "../theme";

/* ----------------------------------------------------------------------
   Yerleşim sabitleri (1920×1080). Güvenli alan: yanlarda 120 px.
   Başlık bloğu üstte ~84–300 px; içerik ~320–900 px; altyazı ~930–1000 px.
   ---------------------------------------------------------------------- */
export const SAFE_X = 120;
export const CONTENT_TOP = 330;
export const CONTENT_BOTTOM = 900;

/** Matematik θ — STIX italik */
export const Theta: React.FC<{ sub?: string; style?: React.CSSProperties }> = ({ sub, style }) => (
  <span style={{ fontFamily: F.math, fontStyle: "italic", fontWeight: 600, ...style }}>
    θ{sub ? <sub style={{ fontSize: "0.55em" }}>{sub}</sub> : null}
  </span>
);

/** Vurgulu kelime */
export const Em: React.FC<{ color?: string; children: React.ReactNode }> = ({ color = C.brand2, children }) => (
  <span style={{ color, fontWeight: 700 }}>{children}</span>
);

export const Mono: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <span style={{ fontFamily: F.mono, ...style }}>{children}</span>
);

/** Kart: koyu panel, ince kenar, hafif üst ışık */
export const Card: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
  glow?: string;
}> = ({ children, style, glow }) => (
  <div
    style={{
      background: `linear-gradient(180deg, ${C.panel2} 0%, ${C.panel} 100%)`,
      border: `1.5px solid ${glow ? glow + "88" : C.line2}`,
      borderRadius: 22,
      boxShadow: glow
        ? `0 0 0 1px ${glow}22, 0 24px 60px -20px ${glow}55, inset 0 1px 0 rgba(255,255,255,.05)`
        : "0 24px 60px -24px rgba(0,0,0,.8), inset 0 1px 0 rgba(255,255,255,.04)",
      padding: 32,
      ...style,
    }}
  >
    {children}
  </div>
);

/** Hap etiket */
export const Chip: React.FC<{
  children: React.ReactNode;
  color?: string;
  solid?: boolean;
  style?: React.CSSProperties;
}> = ({ children, color = C.muted, solid, style }) => (
  <span
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      padding: "8px 20px",
      borderRadius: 999,
      fontFamily: F.sans,
      fontWeight: 700,
      fontSize: 26,
      letterSpacing: "0.01em",
      color: solid ? C.bg : color,
      background: solid ? color : color + "1c",
      border: `1.5px solid ${color}${solid ? "" : "66"}`,
      whiteSpace: "nowrap",
      ...style,
    }}
  >
    {children}
  </span>
);

/** Seviye rozeti: Bilgi · İzle · Uyarı · Kritik · Acil */
export const Level: React.FC<{ name: string; color: string; size?: number }> = ({ name, color, size = 26 }) => (
  <span
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      padding: `${size * 0.25}px ${size * 0.7}px`,
      borderRadius: 10,
      fontFamily: F.sans,
      fontWeight: 800,
      fontSize: size,
      color,
      background: color + "1f",
      border: `2px solid ${color}`,
      letterSpacing: "0.06em",
    }}
  >
    <span style={{ width: size * 0.42, height: size * 0.42, borderRadius: 99, background: color }} />
    {name.toLocaleUpperCase("tr-TR")}
  </span>
);

/** SVG yolunu çizerek göster (progress 0..1) */
export const DrawPath: React.FC<
  { d: string; progress: number } & Omit<React.SVGProps<SVGPathElement>, "d">
> = ({ d, progress, ...rest }) => {
  const p = Math.max(0.0001, Math.min(1, progress));
  const { strokeDasharray, strokeDashoffset } = evolvePath(p, d);
  return (
    <path
      d={d}
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeDasharray={strokeDasharray}
      strokeDashoffset={strokeDashoffset}
      {...rest}
    />
  );
};

/** PANO GÖZ işareti: mavi halka + sarı göz bebeği (destenin favicon'u) */
export const Mark: React.FC<{ size?: number; glow?: number }> = ({ size = 40, glow = 0 }) => (
  <svg width={size} height={size} viewBox="0 0 32 32" style={{ overflow: "visible" }}>
    <rect width="32" height="32" rx="7" fill={C.panel} stroke={C.line2} />
    <circle cx="16" cy="16" r="7" fill="none" stroke={C.izle} strokeWidth="2.5" />
    <circle cx="16" cy="16" r={2.5 + glow * 1.2} fill={C.olcum} />
    {glow ? <circle cx="16" cy="16" r={4 + glow * 6} fill={C.olcum} opacity={0.18 * glow} /> : null}
  </svg>
);

/* ----------------------------------------------------------------------
   24×24 çizgi simgeler (sunum/src/helpers.js IC setinden)
   ---------------------------------------------------------------------- */
const ICONS = {
  therm: '<path d="M14 14.8V5a2 2 0 10-4 0v9.8a4 4 0 104 0z"/><path d="M12 9v7"/>',
  drop: '<path d="M12 3s6 6.4 6 11a6 6 0 01-12 0c0-4.6 6-11 6-11z"/>',
  bolt: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  wave: '<path d="M2 12c2-6 4 6 6 0s4 6 6 0 4 6 6 0"/>',
  flash:
    '<path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/><circle cx="12" cy="12" r="3.2"/>',
  server:
    '<rect x="3" y="4" width="18" height="7" rx="1.5"/><rect x="3" y="13" width="18" height="7" rx="1.5"/><path d="M7 7.5h.01M7 16.5h.01"/>',
  phone: '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
  check: '<path d="M5 12.5l4.2 4.2L19 7"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  bell: '<path d="M6 9a6 6 0 1112 0c0 5 2 6 2 6H4s2-1 2-6zM10 21h4"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  cloudx: '<path d="M7 18h10a4 4 0 00.5-8A6 6 0 006 9.5 4.3 4.3 0 007 18z"/><path d="M3 3l18 18"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/>',
  nfc: '<path d="M6 8.3a8 8 0 010 7.4M9.5 6.5a12 12 0 010 11M13 4.7a16 16 0 010 14.6"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
  wrench:
    '<path d="M14.7 6.3a4 4 0 00-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 005.4-5.4l-2.6 2.6-2.4-.6-.6-2.4z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  chip: '<rect x="6" y="6" width="12" height="12" rx="1.5"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
  battery: '<rect x="2" y="7" width="17" height="10" rx="2"/><path d="M22 11v2M5 10v4M8 10v4"/>',
  antenna: '<path d="M12 12v10M8.5 8.5a5 5 0 017 0M5.6 5.6a9 9 0 0112.8 0"/><circle cx="12" cy="11" r="1.2"/>',
  plug: '<path d="M9 2v6M15 2v6M6 8h12v4a6 6 0 01-12 0zM12 18v4"/>',
  camera:
    '<rect x="3" y="7" width="18" height="13" rx="2"/><circle cx="12" cy="13.5" r="3.5"/><path d="M8 7l1.5-3h5L16 7"/>',
  scan: '<path d="M4 8V5a1 1 0 011-1h3M16 4h3a1 1 0 011 1v3M20 16v3a1 1 0 01-1 1h-3M8 20H5a1 1 0 01-1-1v-3M7 12h10"/>',
  pin: '<path d="M12 21s7-6.2 7-12a7 7 0 00-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/>',
  flag: '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
  book: '<path d="M4 5a2 2 0 012-2h13v16H6a2 2 0 00-2 2zM4 5v16"/>',
  shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
  wifi: '<path d="M2 9a15 15 0 0120 0M5 12.5a10 10 0 0114 0M8.5 16a5 5 0 017 0"/><circle cx="12" cy="19.5" r="1"/>',
  chart: '<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 6-7"/>',
} as const;

export type IconName = keyof typeof ICONS;

export const Icon: React.FC<{
  name: IconName;
  size?: number;
  color?: string;
  stroke?: number;
  style?: React.CSSProperties;
}> = ({ name, size = 36, color = "currentColor", stroke = 1.8, style }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth={stroke}
    strokeLinecap="round"
    strokeLinejoin="round"
    style={{ flexShrink: 0, ...style }}
    dangerouslySetInnerHTML={{ __html: ICONS[name] }}
  />
);
