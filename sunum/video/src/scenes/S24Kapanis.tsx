import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { SceneHeader } from "../ui/SceneHeader";
import { Icon, Mark, Theta } from "../ui/primitives";
import { prog, pulse } from "../ui/motion";
import { C, CLAMP, EASE_IN_OUT, EASE_OUT, F } from "../theme";

/* 24 · KAPANIŞ
   Üç şey (θ · bastırma · dürüstlük) → son cümle → bitiş kartı → siyaha geçiş.
   Ana videonun çerçevesi (marka + ilerleme) bu sahnede gizlidir. */

const POINTS_OUT = 196;
const LINE_IN = 206;
const LINE_OUT = 282;
const END_IN = 292;

const POINTS: { n: string; label: React.ReactNode; text: string; glyph: React.ReactNode; color: string }[] = [
  {
    n: "01",
    label: (
      <>
        <Theta style={{ color: C.olcum }} /> · kardeşine göre fark
      </>
    ),
    text: "Yükten ve mevsimden bağımsız; montaj gününden çalışır. Haftalar önce, tarihiyle ve kalan süresiyle haber verir.",
    glyph: <span style={{ fontFamily: F.math, fontStyle: "italic", fontWeight: 600, fontSize: 84, color: C.olcum, lineHeight: 1 }}>θ</span>,
    color: C.olcum,
  },
  {
    n: "02",
    label: "Bastırma",
    text: "Yüz panoyu yönetilebilir kılan: ürettiğimiz değil, üretmediğimiz alarmların gerekçeli listesi.",
    glyph: (
      <div style={{ position: "relative", width: 64, height: 64 }}>
        <Icon name="bell" size={64} color={C.izle} stroke={1.8} />
        <svg width={64} height={64} viewBox="0 0 24 24" style={{ position: "absolute", left: 0, top: 0 }}>
          <path d="M3 3l18 18" stroke={C.izle} strokeWidth={2} strokeLinecap="round" />
        </svg>
      </div>
    ),
    color: C.izle,
  },
  {
    n: "03",
    label: "Dürüstlük",
    text: "Kör olduğumuz yeri, gecikmenin bir aralık olduğunu ve verinin neyi ölçemediğini ekranda söyleriz.",
    glyph: <Icon name="eye" size={66} color={C.ok} stroke={1.8} />,
    color: C.ok,
  },
];

const LINE1 = "Soru kaç pano alacağınız değil,";
const LINE2 = "hangi panolara koyacağınız.";

const Words: React.FC<{ text: string; frame: number; start: number; color: string }> = ({ text, frame, start, color }) => (
  <div style={{ color }}>
    {text.split(" ").map((w, i) => {
      const s = start + i * 3;
      const p = interpolate(frame, [s, s + 18], [0, 1], { ...CLAMP, easing: EASE_OUT });
      return (
        <span
          key={i}
          style={{
            display: "inline-block",
            marginRight: "0.26em",
            opacity: p,
            translate: `0px ${(1 - p) * 50}px`,
            filter: `blur(${(1 - p) * 10}px)`,
          }}
        >
          {w}
        </span>
      );
    })}
  </div>
);

export const S24Kapanis: React.FC = () => {
  const frame = useCurrentFrame();

  const pointsOut = interpolate(frame, [POINTS_OUT, POINTS_OUT + 16], [1, 0], { ...CLAMP, easing: EASE_IN_OUT });
  const lineOut = interpolate(frame, [LINE_OUT, LINE_OUT + 14], [1, 0], { ...CLAMP, easing: EASE_IN_OUT });
  const end = prog(frame, END_IN, 24);
  const glow = pulse(frame - END_IN, 50);

  return (
    <AbsoluteFill>
      <Backdrop accent={C.brand} second={C.olcum} />

      {/* 1. evre: üç şey */}
      <div style={{ position: "absolute", inset: 0, opacity: pointsOut, translate: `0px ${(1 - pointsOut) * -40}px` }}>
        <SceneHeader kicker="Kapanış" title="Kapatırken *üç* şey." />
        {POINTS.map((p, i) => {
          const s = 44 + i * 42;
          const a = prog(frame, s, 22);
          const box = interpolate(frame, [s, s + 22], [0, 1], {
            ...CLAMP,
            easing: Easing.spring({ damping: 12, stiffness: 140 }),
          });
          const active = interpolate(frame, [s, s + 12, s + 42, s + 54], [0, 1, 1, 0.35], CLAMP);
          return (
            <div
              key={p.n}
              style={{
                position: "absolute",
                left: 120,
                top: 296 + i * 186,
                display: "flex",
                alignItems: "center",
                gap: 40,
                opacity: a,
                translate: `${(1 - a) * -60}px 0px`,
                filter: `blur(${(1 - a) * 8}px)`,
              }}
            >
              <div
                style={{
                  width: 136,
                  height: 136,
                  borderRadius: 30,
                  flexShrink: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: `linear-gradient(180deg, ${C.panel2}, ${C.panel})`,
                  border: `2px solid ${p.color}`,
                  boxShadow: `0 0 ${20 + 40 * active}px -6px ${p.color}`,
                  scale: String(0.5 + 0.5 * box),
                }}
              >
                {p.glyph}
              </div>
              <div style={{ maxWidth: 1360 }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 18 }}>
                  <span style={{ fontFamily: F.mono, fontSize: 26, color: p.color }}>{p.n}</span>
                  <span
                    style={{
                      fontFamily: F.sans,
                      fontSize: 56,
                      fontWeight: 800,
                      color: C.ink,
                      letterSpacing: "-0.02em",
                    }}
                  >
                    {p.label}
                  </span>
                </div>
                <div style={{ fontFamily: F.sans, fontSize: 34, lineHeight: 1.3, color: C.muted, marginTop: 6 }}>{p.text}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 2. evre: son cümle */}
      {frame >= LINE_IN - 2 && frame <= LINE_OUT + 16 ? (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            opacity: lineOut,
            scale: String(1 - (1 - lineOut) * 0.06),
            filter: `blur(${(1 - lineOut) * 8}px)`,
          }}
        >
          <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 92, lineHeight: 1.12, letterSpacing: "-0.03em" }}>
            <Words text={LINE1} frame={frame} start={LINE_IN} color={C.ink} />
            <Words text={LINE2} frame={frame} start={LINE_IN + 14} color={C.brand} />
          </div>
          <div
            style={{
              marginTop: 46,
              display: "flex",
              alignItems: "center",
              gap: 22,
              padding: "16px 34px",
              borderRadius: 999,
              border: `2px solid ${C.ok}`,
              background: C.ok + "18",
              boxShadow: `0 0 50px -12px ${C.ok}`,
              opacity: prog(frame, LINE_IN + 26, 14),
              scale: String(
                interpolate(frame, [LINE_IN + 26, LINE_IN + 44], [0.7, 1], {
                  ...CLAMP,
                  easing: Easing.spring({ damping: 11, stiffness: 150 }),
                }),
              ),
            }}
          >
            <span style={{ fontFamily: F.sans, fontSize: 36, color: C.ink }}>
              Aynı 100 modül, filonun en kötü %10'una
            </span>
            <span style={{ fontFamily: F.mono, fontSize: 36, color: C.dim }}>→</span>
            <span style={{ fontFamily: F.mono, fontSize: 44, fontWeight: 700, color: C.ok }}>2,2 yılda</span>
            <span style={{ fontFamily: F.sans, fontSize: 36, color: C.ink }}>geri öder</span>
          </div>
        </div>
      ) : null}

      {/* 3. evre: bitiş kartı */}
      {frame >= END_IN - 2 ? (
        <AbsoluteFill style={{ opacity: end }}>
          <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
            {[0, 1, 2].map((k) => {
              const t = (((frame - END_IN) / 75 + k / 3) % 1 + 1) % 1;
              return (
                <circle
                  key={k}
                  cx={960}
                  cy={238}
                  r={80 + t * 420}
                  fill="none"
                  stroke={k === 1 ? C.olcum : C.izle}
                  strokeWidth={2}
                  opacity={(1 - t) * 0.35}
                />
              );
            })}
          </svg>
          <div
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              top: 168,
              display: "flex",
              justifyContent: "center",
              scale: String(
                interpolate(frame, [END_IN, END_IN + 26], [0.4, 1], {
                  ...CLAMP,
                  easing: Easing.spring({ damping: 11, stiffness: 130 }),
                }),
              ),
            }}
          >
            <Mark size={140} glow={0.4 + 0.6 * glow} />
          </div>
          <div
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              top: 336,
              textAlign: "center",
              fontFamily: F.sans,
              fontWeight: 900,
              fontSize: 176,
              letterSpacing: "-0.035em",
              lineHeight: 0.95,
              color: C.ink,
              whiteSpace: "nowrap",
            }}
          >
            {"PANO GÖZ".split("").map((ch, i) => {
              const s = END_IN + 8 + i * 3;
              const p = interpolate(frame, [s, s + 22], [0, 1], { ...CLAMP, easing: EASE_OUT });
              return (
                <span
                  key={i}
                  style={{
                    display: "inline-block",
                    width: ch === " " ? "0.28em" : undefined,
                    opacity: p,
                    translate: `0px ${(1 - p) * 80}px`,
                    filter: `blur(${(1 - p) * 14}px)`,
                    color: i >= 5 ? C.brand : undefined,
                  }}
                >
                  {ch}
                </span>
              );
            })}
          </div>
          <div
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              top: 548,
              textAlign: "center",
              fontFamily: F.sans,
              fontSize: 54,
              fontWeight: 700,
              color: C.ink,
              opacity: prog(frame, END_IN + 36, 18),
              translate: `0px ${(1 - prog(frame, END_IN + 36, 22)) * 24}px`,
            }}
          >
            Teşekkürler <span style={{ color: C.dim }}>·</span>{" "}
            <span style={{ color: C.brand2 }}>Sorularınızı bekliyoruz</span>
          </div>
          <div
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              top: 636,
              textAlign: "center",
              fontFamily: F.mono,
              fontSize: 28,
              letterSpacing: "0.16em",
              color: C.muted,
              opacity: prog(frame, END_IN + 48, 18),
            }}
          >
            TAKIM BÜKE · GRID UP HACKATHON · FİNAL
          </div>
          <div
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              top: 736,
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              gap: 46,
              opacity: prog(frame, END_IN + 58, 20),
              translate: `0px ${(1 - prog(frame, END_IN + 58, 24)) * 20}px`,
            }}
          >
            <Img src={staticFile("logo-adm-dark.png")} style={{ height: 62 }} />
            <div style={{ width: 2, height: 64, background: C.line2 }} />
            <Img src={staticFile("logo-gdz-dark.png")} style={{ height: 62 }} />
            <div style={{ width: 2, height: 64, background: C.line2 }} />
            <Img src={staticFile("logo-gridup-dark.png")} style={{ height: 110 }} />
          </div>
        </AbsoluteFill>
      ) : null}

      {/* siyaha geçiş */}
      <AbsoluteFill
        style={{
          backgroundColor: "#000",
          pointerEvents: "none",
          opacity: interpolate(frame, [398, 419], [0, 1], { ...CLAMP, easing: EASE_IN_OUT }),
        }}
      />
    </AbsoluteFill>
  );
};
