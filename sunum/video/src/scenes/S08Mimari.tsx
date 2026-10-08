import React, { useMemo } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { getLength, getPointAtLength } from "@remotion/paths";
import { Backdrop } from "../ui/Backdrop";
import { Narration } from "../ui/Narration";
import { SceneHeader } from "../ui/SceneHeader";
import { Chip, DrawPath, Em, Icon, IconName } from "../ui/primitives";
import { fadeSide, fadeUp, popIn, prog, pulse } from "../ui/motion";
import { C, CLAMP, EASE_OUT, F } from "../theme";

/* 8 · UÇTAN UCA MİMARİ
   Pano (8 sensör + mevcut ark rölesi ve analizör) → ağ geçidi (yerel kurallar, tampon)
   → MQTT 5 · TLS · QoS 1 → dağıtım şirketinin sunucu odası → üç çıkış.
   Ortada bir kopma anı: çerçeveler kaybolmaz, tamponda bekler, bağlantı gelince boşalır. */

/* ---------------- yerleşim ---------------- */
const DEV_X = 140;
const DEV_W = 292;
const DEV_H = 80;
const devY = (i: number) => 396 + i * 94;

const GW = { x: 490, y: 392, w: 360, h: 420 };
const MERGE_Y = 600;

const SRV_GROUP = { x: 990, y: 340, w: 410, h: 528 };
const SRV_X = 1010;
const SRV_W = 370;
const SRV_H = 84;
const srvY = (i: number) => 392 + i * 112;

const OUT_X = 1480;
const OUT_W = 320;
const OUT_H = 120;
const outY = (i: number) => 392 + i * 160;

const LINK = `M${GW.x + GW.w},434 L${SRV_X},434`;

const DEVICES: { t: string; s: string; c: string }[] = [
  { t: "6 × ısıl kelepçe", s: "TMP117 + CT · 868 MHz", c: C.izle },
  { t: "Termal dizi", s: "TN-IR 32×24 · 868 MHz", c: C.izle },
  { t: "RF / ortam düğümü", s: "PD · nem · 868 MHz", c: C.izle },
  { t: "TVOC-2 ark rölesi", s: "RS-485 · panoda mevcut", c: C.brand2 },
  { t: "MPR-53CS analizör", s: "RS-485 · panoda mevcut", c: C.brand2 },
];

const SERVER: { t: string; s: string }[] = [
  { t: "Toplama", s: "zarf · sıra boşluğu · tazelik" },
  { t: "Depo", s: "SQLite · taşınabilir şema" },
  { t: "Dedektör", s: "θ · RLS · CUSUM" },
  { t: "Kurallar", s: "bastırma → füzyon → alarm" },
];

const OUTPUTS: { t: string; s: string; c: string; icon: IconName }[] = [
  { t: "İzleme arayüzü", s: "REST + WebSocket · 1 Hz", c: C.ok, icon: "grid" },
  { t: "SCADA / DMS", s: "Modbus TCP · salt okunur", c: C.ok, icon: "lock" },
  { t: "Bildirim", s: "SMS + sesli arama · onay kodu", c: C.kritik, icon: "phone" },
];

const devPath = (i: number) => {
  const cy = devY(i) + DEV_H / 2;
  return `M${DEV_X + DEV_W},${cy} C${DEV_X + DEV_W + 56},${cy} ${GW.x - 50},${MERGE_Y} ${GW.x},${MERGE_Y}`;
};
const outPath = (i: number) => {
  const sy = srvY(3) + SRV_H / 2;
  const cy = outY(i) + OUT_H / 2;
  return `M${SRV_X + SRV_W},${sy} C${OUT_X - 50},${sy} ${OUT_X - 50},${cy} ${OUT_X},${cy}`;
};

/* zamanlama */
const T_DEV = 40;
const T_GW = 72;
const T_SRV = 140;
const T_OUT = 186;
const T_DOWN = 228;
const T_UP = 274;
const T_END = 296;

/* ---------------- yol üzerinde akan paketler ---------------- */
const Packets: React.FC<{
  d: string;
  frame: number;
  start: number;
  stop?: number;
  n: number;
  speed: number;
  color: string;
  r?: number;
}> = ({ d, frame, start, stop = 100000, n, speed, color, r = 6 }) => {
  const len = useMemo(() => getLength(d), [d]);
  if (frame < start || frame > stop) return null;
  const fadeIn = interpolate(frame, [start, start + 10], [0, 1], CLAMP);
  const fadeOut = interpolate(frame, [stop - 8, stop], [1, 0], CLAMP);
  return (
    <>
      {Array.from({ length: n }, (_, i) => {
        const s = ((frame - start) * speed + (i * len) / n) % len;
        const p = getPointAtLength(d, s);
        if (!p) return null;
        const edge = Math.min(1, s / 24, (len - s) / 24);
        const o = Math.max(0, edge) * fadeIn * fadeOut;
        return (
          <g key={i} opacity={o}>
            <circle cx={p.x} cy={p.y} r={r * 2.6} fill={color} opacity={0.22} />
            <circle cx={p.x} cy={p.y} r={r} fill={color} />
          </g>
        );
      })}
    </>
  );
};

/* ---------------- kutu ---------------- */
const Box: React.FC<{
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  sub: string;
  accent?: string;
  icon?: IconName;
  style?: React.CSSProperties;
}> = ({ x, y, w, h, title, sub, accent = C.line2, icon, style }) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      width: w,
      height: h,
      boxSizing: "border-box",
      padding: "12px 18px",
      borderRadius: 14,
      background: `linear-gradient(180deg, ${C.panel2}, ${C.panel})`,
      border: `1.6px solid ${accent}`,
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      gap: 4,
      ...style,
    }}
  >
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      {icon ? <Icon name={icon} size={30} color={accent} /> : null}
      <div style={{ fontFamily: F.sans, fontWeight: 700, fontSize: 28, color: C.ink, whiteSpace: "nowrap" }}>{title}</div>
    </div>
    <div style={{ fontFamily: F.sans, fontSize: 22, color: C.muted, lineHeight: 1.25 }}>{sub}</div>
  </div>
);

export const S08Mimari: React.FC = () => {
  const frame = useCurrentFrame();

  const down = frame >= T_DOWN && frame < T_UP;
  const downAmt = interpolate(frame, [T_DOWN, T_DOWN + 6, T_UP - 4, T_UP], [0, 1, 1, 0], CLAMP);
  const restoreFlash = interpolate(frame, [T_UP, T_UP + 6, T_UP + 26], [0, 1, 0], CLAMP);
  const buffer = interpolate(frame, [T_GW + 40, T_DOWN, T_UP, T_UP + 26], [0.04, 0.06, 0.46, 0.04], CLAMP);
  const endGlow = prog(frame, T_END, 20);

  return (
    <AbsoluteFill>
      <Backdrop accent={C.izle} second={C.brand} />
      <SceneHeader
        kicker="04 · Mimari"
        title="Sensörden SCADA'ya *tek* zincir."
        lead="Kamu bulutu yok — her şey dağıtım şirketinin kendi sunucu odasında."
      />

      {/* grup çerçeveleri */}
      <div
        style={{
          position: "absolute",
          left: 120,
          top: 340,
          width: 332,
          height: 528,
          borderRadius: 18,
          border: `1.5px dashed ${C.line2}`,
          opacity: prog(frame, T_DEV - 8, 16),
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 140,
          top: 352,
          fontFamily: F.mono,
          fontSize: 22,
          letterSpacing: "0.12em",
          color: C.brand,
          opacity: prog(frame, T_DEV - 6, 16),
        }}
      >
        PANO · 1 MODÜL
      </div>
      <div
        style={{
          position: "absolute",
          left: SRV_GROUP.x,
          top: SRV_GROUP.y,
          width: SRV_GROUP.w,
          height: SRV_GROUP.h,
          borderRadius: 18,
          border: `1.5px dashed ${C.izle}`,
          background: "rgba(74,163,255,.04)",
          opacity: prog(frame, T_SRV - 8, 16),
          boxShadow: `0 0 ${60 * endGlow}px rgba(74,163,255,${0.18 * endGlow})`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: SRV_GROUP.x + 20,
          top: 352,
          fontFamily: F.mono,
          fontSize: 22,
          letterSpacing: "0.06em",
          color: C.izle,
          opacity: prog(frame, T_SRV - 4, 16),
        }}
      >
        SUNUCU ODASI · ON-PREMISE
      </div>

      {/* bağlantılar ve paketler */}
      <svg width={1920} height={1080} style={{ position: "absolute", inset: 0 }}>
        {DEVICES.map((d, i) => (
          <DrawPath
            key={i}
            d={devPath(i)}
            progress={prog(frame, T_DEV + 24 + i * 4, 26)}
            stroke={d.c}
            strokeOpacity={0.5}
            strokeWidth={2.5}
          />
        ))}
        {DEVICES.map((d, i) => (
          <Packets
            key={i}
            d={devPath(i)}
            frame={frame}
            start={T_DEV + 52 + i * 4}
            n={2}
            speed={3.2 + i * 0.4}
            color={d.c}
            r={5}
          />
        ))}

        {/* ağ geçidi → sunucu */}
        <DrawPath
          d={LINK}
          progress={prog(frame, T_SRV, 22)}
          stroke={down ? C.kritik : C.brand}
          strokeOpacity={down ? 0.9 : 0.6}
          strokeWidth={down ? 3 : 4}
          strokeDasharray={down ? "8 10" : undefined}
        />
        <Packets d={LINK} frame={frame} start={T_SRV + 20} stop={T_DOWN} n={3} speed={4} color={C.brand} />
        <Packets d={LINK} frame={frame} start={T_UP} stop={T_UP + 30} n={6} speed={9} color={C.olcum} />
        <Packets d={LINK} frame={frame} start={T_UP + 26} n={3} speed={4} color={C.brand} />
        {downAmt > 0 ? (
          <g opacity={downAmt}>
            <circle cx={920} cy={434} r={22} fill={C.bg} stroke={C.kritik} strokeWidth={3} />
            <path d="M910,424 L930,444 M930,424 L910,444" stroke={C.kritik} strokeWidth={4} strokeLinecap="round" />
          </g>
        ) : null}
        {restoreFlash > 0 ? (
          <circle cx={920} cy={434} r={22 + restoreFlash * 30} fill="none" stroke={C.ok} strokeWidth={3} opacity={restoreFlash} />
        ) : null}

        {/* sunucu içi akış */}
        {[0, 1, 2].map((i) => {
          const y1 = srvY(i) + SRV_H;
          const y2 = srvY(i + 1);
          const d = `M${SRV_X + SRV_W / 2},${y1} L${SRV_X + SRV_W / 2},${y2}`;
          return (
            <g key={i}>
              <DrawPath d={d} progress={prog(frame, T_SRV + 26 + i * 8, 12)} stroke={C.izle} strokeWidth={3} />
              <Packets d={d} frame={frame} start={T_SRV + 40 + i * 8} n={1} speed={1.2} color={C.izle} r={5} />
            </g>
          );
        })}

        {/* çıkışlar */}
        {OUTPUTS.map((o, i) => (
          <DrawPath
            key={i}
            d={outPath(i)}
            progress={prog(frame, T_OUT + i * 5, 22)}
            stroke={o.c}
            strokeOpacity={0.55}
            strokeWidth={2.5}
          />
        ))}
        {OUTPUTS.map((o, i) => (
          <Packets key={i} d={outPath(i)} frame={frame} start={T_OUT + 26 + i * 5} n={2} speed={2.6} color={o.c} r={5} />
        ))}
      </svg>

      {/* yol etiketleri */}
      <div
        style={{
          position: "absolute",
          left: GW.x + GW.w,
          width: SRV_X - GW.x - GW.w,
          top: 388,
          textAlign: "center",
          fontFamily: F.mono,
          fontSize: 21,
          color: C.brand2,
          opacity: prog(frame, T_SRV + 10, 14),
        }}
      >
        MQTT 5 · TLS
      </div>
      <div
        style={{
          position: "absolute",
          left: GW.x + GW.w,
          width: SRV_X - GW.x - GW.w,
          top: 456,
          textAlign: "center",
          whiteSpace: "nowrap",
          fontFamily: down ? F.sans : F.mono,
          fontWeight: down ? 700 : 400,
          fontSize: down ? 22 : 21,
          color: down ? C.kritik : C.brand2,
          opacity: prog(frame, T_SRV + 14, 14),
        }}
      >
        {down ? "bağlantı koptu" : "QoS 1 · S&F"}
      </div>

      {/* cihazlar */}
      {DEVICES.map((d, i) => (
        <Box
          key={i}
          x={DEV_X}
          y={devY(i)}
          w={DEV_W}
          h={DEV_H}
          title={d.t}
          sub={d.s}
          accent={i < 3 ? C.brand : C.line2}
          style={{ padding: "8px 18px", ...fadeSide(frame, T_DEV + i * 6, -40) }}
        />
      ))}

      {/* ağ geçidi */}
      <div
        style={{
          position: "absolute",
          left: GW.x,
          top: GW.y,
          width: GW.w,
          height: GW.h,
          boxSizing: "border-box",
          padding: "20px 22px",
          borderRadius: 18,
          background: `linear-gradient(180deg, ${C.panel2}, ${C.panel})`,
          border: `2px solid ${C.brand}`,
          boxShadow: `0 0 ${30 + 20 * pulse(frame, 50)}px -10px ${C.brand}88`,
          ...fadeUp(frame, T_GW, { dist: 30 }),
        }}
      >
        <div style={{ fontFamily: F.sans, fontWeight: 800, fontSize: 30, color: C.ink }}>Ağ geçidi</div>
        <div style={{ fontFamily: F.mono, fontSize: 21, color: C.muted, marginTop: 2 }}>STM32H563 · LTE</div>
        <div
          style={{
            fontFamily: F.mono,
            fontSize: 20,
            letterSpacing: "0.12em",
            color: C.dim,
            marginTop: 22,
            marginBottom: 10,
          }}
        >
          YEREL KURALLAR
        </div>
        {["bağlantı > 90 °C", "kardeş farkı > 20 K", "ark açması"].map((r, i) => (
          <div
            key={r}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              marginBottom: 8,
              padding: "6px 12px",
              borderRadius: 10,
              background: down ? "rgba(255,107,61,.14)" : "rgba(247,131,32,.08)",
              border: `1.5px solid ${down ? C.kritik : "rgba(247,131,32,.35)"}`,
              fontFamily: F.sans,
              fontWeight: 700,
              fontSize: 24,
              color: C.ink,
              ...popIn(frame, T_GW + 30 + i * 8),
            }}
          >
            <Icon name="shield" size={24} color={down ? C.kritik : C.brand} stroke={2.2} />
            {r}
          </div>
        ))}
        <div
          style={{
            fontFamily: F.mono,
            fontSize: 20,
            letterSpacing: "0.12em",
            color: C.dim,
            marginTop: 16,
            marginBottom: 8,
            opacity: prog(frame, T_GW + 56, 14),
          }}
        >
          TAMPON
        </div>
        <div
          style={{
            height: 16,
            borderRadius: 8,
            background: C.line,
            overflow: "hidden",
            opacity: prog(frame, T_GW + 56, 14),
          }}
        >
          <div
            style={{
              width: `${buffer * 100}%`,
              height: "100%",
              borderRadius: 8,
              background: down ? `linear-gradient(90deg, ${C.uyari}, ${C.kritik})` : `linear-gradient(90deg, ${C.brand}, ${C.olcum})`,
            }}
          />
        </div>
        <div
          style={{
            fontFamily: F.sans,
            fontSize: 21,
            color: down ? C.uyari : C.muted,
            marginTop: 8,
            opacity: prog(frame, T_GW + 60, 14),
          }}
        >
          {down ? "çerçeveler tamponda bekliyor" : "kapasite 20 000 çerçeve"}
        </div>
      </div>

      {/* sunucu */}
      {SERVER.map((s, i) => (
        <Box
          key={i}
          x={SRV_X}
          y={srvY(i)}
          w={SRV_W}
          h={SRV_H}
          title={s.t}
          sub={s.s}
          accent={i === 2 ? C.olcum : C.izle}
          style={{ ...fadeUp(frame, T_SRV + 8 + i * 8, { dist: 24 }) }}
        />
      ))}
      <div
        style={{
          position: "absolute",
          left: SRV_X,
          width: SRV_W,
          top: 826,
          display: "flex",
          justifyContent: "center",
          ...fadeUp(frame, T_SRV + 44, { dist: 14 }),
        }}
      >
        <Chip color={C.ok} style={{ fontSize: 22, padding: "4px 16px" }}>
          <Icon name="cloudx" size={24} color={C.ok} stroke={2} />
          kamu bulutu yok
        </Chip>
      </div>

      {/* çıkışlar */}
      {OUTPUTS.map((o, i) => (
        <Box
          key={i}
          x={OUT_X}
          y={outY(i)}
          w={OUT_W}
          h={OUT_H}
          title={o.t}
          sub={o.s}
          accent={o.c}
          icon={o.icon}
          style={{
            boxShadow: i < 2 ? `0 0 ${36 * endGlow}px -6px ${C.ok}` : undefined,
            ...fadeSide(frame, T_OUT + 8 + i * 7, 40),
          }}
        />
      ))}
      <div
        style={{
          position: "absolute",
          left: OUT_X,
          width: OUT_W,
          top: outY(0) + OUT_H + 3,
          display: "flex",
          justifyContent: "center",
          ...popIn(frame, T_END),
        }}
      >
        <span
          style={{
            padding: "3px 16px",
            borderRadius: 999,
            background: C.ok,
            color: C.bg,
            fontFamily: F.sans,
            fontWeight: 800,
            fontSize: 21,
            whiteSpace: "nowrap",
          }}
        >
          = aynı nesneden · çelişemez
        </span>
      </div>

      {/* tek yön */}
      <div
        style={{
          position: "absolute",
          left: GW.x - 10,
          width: GW.w + 20,
          top: 828,
          display: "flex",
          justifyContent: "center",
          ...popIn(frame, T_END + 10),
        }}
      >
        <Chip color={C.ok} solid style={{ fontSize: 22, padding: "6px 18px" }}>
          <Icon name="lock" size={24} color={C.bg} stroke={2.2} />
          tek yön · panoya komut yok
        </Chip>
      </div>

      <Narration
        lines={[
          {
            from: 40,
            to: 128,
            text: (
              <>
                Panoda 9 cihazlık kit: sensörler <Em color={C.izle}>868 MHz</Em>, mevcut ark rölesi ve analizör{" "}
                <Em>RS-485 Modbus</Em>.
              </>
            ),
          },
          {
            from: 132,
            to: 224,
            text: (
              <>
                Ağ geçidi aptal bir köprü değil: <Em>üç kural</Em> sunucu olmadan da yerelde çalışır.
              </>
            ),
          },
          {
            from: 228,
            to: 292,
            text: (
              <>
                Bağlantı koparsa çerçeve kaybolmaz — broker <Em color={C.olcum}>onaylayana kadar</Em> tamponda bekler.
              </>
            ),
          },
          {
            from: 296,
            to: 358,
            text: (
              <>
                Ekran ile SCADA <Em color={C.ok}>aynı nesneden</Em> beslenir. Akış tek yönlü: panoya komut yok.
              </>
            ),
          },
        ]}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          background: `radial-gradient(500px 300px at 920px 434px, rgba(255,107,61,${0.12 * downAmt}), transparent 70%)`,
          opacity: interpolate(frame, [T_DOWN, T_DOWN + 8], [0, 1], { ...CLAMP, easing: EASE_OUT }),
        }}
      />
    </AbsoluteFill>
  );
};
