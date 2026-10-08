import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { C, CLAMP, F } from "../theme";
import { SCENES, STARTS, TOTAL } from "../timeline";
import { Mark } from "./primitives";

/* Ana videonun sabit çerçevesi: sağ üstte marka + bölüm adı, altta ilerleme çubuğu.
   Kapak ve kapanışta gizlenir. */
export const Chrome: React.FC = () => {
  const frame = useCurrentFrame();

  let idx = 0;
  for (let i = 0; i < STARTS.length; i++) if (frame >= STARTS[i]) idx = i;
  const scene = SCENES[idx];

  const firstEnd = STARTS[1] + 10;
  const lastStart = STARTS[STARTS.length - 1];
  const visible = interpolate(frame, [firstEnd, firstEnd + 20, lastStart, lastStart + 20], [0, 1, 1, 0], CLAMP);

  const sectionStart = STARTS[SCENES.findIndex((s) => s.section === scene.section)];
  const labelIn = interpolate(frame, [sectionStart + 8, sectionStart + 26], [0, 1], CLAMP);

  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity: visible }}>
      <div
        style={{
          position: "absolute",
          top: 78,
          right: 120,
          display: "flex",
          alignItems: "center",
          gap: 16,
        }}
      >
        <div
          style={{
            fontFamily: F.mono,
            fontSize: 22,
            letterSpacing: "0.16em",
            color: C.dim,
            opacity: labelIn,
          }}
        >
          {scene.section.toLocaleUpperCase("tr-TR")}
        </div>
        <div style={{ width: 1, height: 26, background: C.line2 }} />
        <Mark size={38} />
        <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 24, letterSpacing: "0.04em", color: C.ink }}>
          PANO GÖZ
        </div>
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 6, background: C.line }}>
        <div
          style={{
            height: "100%",
            width: `${(frame / TOTAL) * 100}%`,
            background: `linear-gradient(90deg, ${C.brand}, ${C.olcum})`,
            boxShadow: `0 0 16px ${C.brand}`,
          }}
        />
        {STARTS.slice(1).map((s, i) =>
          SCENES[i + 1].section !== SCENES[i].section ? (
            <div
              key={i}
              style={{
                position: "absolute",
                top: 0,
                bottom: 0,
                left: `${(s / TOTAL) * 100}%`,
                width: 3,
                background: C.bg,
              }}
            />
          ) : null,
        )}
      </div>
    </AbsoluteFill>
  );
};
