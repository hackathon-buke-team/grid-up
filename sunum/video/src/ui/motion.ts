import type React from "react";
import { Easing, interpolate } from "remotion";
import { CLAMP, EASE_OUT } from "../theme";

/* Programatik (veriye bağlı) öğeler için hareket yardımcıları.
   Tek seferlik başlık/metin katmanlarında satır içi interpolate() tercih edilir;
   bunlar döngüyle üretilen çubuklar, noktalar, satırlar içindir. */

/** 0 → 1 ilerleme, EASE_OUT ile */
export const prog = (frame: number, start: number, dur = 18, easing = EASE_OUT) =>
  interpolate(frame, [start, start + dur], [0, 1], { ...CLAMP, easing });

/** Aşağıdan yukarı süzülerek belirme */
export const fadeUp = (
  frame: number,
  start: number,
  { dist = 36, dur = 20, blur = 0 }: { dist?: number; dur?: number; blur?: number } = {},
): React.CSSProperties => {
  const p = prog(frame, start, dur);
  return {
    opacity: p,
    translate: `0px ${(1 - p) * dist}px`,
    ...(blur ? { filter: `blur(${(1 - p) * blur}px)` } : {}),
  };
};

/** Yandan kayarak belirme (dx > 0: sağdan gelir) */
export const fadeSide = (frame: number, start: number, dx = -40, dur = 20): React.CSSProperties => {
  const p = prog(frame, start, dur);
  return { opacity: p, translate: `${(1 - p) * dx}px 0px` };
};

/** Yaylı büyüyerek belirme */
export const popIn = (frame: number, start: number, dur = 22): React.CSSProperties => {
  const p = interpolate(frame, [start, start + dur], [0, 1], {
    ...CLAMP,
    easing: Easing.spring({ damping: 12, stiffness: 140 }),
  });
  return { opacity: Math.min(1, p * 1.6), scale: String(0.4 + 0.6 * p) };
};

/** Bir sayıyı zamanla say (başlangıç → bitiş) */
export const countUp = (frame: number, start: number, dur: number, from: number, to: number) =>
  interpolate(frame, [start, start + dur], [from, to], { ...CLAMP, easing: EASE_OUT });

/** Nabız: 0..1 arası yumuşak salınım (periyot kare cinsinden) */
export const pulse = (frame: number, period = 45) => 0.5 - 0.5 * Math.cos((frame / period) * Math.PI * 2);
