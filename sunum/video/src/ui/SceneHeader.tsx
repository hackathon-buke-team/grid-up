import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { C, CLAMP, EASE_OUT, F, TRANSITION } from "../theme";
import { SAFE_X } from "./primitives";

/* Sahne başlığı: ince çizgi + üst etiket (kicker), kelime kelime yükselen başlık,
   ardından açıklama. Başlıkta *yıldızlı* kelimeler marka renginde vurgulanır. */
export const SceneHeader: React.FC<{
  kicker: string;
  title: string;
  lead?: React.ReactNode;
  delay?: number;
  size?: number;
  accent?: string;
  align?: "left" | "center";
}> = ({ kicker, title, lead, delay = TRANSITION - 4, size = 84, accent = C.brand, align = "left" }) => {
  const frame = useCurrentFrame();
  /* *tek* ya da *birden fazla kelime* vurgulanır */
  let inHl = false;
  const words = title.split(" ").map((w) => {
    const opens = w.startsWith("*");
    const closes = w.replace(/[.,:;!?]+$/, "").endsWith("*") && (w.length > 1 || !opens);
    const hl = inHl || opens;
    if (opens) inHl = true;
    if (closes) inHl = false;
    return { text: w.replace(/\*/g, ""), hl };
  });
  const titleEnd = delay + 8 + words.length * 2.5 + 14;

  return (
    <div
      style={{
        position: "absolute",
        left: SAFE_X,
        right: SAFE_X,
        top: 84,
        display: "flex",
        flexDirection: "column",
        alignItems: align === "center" ? "center" : "flex-start",
        textAlign: align,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <div
          style={{
            height: 3,
            borderRadius: 2,
            background: accent,
            width: interpolate(frame, [delay, delay + 16], [0, 56], { ...CLAMP, easing: EASE_OUT }),
          }}
        />
        <div
          style={{
            fontFamily: F.mono,
            fontSize: 26,
            fontWeight: 500,
            letterSpacing: "0.2em",
            color: accent,
            opacity: interpolate(frame, [delay + 4, delay + 18], [0, 1], CLAMP),
            translate: `${interpolate(frame, [delay + 4, delay + 22], [-20, 0], { ...CLAMP, easing: EASE_OUT })}px 0px`,
          }}
        >
          {kicker.toLocaleUpperCase("tr-TR")}
        </div>
      </div>
      <div
        style={{
          marginTop: 20,
          fontFamily: F.sans,
          fontWeight: 800,
          fontSize: size,
          lineHeight: 1.06,
          letterSpacing: "-0.025em",
          color: C.ink,
          maxWidth: 1680,
        }}
      >
        {words.map(({ text, hl }, i) => {
          const s = delay + 8 + i * 2.5;
          const p = interpolate(frame, [s, s + 16], [0, 1], { ...CLAMP, easing: EASE_OUT });
          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                marginRight: "0.26em",
                opacity: p,
                translate: `0px ${(1 - p) * 0.5 * size}px`,
                filter: `blur(${(1 - p) * 10}px)`,
                color: hl ? accent : undefined,
              }}
            >
              {text}
            </span>
          );
        })}
      </div>
      {lead ? (
        <div
          style={{
            marginTop: 18,
            fontFamily: F.sans,
            fontSize: 36,
            fontWeight: 400,
            lineHeight: 1.35,
            color: C.muted,
            maxWidth: 1500,
            opacity: interpolate(frame, [titleEnd - 6, titleEnd + 12], [0, 1], CLAMP),
            translate: `0px ${interpolate(frame, [titleEnd - 6, titleEnd + 14], [18, 0], { ...CLAMP, easing: EASE_OUT })}px`,
          }}
        >
          {lead}
        </div>
      ) : null}
    </div>
  );
};
