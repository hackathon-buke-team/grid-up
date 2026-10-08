import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import type { TransitionPresentation, TransitionPresentationComponentProps } from "@remotion/transitions";
import { heat } from "../theme";

/* İmza geçişi: "termal göz" taraması. Soldan sağa ilerleyen sıcak bir kenar
   yeni sahneyi açar; eski sahne hafifçe kararır ve geri çekilir. */
type SweepProps = Record<string, never>;

const ThermalSweep: React.FC<TransitionPresentationComponentProps<SweepProps>> = ({
  children,
  presentationDirection,
  presentationProgress: p,
}) => {
  const { width } = useVideoConfig();

  if (presentationDirection === "exiting") {
    return (
      <AbsoluteFill style={{ opacity: 1 - p * 0.55, scale: String(1 - p * 0.03) }}>{children}</AbsoluteFill>
    );
  }

  const x = -120 + p * (width + 240);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ clipPath: `inset(0px ${Math.max(0, width - x)}px 0px 0px)` }}>{children}</AbsoluteFill>
      <AbsoluteFill style={{ pointerEvents: "none" }}>
        <div
          style={{
            position: "absolute",
            top: 0,
            bottom: 0,
            left: x - 260,
            width: 260,
            background: `linear-gradient(90deg, transparent, ${heat(0.62, 0.2)} 70%, ${heat(0.85, 0.4)})`,
            mixBlendMode: "screen",
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 0,
            bottom: 0,
            left: x - 3,
            width: 6,
            background: `linear-gradient(180deg, ${heat(0.75)}, ${heat(1)} 50%, ${heat(0.75)})`,
            boxShadow: `0 0 30px 8px ${heat(0.85, 0.65)}, 0 0 90px 30px ${heat(0.7, 0.33)}`,
          }}
        />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const thermalSweep = (): TransitionPresentation<SweepProps> => ({
  component: ThermalSweep,
  props: {},
});

/* Zoom geçişi: eski sahne izleyiciye doğru büyüyüp bulanıklaşarak kaybolur,
   yeni sahne hafif uzaktan yerine oturur — "telefonun içine girme" hissi. */
const ZoomThrough: React.FC<TransitionPresentationComponentProps<SweepProps>> = ({
  children,
  presentationDirection,
  presentationProgress: p,
}) => {
  if (presentationDirection === "exiting") {
    return (
      <AbsoluteFill
        style={{
          opacity: 1 - p,
          scale: String(1 + p * 0.9),
          filter: `blur(${p * 14}px)`,
        }}
      >
        {children}
      </AbsoluteFill>
    );
  }
  return (
    <AbsoluteFill style={{ opacity: Math.min(1, p * 1.4), scale: String(0.82 + p * 0.18) }}>{children}</AbsoluteFill>
  );
};

export const zoomThrough = (): TransitionPresentation<SweepProps> => ({
  component: ZoomThrough,
  props: {},
});
