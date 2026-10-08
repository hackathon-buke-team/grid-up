import React from "react";
import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Em, Theta } from "../ui/primitives";
import { fadeSide, fadeUp, prog, pulse } from "../ui/motion";
import { C, CLAMP, EASE_IN_OUT, EASE_OUT, F } from "../theme";

/* 17 · DEMO: İZLEME EKRANLARI
   Gerçek arayüzün altı ekranı bir tarayıcı çerçevesinde döner. Her ekranda kamera
   önemli bölgeye yavaşça yaklaşır (Ken Burns); sağdaki liste etkin ekranı izler. */

type Shot = {
  file: string;
  route: string;
  title: string;
  desc: string;
  /** kamera: [merkez x, merkez y, yakınlık] görüntü koordinatlarında (1440×900) */
  a: [number, number, number];
  b: [number, number, number];
  /** vurgulanan bölge [x0, y0, x1, y1] görüntü koordinatlarında */
  hl?: [number, number, number, number];
};

const SHOTS: Shot[] = [
  {
    file: "ekran-filo.webp",
    route: "#/filo",
    title: "Filo",
    desc: "Harita · seviye · Δ7 gün · eşiğe kalan gün",
    a: [720, 450, 1],
    b: [1060, 360, 1.5],
    hl: [770, 206, 1416, 600],
  },
  {
    file: "ekran-ikiz.webp",
    route: "#/pano/SOKE-14",
    title: "Dijital ikiz",
    desc: "9 cihaz · 74 bağlantı · 40'ı ölçülüyor",
    a: [720, 450, 1],
    b: [575, 470, 1.45],
    hl: [288, 520, 740, 566],
  },
  {
    file: "ekran-kanit.webp",
    route: "#/kanit/SOKE-14/C07-L2-PABUC",
    title: "Kanıt",
    desc: "θ, CUSUM, değişim noktası · tek eksen",
    a: [720, 450, 1],
    b: [600, 610, 1.55],
    hl: [140, 528, 1064, 708],
  },
  {
    file: "ekran-bastir.webp",
    route: "#/alarm/bastirilan",
    title: "Bastırılanlar",
    desc: "Açılmayan alarmlar, gerekçeleriyle",
    a: [720, 420, 1.05],
    b: [700, 330, 1.5],
    hl: [146, 266, 1416, 356],
  },
  {
    file: "ekran-prpd.webp",
    route: "#/prpd/SOKE-14",
    title: "PRPD",
    desc: "Faz çözünürlüklü RF imzası",
    a: [720, 450, 1],
    b: [600, 380, 1.4],
  },
  {
    file: "ekran-scada.webp",
    route: "#/scada/SOKE-14",
    title: "SCADA",
    desc: "Canlı register bloğu · salt okunur",
    a: [720, 450, 1],
    b: [900, 380, 1.5],
    hl: [420, 360, 1416, 392],
  },
];

const S0 = 34; // ilk ekranın başlangıcı
const D = 62; // ekran başına süre
const X = 14; // örtüşme

/* tarayıcı penceresi */
const FX = 120;
const FY = 300;
const FW = 1170;
const BAR = 50;
const VW = FW;
const VH = 556;
const BASE = Math.max(VW / 1440, VH / 900);

const ShotView: React.FC<{ s: Shot; i: number; frame: number }> = ({ s, i, frame }) => {
  const start = S0 + i * D;
  const end = start + D + X;
  if (frame < start - 1 || (i < SHOTS.length - 1 && frame > end + X)) return null;

  const p = interpolate(frame, [start, i === SHOTS.length - 1 ? 420 : end + X], [0, 1], {
    ...CLAMP,
    easing: EASE_IN_OUT,
  });
  const cx = s.a[0] + (s.b[0] - s.a[0]) * p;
  const cy = s.a[1] + (s.b[1] - s.a[1]) * p;
  const z = s.a[2] + (s.b[2] - s.a[2]) * p;
  const k = BASE * z;
  const tx = Math.min(0, Math.max(VW - 1440 * k, VW / 2 - cx * k));
  const ty = Math.min(0, Math.max(VH - 900 * k, VH / 2 - cy * k));

  const inP = i === 0 ? 1 : prog(frame, start, X, EASE_OUT);
  const hlP = interpolate(frame, [start + 24, start + 36], [0, 1], CLAMP);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        opacity: inP,
        translate: `${(1 - inP) * 60}px 0px`,
      }}
    >
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          width: 1440,
          height: 900,
          transformOrigin: "0 0",
          translate: `${tx}px ${ty}px`,
          scale: String(k),
        }}
      >
        <Img src={staticFile(s.file)} style={{ width: 1440, height: 900, display: "block" }} />
        {s.hl ? (
          <div
            style={{
              position: "absolute",
              left: s.hl[0] - 6,
              top: s.hl[1] - 6,
              width: s.hl[2] - s.hl[0] + 12,
              height: s.hl[3] - s.hl[1] + 12,
              borderRadius: 10,
              border: `${3 / z}px solid ${C.olcum}`,
              boxShadow: `0 0 ${24 / z}px ${C.olcum}88, inset 0 0 ${30 / z}px ${C.olcum}22`,
              opacity: hlP * (0.75 + 0.25 * pulse(frame, 30)),
            }}
          />
        ) : null}
      </div>
    </div>
  );
};

export const S17Demo: React.FC = () => {
  const frame = useCurrentFrame();
  const active = Math.max(0, Math.min(SHOTS.length - 1, Math.floor((frame - S0 + X / 2) / D)));

  return (
    <AbsoluteFill>
      <Backdrop accent={C.izle} second={C.brand} />
      <SceneHeader kicker="08 · Demo" title="Operasyon ekibi ne *görüyor?*" />

      {/* tarayıcı çerçevesi */}
      <div
        style={{
          position: "absolute",
          left: FX,
          top: FY,
          width: FW,
          height: BAR + VH,
          borderRadius: 18,
          overflow: "hidden",
          background: C.panel,
          border: `1.5px solid ${C.line2}`,
          boxShadow: `0 40px 90px -30px rgba(0,0,0,.9), 0 0 0 1px ${C.izle}18`,
          ...fadeUp(frame, 14, { dist: 50, blur: 10, dur: 24 }),
        }}
      >
        <div
          style={{
            height: BAR,
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "0 18px",
            background: C.panel2,
            borderBottom: `1px solid ${C.line2}`,
          }}
        >
          {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
            <span key={c} style={{ width: 13, height: 13, borderRadius: 99, background: c, opacity: 0.85 }} />
          ))}
          <div
            style={{
              marginLeft: 16,
              flex: 1,
              height: 32,
              borderRadius: 8,
              background: C.bg2,
              border: `1px solid ${C.line}`,
              display: "flex",
              alignItems: "center",
              padding: "0 14px",
              fontFamily: F.mono,
              fontSize: 20,
              color: C.muted,
              overflow: "hidden",
              whiteSpace: "nowrap",
            }}
          >
            <span style={{ color: C.dim }}>127.0.0.1:8080/</span>
            <span style={{ color: C.ink }}>{SHOTS[active].route}</span>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              marginLeft: 12,
              fontFamily: F.mono,
              fontSize: 20,
              color: C.ok,
            }}
          >
            <span
              style={{
                width: 11,
                height: 11,
                borderRadius: 99,
                background: C.ok,
                boxShadow: `0 0 ${6 + 8 * pulse(frame, 30)}px ${C.ok}`,
              }}
            />
            canlı · 1 Hz
          </div>
        </div>
        <div style={{ position: "relative", width: VW, height: VH, background: C.bg }}>
          {SHOTS.map((s, i) => (
            <ShotView key={s.file} s={s} i={i} frame={frame} />
          ))}
        </div>
      </div>

      {/* ekran listesi */}
      <div
        style={{
          position: "absolute",
          left: 1330,
          top: FY,
          width: 470,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        {SHOTS.map((s, i) => {
          const on = i === active;
          const start = S0 + i * D;
          const fill = interpolate(frame, [start, start + D], [0, 1], CLAMP);
          const lit = interpolate(frame, [start - 4, start + 6, start + D + 2, start + D + 10], [0, 1, 1, 0], CLAMP);
          return (
            <div
              key={s.file}
              style={{
                position: "relative",
                height: 88,
                borderRadius: 16,
                padding: "12px 20px 0 22px",
                overflow: "hidden",
                background: on ? C.brandSoft : C.panel,
                border: `1.5px solid ${on ? C.brand : C.line}`,
                boxShadow: on ? `0 16px 40px -18px ${C.brand}88` : "none",
                scale: String(1 + 0.015 * lit),
                ...fadeSide(frame, 22 + i * 5, 50, 20),
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <span style={{ fontFamily: F.mono, fontSize: 22, color: on ? C.brand : C.dim, width: 26 }}>
                  {i + 1}
                </span>
                <span style={{ fontFamily: F.sans, fontSize: 30, fontWeight: 800, color: on ? C.ink : C.muted }}>
                  {s.title}
                </span>
              </div>
              <div
                style={{
                  marginLeft: 40,
                  marginTop: 2,
                  fontFamily: F.sans,
                  fontSize: 21,
                  color: on ? C.brand2 : C.dim,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {s.desc}
              </div>
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  bottom: 0,
                  height: 4,
                  width: `${fill * 100}%`,
                  background: on ? C.brand : "transparent",
                }}
              />
            </div>
          );
        })}
      </div>

      <Narration
        lines={[
          {
            from: 30,
            to: 154,
            text: (
              <>
                Filodan panoya, panodan tek bir bağlantıya. <Em>Gri renk bir eksiklik değil, bir beyandır.</Em>
              </>
            ),
          },
          {
            from: 160,
            to: 282,
            text: (
              <>
                Kanıt: <Theta />, CUSUM ve değişim noktası aynı eksende; açılmayan alarmlar <Em>gerekçeleriyle</Em>.
              </>
            ),
          },
          {
            from: 288,
            to: 416,
            text: (
              <>
                Ekrandaki sayı ile SCADA register'ındaki sayı <Em color={C.olcum}>aynı nesneden</Em> gelir — çelişemezler.
              </>
            ),
          },
        ]}
      />
    </AbsoluteFill>
  );
};
