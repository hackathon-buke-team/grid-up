import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { C, CLAMP, EASE_OUT, F } from "../theme";

export type NarrationLine = { from: number; to: number; text: React.ReactNode };

/* Alt anlatım satırı. Videoda ses yok; sahnenin "neden"ini bu satır taşır.
   Satırlar kare aralığıyla verilir, kesişmemelidir. */
export const Narration: React.FC<{ lines: NarrationLine[]; bottom?: number }> = ({ lines, bottom = 62 }) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom,
        display: "flex",
        justifyContent: "center",
        pointerEvents: "none",
      }}
    >
      {lines.map((l, i) => {
        if (frame < l.from - 2 || frame > l.to + 2) return null;
        const o = interpolate(frame, [l.from, l.from + 10, l.to - 10, l.to], [0, 1, 1, 0], CLAMP);
        const y = interpolate(frame, [l.from, l.from + 14], [14, 0], { ...CLAMP, easing: EASE_OUT });
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              bottom: 0,
              maxWidth: 1600,
              padding: "14px 34px",
              borderRadius: 16,
              background: "rgba(6,8,12,.78)",
              border: `1px solid ${C.line2}`,
              fontFamily: F.sans,
              fontSize: 36,
              fontWeight: 500,
              lineHeight: 1.3,
              color: C.ink,
              textAlign: "center",
              opacity: o,
              translate: `0px ${y}px`,
            }}
          >
            {l.text}
          </div>
        );
      })}
    </div>
  );
};
