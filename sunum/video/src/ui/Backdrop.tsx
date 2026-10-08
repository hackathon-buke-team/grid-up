import React, { useId, useMemo } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { noise2D } from "@remotion/noise";
import { C, rng } from "../theme";

/* Her sahnenin altındaki canlı zemin: kayan ızgara, süzülen iki ışık lekesi,
   yukarı doğru yavaşça yükselen toz parçacıkları ve kenar kararması. */
export const Backdrop: React.FC<{
  accent?: string;
  second?: string;
  grid?: boolean;
  particles?: boolean;
}> = ({ accent = C.brand, second = C.izle, grid = true, particles = true }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const t = frame / 30;

  const ax = 24 + noise2D("ax", t * 0.04, 0) * 14;
  const ay = 30 + noise2D("ay", 0, t * 0.04) * 16;
  const bx = 78 + noise2D("bx", t * 0.035, 3) * 12;
  const by = 72 + noise2D("by", 3, t * 0.035) * 14;

  const dust = useMemo(() => {
    const r = rng(42);
    return Array.from({ length: 46 }, () => ({
      x: r() * width,
      y: r() * height,
      s: 1 + r() * 2.2,
      v: 0.25 + r() * 0.6,
      o: 0.12 + r() * 0.3,
      k: r() * 100,
    }));
  }, [width, height]);

  const gid = "g" + useId().replace(/[^a-zA-Z0-9]/g, "");
  const shift = (frame * 0.35) % 64;

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(1100px 820px at ${ax}% ${ay}%, ${accent}26, transparent 70%)`,
        }}
      />
      <AbsoluteFill
        style={{
          background: `radial-gradient(1200px 900px at ${bx}% ${by}%, ${second}1a, transparent 70%)`,
        }}
      />
      {grid ? (
        <AbsoluteFill
          style={{
            maskImage: "radial-gradient(ellipse 75% 70% at 50% 45%, black 30%, transparent 100%)",
            WebkitMaskImage: "radial-gradient(ellipse 75% 70% at 50% 45%, black 30%, transparent 100%)",
          }}
        >
          <svg width={width} height={height}>
            <defs>
              <pattern
                id={gid}
                width={64}
                height={64}
                patternUnits="userSpaceOnUse"
                patternTransform={`translate(${shift} ${shift * 0.5})`}
              >
                <path d="M64 0H0V64" fill="none" stroke={C.line} strokeWidth={1} />
              </pattern>
            </defs>
            <rect width={width} height={height} fill={`url(#${gid})`} opacity={0.55} />
          </svg>
        </AbsoluteFill>
      ) : null}
      {particles ? (
        <AbsoluteFill>
          <svg width={width} height={height}>
            {dust.map((d, i) => {
              const y = (((d.y - frame * d.v) % height) + height) % height;
              const x = d.x + noise2D("dx" + i, frame * 0.004, d.k) * 30;
              return <circle key={i} cx={x} cy={y} r={d.s} fill={i % 5 === 0 ? accent : C.muted} opacity={d.o} />;
            })}
          </svg>
        </AbsoluteFill>
      ) : null}
      <AbsoluteFill
        style={{
          background: "radial-gradient(ellipse 85% 80% at 50% 50%, transparent 55%, rgba(0,0,0,.65) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};
